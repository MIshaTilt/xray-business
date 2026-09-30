import time
import logging
from django.core.management.base import BaseCommand
from engine.max_bot import MaxBotService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Запуск Long Polling обработчика чат-бота платформы MAX (X-Ray Business)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=25,
            help='Таймаут долгого опроса в секундах (по умолчанию 25)',
        )

    def handle(self, *args, **options):
        timeout = options.get('timeout', 25)
        service = MaxBotService()

        self.stdout.write(self.style.SUCCESS("===================================================="))
        self.stdout.write(self.style.SUCCESS("🚀 Запуск MAX Bot через Django Management Command..."))
        self.stdout.write(self.style.SUCCESS("===================================================="))

        try:
            me = service.get_me()
            bot_name = me.get('name') or me.get('first_name')
            username = me.get('username')
            self.stdout.write(self.style.SUCCESS(f"✅ Авторизован бот: {bot_name} (@{username})"))
            self.stdout.write(f"   - Mini App deep link: https://max.ru/{username}?startapp")
            self.stdout.write(f"   - Web App URL: {service.app_url}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Не удалось подключиться к MAX API: {e}"))
            return

        try:
            service.set_commands()
            self.stdout.write(self.style.SUCCESS("✅ Команды меню /start и /help зарегистрированы в MAX"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️ Не удалось зарегистрировать команды меню: {e}"))

        self.stdout.write(self.style.NOTICE(f"🔄 Запуск Long Polling (timeout={timeout}s). Нажмите Ctrl+C для выхода..."))

        marker = None
        while True:
            try:
                params = {'timeout': timeout}
                if marker is not None:
                    params['marker'] = marker

                response = service.call_api('updates', method='GET', query=params)
                marker = response.get('marker', marker)
                updates = response.get('updates', [])

                for update in updates:
                    update_type = update.get('update_type')
                    user = update.get('user') or {}
                    user_name = user.get('first_name') or user.get('name') or ''
                    chat_id = update.get('chat_id')

                    self.stdout.write(f"📥 Событие: {update_type} от {user.get('user_id')} ({user_name}) в чате {chat_id}")
                    service.handle_update(update)

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\n🛑 Бот остановлен пользователем."))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"⚠️ Ошибка опроса: {e}. Повтор через 3 секунды..."))
                time.sleep(3)
