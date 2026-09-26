"""Чтение сделок amoCRM и перевод их в строки таблицы X-Ray."""

from datetime import datetime
from zoneinfo import ZoneInfo

import requests

MSK = ZoneInfo("Europe/Moscow")


class AmoError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def account_host(account: str) -> str:
    host = (account or "").strip().lower()
    host = host.removeprefix("https://").removeprefix("http://").strip("/")
    if "/" in host:
        host = host.split("/")[0]
    if not host:
        raise AmoError("Укажите поддомен amoCRM, например demo или demo.amocrm.ru.")
    if not host.endswith(".amocrm.ru"):
        host = f"{host}.amocrm.ru"
    return host


def _get(host: str, token: str, path: str, params: dict | None = None) -> dict:
    try:
        response = requests.get(
            f"https://{host}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=40,
        )
    except requests.RequestException:
        raise AmoError("amoCRM долго не отвечает. Подождите минуту и нажмите «Забрать сделки» ещё раз.")
    if response.status_code in (401, 403):
        raise AmoError("amoCRM не приняла токен. Проверьте поддомен и долгосрочный токен.")
    if response.status_code >= 400:
        raise AmoError("amoCRM не ответила. Повторите загрузку позже.")
    if not response.content:
        return {}
    return response.json()


def _status_names(host: str, token: str) -> dict[int, str]:
    names: dict[int, str] = {142: "Успешно", 143: "Отказ"}
    data = _get(host, token, "/api/v4/leads/pipelines")
    for pipeline in data.get("_embedded", {}).get("pipelines", []):
        statuses = pipeline.get("_embedded", {}).get("statuses", [])
        regular = [item for item in statuses if item.get("id") not in (142, 143)]
        regular.sort(key=lambda item: item.get("sort") or 0)
        for index, item in enumerate(statuses):
            status_id = int(item["id"])
            if status_id in names:
                continue
            title = (item.get("name") or "").strip()
            if regular and int(regular[0]["id"]) == status_id:
                names[status_id] = "Новая"
            else:
                names[status_id] = title or "В работе"
            index
    return names


def _when(stamp) -> str:
    if not stamp:
        return ""
    moment = datetime.fromtimestamp(int(stamp), tz=MSK)
    return moment.strftime("%d.%m.%Y %H:%M")


def _client_name(lead: dict) -> str:
    embedded = lead.get("_embedded") or {}
    companies = embedded.get("companies") or []
    if companies and companies[0].get("name"):
        return str(companies[0]["name"])
    contacts = embedded.get("contacts") or []
    if contacts and contacts[0].get("name"):
        return str(contacts[0]["name"])
    return str(lead.get("name") or "")


def fetch_lead_rows(account: str, token: str, limit: int = 5000) -> tuple[str, list[dict]]:
    host = account_host(account)
    token = (token or "").strip()
    if not token:
        raise AmoError("Вставьте долгосрочный токен amoCRM.")
    _get(host, token, "/api/v4/account")
    statuses = _status_names(host, token)
    rows: list[dict] = []
    page = 1
    while len(rows) < limit:
        data = _get(host, token, "/api/v4/leads", {"limit": 250, "page": page, "with": "contacts"})
        leads = data.get("_embedded", {}).get("leads", [])
        if not leads:
            break
        for lead in leads:
            price = lead.get("price")
            if price is None or float(price) <= 0:
                continue
            status_id = int(lead.get("status_id") or 0)
            rows.append(
                {
                    "ID": str(lead.get("id") or ""),
                    "Клиент": _client_name(lead),
                    "Сумма": price,
                    "Статус": statuses.get(status_id, "В работе"),
                    "Дата создания": _when(lead.get("created_at")),
                    "Менеджер": "",
                }
            )
            if len(rows) >= limit:
                break
        if len(leads) < 250:
            break
        page += 1
    return host, rows
