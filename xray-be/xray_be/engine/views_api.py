import os
import io
import json
import uuid
from decimal import Decimal
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from engine.parsers import read_table_file
from engine.mapping import guess_column_mapping, CANONICAL_FIELDS
from engine.normalizer import normalize_records
from engine.analyzer import calculate_metrics_and_findings
from engine.narrator import generate_llm_narrative

# In-memory session storage for MVP uploads and snapshots
UPLOADS_STORE = {}
SNAPSHOTS_STORE = {}


def get_coverage(mapping: dict) -> dict:
    has_f = lambda f: bool(mapping.get(f))
    checks = {
        'speed_to_lead': has_f('created_at') and has_f('first_contact_at'),
        'stagnation': has_f('status') and (has_f('status_changed_at') or has_f('created_at')),
        'discount_leakage': has_f('amount') and (has_f('discount_pct') or has_f('list_price')),
        'sales_cycle': has_f('created_at') and has_f('closed_at'),
        'key_account_risk': has_f('client') and has_f('status'),
        'dormant': has_f('client') and (has_f('last_activity_at') or has_f('created_at')),
        'funnel_dropoff': has_f('status') and has_f('amount'),
    }
    metric_order = [
        'speed_to_lead', 'stagnation', 'discount_leakage',
        'sales_cycle', 'key_account_risk', 'dormant', 'funnel_dropoff'
    ]
    available = [m for m in metric_order if checks[m]]
    skipped = [m for m in metric_order if not checks[m]]
    return {'available': available, 'skipped': skipped}


class UploadView(APIView):
    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'code': 'no_file', 'message': 'Файл не прикреплен'}, status=status.HTTP_400_BAD_REQUEST)

        filename = file_obj.name
        try:
            cols, sample_rows, all_rows = read_table_file(file_obj, filename)
        except ValueError as e:
            code = str(e)
            msg = 'Не удалось прочитать таблицу'
            if code == 'bad_encoding':
                msg = 'Неподдерживаемая кодировка файла. Сохраните в UTF-8.'
            elif code == 'not_a_table':
                msg = 'Файл пуст или не содержит таблицы.'
            return Response({'code': code, 'message': msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'code': 'read_error', 'message': f'Ошибка при чтении файла: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        suggested_mapping = guess_column_mapping(cols, sample_rows)
        coverage = get_coverage(suggested_mapping)
        upload_id = str(uuid.uuid4())

        UPLOADS_STORE[upload_id] = {
            'upload_id': upload_id,
            'filename': filename,
            'columns': cols,
            'sample_rows': sample_rows,
            'all_rows': all_rows,
            'mapping': suggested_mapping,
            'status_map': {},
        }

        return Response({
            'upload_id': upload_id,
            'filename': filename,
            'columns': cols,
            'sample_rows': sample_rows,
            'suggested_mapping': suggested_mapping,
            'coverage': coverage
        }, status=status.HTTP_201_CREATED)


class SaveMappingView(APIView):
    def put(self, request, upload_id):
        upload = UPLOADS_STORE.get(str(upload_id))
        if not upload:
            return Response({'code': 'not_found', 'message': 'Сессия загрузки не найдена'}, status=status.HTTP_404_NOT_FOUND)

        mapping = request.data.get('mapping', {})
        status_map = request.data.get('status_map', {})

        # Validation
        if not mapping.get('amount') or (not mapping.get('status') and not mapping.get('created_at')):
            return Response({'code': 'mapping_incomplete', 'message': 'Необходимо выбрать колонку суммы и статуса или даты'}, status=status.HTTP_400_BAD_REQUEST)

        upload['mapping'] = mapping
        upload['status_map'] = status_map
        coverage = get_coverage(mapping)

        return Response({
            'coverage': coverage,
            'warnings': []
        }, status=status.HTTP_200_OK)


class SnapshotCreateView(APIView):
    def get(self, request):
        items = []
        for snap in reversed(list(SNAPSHOTS_STORE.values())):
            diag = snap.get('diagnosis')
            crit = 'ok'
            if diag and diag.get('findings'):
                v_set = {f['verdict'] for f in diag['findings']}
                if 'critical' in v_set:
                    crit = 'critical'
                elif 'watch' in v_set:
                    crit = 'watch'

            items.append({
                'snapshot_id': snap['snapshot_id'],
                'status': snap['status'],
                'created_at': snap['created_at'],
                'filename': snap['filename'],
                'source': snap['source'],
                'period': diag.get('period') if diag else None,
                'headline': diag.get('headline') if diag else None,
                'verdict': crit,
                'coverage_ready': len(diag['coverage']['available']) if diag else 0,
                'coverage_total': 7,
            })
        return Response({'items': items, 'next_cursor': None})

    def post(self, request):
        upload_id = request.data.get('upload_id')
        upload = UPLOADS_STORE.get(str(upload_id))
        if not upload:
            return Response({'code': 'not_found', 'message': 'Файл загрузки не найден'}, status=status.HTTP_404_NOT_FOUND)

        mapping = upload.get('mapping', {})
        status_map = upload.get('status_map', {})

        snapshot_id = str(uuid.uuid4())

        # Normalize and compute immediately
        deals, rejected = normalize_records(upload['all_rows'], mapping, status_map)
        findings, all_metrics, ok_list, low_sample = calculate_metrics_and_findings(deals, mapping)
        coverage = get_coverage(mapping)

        total_amount = sum((d.amount for d in deals), Decimal('0.00'))

        # Dates
        dates = [d.created_at for d in deals if d.created_at]
        p_from = min(dates).strftime('%Y-%m-%d') if dates else None
        p_to = max(dates).strftime('%Y-%m-%d') if dates else None

        headline = findings[0]['action'] if findings else 'По этому файлу критичных утечек не видно.'
        # LLM Enhancement strictly according to TZ §6.5
        headline, findings = generate_llm_narrative(findings, headline)
        body = ' '.join([f['action'] for f in findings])

        SNAPSHOTS_STORE[snapshot_id] = {
            'snapshot_id': snapshot_id,
            'status': 'ready',
            'progress': 100,
            'error': '',
            'created_at': '2026-03-31T12:00:00Z',
            'filename': upload['filename'],
            'source': 'miniapp',
            'diagnosis': {
                'snapshot_id': snapshot_id,
                'headline': headline,
                'body': body,
                'findings': findings,
                'coverage': coverage,
                'period': {'from': p_from, 'to': p_to},
                'totals': {
                    'deals': len(deals) + len(rejected),
                    'amount': f"{total_amount:.2f}",
                    'accepted': len(deals),
                    'rejected': len(rejected),
                },
                'ok': ok_list,
                'low_sample': low_sample,
            },
            'all_metrics': all_metrics,
        }

        return Response({
            'snapshot_id': snapshot_id,
            'status': 'ready',
            'created': True
        }, status=status.HTTP_200_OK)


class SnapshotPollView(APIView):
    def get(self, request, snapshot_id):
        snap = SNAPSHOTS_STORE.get(str(snapshot_id))
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'snapshot_id': snap['snapshot_id'],
            'status': snap['status'],
            'progress': snap['progress'],
            'error': snap['error']
        })


