import os
import io
import json
import uuid
import datetime
from decimal import Decimal
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from engine.parsers import read_table_file
from engine.mapping import guess_column_mapping, derive_computed_columns, CANONICAL_FIELDS
from pathlib import Path
from engine.normalizer import normalize_records
from engine.analyzer import calculate_metrics_and_findings
from engine.narrator import generate_llm_narrative
from engine.models import Upload, Snapshot, ChatMessage, Deal
from engine.ai_mapper import ai_smart_column_mapping, ai_smart_status_mapping
from engine.reports import generate_excel_report, generate_pdf_report
from engine.auth import (
    get_request_identity,
    cleanup_expired_guest_data,
    start_background_cleanup_thread,
)

# Start 5-minute guest cleaner in background
start_background_cleanup_thread()

# Persistent storage for MVP snapshots on disk
DATA_DIR = Path(__file__).resolve().parent.parent.parent / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORE_FILE = DATA_DIR / 'snapshots_store.json'

UPLOADS_STORE = {}
SNAPSHOTS_STORE = {}


def get_upload(upload_id, request=None) -> dict | None:
    cleanup_expired_guest_data()
    key = str(upload_id)
    cached = UPLOADS_STORE.get(key)
    row = Upload.objects.filter(pk=key).first()
    if not cached and not row:
        return None

    if request:
        ident = get_request_identity(request)
        owner_uid = row.user.max_user_id if (row and row.user) else (cached.get('user_id') if cached else None)
        is_guest = (row.user is None) if row else (cached.get('is_guest', True) if cached else True)
        guest_sess = row.guest_session if row else (cached.get('guest_session', '') if cached else '')

        if owner_uid is not None:
            if not ident.user or ident.user.max_user_id != owner_uid:
                return None
        elif is_guest:
            if not ident.is_guest or ident.guest_session != guest_sess:
                return None

    if cached:
        return cached

    entry = {
        'upload_id': key,
        'user_id': row.user.max_user_id if (row and row.user) else None,
        'guest_session': row.guest_session if row else '',
        'is_guest': (row.user is None) if row else True,
        'filename': row.filename if row else '',
        'columns': (row.columns if row else []) or [],
        'sample_rows': (row.sample_rows if row else []) or [],
        'all_rows': (row.all_rows if row else []) or [],
        'mapping': (row.mapping or row.suggested_mapping if row else {}) or {},
        'status_map': (row.status_map if row else {}) or {},
    }
    UPLOADS_STORE[key] = entry
    return entry


def get_snapshot_for_request(snapshot_id, request) -> tuple[dict | None, Snapshot | None]:
    cleanup_expired_guest_data()
    ident = get_request_identity(request)
    s_key = str(snapshot_id)

    snap_obj = Snapshot.objects.filter(id=s_key).first()
    snap_dict = SNAPSHOTS_STORE.get(s_key)

    if not snap_obj and not snap_dict:
        return None, None

    owner_uid = snap_obj.user.max_user_id if (snap_obj and snap_obj.user) else (snap_dict.get('user_id') if snap_dict else None)
    is_guest = snap_obj.is_guest if snap_obj else (snap_dict.get('is_guest', False) if snap_dict else False)
    guest_sess = snap_obj.guest_session if snap_obj else (snap_dict.get('guest_session', '') if snap_dict else '')

    if owner_uid is not None:
        if not ident.user or ident.user.max_user_id != owner_uid:
            return None, None
    elif is_guest:
        if not ident.is_guest or ident.guest_session != guest_sess:
            return None, None

    # Reconstruct snap_dict from snap_obj if missing from in-memory cache
    if not snap_dict and snap_obj:
        diag = {
            'snapshot_id': s_key,
            'headline': snap_obj.headline,
            'body': snap_obj.body,
            'findings': snap_obj.findings,
            'coverage': snap_obj.coverage,
            'period': {
                'from': snap_obj.period_from.isoformat() if snap_obj.period_from else None,
                'to': snap_obj.period_to.isoformat() if snap_obj.period_to else None,
            },
            'totals': snap_obj.totals,
            'ok': snap_obj.ok_list,
            'low_sample': snap_obj.low_sample,
        }
        snap_dict = {
            'snapshot_id': s_key,
            'user_id': owner_uid,
            'guest_session': guest_sess,
            'is_guest': is_guest,
            'scan_no': snap_obj.scan_no,
            'status': snap_obj.status,
            'progress': snap_obj.progress,
            'error': snap_obj.error,
            'created_at': snap_obj.created_at.isoformat(),
            'filename': snap_obj.filename,
            'source': snap_obj.archetype,
            'diagnosis': diag,
            'all_metrics': snap_obj.all_metrics,
        }
        SNAPSHOTS_STORE[s_key] = snap_dict

    return snap_dict, snap_obj


