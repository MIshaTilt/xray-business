import os
import sys
import threading

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from engine.amo_client import AmoError, fetch_lead_rows
from engine.amo_sync import connection_for, public_status, save_token, sync_all, sync_connection
from engine.auth import get_request_identity


class AmoStatusView(APIView):
    def get(self, request):
        ident = get_request_identity(request)
        return Response(public_status(connection_for(ident)))


class AmoConnectView(APIView):
    def post(self, request):
        ident = get_request_identity(request)
        account = request.data.get("account") or ""
        token = "".join(str(request.data.get("token") or "").split())
        try:
            host, rows = fetch_lead_rows(account, token, limit=1)
        except AmoError as exc:
            return Response({"code": "crm_auth", "message": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        connection = save_token(ident, host, token)
        if not rows:
            connection.last_error = "Кабинет подключен. В сделках нет бюджета. В карточке сделки заполните поле «Бюджет» суммой больше нуля и нажмите «Обновить»."
            connection.save(update_fields=["last_error", "account"])
            payload = public_status(connection)
            payload["message"] = connection.last_error
            return Response(payload, status=status.HTTP_200_OK)
        try:
            snapshot_id = sync_connection(connection)
        except AmoError as exc:
            return Response({"code": "crm_unavailable", "message": exc.message}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            print(f"[AMO CONNECT] {exc}")
            return Response(
                {"code": "crm_unavailable", "message": "Сделки прочитаны, но снимок не собрался. Повторите ещё раз."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        connection.refresh_from_db()
        payload = public_status(connection)
        payload["snapshot_id"] = snapshot_id
        return Response(payload, status=status.HTTP_201_CREATED)


class AmoSyncView(APIView):
    def post(self, request):
        ident = get_request_identity(request)
        connection = connection_for(ident)
        if connection is None:
            return Response(
                {"code": "not_found", "message": "Сначала подключите amoCRM."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            snapshot_id = sync_connection(connection)
        except AmoError as exc:
            return Response({"code": "crm_unavailable", "message": exc.message}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"snapshot_id": snapshot_id, "status": "ready"})


def _poll_loop():
    import time

    time.sleep(30)
    while True:
        try:
            sync_all()
        except Exception as exc:
            print(f"[AMO POLL] {exc}")
        time.sleep(300)


def start_amo_poll():
    if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
        return
    threading.Thread(target=_poll_loop, name="amo-poll", daemon=True).start()


start_amo_poll()
