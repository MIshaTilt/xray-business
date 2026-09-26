import json
import re
from decimal import Decimal
from django.db import connection
from django.db.models import Sum, Count, Avg, Q
from engine.models import Deal, Snapshot


AI_TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql_query",
            "description": (
                "Выполнить аналитический SQL SELECT-запрос к таблице deals (сделки текущего снимка). "
                "Используй этот инструмент ВСЕГДА для любых выборок, фильтрации, поиска сделок, аналитики по менеджерам, клиентам, суммам, датам, воронке и среднему чеку.\n"
                "Схема таблицы deals:\n"
                "- deal_id (TEXT): идентификатор сделки / заказа\n"
                "- client (TEXT): имя клиента / покупателя / компании\n"
                "- contact (TEXT): контакты (телефон, email)\n"
                "- manager (TEXT): имя ответственного менеджера\n"
                "- amount (NUMERIC): сумма сделки / выручка в рублях\n"
                "- list_price (NUMERIC): базовая цена без скидки\n"
                "- discount_pct (NUMERIC): скидка в %\n"
                "- status (TEXT): канонический статус ('new', 'in_progress', 'proposal', 'negotiation', 'won', 'lost', 'other')\n"
                "- status_raw (TEXT): исходный статус из CRM / файла пользователя\n"
                "- created_at (TIMESTAMP): дата создания сделки\n"
                "- closed_at (TIMESTAMP): дата закрытия / оплаты / отгрузки сделки\n"
                "- first_contact_at (TIMESTAMP): дата первого контакта\n"
                "- status_changed_at (TIMESTAMP): дата последней смены этапа\n"
                "- last_activity_at (TIMESTAMP): дата последней активности\n"
                "- source (TEXT): канал / источник лида / маркетплейс\n\n"
                "Поддерживаются стандартные функции SQL: COUNT, SUM, AVG, MIN, MAX, GROUP BY, ORDER BY, LIMIT, LIKE (или LOWER(col) LIKE '%...%'), CASE WHEN... "
                "Запрос автоматически изолирован внутри данных текущего отчета."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL SELECT запрос к таблице deals (например: SELECT manager, COUNT(*) as deals_cnt, SUM(amount) as total_amt FROM deals WHERE manager != '' GROUP BY manager ORDER BY total_amt DESC LIMIT 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "render_chart",
            "description": (
                "Построить интерактивный график или диаграмму прямо в чате для наглядной визуализации данных. "
                "Вызывай этот инструмент ВСЕГДА, когда пользователь просит 'построй график', 'нарисуй диаграмму', "
                "'покажи распределение', 'воронку', 'график выручки по времени/датам/динамику', 'сравни менеджеров' или 'сделай чарт'. "
                "Для графиков выручки по времени или датам ОБЯЗАТЕЛЬНО используй chart_type='line' и dimension='date' (или 'month'). "
                "Инструмент возвращает рассчитанные структурированные данные, а интерфейс чата мгновенно рендерит красивый интерактивный график."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {
                        "type": "string",
                        "enum": ["line", "bar", "donut", "funnel"],
                        "description": "Тип графика: 'line' (линейный тренд / динамика по времени/датам), 'bar' (столбчатая диаграмма), 'donut' (круговая диаграмма долей), 'funnel' (воронка продаж)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Понятный заголовок графика на русском языке (например, 'Динамика выручки по датам', 'Выручка по менеджерам', 'Воронка сделок по стадиям', 'Топ-5 ключевых клиентов')"
                    },
                    "dimension": {
                        "type": "string",
                        "enum": ["date", "month", "manager", "status", "client", "source", "custom"],
                        "description": "По какому параметру группировать: 'date' (динамика по датам/дням), 'month' (динамика по месяцам), 'manager' (по менеджерам), 'status' (по этапам/статусам), 'client' (по клиентам), 'source' (по источникам) или 'custom' (если передаешь массив data вручную)"
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["amount", "count", "avg_check"],
                        "description": "Какую метрику считать: 'amount' (общая сумма в рублях), 'count' (количество сделок), 'avg_check' (средний чек). По умолчанию 'amount'."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное число элементов/столбцов (по умолчанию 6, максимум 12)"
                    },
                    "data": {
                        "type": "array",
                        "description": "Опциональный массив произвольных точек данных для графика (если dimension='custom' или нужно отобразить сравнение план/факт, выигранные vs потерянные и т.д.)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "Подпись элемента"},
                                "value": {"type": "number", "description": "Числовое значение"},
                                "color": {"type": "string", "description": "HEX цвет (опционально)"}
                            },
                            "required": ["label", "value"]
                        }
                    }
                },
                "required": ["chart_type", "title"]
            }
        }
    }
]


