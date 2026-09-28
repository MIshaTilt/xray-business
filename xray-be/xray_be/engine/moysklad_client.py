"""Чтение заказов МоегоСклада."""

from datetime import datetime

import requests

from engine.amo_client import AmoError


class MoySkladError(AmoError):
    pass


def _get(token: str, path: str, params: dict | None = None) -> dict:
    try:
        response = requests.get(
            f"https://api.moysklad.ru/api/remap/1.2{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"},
            timeout=40,
        )
    except requests.RequestException:
        raise MoySkladError("МойСклад долго не отвечает. Повторите позже.")
    if response.status_code in (401, 403):
        raise MoySkladError("МойСклад не принял токен. Выпустите Bearer-токен в настройках.")
    if response.status_code >= 400:
        raise MoySkladError("МойСклад не отдал заказы. Повторите позже.")
    return response.json() if response.content else {}


def _when(value) -> str:
    if not value:
        return ""
    try:
        moment = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
        return moment.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return str(value)[:16]


def fetch_order_rows(token: str, limit: int = 5000) -> tuple[str, list[dict]]:
    token = (token or "").strip()
    if not token:
        raise MoySkladError("Вставьте токен МоегоСклада.")
    employee = _get(token, "/context/employee")
    account = str(employee.get("name") or employee.get("uid") or "moysklad")
    rows: list[dict] = []
    offset = 0
    while len(rows) < limit:
        data = _get(token, "/entity/customerorder", {"limit": 100, "offset": offset, "expand": "agent,state"})
        batch = data.get("rows") or []
        if not batch:
            break
        for item in batch:
            try:
                amount = float(item.get("sum") or 0) / 100
            except (TypeError, ValueError):
                amount = 0
            if amount <= 0:
                continue
            agent = item.get("agent") or {}
            state = item.get("state") or {}
            rows.append(
                {
                    "ID": str(item.get("id") or ""),
                    "Клиент": str(agent.get("name") or item.get("name") or ""),
                    "Сумма": amount,
                    "Статус": str(state.get("name") or "В работе"),
                    "Дата создания": _when(item.get("moment")),
                    "Менеджер": "",
                }
            )
            if len(rows) >= limit:
                break
        if len(batch) < 100:
            break
        offset += 100
    return account, rows
