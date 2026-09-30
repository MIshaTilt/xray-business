"""
Модуль для интеграции и взаимодействия с Bot API платформы MAX (https://dev.max.ru).
Поддерживает:
- Отправку сообщений с инлайн-клавиатурой (open_app + link)
- Обработку вебхуков от MAX
- Регистрацию команд бота (/start, /help)
- Получение информации о боте
- Автоматический dual-bot фоллбэк между известными ботами хакатона и сервиса
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

BOT_CONFIGS: dict[str, dict[str, Any]] = {
    't720': {
        'token': 'f9LHodD0cOJ2aT7xFvyJwXT4nznwEjpb-N0HjiVo-8A578hXcqGWt3-_FDjdSeoWEyqCUi6Di28neThjwMka',
        'username': 't720_hakaton_max_bot',
        'name': 'Хакатон МАХ 720',
        'bot_id': 406062985,
    },
    'xray': {
        'token': 'f9LHodD0cOJBhxITwPCdJEVxZ7O2jzj6oDVpd_ODgTheRYaSUX8ErQbLWGisLOw5-U9xswXPu-vQfO0yAcCT',
        'username': 'se14421867_bot',
        'name': 'X-Ray Business',
        'bot_id': 448121973,
    },
}


class MaxBotService:
    def __init__(
        self,
        bot_key: str | None = None,
        token: str | None = None,
        username: str | None = None,
        app_url: str | None = None,
    ):
        config = BOT_CONFIGS.get(bot_key) if bot_key else None
        if config:
            self.bot_key = bot_key
            default_token = config['token']
            default_username = config['username']
        else:
            self.bot_key = None
            default_token = getattr(
                settings,
                'MAX_BOT_TOKEN',
                BOT_CONFIGS['t720']['token'],
            )
            if default_token == BOT_CONFIGS['xray']['token']:
                default_username = BOT_CONFIGS['xray']['username']
            else:
                default_username = getattr(settings, 'MAX_BOT_USERNAME', BOT_CONFIGS['t720']['username'])

        self.token = token or default_token
        self.username = username or default_username
        self.app_url = (app_url or getattr(settings, 'MAX_APP_URL', 'https://xray-business-bot.online')).rstrip('/')

    def call_api(
        self,
        endpoint: str,
        method: str = 'GET',
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Вызов эндпоинта MAX Bot API."""
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        if query:
            url += '?' + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})

        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers = {
            'Authorization': token or self.token,
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

    def get_me(self, token: str | None = None) -> dict[str, Any]:
        """Информация о боте."""
        return self.call_api('me', token=token)

    def set_commands(self, token: str | None = None) -> dict[str, Any]:
        """Регистрация команд в меню мессенджера."""
        commands = [
            {'name': 'start', 'description': 'Открыть мини-приложение X-Ray'},
            {'name': 'help', 'description': 'Справка о возможностях сервиса'},
        ]
        return self.call_api('me/commands', method='PATCH', payload={'commands': commands}, token=token)

    def get_welcome_text(self, user_name: str = '') -> str:
        """Текст приветственного сообщения для пользователя."""
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

    def get_welcome_keyboard(self, username: str | None = None) -> dict[str, Any]:
        """Формирование клавиатуры для открытия Mini App."""
        bot_uname = username or self.username
        return {
            'type': 'inline_keyboard',
            'payload': {
                'buttons': [
                    [
                        {
                            'type': 'open_app',
                            'text': '🚀 Открыть мини-приложение',
                            'web_app': bot_uname,
                        }
                    ],
                    [
                        {
                            'type': 'link',
                            'text': '🌐 Веб-версия',
                            'url': self.app_url,
                        },
                    ],
                ]
            },
        }

    def send_welcome_message(
        self,
        chat_id: int | None = None,
        user_name: str = '',
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Отправляет приветственное сообщение с кнопками.
        Поддерживает автоматический фоллбэк между ботами при ошибках доступа к чату (chat.not.found).
        """
        candidates: list[tuple[str, str]] = [(self.token, self.username)]
        for conf in BOT_CONFIGS.values():
            pair = (conf['token'], conf['username'])
            if pair not in candidates:
                candidates.append(pair)

        targets: list[dict[str, Any]] = []
        if chat_id:
            targets.append({'chat_id': chat_id})
        if user_id:
            targets.append({'user_id': user_id})

        if not targets:
            raise ValueError("Either chat_id or user_id must be provided")

        last_err: Exception | None = None

        for tok, uname in candidates:
            payload = {
                'text': self.get_welcome_text(user_name),
                'attachments': [self.get_welcome_keyboard(uname)],
            }
            for target_query in targets:
                try:
                    res = self.call_api('messages', method='POST', payload=payload, query=target_query, token=tok)
                    logger.info("Успешно отправлено приветствие через бота %s получателю %s", uname, target_query)
                    return res
                except Exception as err:
                    last_err = err
                    logger.warning("Попытка отправки через бота %s получателю %s не удалась: %s", uname, target_query, err)
                    continue

        if last_err:
            raise last_err
        return {'status': 'error'}

    def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = 'application/octet-stream',
        token: str | None = None,
    ) -> str:
        """
        Загружает файл в хранилище платформы MAX и возвращает token для отправки.
        """
        import requests
        res = self.call_api('uploads', method='POST', query={'type': 'file'}, token=token)
        upload_url = res.get('url')
        if not upload_url:
            raise RuntimeError(f"MAX uploads did not return upload URL: {res}")

        files = {'data': (filename, file_bytes, content_type)}
        resp = requests.post(upload_url, files=files, verify=False, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"Failed to upload file to MAX ({resp.status_code}): {resp.text}")

        data = resp.json()
        file_tok = data.get('token')
        if not file_tok:
            raise RuntimeError(f"MAX upload did not return token: {data}")
        return file_tok

    def send_file_message(
        self,
        user_id: int | None = None,
        chat_id: int | None = None,
        file_bytes: bytes | None = None,
        filename: str = 'report.pdf',
        content_type: str = 'application/pdf',
        caption: str = '',
        file_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Отправляет файл (PDF/Excel) в диалог с пользователем или чат в MAX.
        Автоматически пытается загрузить и отправить через основного или запасного бота.
        """
        import time

        candidates: list[tuple[str, str]] = [(self.token, self.username)]
        for conf in BOT_CONFIGS.values():
            pair = (conf['token'], conf['username'])
            if pair not in candidates:
                candidates.append(pair)

        targets: list[dict[str, Any]] = []
        if user_id:
            targets.append({'user_id': user_id})
        if chat_id:
            targets.append({'chat_id': chat_id})

        if not targets:
            raise ValueError("user_id or chat_id required")

        last_err: Exception | None = None

        for tok, uname in candidates:
            try:
                curr_file_token = file_token
                if not curr_file_token:
                    if not file_bytes:
                        raise ValueError("Either file_token or file_bytes must be provided")
                    curr_file_token = self.upload_file(file_bytes, filename, content_type, token=tok)

                text = caption or f"📊 Ваш отчет X-Ray Business готов ({filename})"
                payload = {
                    'text': text,
                    'attachments': [
                        {
                            'type': 'file',
                            'payload': {
                                'token': curr_file_token,
                            },
                        }
                    ],
                }

                for target_query in targets:
                    for attempt in range(5):
                        if attempt > 0:
                            time.sleep(1.0)
                        try:
                            res = self.call_api('messages', method='POST', payload=payload, query=target_query, token=tok)
                            logger.info("Успешно отправлен файл %s через бота %s получателю %s", filename, uname, target_query)
                            return res
                        except Exception as e:
                            err_str = str(e)
                            if 'attachment.not.ready' in err_str:
                                continue
                            raise
            except Exception as e:
                logger.warning("Не удалось отправить файл через бота %s: %s", uname, e)
                last_err = e
                continue

        if last_err:
            raise last_err
        return {'status': 'error'}

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
            logger.info("Обработка bot_started от user_id=%s (%s) в chat_id=%s", user_id, user_name, chat_id)
            if chat_id or user_id:
                self.send_welcome_message(chat_id=chat_id, user_name=user_name, user_id=user_id)
            return True

        # 2. Новое входящее сообщение
        if update_type == 'message_created':
            message = update.get('message') or {}
            body = message.get('body') or {}
            text = (body.get('text') or '').strip()
            recipient = message.get('recipient') or {}
            msg_chat_id = recipient.get('chat_id') or chat_id
            sender = message.get('sender') or user
            sender_name = sender.get('first_name') or sender.get('name') or user_name
            sender_id = sender.get('user_id') or user_id

            if sender.get('is_bot'):
                return False

            if sender_id:
                try:
                    MaxUser.objects.update_or_create(
                        max_user_id=sender_id,
                        defaults={'first_name': sender_name or 'Пользователь MAX'},
                    )
                except Exception as e:
                    logger.warning("Не удалось сохранить MaxUser %s: %s", sender_id, e)

            logger.info("Входящее сообщение от %s (%s): %r (chat_id=%s)", sender_id, sender_name, text, msg_chat_id)
            if msg_chat_id or sender_id:
                self.send_welcome_message(chat_id=msg_chat_id, user_name=sender_name, user_id=sender_id)
            return True

        # 3. Добавление бота в чат
        if update_type == 'bot_added':
            logger.info("Бот добавлен в чат %s", chat_id)
            if chat_id or user_id:
                self.send_welcome_message(chat_id=chat_id, user_name='', user_id=user_id)
            return True

        return False
