"""
Модуль для интеграции и взаимодействия с Bot API платформы MAX (https://dev.max.ru).
Поддерживает:
- Отправку сообщений с инлайн-клавиатурой (open_app + link)
- Обработку вебхуков от MAX
- Регистрацию команд бота (/start, /help)
- Получение информации о боте
"""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from django.conf import settings
from engine.models import MaxUser

logger = logging.getLogger(__name__)

# SSL контекст для обращения к API платформы MAX
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

BASE_URL = 'https://platform-api2.max.ru'


class MaxBotService:
    def __init__(self, token: str | None = None, username: str | None = None, app_url: str | None = None):
        self.token = token or getattr(settings, 'MAX_BOT_TOKEN', 'f9LHodD0cOJBhxITwPCdJEVxZ7O2jzj6oDVpd_ODgTheRYaSUX8ErQbLWGisLOw5-U9xswXPu-vQfO0yAcCT')
        self.username = username or getattr(settings, 'MAX_BOT_USERNAME', 'se14421867_bot')
        self.app_url = (app_url or getattr(settings, 'MAX_APP_URL', 'https://xray-business-bot.online')).rstrip('/')

    def call_api(
        self,
        endpoint: str,
        method: str = 'GET',
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Вызов эндпоинта MAX Bot API."""
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        if query:
            url += '?' + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})

        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers = {
            'Authorization': self.token,
            'Accept': 'application/json',
        }
        if data:
            headers['Content-Type'] = 'application/json; charset=utf-8'

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as response:
                content = response.read().decode('utf-8')
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as err:
            err_body = err.read().decode('utf-8', errors='replace')
            logger.error("[MAX API ERROR] %s %s -> %s: %s", method, url, err.code, err_body)
            raise
        except Exception as err:
            logger.error("[MAX NET ERROR] %s %s -> %s", method, url, err)
            raise

    def get_me(self) -> dict[str, Any]:
        """Информация о боте."""
        return self.call_api('me')

    def set_commands(self) -> dict[str, Any]:
        """Регистрация команд в меню мессенджера."""
        commands = [
            {'name': 'start', 'description': 'Открыть мини-приложение X-Ray'},
            {'name': 'help', 'description': 'Справка о возможностях сервиса'},
        ]
        return self.call_api('me/commands', method='PATCH', payload={'commands': commands})

    def get_welcome_text(self, user_name: str = '') -> str:
        """Текст приветственного сообщения для пользователя."""
        greeting = f"👋 Привет, {user_name}!" if user_name else "👋 Привет!"
        return (
            f"{greeting}\n\n"
            "Добро пожаловать в **X-Ray Business** — интеллектуальную систему экспресс-диагностики и аудита B2B-продаж для платформы MAX.\n\n"
            "🔍 **Что умеет сервис:**\n"
            "• ⚡ Мгновенный анализ воронки продаж и конверсий по этапам\n"
            "• 🛑 Поиск узких мест, «зависших» сделок и аномалий\n"
            "• 💰 Расчет скрытых потерь выручки (Lost Revenue)\n"
            "• 🤖 AI-диагноз и персонализированные рекомендации по росту продаж\n"
            "• 📥 Интеграция с CRM (AmoCRM, Bitrix24, МойСклад) и загрузка Excel/CSV\n\n"
            "🚀 **Чтобы начать работу, нажмите на кнопку ниже и перейдите в мини-приложение:**"
        )

    def get_welcome_keyboard(self) -> dict[str, Any]:
        """Формирование клавиатуры для открытия Mini App."""
        return {
            'type': 'inline_keyboard',
            'payload': {
                'buttons': [
                    [
                        {
                            'type': 'open_app',
                            'text': '🚀 Открыть мини-приложение',
                            'web_app': self.username,
                        }
                    ],
                    [
                        {
                            'type': 'link',
                            'text': '📱 Запустить в MAX',
                            'url': f"https://max.ru/{self.username}?startapp",
                        },
                        {
                            'type': 'link',
                            'text': '🌐 Веб-версия',
                            'url': self.app_url,
                        },
                    ],
                ]
            },
        }

    def send_welcome_message(self, chat_id: int, user_name: str = '') -> dict[str, Any]:
        """Отправляет приветственное сообщение с кнопками в указанный чат."""
        payload = {
            'text': self.get_welcome_text(user_name),
            'attachments': [self.get_welcome_keyboard()],
        }
        return self.call_api('messages', method='POST', payload=payload, query={'chat_id': chat_id})

    def handle_update(self, update: dict[str, Any]) -> bool:
        """
        Обработка входящего события от MAX (через Webhook или Polling).
        Возвращает True, если событие обработано.
        """
        update_type = update.get('update_type')
        chat_id = update.get('chat_id')
        user = update.get('user') or {}
        user_name = user.get('first_name') or user.get('name') or ''
        user_id = user.get('user_id')

        # Сохраняем или обновляем пользователя в базе данных
        if user_id and not user.get('is_bot'):
            try:
                MaxUser.objects.update_or_create(
                    max_user_id=user_id,
                    defaults={'first_name': user_name or 'Пользователь MAX'},
                )
            except Exception as e:
                logger.warning("Не удалось сохранить MaxUser %s: %s", user_id, e)

        # 1. Событие нажатия кнопки "Старт" в мессенджере MAX
        if update_type == 'bot_started':
            logger.info("Обработка bot_started от %s (%s) в чате %s", user_id, user_name, chat_id)
            if chat_id:
                self.send_welcome_message(chat_id, user_name)
            return True

        # 2. Новое входящее сообщение
        if update_type == 'message_created':
            message = update.get('message') or {}
            body = message.get('body') or {}
            text = (body.get('text') or '').strip()
            msg_chat_id = message.get('recipient', {}).get('chat_id') or chat_id
            sender = message.get('sender') or user
            sender_name = sender.get('first_name') or sender.get('name') or user_name

            if sender.get('is_bot'):
                return False

            logger.info("Входящее сообщение от %s (%s): %r", sender.get('user_id'), sender_name, text)
            if msg_chat_id:
                self.send_welcome_message(msg_chat_id, sender_name)
            return True

        # 3. Добавление бота в чат
        if update_type == 'bot_added':
            logger.info("Бот добавлен в чат %s", chat_id)
            if chat_id:
                self.send_welcome_message(chat_id, '')
            return True

        return False