def _run_sql_query(query: str, snapshot_id: str) -> str:
    """
    Executes a read-only SQL SELECT query against the 'deals' table scoped to the given snapshot.
    """
    if not snapshot_id:
        return json.dumps({"error": "snapshot_id не указан"}, ensure_ascii=False)

    if not query or not isinstance(query, str):
        return json.dumps({"error": "Запрос query пустой или некорректный"}, ensure_ascii=False)

    # Clean markdown fences and whitespace
    clean_query = query.strip()
    if clean_query.startswith("```"):
        clean_query = re.sub(r"^```(?:sql)?\s*", "", clean_query, flags=re.IGNORECASE)
        clean_query = re.sub(r"\s*```$", "", clean_query)
    clean_query = clean_query.strip().rstrip("; \t\r\n")

    # Guard against multi-statement execution
    if ";" in clean_query:
        return json.dumps({
            "error": "Точка с запятой ';' не разрешена. Разрешен только один SELECT-запрос.",
            "query": query
        }, ensure_ascii=False)

    # Guard against DDL/DML mutations
    forbidden_pattern = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|EXEC|EXECUTE|TRUNCATE|REPLACE|GRANT|REVOKE|VACUUM)\b",
        re.IGNORECASE
    )
    if forbidden_pattern.search(clean_query):
        return json.dumps({
            "error": "Запросы на изменение данных запрещены. Разрешены только SELECT-запросы.",
            "query": query
        }, ensure_ascii=False)

    # Must start with SELECT or WITH
    if not re.match(r"^\s*(SELECT|WITH)\b", clean_query, re.IGNORECASE):
        return json.dumps({
            "error": "Запрос должен начинаться с ключевого слова SELECT или WITH.",
            "query": query
        }, ensure_ascii=False)

    s_id = str(snapshot_id)
    clean_id = s_id.replace('-', '')

    cte_deals = (
        "WITH deals AS ("
        "SELECT deal_id, client, contact, manager, amount, list_price, discount_pct, "
        "status_raw, status, created_at, first_contact_at, status_changed_at, "
        "last_activity_at, closed_at, source "
        "FROM engine_deal "
        "WHERE snapshot_id = %s OR snapshot_id = %s"
        ")"
    )

    if re.match(r"^\s*WITH\b", clean_query, re.IGNORECASE):
        stripped_user_cte = re.sub(r"^\s*WITH\s+", "", clean_query, flags=re.IGNORECASE)
        full_sql = f"{cte_deals}, {stripped_user_cte}"
    else:
        full_sql = f"{cte_deals} {clean_query}"

    try:
        with connection.cursor() as cur:
            cur.execute(full_sql, [s_id, clean_id])
            cols = [col[0] for col in cur.description] if cur.description else []
            raw_rows = cur.fetchmany(51)
            truncated = len(raw_rows) > 50
            display_rows = raw_rows[:50]

            def serialize_val(v):
                if isinstance(v, Decimal):
                    return float(v) if v % 1 else int(v)
                if hasattr(v, 'isoformat'):
                    return v.isoformat()
                return v

            dict_rows = [
                {cols[i]: serialize_val(row[i]) for i in range(len(cols))}
                for row in display_rows
            ]

            return json.dumps({
                "query": clean_query,
                "columns": cols,
                "rows": dict_rows,
                "row_count": len(dict_rows),
                "truncated": truncated
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"Ошибка выполнения SQL: {str(e)}",
            "query": clean_query
        }, ensure_ascii=False)


