import re
import csv
import io
import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Tuple, Any, Optional

SYNONYMS = {
    'amount': ['сумма', 'бюджет', 'цена', 'цена со скидкой', 'итого', 'сумма сделки', 'amount', 'price', 'чек', 'total_amount', 'выручка', 'к перечислению (выручка)'],
    'status': ['статус', 'этап', 'стадия', 'воронка', 'status', 'состояние'],
    'created_at': ['дата', 'дата создания', 'создано', 'дата заявки', 'created', 'created_at', 'когда', 'время создания', 'дата заказа', 'order_date'],
    'client': ['клиент', 'компания', 'контрагент', 'заказчик', 'client', 'кто купил', 'покупатель', 'фио', 'customer_name'],
    'contact': ['телефон', 'контакт', 'email', 'почта', 'phone'],
    'manager': ['менеджер', 'ответственный', 'владелец', 'manager'],
    'list_price': ['прайс', 'цена без скидки', 'list_price', 'цена до скидки', 'base_price'],
    'discount_pct': ['скидка', 'скидка %', 'discount', 'скинули', 'скидка, %', 'discount_pct'],
    'first_contact_at': ['дата первого контакта', 'первый звонок', 'first_contact', 'первый контакт', 'first_response_time'],
    'status_changed_at': ['дата смены статуса', 'на этапе с', 'status_changed'],
    'last_activity_at': ['дата последней активности', 'последний контакт', 'last_activity'],
    'closed_at': ['дата закрытия', 'дата оплаты', 'closed', 'closed_at', 'дата завершения', 'completion_date'],
    'source': ['канал', 'источник', 'source', 'канал продаж', 'channel'],
    'deal_id': ['id', 'номер', 'номер сделки', 'deal_id', 'номер заказа', 'id заказа', 'order_id', 'id отправления'],
}

STATUS_MAP_DEFAULT = {
    'new': [
        'новая', 'новый', 'новые', 'не разобрана', 'не разобран', 'входящая', 'входящие',
        'лид', 'лиды', 'создан', 'создана', 'создано', 'оформлен', 'оформлена', 'оформлен заказ',
        'поступил', 'поступила', 'принят', 'принята', 'первичный', 'первичный контакт',
        'new', 'lead', 'created', 'open', 'draft', 'черновик'
    ],
    'in_progress': [
        'в работе', 'в обработке', 'обрабатывается', 'квалификация', 'думает', 'созвон',
        'согласование условий', 'сборка', 'собирается', 'комплектация', 'комплектуется',
        'передан в доставку', 'в доставке', 'доставка', 'в пути', 'отгружен', 'отправлен',
        'застряло / думает', 'застряло', 'в работе / переговоры', 'на паузе', 'пауза',
        'in_progress', 'processing', 'shipping', 'shipped', 'in_transit'
    ],
    'proposal': [
        'кп отправлено', 'кп', 'коммерческое', 'коммерческое предложение',
        'счёт выставлен', 'счет выставлен', 'выставлен счет', 'выставлен счёт',
        'счет', 'счёт', 'ожидает оплаты', 'ждет оплаты', 'жду оплаты', 'к оплате',
        'proposal', 'quote', 'awaiting_payment', 'pending_payment', 'invoice'
    ],
    'negotiation': [
        'согласование', 'торг', 'пинать в пятницу', 'переговоры', 'на согласовании',
        'уточнение', 'обсуждение', 'согласование договора', 'договор',
        'negotiation', 'contract'
    ],
    'won': [
        'успешно', 'успешно завершено', 'оплачено', 'оплачен', 'закрыто', 'закрыта', 'закрыт',
        'выиграна', 'выигран', 'выиграно', 'доставлен', 'доставлено', 'доставлен и оплачен',
        'завершен', 'завершена', 'завершено', 'выполнен', 'выполнена', 'выполнено',
        'реализован', 'реализована', 'реализовано', 'выдан', 'вручен', 'получен', 'купили',
        'продано', 'won', 'paid', 'delivered', 'completed', 'success', 'done'
    ],
    'lost': [
        'отказ', 'проиграна', 'проигран', 'проиграно', 'нецелевой', 'отменен', 'отменена',
        'отменено', 'отменен клиентом', 'возврат', 'слив', 'слив / отказ', 'брак', 'спам',
        'недозвон', 'lost', 'cancelled', 'canceled', 'rejected', 'refund', 'returned', 'failed'
    ],
}

