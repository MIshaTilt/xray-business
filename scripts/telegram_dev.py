#!/usr/bin/env python3
"""Локальный Telegram-бот: меню Mini App и ответ на /start."""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / 'xray-be' / '.env'


def load_env() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        raw = line.strip()
        if not raw or raw.startswith('#') or '=' not in raw:
            continue
        key, value = raw.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api(token: str, method: str, payload: dict | None = None) -> dict:
    url = f'https://api.telegram.org/bot{token}/{method}'
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'} if data else {},
        method='POST' if data else 'GET',
    )
    try:
        with urllib.request.urlopen(request, timeout=90, context=SSL_CONTEXT) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = error.read().decode()
        raise SystemExit(f'Telegram {method}: {error.code} {detail}') from error
    if not body.get('ok'):
        raise SystemExit(f'Telegram {method}: {body}')
    return body['result']


def bind_menu(token: str, app_url: str) -> None:
    api(token, 'deleteWebhook', {'drop_pending_updates': False})
    api(
        token,
        'setChatMenuButton',
        {
            'menu_button': {
                'type': 'web_app',
                'text': 'X-Ray',
                'web_app': {'url': app_url},
            }
        },
    )
    api(
        token,
        'setMyCommands',
        {'commands': [{'command': 'start', 'description': 'Открыть X-Ray'}]},
    )


def start_keyboard(app_url: str) -> dict:
    return {
        'inline_keyboard': [[{'text': 'Открыть X-Ray', 'web_app': {'url': app_url}}]]
    }


def handle_start(token: str, app_url: str) -> None:
    offset = 0
    print('Жду /start в Telegram у @xray_business_bot', flush=True)
    while True:
        try:
            updates = api(token, 'getUpdates', {'timeout': 40, 'offset': offset, 'allowed_updates': ['message']})
        except (TimeoutError, urllib.error.URLError) as error:
            print(f'сеть: {error.__class__.__name__}, ещё раз', flush=True)
            time.sleep(2)
            continue
        for update in updates:
            offset = int(update['update_id']) + 1
            message = update.get('message') or {}
            text = (message.get('text') or '').strip()
            chat_id = message.get('chat', {}).get('id')
            if not chat_id or not text.startswith('/start'):
                continue
            api(
                token,
                'sendMessage',
                {
                    'chat_id': chat_id,
                    'text': 'X-Ray на локальной машине. Нажмите кнопку — откроется мини-приложение.',
                    'reply_markup': start_keyboard(app_url),
                },
            )
            print(f'Открыл кнопку для чата {chat_id}', flush=True)
        time.sleep(0.2)


def main() -> None:
    load_env()
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    app_url = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get('TELEGRAM_WEBAPP_URL', '')).strip().rstrip('/')
    if not token:
        raise SystemExit('Нет TELEGRAM_BOT_TOKEN в xray-be/.env')
    if not app_url.startswith('https://'):
        raise SystemExit('Нужен HTTPS URL мини-приложения, например из cloudflared')
    me = api(token, 'getMe')
    bind_menu(token, app_url)
    print(f'Бот @{me.get("username")} → {app_url}', flush=True)
    handle_start(token, app_url)


if __name__ == '__main__':
    main()
