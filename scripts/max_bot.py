#!/usr/bin/env python3
"""
Локальный скрипт для запуска чат-бота платформы MAX:
- Обработка события 'bot_started' (когда пользователь нажал "Старт" в мессенджере MAX)
- Обработка команды /start
- Обработка произвольных сообщений с перенаправлением в Mini App
- Отправка инлайн-кнопок для открытия Mini App (open_app + link)
"""

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

# Поддержка UTF-8 вывода в консоли Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Создаем SSL-контекст с отключением строгой валидации для работы с платформой MAX
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
    SSL_CONTEXT.check_hostname = False
    SSL_CONTEXT.verify_mode = ssl.CERT_NONE
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()
    SSL_CONTEXT.check_hostname = False
    SSL_CONTEXT.verify_mode = ssl.CERT_NONE

ROOT = Path(__file__).resolve().parents[1]
ENV_PATHS = [
    ROOT / '.env',
    ROOT / 'xray-be' / '.env',
]

BASE_URL = 'https://platform-api2.max.ru'


def load_env() -> None:
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding='utf-8').splitlines():
            raw = line.strip()
            if not raw or raw.startswith('#') or '=' not in raw:
                continue
            key, value = raw.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api(token: str, path: str, method: str = 'GET', payload: dict | None = None, query: dict | None = None) -> dict:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    if query:
        url += '?' + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {
        'Authorization': token,
        'Accept': 'application/json',
    }
    if data:
        headers['Content-Type'] = 'application/json; charset=utf-8'

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60, context=SSL_CONTEXT) as response:
            body = response.read().decode('utf-8')
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        print(f"[API ERROR] {method} {url} -> {error.code}: {detail}", file=sys.stderr)
        raise
    except Exception as error:
        print(f"[NET ERROR] {method} {url} -> {error}", file=sys.stderr)
        raise


def get_welcome_text(user_name: str = '') -> str:
    greeting = f"👋 Привет, {user_name}!" if user_name else "👋 Привет!"
    return (
        f"{greeting}\n\n"
        "Добро пожаловать в X-Ray Business — интеллектуальную систему экспресс-диагностики и аудита B2B-продаж для платформы MAX.\n\n"
        "🔍 Что умеет сервис:\n"
        "• ⚡ Мгновенный анализ воронки продаж и конверсий по этапам\n"
        "• 🛑 Поиск узких мест, «зависших» сделок и аномалий\n"
        "• 💰 Расчет скрытых потерь выручки (Lost Revenue)\n"
        "• 🤖 AI-диагноз и персонализированные рекомендации по росту продаж\n"
        "• 📥 Интеграция с CRM (AmoCRM, Bitrix24, МойСклад) и загрузка Excel/CSV\n\n"
        "🚀 Чтобы начать работу, нажмите на кнопку ниже и перейдите в мини-приложение\n\n"
        "⚠️ Если мини-приложение бесконечно загружается, откройте веб-версию (без аутентификации через MAX история удаляется через 24 часа)"
    )


def get_welcome_keyboard(bot_username: str, app_url: str) -> dict:
    return {
        'type': 'inline_keyboard',
        'payload': {
            'buttons': [
                [
                    {
                        'type': 'open_app',
                        'text': '🚀 Открыть мини-приложение',
                        'web_app': bot_username,
                    }
                ],
                [
                    {
                        'type': 'link',
                        'text': '🌐 Веб-версия',
                        'url': app_url,
                    },
                ],
            ]
        },
    }


def send_welcome_message(token: str, chat_id: int, user_name: str, bot_username: str, app_url: str) -> None:
    text = get_welcome_text(user_name)
    keyboard = get_welcome_keyboard(bot_username, app_url)
    payload = {
        'text': text,
        'attachments': [keyboard],
    }
    api(token, 'messages', method='POST', payload=payload, query={'chat_id': chat_id})


def register_commands(token: str) -> None:
    commands = [
        {'name': 'start', 'description': 'Открыть мини-приложение X-Ray'},
        {'name': 'help', 'description': 'Справка о возможностях сервиса'},
    ]
    try:
        api(token, 'me/commands', method='PATCH', payload={'commands': commands})
        print('✅ Команды меню /start и /help зарегистрированы в MAX')
    except Exception as e:
        print(f"⚠️ Предупреждение: не удалось зарегистрировать команды: {e}")


def poll_updates(token: str, bot_username: str, app_url: str) -> None:
    marker = None
    print(f"🔄 Запущен Long Polling бота @{bot_username}. Ожидание событий (Ctrl+C для остановки)...", flush=True)

    while True:
        try:
            params = {'timeout': 25}
            if marker is not None:
                params['marker'] = marker

            response = api(token, 'updates', method='GET', query=params)
            marker = response.get('marker', marker)
            updates = response.get('updates', [])

            for update in updates:
                update_type = update.get('update_type')
                chat_id = update.get('chat_id')
                user = update.get('user') or {}
                user_name = user.get('first_name') or user.get('name') or ''

                if update_type == 'bot_started':
                    print(f"📥 [bot_started] Пользователь {user.get('user_id')} ({user_name}) нажал Старт в чате {chat_id}")
                    if chat_id:
                        send_welcome_message(token, chat_id, user_name, bot_username, app_url)

                elif update_type == 'message_created':
                    message = update.get('message') or {}
                    body = message.get('body') or {}
                    text = (body.get('text') or '').strip()
                    msg_chat_id = message.get('recipient', {}).get('chat_id') or chat_id
                    sender = message.get('sender') or user
                    sender_name = sender.get('first_name') or sender.get('name') or ''

                    if sender.get('is_bot'):
                        continue

                    print(f"📥 [message_created] Сообщение от {sender.get('user_id')} ({sender_name}): {text!r}")
                    if msg_chat_id:
                        send_welcome_message(token, msg_chat_id, sender_name, bot_username, app_url)

                elif update_type == 'bot_added':
                    print(f"📥 [bot_added] Бот добавлен в чат {chat_id}")
                    if chat_id:
                        send_welcome_message(token, chat_id, '', bot_username, app_url)

        except KeyboardInterrupt:
            print("\n🛑 Остановка бота пользователем.")
            break
        except Exception as error:
            print(f"⚠️ Ошибка опроса: {error}. Повтор через 3 секунды...", flush=True)
            time.sleep(3)


def main() -> None:
    load_env()
    token = os.environ.get('MAX_BOT_TOKEN', 'f9LHodD0cOJBhxITwPCdJEVxZ7O2jzj6oDVpd_ODgTheRYaSUX8ErQbLWGisLOw5-U9xswXPu-vQfO0yAcCT').strip()
    bot_username = os.environ.get('MAX_BOT_USERNAME', 't720_hakaton_max_bot').strip()
    app_url = os.environ.get('MAX_APP_URL', 'https://xray-business-bot.online').strip().rstrip('/')

    if not token:
        raise SystemExit('Ошибка: MAX_BOT_TOKEN не задан в .env файле')

    print("====================================================")
    print("🚀 Запуск MAX Bot (Python Runner)...")
    print("====================================================")

    try:
        me = api(token, 'me')
        print(f"✅ Авторизован бот: {me.get('name')} (@{me.get('username')})")
        if me.get('username'):
            bot_username = me.get('username')
    except Exception as e:
        print(f"❌ Ошибка проверки токена: {e}")
        return

    register_commands(token)
    poll_updates(token, bot_username, app_url)


if __name__ == '__main__':
    main()
