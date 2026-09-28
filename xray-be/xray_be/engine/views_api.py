import os
import io
import json
import uuid
import datetime
from decimal import Decimal
from django.conf import settings
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.http import JsonResponse, HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from engine.parsers import read_table_file
from engine.mapping import guess_column_mapping, derive_computed_columns, CANONICAL_FIELDS
from pathlib import Path
from engine.normalizer import normalize_records
from engine.analyzer import calculate_metrics_and_findings
from engine.narrator import filename_to_title, generate_llm_narrative
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


def snapshot_model_to_dict(snap_obj: Snapshot) -> dict:
    s_key = str(snap_obj.id)
    owner_uid = snap_obj.user.max_user_id if snap_obj.user else None
    is_guest = snap_obj.is_guest
    guest_sess = snap_obj.guest_session or ""
    is_cmp = (snap_obj.archetype == 'comparison') or (isinstance(snap_obj.quality, dict) and snap_obj.quality.get('item_type') == 'comparison')
    q = snap_obj.quality or {}
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
        'card_title': q.get('card_title', ''),
    }
    return {
        'snapshot_id': s_key,
        'item_type': 'comparison' if is_cmp else 'snapshot',
        'compare_base_id': q.get('compare_base_id'),
        'compare_target_id': q.get('compare_target_id'),
        'diff_result': q.get('diff_result'),
        'user_id': owner_uid,
        'guest_session': guest_sess,
        'is_guest': is_guest,
        'scan_no': snap_obj.scan_no,
        'status': snap_obj.status,
        'progress': snap_obj.progress,
        'error': snap_obj.error,
        'created_at': snap_obj.created_at.isoformat() if snap_obj.created_at else "",
        'filename': snap_obj.filename,
        'source': 'comparison' if is_cmp else snap_obj.archetype,
        'card_title': q.get('card_title', snap_obj.filename),
        'headline': snap_obj.headline,
        'body': snap_obj.body,
        'verdict': 'ok' if q.get('trend') == 'improved' else 'watch',
        'total_saved_money': q.get('total_saved_money', 0),
        'diagnosis': diag,
        'all_metrics': snap_obj.all_metrics,
    }


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
        snap_dict = snapshot_model_to_dict(snap_obj)
        SNAPSHOTS_STORE[s_key] = snap_dict

    return snap_dict, snap_obj


def persist_upload_mapping(upload_id, mapping: dict, status_map: dict) -> None:
    try:
        Upload.objects.filter(pk=str(upload_id)).update(mapping=mapping, status_map=status_map)
    except Exception as e:
        print(f"[DB ERROR] Не удалось обновить mapping: {e}")


_forgotten_ids: set[str] = set()


def _is_forgotten(key, snap) -> bool:
    key = str(key)
    if key in _forgotten_ids:
        return True
    if not isinstance(snap, dict):
        return False
    sid = str(snap.get('snapshot_id') or '')
    if sid and sid in _forgotten_ids:
        return True
    for field in ('compare_base_id', 'compare_target_id'):
        ref = str(snap.get(field) or '')
        if ref and ref in _forgotten_ids:
            return True
    return False


