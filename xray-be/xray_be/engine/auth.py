import json
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from django.conf import settings
from engine.models import MaxUser, Snapshot, Upload, ChatMessage, Deal


@dataclass
class RequestIdentity:
    user: MaxUser | None
    guest_session: str
    is_guest: bool

    @property
    def display_id(self) -> str:
        if self.user:
            return f"max_{self.user.max_user_id}"
        return f"guest_{self.guest_session}"


def parse_max_user_from_init_data(init_data: str) -> tuple[int | None, str]:
    if not init_data or not isinstance(init_data, str):
        return None, ""
    try:
        # 1. First parse as query string
        parsed = urllib.parse.parse_qs(init_data)
        user_raw = parsed.get("user", [None])[0]
        if not user_raw:
            # If init_data was double encoded or in a different format
            unquoted = urllib.parse.unquote(init_data)
            parsed2 = urllib.parse.parse_qs(unquoted)
            user_raw = parsed2.get("user", [None])[0]

        if user_raw:
            user_obj = json.loads(user_raw)
            uid = user_obj.get("id")
            first_name = user_obj.get("first_name", "")
            if uid is not None and isinstance(uid, (int, str)):
                return int(uid), str(first_name)
    except Exception as e:
        print(f"[AUTH ERROR] Failed to parse initData: {e}")

    # Fallback: check if entire string is JSON
    try:
        data = json.loads(init_data)
        if isinstance(data, dict):
            user_obj = data.get("user", data)
            uid = user_obj.get("id")
            first_name = user_obj.get("first_name", "")
            if uid is not None:
                return int(uid), str(first_name)
    except Exception:
        pass

    return None, ""


def get_request_identity(request) -> RequestIdentity:
    # 1. Try MAX initData from header
    init_data = request.headers.get("X-Max-Init-Data") or request.META.get("HTTP_X_MAX_INIT_DATA", "")
    max_user_id, first_name = parse_max_user_from_init_data(init_data)

    if max_user_id:
        user, created = MaxUser.objects.get_or_create(
            max_user_id=max_user_id,
            defaults={"first_name": first_name or "Пользователь MAX"}
        )
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            user.save(update_fields=["first_name"])
        return RequestIdentity(user=user, guest_session="", is_guest=False)

    # 2. Check guest session header
    guest_session = (
        request.headers.get("X-Guest-Session")
        or request.META.get("HTTP_X_GUEST_SESSION")
        or request.COOKIES.get("xray_guest_session", "")
    ).strip()

    if not guest_session:
        # Stable fallback per remote IP if no header provided
        remote_ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR") or "anon"
        guest_session = f"anon_{remote_ip}"

    return RequestIdentity(user=None, guest_session=guest_session, is_guest=True)


def cleanup_expired_guest_data(max_age_seconds: int = 86400) -> int:
    """
    Erases all guest snapshots, deals, chat history, and uploads older than 24 hours (86400 seconds).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    deleted_count = 0

    # 1. Clean up guest snapshots in DB (cascades to Deals and ChatMessages)
    expired_snaps = Snapshot.objects.filter(is_guest=True, created_at__lt=cutoff)
    expired_ids = list(expired_snaps.values_list("id", flat=True))

    if expired_ids:
        count, _ = expired_snaps.delete()
        deleted_count += len(expired_ids)

    # 2. Clean up guest uploads older than 24 hours
    expired_uploads = Upload.objects.filter(user__isnull=True, created_at__lt=cutoff)
    up_ids = list(expired_uploads.values_list("id", flat=True))
    if up_ids:
        try:
            from engine.views_api import UPLOADS_STORE
            for uid in up_ids:
                UPLOADS_STORE.pop(str(uid), None)
        except Exception:
            pass
        expired_uploads.delete()

    return deleted_count


import threading
import time

_cleanup_started = False

def start_background_cleanup_thread():
    global _cleanup_started
    if _cleanup_started:
        return
    _cleanup_started = True

    def loop():
        while True:
            try:
                time.sleep(300)
                cleanup_expired_guest_data(max_age_seconds=86400)
            except Exception as e:
                print(f"[BG CLEANUP ERROR]: {e}")

    t = threading.Thread(target=loop, daemon=True, name="guest_cleanup_worker")
    t.start()


from rest_framework.authentication import SessionAuthentication

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication without CSRF enforcement for stateless API clients.
    Allows browsers that have active Django admin sessions to communicate with
    the SPA frontend API without triggering 'CSRF Failed: CSRF token missing'.
    """
    def enforce_csrf(self, request):
        return

