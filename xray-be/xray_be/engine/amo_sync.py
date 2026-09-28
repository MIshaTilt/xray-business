"""Сохраняет сделки amoCRM как обычный снимок X-Ray."""

import datetime
import uuid
from decimal import Decimal

from django.core import signing
from django.utils import timezone

from engine.amo_client import AmoError, fetch_lead_rows
from engine.analyzer import calculate_metrics_and_findings
from engine.auth import RequestIdentity
from engine.mapping import guess_column_mapping
from engine.models import AmoConnection, Deal, Snapshot
from engine.narrator import generate_llm_narrative
from engine.normalizer import normalize_records


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
    from engine.views_api import SNAPSHOTS_STORE, get_coverage, next_scan_no, save_disk_store

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

    columns = list(rows[0].keys())
    mapping = guess_column_mapping(columns, rows[:5])
    deals, rejected = normalize_records(rows, mapping, {})
    if not deals:
        connection.last_error = "Сделки amoCRM прочитаны, но ни одна не прошла разбор."
        connection.save(update_fields=["last_error"])
        raise AmoError(connection.last_error)

    findings, all_metrics, ok_list, low_sample = calculate_metrics_and_findings(deals, mapping)
    coverage = get_coverage(mapping)
    total_amount = sum((item.amount for item in deals), Decimal("0.00"))
    dates = [item.created_at for item in deals if item.created_at]
    period_from = min(dates).strftime("%Y-%m-%d") if dates else None
    period_to = max(dates).strftime("%Y-%m-%d") if dates else None
    filename = f"amoCRM {host}"
    headline = findings[0]["action"] if findings else "По этому файлу критичных утечек не видно."
    headline, findings, card_title = generate_llm_narrative(findings, headline, filename)
    body = " ".join(item["action"] for item in findings)
    snapshot_id = str(uuid.uuid4())
    scan_no = next_scan_no()
    ident_user = connection.user

    SNAPSHOTS_STORE[snapshot_id] = {
        "snapshot_id": snapshot_id,
        "user_id": ident_user.max_user_id if ident_user else None,
        "guest_session": connection.guest_session,
        "is_guest": ident_user is None,
        "scan_no": scan_no,
        "status": "ready",
        "progress": 100,
        "error": "",
        "created_at": datetime.datetime.now().isoformat(),
        "filename": filename,
        "source": "amocrm",
        "diagnosis": {
            "snapshot_id": snapshot_id,
            "headline": headline,
            "card_title": card_title,
            "body": body,
            "findings": findings,
            "coverage": coverage,
            "period": {"from": period_from, "to": period_to},
            "totals": {
                "deals": len(deals) + len(rejected),
                "amount": f"{total_amount:.2f}",
                "accepted": len(deals),
                "rejected": len(rejected),
            },
            "ok": ok_list,
            "low_sample": low_sample,
        },
        "all_metrics": all_metrics,
    }
    save_disk_store()

    snap = Snapshot.objects.create(
        id=snapshot_id,
        user=ident_user,
        scan_no=scan_no,
        guest_session=connection.guest_session,
        is_guest=ident_user is None,
        filename=filename,
        headline=headline,
        quality={"card_title": card_title} if card_title else {},
        body=body,
        findings=findings,
        coverage=coverage,
        totals=SNAPSHOTS_STORE[snapshot_id]["diagnosis"]["totals"],
        all_metrics=all_metrics,
        ok_list=ok_list,
        low_sample=low_sample,
        period_from=dates and min(dates).date() or None,
        period_to=dates and max(dates).date() or None,
        status=Snapshot.Status.READY,
        progress=100,
    )
    Deal.objects.bulk_create(
        [
            Deal(
                snapshot=snap,
                deal_id=item.deal_id,
                client=item.client,
                contact=item.contact,
                manager=item.manager,
                amount=item.amount,
                list_price=item.list_price,
                discount_pct=item.discount_pct,
                status_raw=item.status_raw,
                status=item.status,
                created_at=item.created_at,
                first_contact_at=item.first_contact_at,
                status_changed_at=item.status_changed_at,
                last_activity_at=item.last_activity_at,
                closed_at=item.closed_at,
                source=item.source or "amocrm",
                raw_data=item.raw_data or {},
            )
            for item in deals
        ]
    )

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
