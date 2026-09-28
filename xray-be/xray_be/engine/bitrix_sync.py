from django.core import signing
from django.utils import timezone

from engine.auth import RequestIdentity
from engine.bitrix_client import BitrixError, fetch_deal_rows
from engine.models import BitrixConnection
from engine.row_snapshot import publish_rows


def _token(connection: BitrixConnection) -> str:
    return signing.loads(connection.token)


def connections_for(ident: RequestIdentity):
    if ident.user:
        return BitrixConnection.objects.filter(user=ident.user).order_by("-created_at", "-id")
    if not ident.guest_session:
        return BitrixConnection.objects.none()
    return BitrixConnection.objects.filter(guest_session=ident.guest_session, user__isnull=True).order_by("-created_at", "-id")


def save_token(ident: RequestIdentity, account: str, token: str) -> BitrixConnection:
    packed = signing.dumps(token)
    account = (account or "").strip()
    connection = connections_for(ident).filter(account__iexact=account).first()
    if connection is None:
        connection = BitrixConnection(
            user=ident.user,
            guest_session="" if ident.user else ident.guest_session,
            account=account,
        )
    connection.account = account
    connection.token = packed
    connection.last_error = ""
    connection.save()
    return connection


def public_session(connection: BitrixConnection) -> dict:
    return {
        "id": connection.id,
        "account": connection.account,
        "last_sync_at": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
        "last_error": connection.last_error,
        "last_snapshot_id": connection.last_snapshot_id,
    }


def sync_connection(connection: BitrixConnection) -> str:
    try:
        host, rows = fetch_deal_rows(_token(connection))
    except BitrixError as exc:
        connection.last_error = exc.message
        connection.save(update_fields=["last_error"])
        raise
    if not rows:
        connection.last_error = "В Битрикс24 нет сделок с суммой больше нуля."
        connection.save(update_fields=["last_error"])
        raise BitrixError(connection.last_error)
    try:
        snapshot_id = publish_rows(connection.user, connection.guest_session, f"Битрикс24 {host}", "bitrix24", rows)
    except ValueError:
        connection.last_error = "Сделки Битрикс24 прочитаны, но ни одна не прошла разбор."
        connection.save(update_fields=["last_error"])
        raise BitrixError(connection.last_error)
    connection.account = host
    connection.last_sync_at = timezone.now()
    connection.last_error = ""
    connection.last_snapshot_id = snapshot_id
    connection.save()
    return snapshot_id


def sync_all() -> None:
    for connection in BitrixConnection.objects.all():
        try:
            sync_connection(connection)
        except BitrixError:
            continue
        except Exception as exc:
            connection.last_error = "Не удалось обновить сделки Битрикс24."
            connection.save(update_fields=["last_error"])
            print(f"[BITRIX SYNC] {exc}")
