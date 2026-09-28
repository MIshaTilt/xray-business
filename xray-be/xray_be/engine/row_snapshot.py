"""Собирает снимок X-Ray из уже нормализуемых строк таблицы."""

import datetime
import uuid
from decimal import Decimal

from engine.analyzer import calculate_metrics_and_findings
from engine.mapping import guess_column_mapping
from engine.models import Deal, Snapshot
from engine.narrator import generate_llm_narrative
from engine.normalizer import normalize_records


def publish_rows(user, guest_session: str, filename: str, source: str, rows: list[dict]) -> str:
    from engine.views_api import get_coverage, next_scan_no

    if not rows:
        raise ValueError("empty")
    mapping = guess_column_mapping(list(rows[0].keys()), rows[:5])
    deals, rejected = normalize_records(rows, mapping, {})
    if not deals:
        raise ValueError("empty")
    findings, all_metrics, ok_list, low_sample = calculate_metrics_and_findings(deals, mapping)
    coverage = get_coverage(mapping)
    total_amount = sum((item.amount for item in deals), Decimal("0.00"))
    dates = [item.created_at for item in deals if item.created_at]
    period_from = min(dates).strftime("%Y-%m-%d") if dates else None
    period_to = max(dates).strftime("%Y-%m-%d") if dates else None
    headline = findings[0]["action"] if findings else "По этому файлу критичных утечек не видно."
    headline, findings, card_title = generate_llm_narrative(findings, headline, filename)
    body = " ".join(item["action"] for item in findings)
    snapshot_id = str(uuid.uuid4())
    scan_no = next_scan_no()
    totals = {
        "deals": len(deals) + len(rejected),
        "amount": f"{total_amount:.2f}",
        "accepted": len(deals),
        "rejected": len(rejected),
    }
    snap = Snapshot.objects.create(
        id=snapshot_id,
        user=user,
        scan_no=scan_no,
        guest_session=guest_session,
        is_guest=user is None,
        filename=filename,
        headline=headline,
        quality={"card_title": card_title} if card_title else {},
        body=body,
        findings=findings,
        coverage=coverage,
        totals=totals,
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
                source=item.source or source,
                raw_data=item.raw_data or {},
            )
            for item in deals
        ]
    )
    return snapshot_id