class SnapshotDiagnosisView(APIView):
    def get(self, request, snapshot_id):
        snap = SNAPSHOTS_STORE.get(str(snapshot_id))
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(snap['diagnosis'])


class SnapshotMetricDetailView(APIView):
    def get(self, request, snapshot_id, metric_id):
        snap = SNAPSHOTS_STORE.get(str(snapshot_id))
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден'}, status=status.HTTP_404_NOT_FOUND)

        metric_data = snap['all_metrics'].get(metric_id)
        if not metric_data:
            return Response({'code': 'not_found', 'message': 'Метрика не найдена'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'result': metric_data,
            'evidence': metric_data.get('evidence', [])
        })


class SnapshotsListView(APIView):
    def get(self, request):
        items = []
        for snap in reversed(list(SNAPSHOTS_STORE.values())):
            diag = snap.get('diagnosis')
            crit = 'ok'
            if diag and diag.get('findings'):
                v_set = {f['verdict'] for f in diag['findings']}
                if 'critical' in v_set:
                    crit = 'critical'
                elif 'watch' in v_set:
                    crit = 'watch'

            items.append({
                'snapshot_id': snap['snapshot_id'],
                'status': snap['status'],
                'created_at': snap['created_at'],
                'filename': snap['filename'],
                'source': snap['source'],
                'period': diag.get('period') if diag else None,
                'headline': diag.get('headline') if diag else None,
                'verdict': crit,
                'coverage_ready': len(diag['coverage']['available']) if diag else 0,
                'coverage_total': 7,
            })
        return Response({'items': items, 'next_cursor': None})