def load_disk_store():
    global SNAPSHOTS_STORE
    loaded = {}
    if STORE_FILE.exists():
        try:
            with open(STORE_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
        except Exception:
            loaded = {}
    if not isinstance(loaded, dict):
        loaded = {}
    cleaned = {}
    dropped = False
    for key, snap in loaded.items():
        if _is_forgotten(key, snap):
            dropped = True
            continue
        cleaned[key] = snap
    SNAPSHOTS_STORE = cleaned
    if dropped:
        save_disk_store()

def save_disk_store():
    try:
        STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STORE_FILE.with_suffix('.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(SNAPSHOTS_STORE, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STORE_FILE)
    except Exception as e:
        print(f"[STORE ERROR] Не удалось сохранить на диск: {e}")


def forget_snapshot(snapshot_id) -> None:
    """Удаляет снимок и сравнения, которые на него ссылаются, из памяти, файла и базы."""
    s_id = str(snapshot_id)
    _forgotten_ids.add(s_id)
    doomed = []
    for key, snap in list(SNAPSHOTS_STORE.items()):
        if not isinstance(snap, dict):
            continue
        if key == s_id or str(snap.get('snapshot_id') or '') == s_id:
            doomed.append(key)
            continue
        if str(snap.get('compare_base_id') or '') == s_id or str(snap.get('compare_target_id') or '') == s_id:
            doomed.append(key)
    ids = {s_id}
    for key in doomed:
        snap = SNAPSHOTS_STORE.pop(key, None) or {}
        ids.add(str(key))
        _forgotten_ids.add(str(key))
        if snap.get('snapshot_id'):
            sid = str(snap['snapshot_id'])
            ids.add(sid)
            _forgotten_ids.add(sid)
    Snapshot.objects.filter(id__in=list(ids)).delete()
    save_disk_store()

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


def snapshot_card(snap: dict) -> dict:
    if snap.get('item_type') == 'comparison' or snap.get('source') == 'comparison':
        diag = snap.get('diagnosis') or {}
        return {
            'snapshot_id': snap['snapshot_id'],
            'item_type': 'comparison',
            'compare_base_id': snap.get('compare_base_id'),
            'compare_target_id': snap.get('compare_target_id'),
            'scan_no': snap.get('scan_no'),
            'status': snap.get('status', 'ready'),
            'created_at': snap['created_at'],
            'filename': snap.get('filename'),
            'source': 'comparison',
            'period': diag.get('period') if isinstance(diag, dict) else None,
            'headline': snap.get('headline') or (diag.get('headline') if isinstance(diag, dict) else ''),
            'card_title': snap.get('card_title') or (diag.get('card_title') if isinstance(diag, dict) else '') or snap.get('filename'),
            'topics': snap.get('topics', []),
            'verdict': snap.get('verdict', 'ok'),
            'total_saved_money': snap.get('total_saved_money', 0),
            'coverage_ready': 7,
            'coverage_total': 7,
        }

    diag = snap.get('diagnosis')
    crit = 'ok'
    topics = []
    if diag and diag.get('findings'):
        v_set = {f['verdict'] for f in diag['findings']}
        if 'critical' in v_set:
            crit = 'critical'
        elif 'watch' in v_set:
            crit = 'watch'
        ranked = [f for f in diag['findings'] if f.get('verdict') in ('critical', 'watch')]
        ranked.sort(key=lambda item: 0 if item.get('verdict') == 'critical' else 1)
        for finding in ranked:
            metric_id = finding.get('metric_id')
            if metric_id and metric_id not in topics:
                topics.append(metric_id)
            if len(topics) == 2:
                break
    coverage = diag.get('coverage') if isinstance(diag, dict) else None
    available = coverage.get('available') if isinstance(coverage, dict) else None
    coverage_ready = len(available) if isinstance(available, list) else 0
    return {
        'snapshot_id': snap['snapshot_id'],
        'item_type': 'snapshot',
        'scan_no': snap.get('scan_no'),
        'status': snap['status'],
        'created_at': snap['created_at'],
        'filename': snap['filename'],
        'source': snap['source'],
        'period': diag.get('period') if diag else None,
        'headline': diag.get('headline') if diag else None,
        'card_title': ((diag.get('card_title') if diag else None) or '').strip()
        or filename_to_title(snap.get('filename') or ''),
        'topics': topics,
        'verdict': crit,
        'coverage_ready': coverage_ready,
        'coverage_total': 7,
    }


class SnapshotCreateView(APIView):
    def get(self, request):
        cleanup_expired_guest_data()
        ensure_scan_numbers()
        ident = get_request_identity(request)
        items = []

        # Sync any snapshots from DB for this user/guest missing from in-memory cache
        qs = Snapshot.objects.all()
        if ident.user:
            qs = qs.filter(user=ident.user)
        elif ident.is_guest and ident.guest_session:
            qs = qs.filter(is_guest=True, guest_session=ident.guest_session)
        else:
            qs = Snapshot.objects.none()

        for db_snap in qs:
            db_key = str(db_snap.id)
            if db_key in _forgotten_ids:
                continue
            if db_key not in SNAPSHOTS_STORE:
                SNAPSHOTS_STORE[db_key] = snapshot_model_to_dict(db_snap)

        matching_snaps = []
        for snap in SNAPSHOTS_STORE.values():
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

            matching_snaps.append(snap)

        # Sort descending by scan_no or created_at
        matching_snaps.sort(
            key=lambda s: (int(s.get('scan_no') or 0), str(s.get('created_at') or '')),
            reverse=True,
        )

        known_ids = {str(snap.get('snapshot_id') or '') for snap in matching_snaps}
        for snap in matching_snaps:
            if snap.get('item_type') == 'comparison' or snap.get('source') == 'comparison':
                base_id = str(snap.get('compare_base_id') or '')
                target_id = str(snap.get('compare_target_id') or '')
                if base_id not in known_ids or target_id not in known_ids:
                    continue
            items.append(snapshot_card(snap))

        response = Response({'items': items, 'next_cursor': None})
        response['Cache-Control'] = 'no-store'
        return response

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
        headline, findings, card_title = generate_llm_narrative(findings, headline, upload['filename'])
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
                'card_title': card_title,
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
                quality={'card_title': card_title} if card_title else {},
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
        forget_snapshot(snapshot_id)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response['Cache-Control'] = 'no-store'
        return response


class SnapshotDiagnosisView(APIView):
    def get(self, request, snapshot_id):
        snap, snap_obj = get_snapshot_for_request(snapshot_id, request)
        if not snap:
            return Response({'code': 'not_found', 'message': 'Снимок не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)
        ensure_scan_numbers()
        payload = dict(snap.get('diagnosis') or {})
        payload['scan_no'] = snap.get('scan_no')
        payload['snapshot_id'] = snap.get('snapshot_id', snapshot_id)
        payload['item_type'] = snap.get('item_type', 'snapshot')
        payload['compare_base_id'] = snap.get('compare_base_id')
        payload['compare_target_id'] = snap.get('compare_target_id')

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

        response = Response(payload)
        response['Cache-Control'] = 'no-store'
        return response


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
            'b2b_sales_before.csv': '🏢 [1/2 Срез ДО] B2B Услуги: Зависшие сделки и скидки',
            'b2b_sales_after.csv': '🚀 [2/2 Срез ПОСЛЕ] B2B Услуги: Наведение порядка и РОП',
            'retail_q1_before.csv': '🛒 [1/2 Срез ДО] Ритейл: Долгий ответ и брошенные заказы',
            'retail_q2_after.csv': '⚡ [2/2 Срез ПОСЛЕ] Ритейл: Быстрое подтверждение и рост',
            'ecommerce_canonical.csv': 'Стандартный E-commerce (Канонический)',
            'ecommerce_moysklad_1c.csv': 'Выгрузка 1С / МойСклад (Товары и розница)',
            'ecommerce_marketplace.csv': 'Маркетплейсы (Wildberries / Ozon)',
            'ecommerce_messy_user_table.csv': 'Реальная таблица бизнеса (Смешанные форматы)',
            'custom_messy_slang_crm.csv': '🔥 Стресс-тест для AI-нормализатора («Баблос», «Кто тащит»)',
        }
        order = [
            'b2b_sales_before.csv',
            'b2b_sales_after.csv',
            'retail_q1_before.csv',
            'retail_q2_after.csv',
            'ecommerce_canonical.csv',
            'ecommerce_moysklad_1c.csv',
            'ecommerce_marketplace.csv',
            'ecommerce_messy_user_table.csv',
            'custom_messy_slang_crm.csv',
        ]
        for p in tmpl_dir.glob('*.csv'):
            files.append({
                'id': p.name,
                'name': p.name,
                'label': labels.get(p.name, p.name),
                'size_bytes': p.stat().st_size
            })
        files.sort(key=lambda x: order.index(x['id']) if x['id'] in order else 99)
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
            snap_obj = Snapshot.objects.filter(id=str(snapshot_id)).first()
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
            snap_obj = Snapshot.objects.filter(id=str(snapshot_id)).first()
            if not snap_obj:
                return Response({'code': 'not_found', 'message': 'Снимок не найден или срок действия истек'}, status=status.HTTP_404_NOT_FOUND)

        ChatMessage.objects.filter(snapshot=snap_obj).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatListView(APIView):
    """Список чатов по снимкам текущего пользователя, чтобы переключаться между диалогами."""

    def get(self, request):
        cleanup_expired_guest_data()
        ident = get_request_identity(request)
        qs = Snapshot.objects.filter(status=Snapshot.Status.READY)
        if ident.user:
            qs = qs.filter(user=ident.user)
        elif ident.guest_session:
            qs = qs.filter(is_guest=True, guest_session=ident.guest_session)
        else:
            qs = Snapshot.objects.none()

        last_content = (
            ChatMessage.objects.filter(snapshot_id=OuterRef("pk"))
            .exclude(role=ChatMessage.Role.SYSTEM)
            .order_by("-created_at")
            .values("content")[:1]
        )
        last_at = (
            ChatMessage.objects.filter(snapshot_id=OuterRef("pk"))
            .exclude(role=ChatMessage.Role.SYSTEM)
            .order_by("-created_at")
            .values("created_at")[:1]
        )
        qs = qs.annotate(
            message_count=Count("messages", filter=~Q(messages__role=ChatMessage.Role.SYSTEM)),
            last_message=Subquery(last_content),
            last_at=Subquery(last_at),
        ).order_by(F("last_at").desc(nulls_last=True), "-created_at")

        items = []
        for snap in qs[:50]:
            preview = str(snap.last_message or "").replace("\n", " ").strip()
            if len(preview) > 140:
                preview = preview[:137] + "…"
            title = (snap.headline or "").strip() or filename_to_title(snap.filename or "") or "Снимок"
            items.append(
                {
                    "snapshot_id": str(snap.id),
                    "title": title,
                    "filename": snap.filename or "",
                    "created_at": snap.created_at.isoformat(),
                    "message_count": int(snap.message_count or 0),
                    "last_message": preview,
                    "last_at": snap.last_at.isoformat() if snap.last_at else None,
                }
            )
        return Response({"items": items})


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


def snapshot_from_store_dict(snap: dict) -> Snapshot:
    diag = snap.get('diagnosis') if isinstance(snap.get('diagnosis'), dict) else {}
    created = snap.get('created_at')
    when = None
    if isinstance(created, str) and created:
        try:
            when = datetime.datetime.fromisoformat(created)
        except ValueError:
            when = None
    if when is not None and when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    obj = Snapshot(
        id=snap.get('snapshot_id'),
        filename=snap.get('filename') or '',
        headline=diag.get('headline') or snap.get('headline') or '',
        body=diag.get('body') or snap.get('body') or '',
        findings=diag.get('findings') or [],
        coverage=diag.get('coverage') or {},
        totals=diag.get('totals') or snap.get('totals') or {},
        all_metrics=snap.get('all_metrics') or {},
        status=snap.get('status') or Snapshot.Status.READY,
        is_guest=bool(snap.get('is_guest')),
        guest_session=snap.get('guest_session') or '',
    )
    if when is not None:
        obj.created_at = when
    return obj


def cached_comparison(id_a: str, id_b: str) -> dict | None:
    for left, right in ((str(id_a), str(id_b)), (str(id_b), str(id_a))):
        try:
            cmp_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"comparison:{left}:{right}")
        except ValueError:
            continue
        s_cmp_id = str(cmp_id)
        stored = SNAPSHOTS_STORE.get(s_cmp_id)
        if isinstance(stored, dict) and isinstance(stored.get('diff_result'), dict):
            cached = dict(stored['diff_result'])
            cached['comparison_id'] = s_cmp_id
            return cached
        existing = Snapshot.objects.filter(id=cmp_id).first()
        if existing and isinstance(existing.quality, dict) and isinstance(existing.quality.get('diff_result'), dict):
            cached = dict(existing.quality['diff_result'])
            cached['comparison_id'] = s_cmp_id
            return cached
    return None


class SnapshotCompareView(APIView):
    """
    GET /api/snapshots/compare?base_id=<uuid>&target_id=<uuid>
    Compares two snapshots (Before vs After) for the authenticated user / guest session.
    """
    def get(self, request):
        cleanup_expired_guest_data()
        base_id = request.query_params.get('base_id')
        target_id = request.query_params.get('target_id')

        if not base_id or not target_id:
            return Response(
                {'code': 'bad_request', 'message': 'Требуются параметры base_id и target_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        base_dict, snap1 = get_snapshot_for_request(base_id, request)
        target_dict, snap2 = get_snapshot_for_request(target_id, request)

        if not base_dict or not target_dict:
            return Response(
                {'code': 'not_found', 'message': 'Снимок не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        id_a = str(base_dict.get('snapshot_id') or base_id)
        id_b = str(target_dict.get('snapshot_id') or target_id)
        cached = cached_comparison(id_a, id_b)
        if cached:
            response = Response(cached, status=status.HTTP_200_OK)
            response['Cache-Control'] = 'no-store'
            return response

        if snap1 is None:
            snap1 = snapshot_from_store_dict(base_dict)
        if snap2 is None:
            snap2 = snapshot_from_store_dict(target_dict)

        # Determine chronological base and target
        if snap1.created_at <= snap2.created_at:
            base_snap, target_snap = snap1, snap2
        else:
            base_snap, target_snap = snap2, snap1

        cmp_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"comparison:{base_snap.id}:{target_snap.id}")
        s_cmp_id = str(cmp_uuid)

        # 1. Fast Cache Check: return instantly if already calculated!
        existing_snap = Snapshot.objects.filter(id=cmp_uuid).first()
        if existing_snap and existing_snap.quality and isinstance(existing_snap.quality, dict):
            cached_diff = existing_snap.quality.get('diff_result')
            if cached_diff and isinstance(cached_diff, dict):
                cached_diff['comparison_id'] = s_cmp_id
                return Response(cached_diff, status=status.HTTP_200_OK)

        if s_cmp_id in SNAPSHOTS_STORE and isinstance(SNAPSHOTS_STORE[s_cmp_id].get('diff_result'), dict):
            cached_diff = dict(SNAPSHOTS_STORE[s_cmp_id]['diff_result'])
            cached_diff['comparison_id'] = s_cmp_id
            return Response(cached_diff, status=status.HTTP_200_OK)

        from engine.comparator import compare_snapshots
        try:
            diff_result = compare_snapshots(snap1, snap2)

            # Save comparison snapshot in store and DB so it persists in scan history
            ident = get_request_identity(request)

            base_title = (base_snap.filename or 'Срез 1').replace('.csv', '')
            target_title = (target_snap.filename or 'Срез 2').replace('.csv', '')
            cmp_title = f"{base_title} ➔ {target_title}"

            scan_no = existing_snap.scan_no if (existing_snap and existing_snap.scan_no) else next_scan_no()

            trend = diff_result.get('summary', {}).get('trend', 'improved')
            verdict = 'ok' if trend == 'improved' else 'watch'
            saved_money = diff_result.get('total_saved_money', 0)

            cmp_obj, _ = Snapshot.objects.update_or_create(
                id=cmp_uuid,
                defaults={
                    'user': ident.user,
                    'upload': target_snap.upload,
                    'scan_no': scan_no,
                    'guest_session': ident.guest_session if ident.is_guest else "",
                    'is_guest': ident.is_guest,
                    'filename': cmp_title,
                    'archetype': 'comparison',
                    'headline': diff_result.get('summary', {}).get('headline', ''),
                    'body': diff_result.get('summary', {}).get('body', ''),
                    'findings': [],
                    'coverage': {'available': [m['metric_id'] for m in diff_result.get('metrics_diff', [])], 'skipped': []},
                    'totals': diff_result.get('totals_diff', {}),
                    'all_metrics': {m['metric_id']: m for m in diff_result.get('metrics_diff', [])},
                    'quality': {
                        'item_type': 'comparison',
                        'compare_base_id': str(base_snap.id),
                        'compare_target_id': str(target_snap.id),
                        'base_filename': base_snap.filename,
                        'target_filename': target_snap.filename,
                        'card_title': f"⚡ {cmp_title}",
                        'total_saved_money': saved_money,
                        'trend': trend,
                        'diff_result': diff_result,
                    }
                }
            )

            # Store in SNAPSHOTS_STORE
            SNAPSHOTS_STORE[s_cmp_id] = {
                'snapshot_id': s_cmp_id,
                'item_type': 'comparison',
                'compare_base_id': str(base_snap.id),
                'compare_target_id': str(target_snap.id),
                'diff_result': diff_result,
                'user_id': ident.user.max_user_id if ident.user else None,
                'guest_session': ident.guest_session if ident.is_guest else "",
                'is_guest': ident.is_guest,
                'scan_no': scan_no,
                'status': 'ready',
                'progress': 100,
                'error': '',
                'created_at': cmp_obj.created_at.isoformat(),
                'filename': cmp_title,
                'source': 'comparison',
                'card_title': f"⚡ {cmp_title}",
                'headline': diff_result.get('summary', {}).get('headline', ''),
                'body': diff_result.get('summary', {}).get('body', ''),
                'verdict': verdict,
                'total_saved_money': saved_money,
                'totals': diff_result.get('totals_diff', {}),
                'all_metrics': {m['metric_id']: m for m in diff_result.get('metrics_diff', [])},
                'diagnosis': {
                    'snapshot_id': s_cmp_id,
                    'card_title': f"⚡ {cmp_title}",
                    'headline': diff_result.get('summary', {}).get('headline', ''),
                    'body': diff_result.get('summary', {}).get('body', ''),
                    'findings': [],
                    'coverage': {'available': [m['metric_id'] for m in diff_result.get('metrics_diff', [])], 'skipped': []},
                    'totals': diff_result.get('totals_diff', {}),
                }
            }
            save_disk_store()

            diff_result['comparison_id'] = s_cmp_id
            return Response(diff_result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'code': 'comparison_error', 'message': f'Ошибка сравнения снимков: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