CANONICAL_FIELDS = [
    'amount', 'status', 'created_at', 'client', 'contact', 'manager',
    'list_price', 'discount_pct', 'first_contact_at', 'closed_at',
    'status_changed_at', 'last_activity_at', 'source', 'deal_id'
]

MONTHS_RU = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
    'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
    'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
}


def normalize_string(val: str) -> str:
    if not val:
        return ""
    val = val.strip().lower().replace('ё', 'е')
    return re.sub(r'\s+', ' ', val)


def parse_money(raw: Any) -> Optional[Decimal]:
    if raw is None or raw == '':
        return None
    s = str(raw).strip().lower().replace('\xa0', '').replace(' ', '')
    # If it contains letters other than руб / млн / тыс / ₽, it is not a pure money field (e.g. order id 'ORD-8801')
    cleaned_test = re.sub(r'(руб|рублей|р|млн|тыс|₽)', '', s)
    if re.search(r'[a-zA-Zа-яА-Я]', cleaned_test):
        return None

    s = re.sub(r'[₽руб\.]+$', '', s).strip()
    multiplier = Decimal(1)
    if 'млн' in s:
        multiplier = Decimal(1000000)
        s = s.replace('млн', '')
    elif 'тыс' in s:
        multiplier = Decimal(1000)
        s = s.replace('тыс', '')

    s = re.sub(r'[^\d,\.-]', '', s)
    if not s:
        return None

    # Handle commas and dots
    if ',' in s and '.' in s:
        last_comma = s.rfind(',')
        last_dot = s.rfind('.')
        if last_comma > last_dot:
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')

    try:
        val = Decimal(s) * multiplier
        return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def parse_date(raw: Any) -> Optional[datetime.datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime.datetime):
        return raw
    if isinstance(raw, datetime.date):
        return datetime.datetime(raw.year, raw.month, raw.day)

    s = str(raw).strip()
    if not s:
        return None

    # Excel serial number
    if re.match(r'^\d{5}(\.\d+)?$', s):
        try:
            excel_days = float(s)
            dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=excel_days)
            return dt
        except Exception:
            pass

    # Try Russian textual month: 14 мая 2024
    match_ru = re.match(r'^(\d{1,2})\s+([а-яёА-ЯЁ]+)\s+(\d{2,4})(?:\s+(\d{1,2}):(\d{2}))?', s, re.IGNORECASE)
    if match_ru:
        day = int(match_ru.group(1))
        m_name = match_ru.group(2).lower().replace('ё', 'е')
        year = int(match_ru.group(3))
        if year < 100:
            year += 2000
        month = MONTHS_RU.get(m_name)
        if month:
            hour = int(match_ru.group(4) or 0)
            minute = int(match_ru.group(5) or 0)
            try:
                return datetime.datetime(year, month, day, hour, minute)
            except Exception:
                pass

    # Standard formats
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%d.%m.%Y %H:%M:%S',
        '%d.%m.%Y %H:%M',
        '%d.%m.%Y',
        '%d.%m.%y %H:%M',
        '%d.%m.%y',
        '%d/%m/%Y %H:%M',
        '%d/%m/%Y',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d',
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass

    return None


