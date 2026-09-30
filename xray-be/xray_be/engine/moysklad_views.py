from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from engine.auth import get_request_identity
from engine.moysklad_client import MoySkladError, fetch_order_rows
from engine.moysklad_sync import connections_for, public_session, save_token, sync_connection


class MoySkladStatusView(APIView):
    def get(self, request):
        ident = get_request_identity(request)
        sessions = [public_session(item) for item in connections_for(ident)]
        return Response({"connected": bool(sessions), "sessions": sessions})


class MoySkladConnectView(APIView):
    def post(self, request):
        ident = get_request_identity(request)
        token = "".join(str(request.data.get("token") or "").split())
        try:
            account, rows = fetch_order_rows(token, limit=1)
        except MoySkladError as exc:
            return Response({"code": "crm_auth", "message": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        connection = save_token(ident, account, token)
        if not rows:
            connection.last_error = "Кабинет подключен. В заказах нет суммы. Заполните сумму и нажмите «Обновить»."
            connection.save(update_fields=["last_error", "account"])
            payload = public_session(connection)
            payload["connected"] = True
            payload["message"] = connection.last_error
            return Response(payload, status=status.HTTP_200_OK)
        try:
            snapshot_id = sync_connection(connection)
        except MoySkladError as exc:
            return Response({"code": "crm_unavailable", "message": exc.message}, status=status.HTTP_502_BAD_GATEWAY)
        payload = public_session(connection)
        payload["connected"] = True
        payload["snapshot_id"] = snapshot_id
        return Response(payload, status=status.HTTP_201_CREATED)


class MoySkladDeleteView(APIView):
    def delete(self, request, connection_id):
        ident = get_request_identity(request)
        connection = connections_for(ident).filter(id=connection_id).first()
        if connection is None:
            return Response(
                {"code": "not_found", "message": "Сессия МойСклад не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )
        connection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MoySkladSyncView(APIView):
    def post(self, request):
        ident = get_request_identity(request)
        found = connections_for(ident)
        connection_id = request.data.get("id")
        connection = found.filter(id=connection_id).first() if connection_id else found.first()
        if connection is None:
            return Response({"code": "not_found", "message": "Сначала подключите МойСклад."}, status=status.HTTP_404_NOT_FOUND)
        try:
            snapshot_id = sync_connection(connection)
        except MoySkladError as exc:
            return Response({"code": "crm_unavailable", "message": exc.message}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"snapshot_id": snapshot_id, "status": "ready"})