def persist_upload_mapping(upload_id, mapping: dict, status_map: dict) -> None:
    try:
        Upload.objects.filter(pk=str(upload_id)).update(mapping=mapping, status_map=status_map)
    except Exception as e:
        print(f"[DB ERROR] Не удалось обновить mapping: {e}")


def load_disk_store():
    global SNAPSHOTS_STORE
    if STORE_FILE.exists():
        try:
            with open(STORE_FILE, 'r', encoding='utf-8') as f:
                SNAPSHOTS_STORE = json.load(f)
        except Exception:
            SNAPSHOTS_STORE = {}

def save_disk_store():
    try:
        with open(STORE_FILE, 'w', encoding='utf-8') as f:
            json.dump(SNAPSHOTS_STORE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[STORE ERROR] Не удалось сохранить на диск: {e}")

load_disk_store()


def ensure_scan_numbers():
    missing = [snap for snap in SNAPSHOTS_STORE.values() if not snap.get('scan_no')]
    if not missing:
        return
    current = max((int(snap.get('scan_no') or 0) for snap in SNAPSHOTS_STORE.values()), default=0)
    for snap in sorted(missing, key=lambda item: item.get('created_at') or ''):
        current += 1
        snap['scan_no'] = current
    save_disk_store()


def next_scan_no() -> int:
    ensure_scan_numbers()
    nums = [int(snap.get('scan_no') or 0) for snap in SNAPSHOTS_STORE.values()]
    return max(nums, default=0) + 1


def get_coverage(mapping: dict, columns: list = None) -> dict:
    has_f = lambda f: bool(mapping.get(f))
    has_col_disc = False
    if columns:
        from engine.mapping import normalize_string
        for c in columns:
            nc = normalize_string(c)
            if any(w in nc for w in ['скидк', 'скинули', 'discount', 'цена без скидки', 'розничная цена']):
                has_col_disc = True
                break

    checks = {
        'speed_to_lead': has_f('created_at') and has_f('first_contact_at'),
        'stagnation': has_f('status') and (has_f('status_changed_at') or has_f('created_at')),
        'discount_leakage': has_f('amount') and (has_f('discount_pct') or has_f('list_price') or has_col_disc),
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
        ext = os.path.splitext(filename)[1].lower()
        if ext != '.csv':
            return Response(
                {
                    'code': 'bad_format',
                    'message': 'Нужен CSV — выгрузка из 1С, Битрикс24, МойСклад, amoCRM и похожих систем.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
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

        # AI-Fallback: if key fields or status/manager/deal_id are unmapped, let LLM resolve unmapped columns
        if not suggested_mapping.get('amount') or not suggested_mapping.get('status') or not suggested_mapping.get('manager') or not suggested_mapping.get('deal_id'):
            suggested_mapping = ai_smart_column_mapping(cols, sample_rows, suggested_mapping)

        # AI / Heuristic Status Normalization
        status_map = {}
        status_col = suggested_mapping.get('status')
        if status_col:
            unique_statuses = list(dict.fromkeys(
                str(r.get(status_col, '')).strip()
                for r in all_rows
                if str(r.get(status_col, '')).strip()
            ))
            if unique_statuses:
                status_map = ai_smart_status_mapping(unique_statuses, sample_rows)

        # Automatically derive missing computed columns (e.g. 'Скидка, % (авто)', 'Прайс до скидки (авто)')
        cols, sample_rows, all_rows, suggested_mapping, auto_computed_columns = derive_computed_columns(
            cols, sample_rows, all_rows, suggested_mapping
        )

        coverage = get_coverage(suggested_mapping, cols)
        upload_id = str(uuid.uuid4())
        ident = get_request_identity(request)

        UPLOADS_STORE[upload_id] = {
            'upload_id': upload_id,
            'user_id': ident.user.max_user_id if ident.user else None,
            'guest_session': ident.guest_session if ident.is_guest else "",
            'is_guest': ident.is_guest,
            'filename': filename,
            'columns': cols,
            'sample_rows': sample_rows,
            'all_rows': all_rows,
            'mapping': suggested_mapping,
            'status_map': status_map,
            'auto_computed_columns': auto_computed_columns,
        }

        try:
            Upload.objects.create(
                id=upload_id,
                user=ident.user,
                guest_session=ident.guest_session if ident.is_guest else "",
                filename=filename,
                columns=cols,
                sample_rows=sample_rows,
                all_rows=all_rows,
                suggested_mapping=suggested_mapping,
                mapping=suggested_mapping,
                status_map=status_map,
            )
        except Exception as e:
            print(f"[DB ERROR] Не удалось сохранить Upload: {e}")

        return Response({
            'upload_id': upload_id,
            'filename': filename,
            'columns': cols,
            'sample_rows': sample_rows,
            'suggested_mapping': suggested_mapping,
            'coverage': coverage,
            'auto_computed_columns': auto_computed_columns,
        }, status=status.HTTP_201_CREATED)


class SaveMappingView(APIView):
    def put(self, request, upload_id):
        upload = get_upload(upload_id, request=request)
        if not upload:
            return Response({'code': 'not_found', 'message': 'Сессия загрузки не найдена или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)

        mapping = request.data.get('mapping', {})
        status_map = request.data.get('status_map') or {}

        # Validation
        if not mapping.get('amount') or (not mapping.get('status') and not mapping.get('created_at')):
            return Response({'code': 'mapping_incomplete', 'message': 'Необходимо выбрать колонку суммы и статуса или даты'}, status=status.HTTP_400_BAD_REQUEST)

        status_col = mapping.get('status')
        if status_col and not status_map:
            all_rows = upload.get('all_rows') or []
            unique_statuses = list(dict.fromkeys(
                str(r.get(status_col, '')).strip()
                for r in all_rows
                if str(r.get(status_col, '')).strip()
            ))
            if unique_statuses:
                status_map = ai_smart_status_mapping(unique_statuses, upload.get('sample_rows'))

        upload['mapping'] = mapping
        upload['status_map'] = status_map
        persist_upload_mapping(upload_id, mapping, status_map)
        coverage = get_coverage(mapping, upload.get('columns'))

        return Response({
            'coverage': coverage,
            'warnings': [],
            'auto_computed_columns': upload.get('auto_computed_columns', []),
        }, status=status.HTTP_200_OK)


class SnapshotCreateView(APIView):
    def get(self, request):
        cleanup_expired_guest_data()
        ensure_scan_numbers()
        ident = get_request_identity(request)
        items = []

        for snap in reversed(list(SNAPSHOTS_STORE.values())):
            owner_uid = snap.get('user_id')
            is_guest = snap.get('is_guest', False)
            guest_sess = snap.get('guest_session', '')

            # Isolation check:
            if ident.user:
                if owner_uid != ident.user.max_user_id:
                    continue
            elif ident.is_guest:
                if not is_guest or guest_sess != ident.guest_session:
                    continue
            else:
                continue

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
                'scan_no': snap.get('scan_no'),
                'status': snap['status'],
                'created_at': snap['created_at'],
                'filename': snap['filename'],
                'source': snap['source'],
                'period': diag.get('period') if diag else None,
                'headline': diag.get('headline') if diag else None,
                'verdict': crit,
                'coverage_ready': len(diag.get('coverage', {}).get('available', [])) if (diag and isinstance(diag.get('coverage'), dict)) else 0,
                'coverage_total': 7,
            })
        return Response({'items': items, 'next_cursor': None})

    def post(self, request):
        cleanup_expired_guest_data()
        ident = get_request_identity(request)
        upload_id = request.data.get('upload_id')
        upload = get_upload(upload_id, request=request)
        if not upload:
            return Response({'code': 'not_found', 'message': 'Файл загрузки не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)

        mapping = upload.get('mapping', {})
        status_map = upload.get('status_map') or {}

        status_col = mapping.get('status')
        if status_col and not status_map:
            all_rows = upload.get('all_rows') or []
            unique_statuses = list(dict.fromkeys(
                str(r.get(status_col, '')).strip()
                for r in all_rows
                if str(r.get(status_col, '')).strip()
            ))
            if unique_statuses:
                status_map = ai_smart_status_mapping(unique_statuses, upload.get('sample_rows'))
                upload['status_map'] = status_map
                persist_upload_mapping(upload_id, mapping, status_map)

        snapshot_id = str(uuid.uuid4())
        scan_no = next_scan_no()

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
            'user_id': ident.user.max_user_id if ident.user else None,
            'guest_session': ident.guest_session if ident.is_guest else "",
            'is_guest': ident.is_guest,
            'scan_no': scan_no,
            'status': 'ready',
            'progress': 100,
            'error': '',
            'created_at': datetime.datetime.now().isoformat(),
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

        save_disk_store()

        try:
            snap_instance = Snapshot.objects.create(
                id=snapshot_id,
                user=ident.user,
                upload=Upload.objects.filter(id=upload_id).first(),
                scan_no=scan_no,
                guest_session=ident.guest_session if ident.is_guest else "",
                is_guest=ident.is_guest,
                filename=upload['filename'],
                headline=headline,
                body=body,
                findings=findings,
                coverage=coverage,
                totals={
                    'deals': len(deals) + len(rejected),
                    'amount': f"{total_amount:.2f}",
                    'accepted': len(deals),
                    'rejected': len(rejected),
                },
                all_metrics=all_metrics,
                ok_list=ok_list,
                low_sample=low_sample,
            )
            # Bulk create Deals for RAG and tool queries
            deal_objects = [
                Deal(
                    snapshot=snap_instance,
                    deal_id=d.deal_id,
                    client=d.client,
                    contact=d.contact,
                    manager=d.manager,
                    amount=d.amount,
                    list_price=d.list_price,
                    discount_pct=d.discount_pct,
                    status_raw=d.status_raw,
                    status=d.status,
                    created_at=d.created_at,
                    first_contact_at=d.first_contact_at,
                    status_changed_at=d.status_changed_at,
                    last_activity_at=d.last_activity_at,
                    closed_at=d.closed_at,
                    source=d.source,
                    raw_data=d.raw_data or {},
                )
                for d in deals
            ]
            Deal.objects.bulk_create(deal_objects)
        except Exception as e:
            print(f"[DB ERROR] Не удалось сохранить Snapshot и Deals: {e}")

        return Response({
            'snapshot_id': snapshot_id,
            'status': 'ready',
            'created': True
        }, status=status.HTTP_200_OK)


class SnapshotPollView(APIView):
    def get(self, request, snapshot_id):
        snap, _ = get_snapshot_for_request(snapshot_id, request)
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'snapshot_id': snap['snapshot_id'],
            'status': snap['status'],
            'progress': snap['progress'],
            'error': snap['error']
        })

    def delete(self, request, snapshot_id):
        snap, snap_obj = get_snapshot_for_request(snapshot_id, request)
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден'}, status=status.HTTP_404_NOT_FOUND)
        s_id = str(snapshot_id)
        if s_id in SNAPSHOTS_STORE:
            del SNAPSHOTS_STORE[s_id]
            save_disk_store()
        if snap_obj:
            snap_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SnapshotDiagnosisView(APIView):
    def get(self, request, snapshot_id):
        snap, snap_obj = get_snapshot_for_request(snapshot_id, request)
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)
        ensure_scan_numbers()
        payload = dict(snap.get('diagnosis') or {})
        payload['scan_no'] = snap.get('scan_no')
        payload['snapshot_id'] = snap.get('snapshot_id', snapshot_id)

        # Include available columns from upload for AI SQL analytics
        cols = []
        if snap_obj and snap_obj.upload and snap_obj.upload.columns:
            cols = list(snap_obj.upload.columns)
        elif snap.get('upload_id') and snap.get('upload_id') in UPLOADS_STORE:
            cols = list(UPLOADS_STORE[snap['upload_id']].get('columns', []))
        elif snap_obj:
            sample_deal = Deal.objects.filter(snapshot=snap_obj).exclude(raw_data={}).first()
            if sample_deal and sample_deal.raw_data:
                cols = list(sample_deal.raw_data.keys())

        if not cols and snap.get('filename'):
            matching_upload = Upload.objects.filter(filename=snap['filename']).order_by('-created_at').first()
            if matching_upload and matching_upload.columns:
                cols = list(matching_upload.columns)

        payload['available_columns'] = cols

        return Response(payload)


class SnapshotMetricDetailView(APIView):
    def get(self, request, snapshot_id, metric_id):
        snap, _ = get_snapshot_for_request(snapshot_id, request)
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)

        metric_data = snap.get('all_metrics', {}).get(metric_id)
        if not metric_data:
            return Response({'code': 'not_found', 'message': 'Метрика не найдена'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'result': metric_data,
            'evidence': metric_data.get('evidence', [])
        })


class SnapshotsListView(APIView):
    def get(self, request):
        return SnapshotCreateView().get(request)


class TemplatesListView(APIView):
    """
    Returns list of available pre-made template CSV files from 'templates' folder.
    """
    def get(self, request):
        tmpl_dir = Path(__file__).resolve().parent.parent.parent.parent / 'templates'
        if not tmpl_dir.exists():
            return Response({'items': []})

        files = []
        labels = {
            'ecommerce_canonical.csv': 'Стандартный E-commerce (Канонический)',
            'ecommerce_moysklad_1c.csv': 'Выгрузка 1С / МойСклад (Товары и розница)',
            'ecommerce_marketplace.csv': 'Маркетплейсы (Wildberries / Ozon)',
            'ecommerce_messy_user_table.csv': 'Реальная таблица бизнеса (Смешанные форматы)',
            'custom_messy_slang_crm.csv': '🔥 Стресс-тест для AI-нормализатора («Баблос», «Кто тащит»)'
        }
        for p in tmpl_dir.glob('*.csv'):
            files.append({
                'id': p.name,
                'name': p.name,
                'label': labels.get(p.name, p.name),
                'size_bytes': p.stat().st_size
            })
        return Response({'items': files})


class LoadTemplateView(APIView):
    """
    Loads and runs an upload session for a chosen template CSV directly.
    """
    def post(self, request, template_id):
        tmpl_dir = Path(__file__).resolve().parent.parent.parent.parent / 'templates'
        target_file = tmpl_dir / template_id

        # Security check: ensure path stays inside templates
        if not target_file.exists() or not target_file.is_file():
            return Response({'code': 'not_found', 'message': 'Шаблон не найден'}, status=status.HTTP_404_NOT_FOUND)

        with open(target_file, 'rb') as f:
            try:
                cols, sample_rows, all_rows = read_table_file(f, target_file.name)
            except Exception as e:
                return Response({'code': 'read_error', 'message': f'Ошибка чтения шаблона: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        suggested_mapping = guess_column_mapping(cols, sample_rows)

        # AI-Fallback: if key fields or status/manager/deal_id are unmapped, let LLM resolve unmapped columns
        if not suggested_mapping.get('amount') or not suggested_mapping.get('status') or not suggested_mapping.get('manager') or not suggested_mapping.get('deal_id'):
            suggested_mapping = ai_smart_column_mapping(cols, sample_rows, suggested_mapping)

        # AI / Heuristic Status Normalization
        status_map = {}
        status_col = suggested_mapping.get('status')
        if status_col:
            unique_statuses = list(dict.fromkeys(
                str(r.get(status_col, '')).strip()
                for r in all_rows
                if str(r.get(status_col, '')).strip()
            ))
            if unique_statuses:
                status_map = ai_smart_status_mapping(unique_statuses, sample_rows)

        # Automatically derive missing computed columns (e.g. 'Скидка, % (авто)', 'Прайс до скидки (авто)')
        cols, sample_rows, all_rows, suggested_mapping, auto_computed_columns = derive_computed_columns(
            cols, sample_rows, all_rows, suggested_mapping
        )

        coverage = get_coverage(suggested_mapping, cols)
        upload_id = str(uuid.uuid4())
        ident = get_request_identity(request)

        UPLOADS_STORE[upload_id] = {
            'upload_id': upload_id,
            'user_id': ident.user.max_user_id if ident.user else None,
            'guest_session': ident.guest_session if ident.is_guest else "",
            'is_guest': ident.is_guest,
            'filename': target_file.name,
            'columns': cols,
            'sample_rows': sample_rows,
            'all_rows': all_rows,
            'mapping': suggested_mapping,
            'status_map': status_map,
            'auto_computed_columns': auto_computed_columns,
        }

        try:
            Upload.objects.create(
                id=upload_id,
                user=ident.user,
                guest_session=ident.guest_session if ident.is_guest else "",
                filename=target_file.name,
                columns=cols,
                sample_rows=sample_rows,
                all_rows=all_rows,
                suggested_mapping=suggested_mapping,
                mapping=suggested_mapping,
                status_map=status_map,
                source=Upload.Source.DEMO,
            )
        except Exception as e:
            print(f"[DB ERROR] Не удалось сохранить Upload шаблона: {e}")

        return Response({
            'upload_id': upload_id,
            'filename': target_file.name,
            'columns': cols,
            'sample_rows': sample_rows,
            'suggested_mapping': suggested_mapping,
            'coverage': coverage,
            'auto_computed_columns': auto_computed_columns,
        }, status=status.HTTP_201_CREATED)


class SnapshotChatHistoryView(APIView):
    """
    GET: Returns complete chat history from PostgreSQL/SQLite for a given snapshot.
    DELETE: Clears chat history for a snapshot.
    """
    def get(self, request, snapshot_id):
        _, snap_obj = get_snapshot_for_request(snapshot_id, request)
        if not snap_obj:
            return Response({'code': 'not_found', 'message': 'Снимок не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)

        messages_qs = ChatMessage.objects.filter(snapshot=snap_obj).order_by('created_at')
        items = []
        for m in messages_qs:
            items.append({
                'id': m.id,
                'role': m.role,
                'content': m.content,
                'tool_calls': m.tool_calls or [],
                'created_at': m.created_at.isoformat()
            })
        return Response({'messages': items})

    def delete(self, request, snapshot_id):
        _, snap_obj = get_snapshot_for_request(snapshot_id, request)
        if not snap_obj:
            return Response({'code': 'not_found', 'message': 'Снимок не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)

        ChatMessage.objects.filter(snapshot=snap_obj).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SnapshotExportExcelView(APIView):
    """
    GET /api/snapshots/<id>/export-excel
    Generates beautiful multi-sheet Excel spreadsheet with audit summary and stagnant deals registry.
    """
    def get(self, request, snapshot_id):
        _, snap = get_snapshot_for_request(snapshot_id, request)
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)

        s_id = str(snapshot_id)
        deals_qs = Deal.objects.filter(snapshot=snap)
        excel_buffer = generate_excel_report(snap, deals_qs)

        filename = f"xray_audit_{s_id[:8]}.xlsx"
        response = HttpResponse(
            excel_buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class SnapshotExportPdfView(APIView):
    """
    GET /api/snapshots/<id>/export-pdf
    Generates branded PDF audit report with health score, threats and action plan.
    """
    def get(self, request, snapshot_id):
        _, snap = get_snapshot_for_request(snapshot_id, request)
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)

        s_id = str(snapshot_id)
        deals_qs = Deal.objects.filter(snapshot=snap)
        pdf_buffer = generate_pdf_report(snap, deals_qs)

        filename = f"xray_audit_{s_id[:8]}.pdf"
        response = HttpResponse(
            pdf_buffer.getvalue(),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response