def execute_tool_call(tool_name: str, arguments: dict, snapshot_id: str) -> str:
    """
    Executes tool query directly against the SQLite / Postgres database for the given snapshot.
    Returns JSON string with factual data.
    """
    if not snapshot_id:
        return json.dumps({"error": "snapshot_id не указан"})

    if tool_name == "execute_sql_query":
        return _run_sql_query(arguments.get("query", ""), snapshot_id)

    qs = Deal.objects.filter(snapshot_id=snapshot_id)

    if tool_name == "search_deals":
        status = arguments.get("status")
        client = arguments.get("client")
        manager = arguments.get("manager")
        min_amount = arguments.get("min_amount")
        order_by = arguments.get("order_by", "amount_desc")
        limit = min(int(arguments.get("limit", 5)), 15)

        if status:
            qs = qs.filter(status=status)
        if client:
            qs = qs.filter(client__icontains=client)
        if manager:
            qs = qs.filter(manager__icontains=manager)
        if min_amount is not None:
            qs = qs.filter(amount__gte=Decimal(str(min_amount)))

        if order_by == "amount_desc":
            qs = qs.order_by("-amount")
        elif order_by == "amount_asc":
            qs = qs.order_by("amount")
        elif order_by == "created_desc":
            qs = qs.order_by("-created_at")

        results = []
        for d in qs[:limit]:
            results.append({
                "deal_id": d.deal_id,
                "client": d.client or "Без названия",
                "amount": float(d.amount),
                "status": d.status,
                "manager": d.manager or "Не назначен",
                "contact": d.contact or "—",
                "created_at": d.created_at.strftime("%Y-%m-%d") if d.created_at else None
            })

        return json.dumps({
            "total_found": qs.count(),
            "deals": results
        }, ensure_ascii=False)

    elif tool_name == "get_manager_stats":
        stats = qs.exclude(manager="").values("manager").annotate(
            total_deals=Count("id"),
            total_amount=Sum("amount"),
            won_deals=Count("id", filter=Q(status="won")),
            lost_deals=Count("id", filter=Q(status="lost")),
            stagnant_deals=Count("id", filter=Q(status__in=["new", "in_progress", "proposal", "negotiation", "other"])),
            avg_check=Avg("amount")
        ).order_by("-total_amount")

        results = []
        for s in stats[:15]:
            results.append({
                "manager": s["manager"],
                "total_deals": s["total_deals"],
                "total_amount": float(s["total_amount"] or 0),
                "won_deals": s["won_deals"],
                "lost_deals": s["lost_deals"],
                "stagnant_deals": s["stagnant_deals"],
                "avg_check": round(float(s["avg_check"] or 0), 2)
            })

        return json.dumps({"managers": results}, ensure_ascii=False)

    elif tool_name == "get_top_clients":
        limit = min(int(arguments.get("limit", 5)), 10)
        clients = qs.exclude(client="").values("client").annotate(
            total_amount=Sum("amount"),
            deals_count=Count("id")
        ).order_by("-total_amount")[:limit]

        results = []
        for c in clients:
            results.append({
                "client": c["client"],
                "total_amount": float(c["total_amount"] or 0),
                "deals_count": c["deals_count"]
            })

        return json.dumps({"top_clients": results}, ensure_ascii=False)

    elif tool_name == "render_chart":
        chart_type = arguments.get("chart_type", "bar")
        if chart_type == "pie":
            chart_type = "donut"
        if chart_type not in ("bar", "donut", "funnel", "line"):
            chart_type = "bar"

        title = arguments.get("title", "Аналитический график")
        dimension = arguments.get("dimension")
        metric = arguments.get("metric", "amount")
        limit = min(max(int(arguments.get("limit", 6)), 2), 15)
        custom_data = arguments.get("data")

        # Color palette
        palette = [
            "#3B82F6",  # Blue
            "#10B981",  # Emerald
            "#8B5CF6",  # Purple
            "#F59E0B",  # Amber
            "#06B6D4",  # Cyan
            "#EC4899",  # Pink
            "#F97316",  # Orange
            "#6366F1",  # Indigo
            "#14B8A6",  # Teal
            "#E11D48",  # Rose
        ]

        status_meta = {
            "new": {"label": "Новые", "color": "#06B6D4"},
            "in_progress": {"label": "В работе", "color": "#F59E0B"},
            "proposal": {"label": "КП / Предложение", "color": "#3B82F6"},
            "negotiation": {"label": "Переговоры", "color": "#8B5CF6"},
            "won": {"label": "Выиграны (Успешно)", "color": "#10B981"},
            "lost": {"label": "Проиграны (Отказ)", "color": "#EF4444"},
            "other": {"label": "Прочие", "color": "#94A3B8"},
        }

        # Auto-detect dimension if missing or invalid
        time_keywords = ["врем", "дат", "месяц", "динамик", "период", "день", "дням", "тренд", "хронолог"]
        if not dimension or dimension not in ("date", "month", "manager", "status", "client", "source", "custom"):
            if chart_type == "line" or any(w in title.lower() for w in time_keywords):
                dimension = "date"
            elif chart_type == "funnel":
                dimension = "status"
            elif any(w in title.lower() for w in ["статус", "этап", "стади", "воронк"]):
                dimension = "status"
            elif any(w in title.lower() for w in ["клиент", "заказчик", "покупател"]):
                dimension = "client"
            elif any(w in title.lower() for w in ["источник", "канал"]):
                dimension = "source"
            else:
                dimension = "manager"

        if dimension in ("date", "month", "time") and chart_type == "bar":
            chart_type = "line"

        items = []
        metric_label = "Выручка" if metric == "amount" else ("Количество сделок" if metric == "count" else "Средний чек")
        unit = "₽" if metric in ("amount", "avg_check") else "шт."

        def fmt_val(val: float, is_rub: bool) -> str:
            if is_rub:
                return f"{int(round(val)):,}".replace(",", " ") + " ₽"
            return f"{int(round(val)):,}".replace(",", " ") + " шт."

        if custom_data and isinstance(custom_data, list) and len(custom_data) > 0:
            for idx, d in enumerate(custom_data):
                val = float(d.get("value", 0))
                lbl = str(d.get("label", f"Пункт {idx+1}"))
                clr = d.get("color") or palette[idx % len(palette)]
                items.append({
                    "label": lbl,
                    "value": val,
                    "formatted_value": fmt_val(val, metric in ("amount", "avg_check")),
                    "color": clr,
                    "hint": d.get("hint", "")
                })

        elif dimension == "status" or chart_type == "funnel":
            has_canonical = qs.exclude(status="other").exists()
            use_raw = not has_canonical and qs.exclude(status_raw="").exists()

            if use_raw:
                raw_stats = list(qs.exclude(status_raw="").values("status_raw").annotate(
                    total_amount=Sum("amount"),
                    deals_count=Count("id"),
                    avg_check=Avg("amount")
                ))

                def stage_order(lbl):
                    l = lbl.lower()
                    if any(w in l for w in ["нов", "вход", "лид"]):
                        return 1
                    if any(w in l for w in ["работ"]):
                        return 2
                    if any(w in l for w in ["кп", "предложен", "переговор"]):
                        return 3
                    if any(w in l for w in ["застря", "дум", "пауз"]):
                        return 4
                    if any(w in l for w in ["успеш", "выигр", "оплач", "завершен"]):
                        return 5
                    if any(w in l for w in ["слив", "отказ", "проигр", "отмен"]):
                        return 6
                    return 7

                if chart_type == "funnel":
                    raw_stats.sort(key=lambda r: stage_order(r["status_raw"]))
                else:
                    raw_stats.sort(key=lambda r: float(r["total_amount"] or 0) if metric == "amount" else int(r["deals_count"] or 0), reverse=True)

                for idx, r in enumerate(raw_stats):
                    lbl = r["status_raw"]
                    amt = float(r.get("total_amount") or 0)
                    cnt = int(r.get("deals_count") or 0)
                    avg = float(r.get("avg_check") or 0)
                    val = amt if metric == "amount" else (cnt if metric == "count" else avg)

                    clr = palette[idx % len(palette)]
                    lbl_lower = lbl.lower()
                    if any(w in lbl_lower for w in ["успеш", "выигр", "оплач", "завершен"]):
                        clr = "#10B981"
                    elif any(w in lbl_lower for w in ["слив", "отказ", "проигр", "отмен"]):
                        clr = "#EF4444"
                    elif any(w in lbl_lower for w in ["переговор", "кп", "предложен"]):
                        clr = "#8B5CF6"
                    elif any(w in lbl_lower for w in ["застря", "дум", "пауз"]):
                        clr = "#F59E0B"
                    elif any(w in lbl_lower for w in ["нов", "лид", "вход"]):
                        clr = "#06B6D4"

                    items.append({
                        "label": lbl,
                        "value": val,
                        "amount": amt,
                        "count": cnt,
                        "avg_check": avg,
                        "formatted_value": fmt_val(val, metric in ("amount", "avg_check")),
                        "color": clr,
                        "hint": f"{cnt} сделок на {fmt_val(amt, True)}"
                    })
            else:
                status_stats = list(qs.values("status").annotate(
                    total_amount=Sum("amount"),
                    deals_count=Count("id"),
                    avg_check=Avg("amount")
                ))
                stat_by_status = {s["status"]: s for s in status_stats}

                if chart_type == "funnel":
                    funnel_stages = ["new", "in_progress", "proposal", "negotiation", "won"]
                    for st_key in funnel_stages:
                        row = stat_by_status.get(st_key, {"total_amount": 0, "deals_count": 0, "avg_check": 0})
                        amt = float(row.get("total_amount") or 0)
                        cnt = int(row.get("deals_count") or 0)
                        avg = float(row.get("avg_check") or 0)
                        val = amt if metric == "amount" else cnt
                        meta = status_meta.get(st_key, {"label": st_key, "color": "#94A3B8"})
                        items.append({
                            "label": meta["label"],
                            "stage_key": st_key,
                            "value": val,
                            "amount": amt,
                            "count": cnt,
                            "avg_check": avg,
                            "formatted_value": fmt_val(val, metric == "amount"),
                            "color": meta["color"],
                            "hint": f"{cnt} сделок на сумму {fmt_val(amt, True)}"
                        })
                    if "lost" in stat_by_status:
                        lost_row = stat_by_status["lost"]
                        lost_amt = float(lost_row.get("total_amount") or 0)
                        lost_cnt = int(lost_row.get("deals_count") or 0)
                        items.append({
                            "label": status_meta["lost"]["label"],
                            "stage_key": "lost",
                            "value": lost_amt if metric == "amount" else lost_cnt,
                            "amount": lost_amt,
                            "count": lost_cnt,
                            "avg_check": float(lost_row.get("avg_check") or 0),
                            "formatted_value": fmt_val(lost_amt if metric == "amount" else lost_cnt, metric == "amount"),
                            "color": status_meta["lost"]["color"],
                            "hint": f"Потеряно: {lost_cnt} сделок на {fmt_val(lost_amt, True)}"
                        })
                else:
                    for idx, (st_key, meta) in enumerate(status_meta.items()):
                        if st_key in stat_by_status:
                            row = stat_by_status[st_key]
                            amt = float(row.get("total_amount") or 0)
                            cnt = int(row.get("deals_count") or 0)
                            val = amt if metric == "amount" else (cnt if metric == "count" else float(row.get("avg_check") or 0))
                            items.append({
                                "label": meta["label"],
                                "value": val,
                                "amount": amt,
                                "count": cnt,
                                "formatted_value": fmt_val(val, metric in ("amount", "avg_check")),
                                "color": meta["color"],
                                "hint": f"{cnt} сделок, средний чек {fmt_val(row.get('avg_check') or 0, True)}"
                            })
                    items.sort(key=lambda x: x["value"], reverse=True)

        elif dimension == "manager":
            mgr_qs = qs.exclude(manager="").values("manager").annotate(
                total_amount=Sum("amount"),
                deals_count=Count("id"),
                avg_check=Avg("amount"),
                won_amount=Sum("amount", filter=Q(status="won")),
                won_count=Count("id", filter=Q(status="won"))
            )
            if metric == "count":
                mgr_qs = mgr_qs.order_by("-deals_count")
            elif metric == "avg_check":
                mgr_qs = mgr_qs.order_by("-avg_check")
            else:
                mgr_qs = mgr_qs.order_by("-total_amount")

            for idx, m in enumerate(mgr_qs[:limit]):
                amt = float(m["total_amount"] or 0)
                cnt = int(m["deals_count"] or 0)
                avg = float(m["avg_check"] or 0)
                won_cnt = int(m["won_count"] or 0)
                val = amt if metric == "amount" else (cnt if metric == "count" else avg)
                items.append({
                    "label": m["manager"],
                    "value": val,
                    "amount": amt,
                    "count": cnt,
                    "won_count": won_cnt,
                    "formatted_value": fmt_val(val, metric in ("amount", "avg_check")),
                    "color": palette[idx % len(palette)],
                    "hint": f"{cnt} сделок ({won_cnt} выиграно), ср. чек {fmt_val(avg, True)}"
                })

        elif dimension == "client":
            client_qs = qs.exclude(client="").values("client").annotate(
                total_amount=Sum("amount"),
                deals_count=Count("id"),
                avg_check=Avg("amount")
            ).order_by("-total_amount" if metric != "count" else "-deals_count")

            for idx, c in enumerate(client_qs[:limit]):
                amt = float(c["total_amount"] or 0)
                cnt = int(c["deals_count"] or 0)
                val = amt if metric == "amount" else (cnt if metric == "count" else float(c["avg_check"] or 0))
                items.append({
                    "label": c["client"],
                    "value": val,
                    "amount": amt,
                    "count": cnt,
                    "formatted_value": fmt_val(val, metric in ("amount", "avg_check")),
                    "color": palette[idx % len(palette)],
                    "hint": f"{cnt} сделок на {fmt_val(amt, True)}"
                })

        elif dimension == "source":
            src_qs = qs.exclude(source="").values("source").annotate(
                total_amount=Sum("amount"),
                deals_count=Count("id"),
                avg_check=Avg("amount")
            ).order_by("-total_amount" if metric != "count" else "-deals_count")

            for idx, s in enumerate(src_qs[:limit]):
                amt = float(s["total_amount"] or 0)
                cnt = int(s["deals_count"] or 0)
                val = amt if metric == "amount" else (cnt if metric == "count" else float(s["avg_check"] or 0))
                items.append({
                    "label": s["source"],
                    "value": val,
                    "amount": amt,
                    "count": cnt,
                    "formatted_value": fmt_val(val, metric in ("amount", "avg_check")),
                    "color": palette[idx % len(palette)],
                    "hint": f"{cnt} сделок на сумму {fmt_val(amt, True)}"
                })

        elif dimension in ("date", "month", "time"):
            deals_with_date = qs.exclude(created_at=None).order_by("created_at")
            if deals_with_date.exists():
                ru_months = {
                    "01": "Янв", "02": "Фев", "03": "Мар", "04": "Апр",
                    "05": "Май", "06": "Июн", "07": "Июл", "08": "Авг",
                    "09": "Сен", "10": "Окт", "11": "Ноя", "12": "Дек"
                }
                from collections import defaultdict
                date_groups = defaultdict(lambda: {"amount": 0.0, "count": 0, "label": ""})

                dates = [d.created_at.date() for d in deals_with_date if d.created_at]
                span_days = (max(dates) - min(dates)).days if dates else 0

                group_by_month = (dimension == "month") or (span_days > 75 and dimension != "date")

                for d in deals_with_date:
                    if not d.created_at:
                        continue
                    dt = d.created_at
                    m_code = dt.strftime("%m")
                    m_name = ru_months.get(m_code, m_code)
                    if group_by_month:
                        key = dt.strftime("%Y-%m")
                        lbl = f"{m_name} {dt.strftime('%Y')}"
                    else:
                        key = dt.strftime("%Y-%m-%d")
                        day_str = dt.strftime("%d")
                        lbl = f"{day_str} {m_name}"

                    date_groups[key]["label"] = lbl
                    date_groups[key]["amount"] += float(d.amount or 0)
                    date_groups[key]["count"] += 1

                sorted_keys = sorted(date_groups.keys())
                for idx, k in enumerate(sorted_keys):
                    grp = date_groups[k]
                    amt = grp["amount"]
                    cnt = grp["count"]
                    val = amt if metric == "amount" else cnt
                    items.append({
                        "label": grp.get("label", k),
                        "date_key": k,
                        "value": val,
                        "amount": amt,
                        "count": cnt,
                        "formatted_value": fmt_val(val, metric == "amount"),
                        "color": "#3B82F6",
                        "hint": f"{cnt} сделок на {fmt_val(amt, True)}"
                    })

        # Calculate totals & percentages
        total_val = sum(it["value"] for it in items)
        for it in items:
            pct = round((it["value"] / total_val * 100), 1) if total_val > 0 else 0
            it["percentage"] = pct

        formatted_total = fmt_val(total_val, metric in ("amount", "avg_check"))
        if dimension in ("date", "month", "time") and items:
            peak = max(items, key=lambda x: x["value"])
            leader_info = f"Пик выручки: {peak['label']} ({peak['formatted_value']})"
        elif items:
            leader_info = f"Лидер: {items[0]['label']} ({items[0]['formatted_value']}, {items[0]['percentage']}%)"
        else:
            leader_info = "Нет данных"

        summary = (
            f"Построен график '{title}'. "
            f"Всего: {formatted_total}. "
            f"Показано позиций: {len(items)}. "
            f"{leader_info}."
        )

        return json.dumps({
            "chart_type": chart_type,
            "title": title,
            "dimension": dimension,
            "metric": metric,
            "metric_label": metric_label,
            "unit": unit,
            "total": total_val,
            "formatted_total": formatted_total,
            "items": items,
            "summary": summary
        }, ensure_ascii=False)

    return json.dumps({"error": f"Неизвестная функция: {tool_name}"})
