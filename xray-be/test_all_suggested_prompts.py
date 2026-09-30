import os
import sys
import warnings
warnings.filterwarnings('ignore')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

import json
import uuid
import time
from pathlib import Path
import django

sys.path.insert(0, os.path.abspath('xray_be'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xray_be.settings')
django.setup()

from engine.models import Snapshot, Upload, Deal
from engine.views_api import (
    derive_computed_columns,
    get_coverage,
    read_table_file,
    guess_column_mapping,
    ai_smart_column_mapping,
    ai_smart_status_mapping,
    normalize_records
)
from engine.analyzer import calculate_metrics_and_findings
from xray_be.views import stream_openai_response
from engine.tools import ensure_snapshot_deals, get_snapshot_extra_columns

def build_diagnosis_dict(snap):
    cols = get_snapshot_extra_columns(str(snap.id))
    deals_qs = Deal.objects.filter(snapshot=snap)
    cnt = deals_qs.count()
    from django.db.models import Sum, Min, Max
    total_amt = deals_qs.aggregate(s=Sum('amount'))['s'] or 0
    min_date = deals_qs.aggregate(m=Min('created_at'))['m']
    max_date = deals_qs.aggregate(m=Max('created_at'))['m']

    return {
        'headline': snap.headline or 'Анализ продаж',
        'findings': snap.findings or [],
        'totals': snap.totals or {
            'deals': cnt,
            'amount': f"{total_amt:.2f}"
        },
        'period': {
            'from': (min_date.strftime('%Y-%m-%d') if min_date else None) or (snap.period_from.strftime('%Y-%m-%d') if snap.period_from else None),
            'to': (max_date.strftime('%Y-%m-%d') if max_date else None) or (snap.period_to.strftime('%Y-%m-%d') if snap.period_to else None),
        },
        'available_columns': cols
    }

def load_or_get_snapshot_for_csv(csv_path: Path):
    filename = csv_path.name
    # Check if a snapshot with this upload filename already exists
    snap = Snapshot.objects.filter(upload__filename=filename).order_by('-created_at').first()
    if snap and Deal.objects.filter(snapshot=snap).count() > 0:
        print(f"[FOUND EXISTING] Snapshot {snap.id} for {filename} ({Deal.objects.filter(snapshot=snap).count()} deals)")
        return snap

    print(f"[CREATING] Snapshot for {filename}...")
    with open(csv_path, 'rb') as f:
        cols, sample_rows, all_rows = read_table_file(f, filename)

    mapping = guess_column_mapping(cols, sample_rows)
    if not mapping.get('amount') or not mapping.get('status') or not mapping.get('manager') or not mapping.get('deal_id'):
        mapping = ai_smart_column_mapping(cols, sample_rows, mapping)

    status_map = {}
    status_col = mapping.get('status')
    if status_col:
        unique_statuses = list(dict.fromkeys(
            str(r.get(status_col, '')).strip()
            for r in all_rows
            if str(r.get(status_col, '')).strip()
        ))
        if unique_statuses:
            status_map = ai_smart_status_mapping(unique_statuses, sample_rows)

    cols, sample_rows, all_rows, mapping, auto_computed = derive_computed_columns(
        cols, sample_rows, all_rows, mapping
    )

    upload_id = str(uuid.uuid4())
    upload = Upload.objects.create(
        id=upload_id,
        filename=filename,
        columns=cols,
        sample_rows=sample_rows,
        all_rows=all_rows,
        suggested_mapping=mapping,
        mapping=mapping,
        status_map=status_map,
        source=Upload.Source.DEMO,
    )

    deals, rejected = normalize_records(all_rows, mapping, status_map)
    findings, all_metrics, ok_list, low_sample = calculate_metrics_and_findings(deals, mapping)
    coverage = get_coverage(mapping)

    from decimal import Decimal
    total_amount = sum((d.amount for d in deals), Decimal('0.00'))
    dates = [d.created_at for d in deals if d.created_at]
    p_from = min(dates).date() if dates else None
    p_to = max(dates).date() if dates else None
    headline = findings[0]['action'] if findings else 'По этому файлу критичных утечек не видно.'

    snap = Snapshot.objects.create(
        upload=upload,
        status=Snapshot.Status.READY,
        headline=headline,
        body=' '.join([f.get('action', '') for f in findings]),
        period_from=p_from,
        period_to=p_to,
        all_metrics=all_metrics,
        findings=findings,
        coverage=coverage,
        ok_list=ok_list,
        low_sample=low_sample,
        totals={
            'deals': len(deals) + len(rejected),
            'amount': f"{total_amount:.2f}",
            'accepted': len(deals),
            'rejected': len(rejected),
        },
    )

    deal_objs = [
        Deal(
            snapshot=snap,
            deal_id=d.deal_id,
            client=d.client,
            contact=d.contact,
            manager=d.manager,
            amount=d.amount,
            list_price=d.list_price,
            discount_pct=d.discount_pct,
            status_raw=d.status_raw,
            status=d.status,
            created_at=d.created_at,
            first_contact_at=d.first_contact_at,
            status_changed_at=d.status_changed_at,
            last_activity_at=d.last_activity_at,
            closed_at=d.closed_at,
            source=d.source,
            raw_data=d.raw_data or {},
        )
        for d in deals
    ]
    Deal.objects.bulk_create(deal_objs)
    print(f"[CREATED] Snapshot {snap.id} with {len(deal_objs)} deals for {filename}")
    return snap


def get_suggested_prompts(diagnosis: dict):
    suggestions = []
    available_cols = diagnosis.get('available_columns', [])
    norm_cols = [c.lower() for c in available_cols]

    has_category = any('категори' in c or 'category' in c or 'группа' in c for c in norm_cols)
    has_product = any('товар' in c or 'артикул' in c or 'номенклатур' in c or 'продукт' in c for c in norm_cols)
    has_city = any('город' in c or 'city' in c or 'регион' in c for c in norm_cols)
    has_channel = any('канал' in c or 'склад' in c or 'площадк' in c or 'точка' in c for c in norm_cols)
    has_payment = any('оплат' in c or 'payment' in c for c in norm_cols)
    has_manager = any('менеджер' in c or 'manager' in c or 'кто тащит' in c or 'ответствен' in c for c in norm_cols)

    if has_category:
        suggestions.append({
            'label': '📦 Выручка по категориям',
            'query': 'Сравни выручку и количество заказов по категориям каталога.'
        })
    if has_product:
        suggestions.append({
            'label': '🏆 Топ-5 товаров',
            'query': 'Покажи топ-5 самых продаваемых товаров по сумме выручки.'
        })
    if has_city:
        suggestions.append({
            'label': '🌍 Срез по городам',
            'query': 'В каких городах самый высокий средний чек? Сравни города по выручке.'
        })
    if has_channel:
        suggestions.append({
            'label': '🛒 Продажи по каналам',
            'query': 'Сравни продажи, количество заказов и выручку по каналам сбыта (складам/площадкам).'
        })
    if has_payment:
        suggestions.append({
            'label': '💳 Способы оплаты',
            'query': 'Какими способами оплаты чаще всего пользуются и какая выручка по каждому?'
        })

    findings = diagnosis.get('findings', [])
    stagnation_finding = next((f for f in findings if f.get('metric_id') == 'stagnation'), None)
    discount_finding = next((f for f in findings if f.get('metric_id') == 'discount_leakage'), None)
    speed_finding = next((f for f in findings if f.get('metric_id') == 'speed_to_lead'), None)
    key_account_finding = next((f for f in findings if f.get('metric_id') == 'key_account_risk'), None)

    if stagnation_finding:
        amt_str = f" ({stagnation_finding.get('money_impact')} ₽)" if stagnation_finding.get('money_impact') else ""
        suggestions.append({
            'label': f"⏳ Зависшие сделки{amt_str}",
            'query': 'Покажи зависшие сделки, где застряли деньги, и предложи план действий для РОПа.'
        })
    if discount_finding:
        suggestions.append({
            'label': '💸 Сделки с макс. скидками',
            'query': 'Найди сделки с самыми большими скидками и оцени потери маржи.'
        })
    if speed_finding:
        suggestions.append({
            'label': '⚡ Задержки первого ответа',
            'query': 'Сколько лидов ждут первого ответа дольше нормы и кто из менеджеров отвечает медленнее всех?'
        })
    if key_account_finding:
        suggestions.append({
            'label': '👑 Топ клиентов по выручке',
            'query': 'Выведи топ ключевых клиентов по выручке и оцени риск концентрации.'
        })

    if has_manager or len(norm_cols) == 0:
        suggestions.append({
            'label': '👥 Эффективность менеджеров',
            'query': 'Кто из менеджеров лучший по выручке и закрытым сделкам? Сравни показатели команды.'
        })

    suggestions.append({
        'label': '📈 График выручки по дням',
        'query': 'Построй интерактивный график динамики выручки по датам.'
    })
    suggestions.append({
        'label': '📉 Воронка по этапам',
        'query': 'Построй сводную таблицу воронки продаж по этапам сделок и рассчитай конверсию между стадиями.'
    })
    suggestions.append({
        'label': '🔍 Самые крупные сделки',
        'query': 'Найди топ-5 самых крупных сделок в отчете.'
    })

    seen = set()
    result = []
    for s in suggestions:
        if s['label'] not in seen:
            seen.add(s['label'])
            result.append(s)
            if len(result) >= 7:
                break
    return result


def build_system_prompt(diagnosis: dict) -> str:
    threats_text = "\n".join([
        f"{idx + 1}. [{f.get('verdict', '').upper()}] {f.get('metric_id')}: {f.get('action')} "
        f"(Деньги под угрозой: {f.get('money_impact', 'не применимо') + ' руб.' if f.get('money_impact') else 'не применимо'}, "
        f"порог: {f.get('threshold_label')})"
        for idx, f in enumerate(diagnosis.get('findings', []))
    ])

    standard_fields = {
        'deal_id', 'client', 'contact', 'manager', 'amount', 'list_price',
        'discount_pct', 'status', 'status_raw', 'created_at', 'first_contact_at',
        'status_changed_at', 'last_activity_at', 'closed_at', 'source'
    }
    custom_cols = [c for c in diagnosis.get('available_columns', []) if c and c not in standard_fields]
    custom_cols_section = ""
    if custom_cols:
        custom_cols_section = (
            "\n  ДОПОЛНИТЕЛЬНЫЕ СТОЛБЦЫ ИЗ ИСХОДНОГО ФАЙЛА ПОЛЬЗОВАТЕЛЯ (также доступны в таблице deals!):\n" +
            "\n".join([f'  * "{c}"' for c in custom_cols]) +
            f'\n  Ты можешь обращаться к ним напрямую в SELECT, WHERE, GROUP BY, ORDER BY, заключая их в двойные кавычки (например: SELECT "{custom_cols[0]}", COUNT(*), SUM(amount) FROM deals GROUP BY "{custom_cols[0]}").\n' +
            "  Используй эти столбцы для глубокого анализа товаров, категорий, городов, каналов, способов оплаты и любых специфичных для бизнеса метрик!\n"
        )

    return (
        "Ты — персональный бизнес-аналитик и консультант по продажам сервиса X-Ray.\n"
        "Перед тобой результаты рентгена продаж реального бизнеса пользователя:\n\n"
        f"Главный вывод диагноза: \"{diagnosis.get('headline')}\"\n\n"
        "Общая статистика:\n"
        f"- Всего сделок: {diagnosis.get('totals', {}).get('deals')}\n"
        f"- Общая сумма: {diagnosis.get('totals', {}).get('amount')} руб.\n"
        f"- Период: с {diagnosis.get('period', {}).get('from') or 'начала'} по {diagnosis.get('period', {}).get('to') or 'конец'}\n\n"
        f"Ключевые найденные угрозы и утечки:\n{threats_text}\n\n"
        "ВАЖНО ОБ ИНСТРУМЕНТАХ (TOOLS) И SQL-АНАЛИТИКЕ:\n"
        "У тебя есть доступ к базе сделок текущего отчета через инструмент execute_sql_query и к построению интерактивных графиков через render_chart.\n"
        "- execute_sql_query: ТВОЙ ГЛАВНЫЙ ИНСТРУМЕНТ для получения любых данных. Используй его ВСЕГДА, когда пользователь спрашивает о:\n"
        "  1. Менеджерах (кто лучше или хуже работает, кто закрывает больше выручки, у кого зависли сделки, средний чек, статистика команды).\n"
        "     Пример: SELECT manager, COUNT(*) as deals_cnt, SUM(amount) as total_amt, SUM(CASE WHEN status=\"won\" THEN 1 ELSE 0 END) as won_cnt, SUM(CASE WHEN status=\"lost\" THEN 1 ELSE 0 END) as lost_cnt, ROUND(AVG(amount), 2) as avg_check FROM deals WHERE manager != \"\" GROUP BY manager ORDER BY total_amt DESC\n"
        "  2. Клиентах и покупателях (топ клиентов по сумме покупок, средний чек, история сделок конкретного контрагента).\n"
        "     Пример: SELECT client, COUNT(*) as orders_cnt, SUM(amount) as total_amt, ROUND(AVG(amount), 2) as avg_check FROM deals WHERE client != \"\" GROUP BY client ORDER BY total_amt DESC LIMIT 10\n"
        "  3. Поиске конкретных сделок (по фильтрам, статусам, суммам, датам, клиентам или менеджерам).\n"
        "     Пример: SELECT deal_id, client, manager, amount, status, status_raw, created_at FROM deals WHERE amount > 50000 ORDER BY amount DESC LIMIT 15\n"
        "  4. Анализе этапов и причин отказов (распределение по status_raw, потерянные заказы, каналы source, скидки discount_pct).\n"
        "  Схема таблицы deals:\n"
        "  * deal_id (текст): идентификатор сделки / заказа\n"
        "  * client (текст): имя клиента или название компании\n"
        "  * contact (текст): телефон / email\n"
        "  * manager (текст): имя ответственного менеджера\n"
        "  * amount (число): сумма сделки / выручка в рублях\n"
        "  * list_price (число): базовая цена без скидки\n"
        "  * discount_pct (число): скидка в %\n"
        "  * status (текст): канонический статус (\"new\", \"in_progress\", \"proposal\", \"negotiation\", \"won\", \"lost\", \"other\")\n"
        "  * status_raw (текст): исходный статус из CRM / файла пользователя (например, \"Доставлен и оплачен\", \"В обработке\")\n"
        "  * created_at, closed_at, first_contact_at, status_changed_at, last_activity_at (даты/время)\n"
        "  * source (текст): канал / источник / маркетплейс\n"
        f"{custom_cols_section}"
        "  Пиши только одиночные SELECT-запросы. Все данные уже изолированы по текущему снимку.\n"
        "- render_chart: вызывай для визуализации, когда пользователь просит \"построй график\", \"нарисуй диаграмму\", \"динамику выручки по времени\", \"сравни менеджеров визуально\", \"распределение выручки/сделок\" или \"сделай чарт\".\n"
        "  * Для графиков выручки по времени/датам: chart_type=\"line\", dimension=\"date\" (или \"month\").\n"
        "  * Для менеджеров: chart_type=\"bar\", dimension=\"manager\".\n"
        "  * Для клиентов: chart_type=\"bar\", dimension=\"client\".\n"
        "  * Ты также можешь передавать произвольно рассчитанные через SQL данные в массив data для render_chart!\n"
        "ВАЖНО: Для анализа воронки продаж, этапов сделок и конверсий НЕ пытайся строить график-воронку через render_chart. С этой задачей ты отлично справляешься текстом: запрашивай данные через execute_sql_query (GROUP BY status или status_raw) и формируй наглядную, структурированную Markdown-таблицу стадий воронки с числом заказов, выручкой и конверсией между этапами!\n"
        "Никогда не говори \"в отчете нет данных о менеджерах или клиентах\" без предварительного выполнения execute_sql_query к таблице deals.\n"
        "Когда строишь график через render_chart, в тексте своего ответа обязательно прокомментируй полученные на графике данные, динамику, пики и дай практические советы.\n\n"
        "ПРАВИЛА ОБЩЕНИЯ:\n"
        "1. Опирайся на конкретные цифры и факты из отчета и SQL-ответов. Не придумывай финансовые показатели.\n"
        "2. Отвечай кратко, емко, дружелюбно, языком опытного предпринимателя и трекера.\n"
        "3. Давай практические советы по шагам: что сделать РОПу, менеджерам или владельцу уже сегодня."
    )


def test_prompt(snap, system_prompt: str, user_query: str):
    """
    Runs chat stream generator, collects tools, errors, and text chunks.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    tool_events = []
    text_chunks = []
    has_sql_error = False
    sql_error_msg = ""

    gen = stream_openai_response(messages, snapshot_id=str(snap.id))
    for raw in gen:
        raw_str = raw.strip()
        if not raw_str.startswith("data: "):
            continue
        data_content = raw_str[6:].strip()
        if data_content == "[DONE]":
            break

        try:
            ev = json.loads(data_content)
        except Exception:
            continue

        if ev.get("type") == "tool_call":
            tool_name = ev.get("tool_name")
            tool_res_raw = ev.get("result", "")
            try:
                t_res = json.loads(tool_res_raw) if isinstance(tool_res_raw, str) else tool_res_raw
            except Exception:
                t_res = {}

            if isinstance(t_res, dict) and "error" in t_res:
                has_sql_error = True
                sql_error_msg = t_res["error"]

            tool_events.append({
                "name": tool_name,
                "args": ev.get("arguments"),
                "has_error": "error" in t_res if isinstance(t_res, dict) else False,
                "error": t_res.get("error") if isinstance(t_res, dict) else ""
            })
        elif "choices" in ev:
            delta = ev["choices"][0].get("delta", {})
            if "content" in delta and delta["content"]:
                text_chunks.append(delta["content"])

    full_text = "".join(text_chunks).strip()
    return {
        "tools": tool_events,
        "has_sql_error": has_sql_error,
        "sql_error": sql_error_msg,
        "text_length": len(full_text),
        "text_preview": full_text[:120].replace("\n", " "),
        "success": (not has_sql_error) and len(full_text) > 20
    }


def main():
    root = Path(__file__).resolve().parent.parent
    csv_paths = [
        root / 'templates' / 'ecommerce_canonical.csv',
        root / 'templates' / 'ecommerce_marketplace.csv',
        root / 'templates' / 'ecommerce_moysklad_1c.csv',
        root / 'templates' / 'ecommerce_messy_user_table.csv',
        root / 'templates' / 'custom_messy_slang_crm.csv',
        root / 'xray-fe' / 'public' / 'demo_deals.csv',
    ]

    all_test_results = []
    print(f"=== STARTING TESTING ACROSS {len(csv_paths)} DATASETS ===")

    for p in csv_paths:
        if not p.exists():
            print(f"Skipping missing file {p}")
            continue

        print(f"\n=======================================================")
        print(f"DATASET: {p.name}")
        print(f"=======================================================")

        snap = load_or_get_snapshot_for_csv(p)
        diagnosis = build_diagnosis_dict(snap)
        suggestions = get_suggested_prompts(diagnosis)
        system_prompt = build_system_prompt(diagnosis)

        print(f"Available columns ({len(diagnosis.get('available_columns', []))}): {diagnosis.get('available_columns', [])}")
        print(f"Generated {len(suggestions)} prompt suggestions:")
        for idx, s in enumerate(suggestions):
            print(f"  {idx+1}. {s['label']} -> \"{s['query']}\"")

        for s in suggestions:
            label = s['label']
            query = s['query']
            print(f"\n  Testing [{label}]...")
            t0 = time.time()
            res = test_prompt(snap, system_prompt, query)
            duration = round(time.time() - t0, 1)

            tools_str = ", ".join([f"{t['name']}{'(ERR)' if t['has_error'] else ''}" for t in res['tools']]) or "no tools"
            status_str = "PASS" if res['success'] else "FAIL"

            print(f"    Status: [{status_str}] in {duration}s | Tools: {tools_str} | Text len: {res['text_length']}")
            if res['has_sql_error']:
                print(f"    !!! SQL ERROR: {res['sql_error']}")
            print(f"    Response preview: {res['text_preview']}...")

            all_test_results.append({
                "dataset": p.name,
                "label": label,
                "query": query,
                "tools": tools_str,
                "status": status_str,
                "sql_error": res['sql_error'],
                "duration": duration,
                "preview": res['text_preview']
            })
            with open('prompt_test_results.json', 'w', encoding='utf-8') as f_out:
                json.dump(all_test_results, f_out, ensure_ascii=False, indent=2)

    print("\n\n=======================================================")
    print("FINAL SUMMARY REPORT:")
    print("=======================================================")
    total = len(all_test_results)
    passed = sum(1 for r in all_test_results if r['status'] == 'PASS')
    failed = total - passed

    print(f"TOTAL TESTS: {total} | PASSED: {passed} | FAILED: {failed}\n")
    for r in all_test_results:
        flag = "✅" if r['status'] == 'PASS' else "❌"
        print(f"{flag} [{r['dataset'][:20]:20}] {r['label'][:25]:25} | {r['tools'][:25]:25} | {r['duration']}s")
        if r['status'] == 'FAIL':
            print(f"    -> Query: {r['query']}")
            print(f"    -> SQL Error: {r['sql_error']}")

if __name__ == '__main__':
    main()
