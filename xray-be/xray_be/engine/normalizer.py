import hashlib
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional
from .mapping import parse_money, parse_date, map_status


class NormalizedDeal:
    def __init__(
        self,
        deal_id: str,
        client: str,
        contact: str,
        manager: str,
        amount: Decimal,
        list_price: Optional[Decimal],
        discount_pct: Optional[Decimal],
        status_raw: str,
        status: str,
        created_at: Optional[Any],
        first_contact_at: Optional[Any],
        status_changed_at: Optional[Any],
        last_activity_at: Optional[Any],
        closed_at: Optional[Any],
        source: str,
    ):
        self.deal_id = deal_id
        self.client = client
        self.contact = contact
        self.manager = manager
        self.amount = amount
        self.list_price = list_price
        self.discount_pct = discount_pct
        self.status_raw = status_raw
        self.status = status
        self.created_at = created_at
        self.first_contact_at = first_contact_at
        self.status_changed_at = status_changed_at
        self.last_activity_at = last_activity_at
        self.closed_at = closed_at
        self.source = source


def normalize_records(
    rows: List[Dict[str, Any]],
    mapping: Dict[str, str],
    status_map: Optional[Dict[str, str]] = None
) -> Tuple[List[NormalizedDeal], List[Dict[str, Any]]]:
    """
    Normalizes rows into valid deals and quality.rejected list.
    """
    deals: List[NormalizedDeal] = []
    rejected: List[Dict[str, Any]] = []
    seen_ids = set()

    for idx, row in enumerate(rows, start=1):
        # 1. Check Amount
        amount_col = mapping.get('amount')
        raw_amount = row.get(amount_col) if amount_col else None
        if raw_amount is None or str(raw_amount).strip() == '':
            rejected.append({'row': idx, 'code': 'empty_amount'})
            continue

        amount = parse_money(raw_amount)
        if amount is None:
            rejected.append({'row': idx, 'code': 'bad_amount'})
            continue
        if amount <= 0:
            rejected.append({'row': idx, 'code': 'non_positive'})
            continue

        # 2. Deal ID
        id_col = mapping.get('deal_id')
        raw_id = str(row.get(id_col)).strip() if id_col and row.get(id_col) else ''
        if raw_id:
            deal_id = raw_id[:64]
        else:
            client_col = mapping.get('client')
            client_val = str(row.get(client_col, '')).strip()
            created_col = mapping.get('created_at')
            created_val = str(row.get(created_col, '')).strip()
            raw_hash_str = f"{idx}|{amount}|{client_val}|{created_val}"
            deal_id = hashlib.sha256(raw_hash_str.encode('utf-8')).hexdigest()[:32]

        if deal_id in seen_ids:
            rejected.append({'row': idx, 'code': 'duplicate_deal_id'})
            continue
        seen_ids.add(deal_id)

        # 3. Status
        status_col = mapping.get('status')
        raw_status = str(row.get(status_col, '')).strip() if status_col else ''
        status = map_status(raw_status, status_map)

        # 4. Dates
        def get_dt(field_name: str):
            col = mapping.get(field_name)
            if not col or not row.get(col):
                return None
            return parse_date(row.get(col))

        created_at = get_dt('created_at')
        first_contact_at = get_dt('first_contact_at')
        status_changed_at = get_dt('status_changed_at')
        last_activity_at = get_dt('last_activity_at')
        closed_at = get_dt('closed_at')

        # 5. Pricing & Discounts
        lp_col = mapping.get('list_price')
        list_price = parse_money(row.get(lp_col)) if lp_col and row.get(lp_col) else None

        disc_col = mapping.get('discount_pct')
        discount_pct = parse_money(row.get(disc_col)) if disc_col and row.get(disc_col) else None

        client_col = mapping.get('client')
        client = str(row.get(client_col, '')).strip() if client_col else ''

        contact_col = mapping.get('contact')
        contact = str(row.get(contact_col, '')).strip() if contact_col else ''

        manager_col = mapping.get('manager')
        manager = str(row.get(manager_col, '')).strip() if manager_col else ''

        source_col = mapping.get('source')
        source = str(row.get(source_col, '')).strip() if source_col else ''

        deal = NormalizedDeal(
            deal_id=deal_id,
            client=client,
            contact=contact,
            manager=manager,
            amount=amount,
            list_price=list_price,
            discount_pct=discount_pct,
            status_raw=raw_status,
            status=status,
            created_at=created_at,
            first_contact_at=first_contact_at,
            status_changed_at=status_changed_at,
            last_activity_at=last_activity_at,
            closed_at=closed_at,
            source=source
        )
        deals.append(deal)

    return deals, rejected
