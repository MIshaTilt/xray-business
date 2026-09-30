import hashlib
import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Tuple, Optional
from .mapping import parse_money, parse_date, map_status, normalize_string


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
        raw_data: Optional[Dict[str, Any]] = None,
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
        self.raw_data = raw_data or {}


def normalize_records(
    rows: List[Dict[str, Any]],
    mapping: Dict[str, str],
    status_map: Optional[Dict[str, str]] = None
) -> Tuple[List[NormalizedDeal], List[Dict[str, Any]]]:
    """
    Normalizes rows into valid deals and quality.rejected list.
    Intelligently derives missing fields (e.g. discount_pct, list_price, first_contact_at)
    from available raw columns if not directly mapped.
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

        # Auto-derive first_contact_at from response delay if available
        if not first_contact_at and created_at:
            for k, v in row.items():
                if v and any(w in normalize_string(k) for w in ['delay', 'задержк', 'минут']):
                    d_min = parse_money(v)
                    if d_min and d_min > 0:
                        first_contact_at = created_at + datetime.timedelta(minutes=float(d_min))
                        break

        # Auto-derive closed_at from delivery/payment dates if available
        if not closed_at:
            for k, v in row.items():
                if v and any(w in normalize_string(k) for w in ['дата доставки', 'доставлен', 'дата оплаты', 'completion_date', 'дата завершения']):
                    closed_at = parse_date(v)
                    if closed_at:
                        break

        # 5. Pricing & Discounts (with intelligent derivation of missing columns)
        lp_col = mapping.get('list_price')
        disc_col = mapping.get('discount_pct')

        # Auto-detect unmapped discount and unit price / quantity columns if not explicitly mapped
        if not disc_col:
            for k in row.keys():
                norm_k = normalize_string(k)
                if any(w in norm_k for w in ['скидк', 'скинули', 'discount']):
                    disc_col = k
                    break

        qty_col = None
        for k in row.keys():
            norm_k = normalize_string(k)
            if norm_k in ['количество', 'кол-во', 'штук', 'количество штук', 'quantity', 'qty', 'шт']:
                qty_col = k
                break

        qty = parse_money(row.get(qty_col)) if qty_col else None
        raw_lp = parse_money(row.get(lp_col)) if lp_col and row.get(lp_col) else None

        # Auto-detect unit price if list_price is not mapped
        if not raw_lp:
            for k in row.keys():
                norm_k = normalize_string(k)
                if any(w in norm_k for w in ['розничная цена', 'цена без скидки', 'прайс', 'unit_price', 'цена за шт']):
                    raw_lp = parse_money(row.get(k))
                    if raw_lp:
                        break

        # If list_price is per-unit and quantity > 1 and list_price < amount, scale to total list price
        if raw_lp and qty and qty > 1 and raw_lp < amount:
            list_price = (raw_lp * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            list_price = raw_lp

        raw_disc = parse_money(row.get(disc_col)) if disc_col and row.get(disc_col) else None
        discount_pct = None

        if raw_disc is not None:
            disc_col_norm = normalize_string(disc_col or '')
            is_money_discount = (
                any(w in disc_col_norm for w in ['руб', 'rub', 'amount', 'рублей']) or
                raw_disc > 100
            )
            if is_money_discount:
                discount_money = raw_disc
                if list_price is None:
                    list_price = (amount + discount_money).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if list_price and list_price > 0:
                    discount_pct = ((discount_money / list_price) * Decimal(100)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                else:
                    discount_pct = Decimal('0.0')
            else:
                discount_pct = raw_disc.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                if list_price is None and discount_pct < 100 and discount_pct >= 0:
                    list_price = (amount / (Decimal(1) - discount_pct / Decimal(100))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        elif list_price is not None:
            if list_price > amount:
                discount_pct = (((list_price - amount) / list_price) * Decimal(100)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
            else:
                discount_pct = Decimal('0.0')

        if discount_pct is not None:
            discount_pct = min(max(discount_pct, Decimal('0.0')), Decimal('100.0'))

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
            source=source,
            raw_data=dict(row)
        )
        deals.append(deal)

    return deals, rejected
