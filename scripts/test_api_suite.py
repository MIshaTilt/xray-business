"""
Automated end-to-end API test suite for X-Ray Business.
Validates all endpoints specified in DATA-API.yaml and openapi.yaml.
"""
import os
import sys
import io
import json
import time
import requests

BASE_URL = os.environ.get('API_BASE_URL', 'http://127.0.0.1:8000')

PASSED = 0
FAILED = 0


def log_test(name, success, details=""):
    global PASSED, FAILED
    if success:
        PASSED += 1
        print(f"  [PASS] {name} {details}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} - {details}")


def run_all_tests():
    print(f"\n========================================================")
    print(f"  STARTING X-RAY BUSINESS LIVE API TEST SUITE")
    print(f"  Target URL: {BASE_URL}")
    print(f"========================================================\n")

    session = requests.Session()
    session.headers.update({'x-guest-session': f'test_runner_{int(time.time())}'})

    # Test 1: GET /openapi.yaml
    try:
        r = session.get(f"{BASE_URL}/openapi.yaml", timeout=10)
        success = r.status_code == 200 and 'openapi:' in r.text
        log_test("GET /openapi.yaml (OpenAPI 3.1 Spec)", success, f"HTTP {r.status_code}, {len(r.content)} bytes")
    except Exception as e:
        log_test("GET /openapi.yaml (OpenAPI 3.1 Spec)", False, str(e))

    # Test 2: GET /DATA-API.yaml
    try:
        r = session.get(f"{BASE_URL}/DATA-API.yaml", timeout=10)
        success = r.status_code == 200 and ('DATA-API' in r.text or 'version:' in r.text)
        log_test("GET /DATA-API.yaml (Evaluation Plan)", success, f"HTTP {r.status_code}, {len(r.content)} bytes")
    except Exception as e:
        log_test("GET /DATA-API.yaml (Evaluation Plan)", False, str(e))

    # Test 3: GET /api/docs/ (Swagger UI)
    try:
        r = session.get(f"{BASE_URL}/api/docs/", timeout=10)
        success = r.status_code == 200 and 'swagger-ui' in r.text
        log_test("GET /api/docs/ (Swagger UI for Jury)", success, f"HTTP {r.status_code}")
    except Exception as e:
        log_test("GET /api/docs/ (Swagger UI for Jury)", False, str(e))

    # Test 4: GET /api/templates
    try:
        r = session.get(f"{BASE_URL}/api/templates", timeout=10)
        data = r.json()
        items = data.get('items', data.get('templates', []))
        success = r.status_code == 200 and len(items) > 0
        log_test("GET /api/templates (List Pre-built Templates)", success, f"HTTP {r.status_code}, {len(items)} templates found")
    except Exception as e:
        log_test("GET /api/templates (List Pre-built Templates)", False, str(e))

    # Test 5: POST /api/templates/ecommerce_canonical/load
    template_upload_id = None
    try:
        r = session.post(f"{BASE_URL}/api/templates/ecommerce_canonical/load", timeout=15)
        data = r.json()
        template_upload_id = data.get('upload_id')
        success = r.status_code in (200, 201) and template_upload_id is not None
        log_test("POST /api/templates/{id}/load (Load Template File)", success, f"HTTP {r.status_code}, upload_id={template_upload_id}")
    except Exception as e:
        log_test("POST /api/templates/{id}/load (Load Template File)", False, str(e))

    # Test 6: POST /api/uploads (Multipart CSV Upload)
    direct_upload_id = None
    suggested_mapping = {}
    try:
        csv_sample = (
            "ID сделки,Клиент,Менеджер,Сумма,Статус,Дата создания,Дата первого контакта,Дата закрытия\n"
            "D-101,ООО Альфа,Иванов И.,150000,Успешно реализовано,2026-08-01 10:00:00,2026-08-01 10:15:00,2026-08-10 14:00:00\n"
            "D-102,ИП Сидоров,Петров П.,75000,В работе,2026-08-02 11:00:00,2026-08-02 11:30:00,\n"
            "D-103,АО Бета,Иванов И.,320000,В работе,2026-08-03 09:00:00,2026-08-04 15:00:00,\n"
            "D-104,ООО Гамма,Смирнов С.,50000,Закрыто и не реализовано,2026-08-05 12:00:00,2026-08-05 13:00:00,2026-08-06 10:00:00\n"
        )
        files = {'file': ('test_sales.csv', io.BytesIO(csv_sample.encode('utf-8')), 'text/csv')}
        r = session.post(f"{BASE_URL}/api/uploads", files=files, timeout=10)
        data = r.json()
        direct_upload_id = data.get('upload_id')
        suggested_mapping = data.get('suggested_mapping', {})
        success = r.status_code in (200, 201) and direct_upload_id is not None
        log_test("POST /api/uploads (Multipart CSV Upload)", success, f"HTTP {r.status_code}, upload_id={direct_upload_id}, cols={len(data.get('columns', []))}")
    except Exception as e:
        log_test("POST /api/uploads (Multipart CSV Upload)", False, str(e))

    # Test 7: PUT /api/uploads/{upload_id}/mapping
    target_upload_id = direct_upload_id or template_upload_id
    try:
        r = session.put(
            f"{BASE_URL}/api/uploads/{target_upload_id}/mapping",
            json={'mapping': suggested_mapping},
            timeout=10
        )
        success = r.status_code == 200
        log_test("PUT /api/uploads/{id}/mapping (Save Column Mapping)", success, f"HTTP {r.status_code}")
    except Exception as e:
        log_test("PUT /api/uploads/{id}/mapping (Save Column Mapping)", False, str(e))

    # Test 8: POST /api/snapshots (Create Analysis Snapshot 1)
    snapshot_id_1 = None
    try:
        r = session.post(
            f"{BASE_URL}/api/snapshots",
            json={'upload_id': target_upload_id},
            timeout=25
        )
        data = r.json()
        snapshot_id_1 = data.get('snapshot_id')
        success = r.status_code == 200 and snapshot_id_1 is not None and data.get('status') == 'ready'
        log_test("POST /api/snapshots (Generate Diagnosis Snapshot 1)", success, f"HTTP {r.status_code}, snapshot_id={snapshot_id_1}")
    except Exception as e:
        log_test("POST /api/snapshots (Generate Diagnosis Snapshot 1)", False, str(e))

    # Test 9: GET /api/snapshots (List Snapshots)
    try:
        r = session.get(f"{BASE_URL}/api/snapshots", timeout=10)
        data = r.json()
        items = data.get('items', [])
        found = any(s.get('snapshot_id') == snapshot_id_1 for s in items)
        success = r.status_code == 200 and len(items) > 0 and found
        log_test("GET /api/snapshots (List Snapshots)", success, f"HTTP {r.status_code}, total={len(items)}, found_new={found}")
    except Exception as e:
        log_test("GET /api/snapshots (List Snapshots)", False, str(e))

    # Test 10: GET /api/snapshots/{snapshot_id} (Poll Status)
    try:
        r = session.get(f"{BASE_URL}/api/snapshots/{snapshot_id_1}", timeout=10)
        data = r.json()
        success = r.status_code == 200 and data.get('status') == 'ready'
        log_test("GET /api/snapshots/{id} (Poll Snapshot Status)", success, f"HTTP {r.status_code}, progress={data.get('progress')}%")
    except Exception as e:
        log_test("GET /api/snapshots/{id} (Poll Snapshot Status)", False, str(e))

    # Test 11: GET /api/snapshots/{snapshot_id}/diagnosis (Get Full Diagnosis)
    try:
        r = session.get(f"{BASE_URL}/api/snapshots/{snapshot_id_1}/diagnosis", timeout=10)
        data = r.json()
        has_headline = bool(data.get('headline'))
        has_findings = isinstance(data.get('findings'), list)
        has_totals = isinstance(data.get('totals'), dict)
        success = r.status_code == 200 and has_headline and has_findings and has_totals
        log_test("GET /api/snapshots/{id}/diagnosis (Retrieve Full Diagnosis)", success, f"HTTP {r.status_code}, findings={len(data.get('findings', []))}, deals={data.get('totals', {}).get('deals')}")
    except Exception as e:
        log_test("GET /api/snapshots/{id}/diagnosis (Retrieve Full Diagnosis)", False, str(e))

    # Test 12: GET /api/snapshots/{snapshot_id}/metrics/{metric_id} (Metric Detail)
    try:
        r = session.get(f"{BASE_URL}/api/snapshots/{snapshot_id_1}/metrics/stagnation", timeout=10)
        data = r.json()
        metric_res = data.get('result', {})
        success = r.status_code == 200 and (metric_res.get('metric_id') == 'stagnation' or 'result' in data)
        log_test("GET /api/snapshots/{id}/metrics/stagnation (Metric Detail View)", success, f"HTTP {r.status_code}, verdict={metric_res.get('verdict')}, impact={metric_res.get('money_impact')}")
    except Exception as e:
        log_test("GET /api/snapshots/{id}/metrics/stagnation (Metric Detail View)", False, str(e))

    # Test 13: Create Snapshot 2 and POST /api/snapshots/compare
    try:
        up2_id = template_upload_id
        if not up2_id:
            r_load2 = session.post(f"{BASE_URL}/api/templates/ecommerce_canonical.csv/load", timeout=15)
            up2_id = r_load2.json().get('upload_id')
        r_snap2 = session.post(f"{BASE_URL}/api/snapshots", json={'upload_id': up2_id}, timeout=25)
        snapshot_id_2 = r_snap2.json().get('snapshot_id')

        r_cmp = session.post(
            f"{BASE_URL}/api/snapshots/compare",
            json={'base_snapshot_id': snapshot_id_1, 'target_snapshot_id': snapshot_id_2},
            timeout=25
        )
        cmp_data = r_cmp.json()
        success = r_cmp.status_code in (200, 201) and ('diff_result' in cmp_data or 'changes' in cmp_data or 'summary' in cmp_data or 'status' in cmp_data)
        log_test("POST /api/snapshots/compare (Compare Two Snapshots)", success, f"HTTP {r_cmp.status_code}, comparison completed")
    except Exception as e:
        log_test("POST /api/snapshots/compare (Compare Two Snapshots)", False, str(e))

    # Test 14: GET /api/snapshots/{snapshot_id}/export-excel
    try:
        r = session.get(f"{BASE_URL}/api/snapshots/{snapshot_id_1}/export-excel", timeout=15)
        is_excel = r.status_code == 200 and len(r.content) > 1000
        log_test("GET /api/snapshots/{id}/export-excel (Download Excel Audit)", is_excel, f"HTTP {r.status_code}, {len(r.content)} bytes")
    except Exception as e:
        log_test("GET /api/snapshots/{id}/export-excel (Download Excel Audit)", False, str(e))

    # Test 15: GET /api/snapshots/{snapshot_id}/export-pdf
    try:
        r = session.get(f"{BASE_URL}/api/snapshots/{snapshot_id_1}/export-pdf", timeout=15)
        is_pdf = r.status_code == 200 and r.content.startswith(b'%PDF')
        log_test("GET /api/snapshots/{id}/export-pdf (Download PDF Report)", is_pdf, f"HTTP {r.status_code}, {len(r.content)} bytes")
    except Exception as e:
        log_test("GET /api/snapshots/{id}/export-pdf (Download PDF Report)", False, str(e))

    # Test 16: GET /api/amo (amoCRM integration status)
    try:
        r = session.get(f"{BASE_URL}/api/amo", timeout=10)
        data = r.json()
        success = r.status_code == 200 and 'connected' in data
        log_test("GET /api/amo (Check amoCRM Integration Status)", success, f"HTTP {r.status_code}, connected={data.get('connected')}")
    except Exception as e:
        log_test("GET /api/amo (Check amoCRM Integration Status)", False, str(e))

    print(f"\n--------------------------------------------------------")
    print(f"  TEST RESULTS SUMMARY:")
    print(f"  TOTAL:  {PASSED + FAILED}")
    print(f"  PASSED: {PASSED}")
    print(f"  FAILED: {FAILED}")
    print(f"--------------------------------------------------------\n")

    return 0 if FAILED == 0 else 1


if __name__ == '__main__':
    code = run_all_tests()
    sys.exit(code)
