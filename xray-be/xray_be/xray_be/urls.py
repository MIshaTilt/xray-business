"""
URL configuration for xray_be project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from .views import chat_stream
from engine.amo_views import AmoConnectView, AmoDeleteView, AmoStatusView, AmoSyncView
from engine.bitrix_views import BitrixConnectView, BitrixDeleteView, BitrixStatusView, BitrixSyncView
from engine.moysklad_views import MoySkladConnectView, MoySkladDeleteView, MoySkladStatusView, MoySkladSyncView
from engine.views_api import (
    UploadView,
    SaveMappingView,
    SnapshotCreateView,
    SnapshotPollView,
    SnapshotDiagnosisView,
    SnapshotMetricDetailView,
    SnapshotsListView,
    TemplatesListView,
    LoadTemplateView,
    SnapshotChatHistoryView,
    ChatListView,
    SnapshotExportExcelView,
    SnapshotExportPdfView,
    SnapshotCompareView,
)

def serve_spec_file(filename):
    def _view(_request):
        candidates = [
            settings.BASE_DIR.parent / filename,
            settings.BASE_DIR.parent.parent / filename,
            settings.BASE_DIR / filename,
        ]
        for p in candidates:
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    return HttpResponse(f.read(), content_type='text/yaml; charset=utf-8')
        return HttpResponse(f"File {filename} not found", status=404)
    return _view

def api_home(_request):
    return HttpResponse(
        """<!doctype html><meta charset="utf-8"><title>X-Ray Business API</title>
        <body style="font-family:Segoe UI,sans-serif;padding:40px;line-height:1.6;max-width:800px;margin:0 auto">
        <h1 style="color:#0f172a">X-Ray Business API</h1>
        <p>Интеллектуальная система экспресс-диагностики и аудита B2B-продаж для платформы MAX.</p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0"/>
        <h3>Быстрые ссылки для жюри:</h3>
        <ul>
          <li><a href="/api/docs/" style="font-weight:bold;color:#2563eb">Интерактивная документация Swagger UI (/api/docs/)</a></li>
          <li><a href="/api/redoc/" style="color:#2563eb">Документация ReDoc (/api/redoc/)</a></li>
          <li><a href="/openapi.yaml" style="color:#2563eb">Спецификация OpenAPI 3.1 (/openapi.yaml)</a></li>
          <li><a href="/DATA-API.yaml" style="color:#2563eb">План проверки DATA-API.yaml (/DATA-API.yaml)</a></li>
          <li><a href="/admin/" style="color:#2563eb">Панель администратора Django (/admin/)</a></li>
        </ul>
        </body>""",
        content_type="text/html; charset=utf-8",
    )

urlpatterns = [
    path('', api_home),
    path('admin', RedirectView.as_view(url='/admin/', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/chat/stream/', chat_stream, name='chat_stream'),

    # X-Ray Core API endpoints
    path('api/uploads', UploadView.as_view(), name='api_uploads'),
    path('api/uploads/<uuid:upload_id>/mapping', SaveMappingView.as_view(), name='api_upload_mapping'),
    path('api/snapshots', SnapshotCreateView.as_view(), name='api_snapshots_create'),
    path('api/snapshots/compare', SnapshotCompareView.as_view(), name='api_snapshots_compare'),
    path('api/snapshots/<uuid:snapshot_id>', SnapshotPollView.as_view(), name='api_snapshot_poll'),
    path('api/snapshots/<uuid:snapshot_id>/diagnosis', SnapshotDiagnosisView.as_view(), name='api_snapshot_diagnosis'),
    path('api/snapshots/<uuid:snapshot_id>/metrics/<str:metric_id>', SnapshotMetricDetailView.as_view(), name='api_snapshot_metric_detail'),

    # Chat history endpoints
    path('api/snapshots/<uuid:snapshot_id>/chat', SnapshotChatHistoryView.as_view(), name='api_snapshot_chat_history'),
    path('api/chats', ChatListView.as_view(), name='api_chats'),

    # Export endpoints
    path('api/snapshots/<uuid:snapshot_id>/export-excel', SnapshotExportExcelView.as_view(), name='api_snapshot_export_excel'),
    path('api/snapshots/<uuid:snapshot_id>/export-pdf', SnapshotExportPdfView.as_view(), name='api_snapshot_export_pdf'),

    # Templates endpoints
    path('api/templates', TemplatesListView.as_view(), name='api_templates_list'),
    path('api/templates/<str:template_id>/load', LoadTemplateView.as_view(), name='api_template_load'),

    # AmoCRM endpoints
    path('api/amo', AmoStatusView.as_view(), name='api_amo_status'),
    path('api/amo/connect', AmoConnectView.as_view(), name='api_amo_connect'),
    path('api/amo/sync', AmoSyncView.as_view(), name='api_amo_sync'),
    path('api/amo/<int:connection_id>', AmoDeleteView.as_view(), name='api_amo_delete'),

    # Bitrix24 endpoints
    path('api/bitrix', BitrixStatusView.as_view(), name='api_bitrix_status'),
    path('api/bitrix/connect', BitrixConnectView.as_view(), name='api_bitrix_connect'),
    path('api/bitrix/sync', BitrixSyncView.as_view(), name='api_bitrix_sync'),
    path('api/bitrix/<int:connection_id>', BitrixDeleteView.as_view(), name='api_bitrix_delete'),

    # MoySklad endpoints
    path('api/moysklad', MoySkladStatusView.as_view(), name='api_moysklad_status'),
    path('api/moysklad/connect', MoySkladConnectView.as_view(), name='api_moysklad_connect'),
    path('api/moysklad/sync', MoySkladSyncView.as_view(), name='api_moysklad_sync'),
    path('api/moysklad/<int:connection_id>', MoySkladDeleteView.as_view(), name='api_moysklad_delete'),

    # Swagger / OpenAPI documentation endpoints for Jury & Platform verification
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url='/openapi.yaml'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url='/openapi.yaml'), name='redoc'),
    path('docs', RedirectView.as_view(url='/api/docs/', permanent=False)),
    path('docs/', RedirectView.as_view(url='/api/docs/', permanent=False)),
    path('swagger', RedirectView.as_view(url='/api/docs/', permanent=False)),
    path('swagger/', RedirectView.as_view(url='/api/docs/', permanent=False)),

    # Automated check specification files
    path('openapi.yaml', serve_spec_file('openapi.yaml'), name='spec_openapi'),
    path('DATA-API.yaml', serve_spec_file('DATA-API.yaml'), name='spec_data_api'),
]
