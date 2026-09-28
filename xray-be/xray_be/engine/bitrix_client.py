"""Чтение сделок Битрикс24 по входящему вебхуку."""

from datetime import datetime
from urllib.parse import urlparse

import requests

from engine.amo_client import AmoError


class BitrixError(AmoError):
    pass


def webhook_base(url: str) -> str:
    raw = (url or "").strip()
    if not raw.startswith("https://") or "/rest/" not in raw:
        raise BitrixError("Нужен URL входящего вебхука: https://имя.bitrix24.ru/rest/1/код/")
    return raw if raw.endswith("/") else raw + "/"


def _when(value) -> str:
    if not value:
        return ""
    text = str(value).replace("T", " ")[:16]
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return moment.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return text


def _status(stage: str) -> str:
    stage = stage or ""
    if stage.endswith(":WON") or stage == "WON":
        return "Успешно"
    if stage.endswith(":LOSE") or stage.endswith(":LOST") or stage == "LOSE":
        return "Отказ"
    if stage == "NEW" or stage.endswith(":NEW"):
        return "Новая"
    return stage or "В работе"


def fetch_deal_rows(webhook_url: str, limit: int = 5000) -> tuple[str, list[dict]]:
    base = webhook_base(webhook_url)
    account = urlparse(base).hostname or "bitrix24"
    rows: list[dict] = []
    start = 0
    while len(rows) < limit:
        try:
            response = requests.post(
                f"{base}crm.deal.list.json",
                json={
                    "select": ["ID", "TITLE", "OPPORTUNITY", "STAGE_ID", "DATE_CREATE", "DATE_MODIFY", "CLOSEDATE"],
                    "start": start,
                    "order": {"DATE_MODIFY": "ASC"},
                },
                timeout=40,
            )
        except requests.RequestException:
            raise BitrixError("Битрикс24 долго не отвечает. Повторите позже.")
        if response.status_code in (401, 403):
            raise BitrixError("Битрикс24 не принял вебхук. Создайте входящий вебхук с правом CRM.")
        data = response.json() if response.content else {}
        if response.status_code >= 400 or data.get("error"):
            raise BitrixError("Битрикс24 не отдал сделки. Проверьте URL вебхука.")
        batch = data.get("result") or []
        if not batch:
            break
        for item in batch:
            price = item.get("OPPORTUNITY")
            try:
                amount = float(price)
            except (TypeError, ValueError):
                amount = 0
            if amount <= 0:
                continue
            rows.append(
                {
                    "ID": str(item.get("ID") or ""),
                    "Клиент": str(item.get("TITLE") or ""),
                    "Сумма": price,
                    "Статус": _status(str(item.get("STAGE_ID") or "")),
                    "Дата создания": _when(item.get("DATE_CREATE")),
                    "Менеджер": "",
                }
            )
            if len(rows) >= limit:
                break
        if "next" not in data:
            break
        start = data["next"]
    return account, rows