def guess_column_mapping(columns: List[str], sample_rows: List[Dict[str, Any]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    assigned_cols = set()

    for canon_field in CANONICAL_FIELDS:
        syns = SYNONYMS.get(canon_field, [])
        for col in columns:
            if col in assigned_cols:
                continue
            norm_col = normalize_string(col)
            if norm_col in syns:
                mapping[canon_field] = col
                assigned_cols.add(col)
                break

    # Type-based heuristic for unassigned date/money columns
    date_fields = ['created_at', 'closed_at', 'first_contact_at', 'status_changed_at', 'last_activity_at']
    for col in columns:
        if col in assigned_cols:
            continue
        vals = [row.get(col) for row in sample_rows[:20] if row.get(col)]
        if not vals:
            continue

        # Check dates
        date_count = sum(1 for v in vals if parse_date(v) is not None)
        if date_count / len(vals) >= 0.8:
            for df in date_fields:
                if df not in mapping:
                    mapping[df] = col
                    assigned_cols.add(col)
                    break
            continue

        # Check money
        money_count = sum(1 for v in vals if parse_money(v) is not None)
        if money_count / len(vals) >= 0.8:
            if 'amount' not in mapping:
                mapping['amount'] = col
                assigned_cols.add(col)
            elif 'list_price' not in mapping:
                mapping['list_price'] = col
                assigned_cols.add(col)

    return mapping


def map_status(raw: str, user_status_map: Optional[Dict[str, str]] = None) -> str:
    if not raw:
        return 'other'
    raw_str = str(raw).strip()
    if user_status_map and raw_str in user_status_map:
        return user_status_map[raw_str]

    norm = normalize_string(raw_str)
    if user_status_map:
        for k, v in user_status_map.items():
            if normalize_string(k) == norm:
                return v

    # 1. Exact match against defaults
    for canon, syns in STATUS_MAP_DEFAULT.items():
        if norm in syns:
            return canon

    # 2. Check compound splits (e.g. 'Слив / Отказ', 'В работе / переговоры', 'Отказ; брак')
    parts = [p.strip() for p in re.split(r'[/\\,;|]', norm) if p.strip()]
    if len(parts) > 1:
        for p in parts:
            for canon, syns in STATUS_MAP_DEFAULT.items():
                if p in syns:
                    return canon

    # 3. Semantic keyword & stem rules (ordered by strict business priority)
    # Rule 3.1: Rejection / Cancellation / Loss overrides everything
    loss_stems = [
        'отказ', 'отмен', 'возврат', 'проигр', 'слив', 'брак', 'спам', 'нецелев',
        'недозвон', 'ошибочн', 'lost', 'cancel', 'reject', 'refund'
    ]
    if any(stem in norm for stem in loss_stems):
        return 'lost'

    # Rule 3.2: Awaiting payment / quotes (must precede won payment check!)
    awaiting_stems = [
        'ожидает оплат', 'ждет оплат', 'жду оплат', 'к оплат', 'ожидани',
        'awaiting_pay', 'pending_pay', 'счет', 'счёт', 'кп', 'коммерческ', 'quote', 'proposal', 'invoice'
    ]
    if any(stem in norm for stem in awaiting_stems):
        return 'proposal'

    # Rule 3.3: Won / Delivered / Paid / Completed
    won_stems = [
        'доставлен', 'оплач', 'выдан', 'вручен', 'получен', 'выигр', 'выполнен',
        'завершен', 'реализован', 'успеш', 'купили', 'won', 'paid', 'deliver', 'complet'
    ]
    if any(stem in norm for stem in won_stems):
        return 'won'

    # Rule 3.4: Negotiation / Agreement
    negotiation_stems = ['переговор', 'согласован', 'торг', 'договор', 'negotiat', 'contract']
    if any(stem in norm for stem in negotiation_stems):
        return 'negotiation'

    # Rule 3.5: In Progress / Processing / Shipping / Delay
    progress_stems = [
        'работ', 'обработк', 'обрабатыва', 'сборк', 'комплектац', 'доставк', 'в пути',
        'отгруз', 'отгружен', 'отправлен', 'квалификац', 'думает', 'созвон', 'пауз',
        'застря', 'курьер', 'process', 'ship'
    ]
    if any(stem in norm for stem in progress_stems):
        return 'in_progress'

    # Rule 3.6: New / Lead
    new_stems = [
        'нов', 'не разобран', 'входящ', 'лид', 'создан', 'оформлен', 'поступил',
        'принят', 'первичн', 'lead', 'new', 'creat'
    ]
    if any(stem in norm for stem in new_stems):
        return 'new'

    return 'other'


def build_status_map(
    unique_statuses: List[str],
    user_status_map: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    Builds a status_map dictionary for a list of unique raw statuses.
    """
    result: Dict[str, str] = {}
    for st in unique_statuses:
        if not st:
            continue
        result[st] = map_status(st, user_status_map)
    return result
