from django.core import signing
from django.utils import timezone

from engine.auth import RequestIdentity
from engine.models import MoySkladConnection
from engine.moysklad_client import MoySkladError, fetch_order_rows
from engine.row_snapshot import publish_rows


def _token(connection: MoySkladConnection) -> str:
    return signing.loads(connection.token)


def connections_for(ident: RequestIdentity):
    if ident.user:
        return MoySkladConnection.objects.filter(user=ident.user).order_by("-created_at", "-id")
    if not ident.guest_session:
        return MoySkladConnection.objects.none()
    return MoySkladConnection.objects.filter(guest_session=ident.guest_session, user__isnull=True).order_by("-created_at", "-id")


def save_token(ident: RequestIdentity, account: str, token: str) -> MoySkladConnection:
    packed = signing.dumps(token)
    account = (account or "").strip()
    connection = connections_for(ident).filter(account__iexact=account).first()
    if connection is None:
        connection = MoySkladConnection(
            user=ident.user,
            guest_session="" if ident.user else ident.guest_session,
            account=account,
        )
    connection.account = account
    connection.token = packed
    connection.last_error = ""
    connection.save()
    return connection


def public_session(connection: MoySkladConnection) -> dict:
    return {
        "id": connection.id,
        "account": connection.account,
        "last_sync_at": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
        "last_error": connection.last_error,
        "last_snapshot_id": connection.last_snapshot_id,
    }


def sync_connection(connection: MoySkladConnection) -> str:
    try:
        account, rows = fetch_order_rows(_token(connection))
    except MoySkladError as exc:
        connection.last_error = exc.message
        connection.save(update_fields=["last_error"])
        raise
    if not rows:
        connection.last_error = "В МоёмСкладе нет заказов с суммой больше нуля."
        connection.save(update_fields=["last_error"])
        raise MoySkladError(connection.last_error)
    try:
        snapshot_id = publish_rows(connection.user, connection.guest_session, f"МойСклад {account}", "moysklad", rows)
    except ValueError:
        connection.last_error = "Заказы МоегоСклада прочитаны, но ни один не прошёл разбор."
        connection.save(update_fields=["last_error"])
        raise MoySkladError(connection.last_error)
    connection.account = account
    connection.last_sync_at = timezone.now()
    connection.last_error = ""
    connection.last_snapshot_id = snapshot_id
    connection.save()
    return snapshot_id


def sync_all() -> None:
    for connection in MoySkladConnection.objects.all():
        try:
            sync_connection(connection)
        except MoySkladError:
            continue
        except Exception as exc:
            connection.last_error = "Не удалось обновить заказы МоегоСклада."
            connection.save(update_fields=["last_error"])
            print(f"[MOYSKLAD SYNC] {exc}")
