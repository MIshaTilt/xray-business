import re
import csv
import io
import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Tuple, Any, Optional

SYNONYMS = {
    'amount': [
        'сумма', 'бюджет', 'цена', 'цена со скидкой', 'итого', 'сумма сделки',
        'amount', 'price', 'чек', 'total_amount', 'выручка', 'к перечислению (выручка)',
        'сумма документа (итого)', 'итого к оплате', 'к оплате', 'сумма к оплате', 'всего'
    ],
    'status': [
        'статус', 'этап', 'стадия', 'воронка', 'status', 'состояние',
        'текущее состояние', 'статус заказа', 'стадия заказа', 'статус сделки', 'стадия сделки'
    ],
    'created_at': [
        'дата', 'дата создания', 'создано', 'дата заявки', 'created', 'created_at',
        'когда', 'время создания', 'дата заказа', 'order_date', 'дата оформления',
        'дата и время создания'
    ],
    'client': [
        'клиент', 'компания', 'контрагент', 'заказчик', 'client', 'кто купил',
        'покупатель', 'фио', 'customer_name', 'контрагент (покупатель)'
    ],
    'contact': [
        'телефон', 'контакт', 'email', 'почта', 'phone', 'телефон покупателя', 'телефон клиента'
    ],
    'manager': [
        'менеджер', 'ответственный', 'владелец', 'manager', 'ответственный менеджер'
    ],
    'list_price': [
        'прайс', 'цена без скидки', 'list_price', 'цена до скидки', 'base_price',
        'розничная цена', 'цена без скидки (руб.)', 'цена без скидки (руб)',
        'базовая цена', 'исходная цена', 'unit_price', 'цена за шт'
    ],
    'discount_pct': [
        'скидка', 'скидка %', 'discount', 'скинули', 'скидка, %', 'discount_pct',
        'скидка продавца, руб.', 'скидка продавца', 'скидка клиента (руб)',
        'скидка клиента', 'скидка, руб.', 'скидка, руб', 'скидка (руб)',
        'discount_amount'
    ],
    'first_contact_at': [
        'дата первого контакта', 'первый звонок', 'first_contact', 'первый контакт',
        'first_response_time', 'первый контакт (авто)'
    ],
    'status_changed_at': [
        'дата смены статуса', 'на этапе с', 'status_changed', 'дней на этапе',
        'дней без движения', 'days_in_stage', 'дата смены статуса (авто)'
    ],
    'last_activity_at': [
        'дата последней активности', 'последний контакт', 'last_activity',
        'дата последнего звонка', 'последний звонок', 'дата задачи',
        'updated_at', 'дата обновления', 'последняя активность (авто)'
    ],
    'closed_at': [
        'дата закрытия', 'дата оплаты', 'closed', 'closed_at', 'дата завершения',
        'completion_date', 'дата доставки', 'дата отгрузки', 'дата чека',
        'дата вручения', 'delivery_date', 'paid_at', 'shipped_at', 'дата закрытия (авто)'
    ],
    'source': ['канал', 'источник', 'source', 'канал продаж', 'channel', 'склад / канал', 'канал сбыта', 'точка продажи'],
    'deal_id': ['id', 'номер', 'номер сделки', 'deal_id', 'номер заказа', 'id заказа', 'order_id', 'id отправления', 'код', '\ufeffномер заказа'],
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
        norm_col = normalize_string(col)
        # Exclude obvious non-money numeric columns (counts, delays, minutes, ids)
        if any(w in norm_col for w in ['кол-во', 'количество', 'штук', 'минут', 'секунд', 'дней', 'delay', 'qty', 'count', 'id', 'номер']):
            continue

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


def derive_computed_columns(
    cols: List[str],
    sample_rows: List[Dict[str, Any]],
    all_rows: List[Dict[str, Any]],
    mapping: Dict[str, str]
) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str], List[str]]:
    """
    Synthesizes missing columns (e.g. 'Скидка, % (авто)', 'Прайс до скидки (авто)', 'Первый контакт (авто)')
    from available raw data when direct canonical fields are absent.
    Returns: (updated_cols, updated_sample_rows, updated_all_rows, updated_mapping, auto_computed_columns)
    """
    updated_cols = list(cols)
    auto_computed: List[str] = []

    amount_col = mapping.get('amount')
    created_col = mapping.get('created_at')

    # --- 1. DISCOUNT % & LIST PRICE ---
    existing_disc = mapping.get('discount_pct')
    is_real_pct = False
    if existing_disc:
        norm_disc_name = normalize_string(existing_disc)
        if 'руб' in norm_disc_name or 'amount' in norm_disc_name:
            is_real_pct = False
        else:
            # Check values: if any > 100, it's money, not percentage
            sample_disc_vals = [parse_money(r.get(existing_disc)) for r in sample_rows[:15] if r.get(existing_disc)]
            if any(v is not None and v > 100 for v in sample_disc_vals):
                is_real_pct = False
            elif sample_disc_vals:
                is_real_pct = True

    # Identify potential raw columns for discount in rubles, unit price, quantity
    money_disc_col = None
    unit_price_col = mapping.get('list_price')
    qty_col = None

    for c in cols:
        norm = normalize_string(c)
        if not money_disc_col and any(w in norm for w in ['скидк', 'скинули', 'дисконт', 'discount', 'disc']) and 'без скидк' not in norm:
            if not is_real_pct:
                money_disc_col = c
        if not unit_price_col and any(w in norm for w in ['цена за шт', 'розничная цена', 'цена без скидки', 'прайс', 'regular_price', 'цена товара']):
            unit_price_col = c
        if not qty_col and any(w in norm for w in ['кол-во', 'количество', 'штук', 'шт', 'qty', 'count']):
            qty_col = c

    # 1a. Synthesize 'Скидка, % (авто)'
    if not is_real_pct and amount_col and (money_disc_col or (unit_price_col and unit_price_col != amount_col)):
        auto_disc_name = 'Скидка, % (авто)'
        if auto_disc_name not in updated_cols:
            updated_cols.append(auto_disc_name)
        auto_computed.append(auto_disc_name)
        mapping['discount_pct'] = auto_disc_name

        for r_list in (all_rows, sample_rows):
            for r in r_list:
                amt = parse_money(r.get(amount_col)) or Decimal(0)
                pct_val = Decimal(0)
                if money_disc_col:
                    disc_m = parse_money(r.get(money_disc_col)) or Decimal(0)
                    lp = amt + disc_m
                    if lp > 0 and disc_m > 0:
                        pct_val = (disc_m / lp) * Decimal(100)
                elif unit_price_col:
                    up = parse_money(r.get(unit_price_col)) or Decimal(0)
                    qty = parse_money(r.get(qty_col)) if qty_col else Decimal(1)
                    if not qty or qty <= 0:
                        qty = Decimal(1)
                    lp = up * qty
                    if lp > amt and lp > 0:
                        pct_val = ((lp - amt) / lp) * Decimal(100)
                pct_val = min(Decimal(100), max(Decimal(0), pct_val)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                r[auto_disc_name] = f"{pct_val}%"

    # 1b. Synthesize 'Прайс до скидки (авто)'
    has_lp = bool(mapping.get('list_price')) and mapping.get('list_price') not in auto_computed
    if not has_lp and amount_col and (money_disc_col or (unit_price_col and qty_col)):
        auto_lp_name = 'Прайс до скидки (авто)'
        if auto_lp_name not in updated_cols:
            updated_cols.append(auto_lp_name)
        auto_computed.append(auto_lp_name)
        mapping['list_price'] = auto_lp_name

        for r_list in (all_rows, sample_rows):
            for r in r_list:
                amt = parse_money(r.get(amount_col)) or Decimal(0)
                lp_val = amt
                if money_disc_col:
                    disc_m = parse_money(r.get(money_disc_col)) or Decimal(0)
                    lp_val = amt + disc_m
                elif unit_price_col:
                    up = parse_money(r.get(unit_price_col)) or Decimal(0)
                    qty = parse_money(r.get(qty_col)) if qty_col else Decimal(1)
                    if not qty or qty <= 0:
                        qty = Decimal(1)
                    lp_val = up * qty
                r[auto_lp_name] = f"{int(lp_val):,} ₽".replace(',', ' ')

    # --- 2. FIRST CONTACT AT DERIVATION ---
    if not mapping.get('first_contact_at') and created_col:
        delay_col = None
        for c in cols:
            norm = normalize_string(c)
            if any(w in norm for w in ['delay', 'опоздан', 'задержк', 'минут', 'время первого ответа', 'время ответа', 'скорость ответа']) and 'ответствен' not in norm:
                delay_col = c
                break
        if delay_col:
            auto_fc_name = 'Первый контакт (авто)'
            if auto_fc_name not in updated_cols:
                updated_cols.append(auto_fc_name)
            auto_computed.append(auto_fc_name)
            mapping['first_contact_at'] = auto_fc_name

            for r_list in (all_rows, sample_rows):
                for r in r_list:
                    c_dt = parse_date(r.get(created_col))
                    raw_delay = r.get(delay_col)
                    if c_dt and raw_delay is not None:
                        delay_num = re.sub(r'[^\d.]', '', str(raw_delay))
                        try:
                            d_min = float(delay_num)
                            fc_dt = c_dt + datetime.timedelta(minutes=d_min)
                            r[auto_fc_name] = fc_dt.strftime('%d.%m.%Y %H:%M')
                        except Exception:
                            r[auto_fc_name] = '—'
                    else:
                        r[auto_fc_name] = '—'

    # --- 3. CLOSED AT DERIVATION ---
    if not mapping.get('closed_at'):
        closed_date_col = None
        duration_col = None
        for c in cols:
            norm = normalize_string(c)
            if not closed_date_col and any(w in norm for w in [
                'дата доставки', 'дата отгрузки', 'дата оплаты', 'дата чека',
                'дата завершения', 'дата закрытия', 'дата вручения',
                'delivery_date', 'closed_at', 'completion_date', 'paid_at', 'shipped_at'
            ]) and 'способ' not in norm and 'type' not in norm and 'город' not in norm:
                closed_date_col = c
            if not duration_col and any(w in norm for w in [
                'дней в сделке', 'дней до закрытия', 'цикл (дни)', 'длительность',
                'срок (дни)', 'duration_days', 'cycle_days'
            ]):
                duration_col = c

        if closed_date_col or (duration_col and created_col):
            auto_cl_name = 'Дата закрытия (авто)'
            if auto_cl_name not in updated_cols:
                updated_cols.append(auto_cl_name)
            auto_computed.append(auto_cl_name)
            mapping['closed_at'] = auto_cl_name

            for r_list in (all_rows, sample_rows):
                for r in r_list:
                    if closed_date_col:
                        val = parse_date(r.get(closed_date_col))
                        r[auto_cl_name] = val.strftime('%d.%m.%Y %H:%M') if val else '—'
                    elif duration_col and created_col:
                        c_dt = parse_date(r.get(created_col))
                        raw_dur = r.get(duration_col)
                        if c_dt and raw_dur is not None:
                            try:
                                dur_days = float(re.sub(r'[^\d.]', '', str(raw_dur)) or 0)
                                cl_dt = c_dt + datetime.timedelta(days=dur_days)
                                r[auto_cl_name] = cl_dt.strftime('%d.%m.%Y %H:%M')
                            except Exception:
                                r[auto_cl_name] = '—'
                        else:
                            r[auto_cl_name] = '—'

    # --- 4. STATUS CHANGED AT DERIVATION ---
    if not mapping.get('status_changed_at'):
        stale_days_col = None
        for c in cols:
            norm = normalize_string(c)
            if any(w in norm for w in [
                'дней на этапе', 'дней без движения', 'время простоя',
                'days_in_stage', 'простой (дней)', 'дней в статусе', 'stale_days'
            ]):
                stale_days_col = c
                break
        if stale_days_col:
            auto_sc_name = 'Дата смены статуса (авто)'
            if auto_sc_name not in updated_cols:
                updated_cols.append(auto_sc_name)
            auto_computed.append(auto_sc_name)
            mapping['status_changed_at'] = auto_sc_name
            now_dt = datetime.datetime.now()

            for r_list in (all_rows, sample_rows):
                for r in r_list:
                    raw_stale = r.get(stale_days_col)
                    if raw_stale is not None:
                        try:
                            s_days = float(re.sub(r'[^\d.]', '', str(raw_stale)) or 0)
                            sc_dt = now_dt - datetime.timedelta(days=s_days)
                            r[auto_sc_name] = sc_dt.strftime('%d.%m.%Y %H:%M')
                        except Exception:
                            r[auto_sc_name] = '—'
                    else:
                        r[auto_sc_name] = '—'

    # --- 5. LAST ACTIVITY AT DERIVATION ---
    if not mapping.get('last_activity_at'):
        act_col = None
        for c in cols:
            norm = normalize_string(c)
            if any(w in norm for w in [
                'дата последнего контакта', 'последний звонок', 'дата задачи',
                'последняя активность', 'updated_at', 'last_contact', 'дата обновления'
            ]):
                act_col = c
                break
        if act_col:
            auto_act_name = 'Последняя активность (авто)'
            if auto_act_name not in updated_cols:
                updated_cols.append(auto_act_name)
            auto_computed.append(auto_act_name)
            mapping['last_activity_at'] = auto_act_name

            for r_list in (all_rows, sample_rows):
                for r in r_list:
                    val = parse_date(r.get(act_col))
                    r[auto_act_name] = val.strftime('%d.%m.%Y %H:%M') if val else '—'

    # --- 6. REALIZED UNIT PRICE ---
    if amount_col and qty_col:
        auto_unit_price = 'Цена за шт. факт (авто)'
        if auto_unit_price not in updated_cols:
            updated_cols.append(auto_unit_price)
        auto_computed.append(auto_unit_price)

        for r_list in (all_rows, sample_rows):
            for r in r_list:
                amt = parse_money(r.get(amount_col)) or Decimal(0)
                qty = parse_money(r.get(qty_col)) if qty_col else Decimal(1)
                if qty and qty > 0 and amt > 0:
                    unit_p = (amt / qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    r[auto_unit_price] = f"{float(unit_p):,.2f} ₽".replace(',', ' ')
                else:
                    r[auto_unit_price] = '—'

    # --- 7. GROSS MARGIN & PROFIT DERIVATION ---
    cost_col = None
    for c in cols:
        norm = normalize_string(c)
        if any(w in norm for w in ['себестоимость', 'закупка', 'цена закупки', 'входная цена', 'cost_price', 'cogs', 'себес']):
            cost_col = c
            break

    if cost_col and amount_col:
        auto_profit_name = 'Валовая прибыль (авто)'
        auto_margin_name = 'Маржинальность, % (авто)'
        if auto_profit_name not in updated_cols:
            updated_cols.append(auto_profit_name)
        if auto_margin_name not in updated_cols:
            updated_cols.append(auto_margin_name)
        auto_computed.extend([auto_profit_name, auto_margin_name])

        for r_list in (all_rows, sample_rows):
            for r in r_list:
                amt = parse_money(r.get(amount_col)) or Decimal(0)
                c_val = parse_money(r.get(cost_col)) or Decimal(0)
                qty = parse_money(r.get(qty_col)) if qty_col else Decimal(1)
                if not qty or qty <= 0:
                    qty = Decimal(1)
                total_cost = c_val * qty
                profit = amt - total_cost
                margin = (profit / amt * Decimal(100)) if amt > 0 else Decimal(0)
                margin = margin.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                r[auto_profit_name] = f"{int(profit):,} ₽".replace(',', ' ')
                r[auto_margin_name] = f"{margin}%"

    # --- 8. MARKETPLACE COMMISSION DERIVATION ---
    comm_col = None
    for c in cols:
        norm = normalize_string(c)
        if any(w in norm for w in [
            'комиссия', 'удержания', 'вознаграждение wb', 'вознаграждение ozon',
            'комиссия маркетплейса', 'эквайринг', 'логистика маркетплейса', 'marketplace_fee'
        ]) and 'ответствен' not in norm:
            comm_col = c
            break

    if comm_col and amount_col:
        auto_comm_name = 'Удержания площадки (авто)'
        auto_comm_pct = 'Комиссия маркетплейса, % (авто)'
        if auto_comm_name not in updated_cols:
            updated_cols.append(auto_comm_name)
        if auto_comm_pct not in updated_cols:
            updated_cols.append(auto_comm_pct)
        auto_computed.extend([auto_comm_name, auto_comm_pct])

        for r_list in (all_rows, sample_rows):
            for r in r_list:
                amt = parse_money(r.get(amount_col)) or Decimal(0)
                fee = parse_money(r.get(comm_col)) or Decimal(0)
                base = amt + fee
                fee_pct = (fee / base * Decimal(100)) if base > 0 else Decimal(0)
                fee_pct = fee_pct.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                r[auto_comm_name] = f"{int(fee):,} ₽".replace(',', ' ')
                r[auto_comm_pct] = f"{fee_pct}%"

    return updated_cols, sample_rows, all_rows, mapping, auto_computed


