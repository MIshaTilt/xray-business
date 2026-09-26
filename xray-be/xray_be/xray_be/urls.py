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
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from .views import chat_stream
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
    SnapshotExportExcelView,
    SnapshotExportPdfView,
    SnapshotCompareView,
)

urlpatterns = [
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

    # Export endpoints
    path('api/snapshots/<uuid:snapshot_id>/export-excel', SnapshotExportExcelView.as_view(), name='api_snapshot_export_excel'),
    path('api/snapshots/<uuid:snapshot_id>/export-pdf', SnapshotExportPdfView.as_view(), name='api_snapshot_export_pdf'),

    # Templates endpoints
    path('api/templates', TemplatesListView.as_view(), name='api_templates_list'),
    path('api/templates/<str:template_id>/load', LoadTemplateView.as_view(), name='api_template_load'),
]
