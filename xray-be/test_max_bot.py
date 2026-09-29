import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'xray_be'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xray_be.settings')
django.setup()

from django.test import Client

def test_webhook_endpoints():
    c = Client()
    # 1. Test GET /api/max/webhook
    resp_get = c.get('/api/max/webhook')
    print("GET /api/max/webhook status:", resp_get.status_code)
    print("GET response:", resp_get.json())
    assert resp_get.status_code == 200
    assert resp_get.json().get("status") == "ok"
    assert resp_get.json().get("bot", {}).get("username") == "se14421867_bot"

    # 2. Test POST /api/max/webhook with dummy update
    dummy_payload = {
        "update_type": "test_ping",
        "chat_id": 123456,
        "user": {"user_id": 999999, "first_name": "Тестер"},
    }
    resp_post = c.post('/api/max/webhook', data=dummy_payload, content_type='application/json')
    print("POST /api/max/webhook status:", resp_post.status_code)
    print("POST response:", resp_post.json())
    assert resp_post.status_code == 200
    assert resp_post.json().get("ok") is True

    print("\n✅ ВСЕ ТЕСТЫ DJANGO WEBHOOK ПРОЙДЕНЫ УСПЕШНО!")

if __name__ == '__main__':
    test_webhook_endpoints()
