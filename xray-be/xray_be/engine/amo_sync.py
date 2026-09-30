"""Сохраняет сделки amoCRM как обычный снимок X-Ray."""

from django.core import signing
from django.utils import timezone

from engine.amo_client import AmoError, fetch_lead_rows
from engine.auth import RequestIdentity
from engine.models import AmoConnection


def _token(connection: AmoConnection) -> str:
    return signing.loads(connection.token)


def connections_for(ident: RequestIdentity):
    if ident.user:
        return AmoConnection.objects.filter(user=ident.user).order_by("-created_at", "-id")
    if not ident.guest_session:
        return AmoConnection.objects.none()
    return AmoConnection.objects.filter(guest_session=ident.guest_session, user__isnull=True).order_by("-created_at", "-id")


def connection_for(ident: RequestIdentity) -> AmoConnection | None:
    return connections_for(ident).first()


def save_token(ident: RequestIdentity, account: str, token: str) -> AmoConnection:
    packed = signing.dumps(token)
    account = (account or "").strip()
    connection = connections_for(ident).filter(account__iexact=account).first()
    if connection is None:
        connection = AmoConnection(
            user=ident.user,
            guest_session="" if ident.user else ident.guest_session,
            account=account,
        )
    connection.account = account
    connection.token = packed
    connection.last_error = ""
    connection.save()
    return connection


def public_session(connection: AmoConnection) -> dict:
    return {
        "id": connection.id,
        "account": connection.account,
        "last_sync_at": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
        "last_error": connection.last_error,
        "last_snapshot_id": connection.last_snapshot_id,
    }


def public_status(connection: AmoConnection | None) -> dict:
    if connection is None:
        return {"connected": False, "sessions": []}
    payload = public_session(connection)
    payload["connected"] = True
    payload["sessions"] = [payload.copy()]
    return payload


def sync_connection(connection: AmoConnection) -> str:
    from engine.row_snapshot import publish_rows

    try:
        host, rows = fetch_lead_rows(connection.account, _token(connection))
    except AmoError as exc:
        connection.last_error = exc.message
        connection.save(update_fields=["last_error"])
        raise

    if not rows:
        connection.last_error = "В amoCRM нет сделок с суммой больше нуля."
        connection.save(update_fields=["last_error"])
        raise AmoError(connection.last_error)

    try:
        snapshot_id = publish_rows(connection.user, connection.guest_session, f"amoCRM {host}", "amocrm", rows)
    except ValueError:
        connection.last_error = "Сделки amoCRM прочитаны, но ни одна не прошла разбор."
        connection.save(update_fields=["last_error"])
        raise AmoError(connection.last_error)

    connection.account = host
    connection.last_sync_at = timezone.now()
    connection.last_error = ""
    connection.last_snapshot_id = snapshot_id
    connection.save()
    return snapshot_id


def sync_all() -> None:
    for connection in AmoConnection.objects.all():
        try:
            sync_connection(connection)
        except AmoError:
            continue
        except Exception as exc:
            connection.last_error = "Не удалось обновить сделки amoCRM."
            connection.save(update_fields=["last_error"])
            print(f"[AMO SYNC] {exc}")
