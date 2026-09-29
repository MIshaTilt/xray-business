import json
import logging
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from engine.max_bot import MaxBotService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class MaxWebhookView(View):
    """
    Эндпоинт для приема и обработки вебхуков от платформы MAX (https://dev.max.ru).
    """

    def get(self, request, *args, **kwargs):
        """Проверка статуса подключения бота к платформе MAX."""
        service = MaxBotService()
        try:
            bot_info = service.get_me()
            return JsonResponse({
                "status": "ok",
                "service": "X-Ray Business MAX Bot",
                "bot": {
                    "user_id": bot_info.get("user_id"),
                    "username": bot_info.get("username"),
                    "name": bot_info.get("name") or bot_info.get("first_name"),
                },
                "mini_app_url": service.app_url,
                "mini_app_deep_link": f"https://max.ru/{service.username}?startapp",
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": f"Не удалось получить информацию о боте: {e}",
            }, status=500)

    def post(self, request, *args, **kwargs):
        """Обработка входящих событий от MAX (bot_started, message_created, bot_added)."""
        try:
            body = request.body.decode('utf-8')
            if not body:
                return JsonResponse({"ok": False, "error": "Empty body"}, status=400)
            data = json.loads(body)
        except Exception as e:
            logger.error("Ошибка парсинга JSON вебхука MAX: %s", e)
            return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

        logger.info("Получен вебхук MAX: %s", data.get("update_type"))
        service = MaxBotService()

        try:
            # Обработка как одиночного update, так и массива updates
            if isinstance(data, dict):
                if "updates" in data and isinstance(data["updates"], list):
                    for u in data["updates"]:
                        service.handle_update(u)
                else:
                    service.handle_update(data)
            elif isinstance(data, list):
                for u in data:
                    service.handle_update(u)

            return JsonResponse({"ok": True})
        except Exception as e:
            logger.error("Ошибка при обработке вебхука MAX: %s", e, exc_info=True)
            return JsonResponse({"ok": False, "error": str(e)}, status=500)
