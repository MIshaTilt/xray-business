import json
from decimal import Decimal
from django.db.models import Sum, Count, Avg
from engine.models import Deal, Snapshot


AI_TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_deals",
            "description": "Поиск сделок в отчете по фильтрам: статус, имя клиента, менеджер или минимальная сумма.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Статус сделки: new, in_progress, proposal, negotiation, won, lost, other"
                    },
                    "client": {
                        "type": "string",
                        "description": "Фрагмент имени клиента или компании"
                    },
                    "manager": {
                        "type": "string",
                        "description": "Имя менеджера"
                    },
                    "min_amount": {
                        "type": "number",
                        "description": "Минимальная сумма сделки в рублях"
                    },
                    "order_by": {
                        "type": "string",
                        "enum": ["amount_desc", "amount_asc", "created_desc"],
                        "description": "Сортировка: amount_desc (самые крупные), amount_asc (мелкие), created_desc (свежие)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Количество возвращаемых сделок (по умолчанию 5, максимум 15)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_manager_stats",
            "description": "Получить статистику по менеджерам: сколько сделок закрыли, сколько зависло, средний чек и сумма потерь.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_clients",
            "description": "Получить список ключевых клиентов с наибольшей суммой покупок/сделок.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Количество клиентов (по умолчанию 5)"
                    }
                }
            }
        }
    }
]


def execute_tool_call(tool_name: str, arguments: dict, snapshot_id: str) -> str:
    """
    Executes tool query directly against the SQLite / Postgres database for the given snapshot.
    Returns JSON string with factual data.
    """
    if not snapshot_id:
        return json.dumps({"error": "snapshot_id не указан"})

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
            won_deals=Count("id", filter=Deal.objects.filter(status="won")),
            avg_check=Avg("amount")
        ).order_by("-total_amount")

        results = []
        for s in stats[:10]:
            results.append({
                "manager": s["manager"],
                "total_deals": s["total_deals"],
                "total_amount": float(s["total_amount"] or 0),
                "won_deals": s["won_deals"],
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

    return json.dumps({"error": f"Неизвестная функция: {tool_name}"})
