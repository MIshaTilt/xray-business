import os
import sys
import threading

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from engine.amo_client import AmoError, fetch_lead_rows
from engine.amo_sync import connections_for, public_session, save_token, sync_all, sync_connection
from engine.auth import get_request_identity


class AmoStatusView(APIView):
    def get(self, request):
        ident = get_request_identity(request)
        sessions = [public_session(item) for item in connections_for(ident)]
        return Response({"connected": bool(sessions), "sessions": sessions})


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
            connection.last_error = "Кабинет подключен. В сделках нет бюджета. Заполните поле «Бюджет» и заберите сделки из меню."
            connection.save(update_fields=["last_error", "account"])
            payload = public_session(connection)
            payload["connected"] = True
            payload["message"] = connection.last_error
            return Response(payload, status=status.HTTP_200_OK)
        try:
            snapshot_id = sync_connection(connection)
        except AmoError as exc:
            return Response({"code": "crm_unavailable", "message": exc.message}, status=status.HTTP_502_BAD_GATEWAY)
        payload = public_session(connection)
        payload["connected"] = True
        payload["snapshot_id"] = snapshot_id
        return Response(payload, status=status.HTTP_201_CREATED)


class AmoDeleteView(APIView):
    def delete(self, request, connection_id):
        ident = get_request_identity(request)
        connection = connections_for(ident).filter(id=connection_id).first()
        if connection is None:
            return Response(
                {"code": "not_found", "message": "Сессия amoCRM не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )
        connection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AmoSyncView(APIView):
    def post(self, request):
        ident = get_request_identity(request)
        connection_id = request.data.get("id")
        found = connections_for(ident)
        connection = found.filter(id=connection_id).first() if connection_id else found.first()
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
            from engine.bitrix_sync import sync_all as bitrix_sync_all
            from engine.moysklad_sync import sync_all as moysklad_sync_all

            bitrix_sync_all()
            moysklad_sync_all()
        except Exception as exc:
            print(f"[CRM POLL] {exc}")
        time.sleep(300)


def start_amo_poll():
    if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
        return
    threading.Thread(target=_poll_loop, name="amo-poll", daemon=True).start()


start_amo_poll()
