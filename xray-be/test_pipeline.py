import requests
import json

base_url = 'http://127.0.0.1:8000'

# 1. Upload CSV
with open('C:/Users/mdsv/Documents/Dev/xray-business/faker/data/ecommerce_canonical.csv', 'rb') as f:
    r = requests.post(f'{base_url}/api/uploads', files={'file': ('ecommerce_canonical.csv', f, 'text/csv')})
    print('Upload status:', r.status_code)
    up_data = r.json()
    upload_id = up_data['upload_id']
    print('Suggested mapping fields:', list(up_data['suggested_mapping'].keys()))
    print('Coverage available:', up_data['coverage']['available'])

# 2. Confirm / Save Mapping
r = requests.put(f'{base_url}/api/uploads/{upload_id}/mapping', json={'mapping': up_data['suggested_mapping']})
print('Mapping save status:', r.status_code)

# 3. Create snapshot
r = requests.post(f'{base_url}/api/snapshots', json={'upload_id': upload_id})
print('Snapshot create status:', r.status_code)
snap_id = r.json()['snapshot_id']

# 4. Get Diagnosis
r = requests.get(f'{base_url}/api/snapshots/{snap_id}/diagnosis')
print('Diagnosis status:', r.status_code)
diag = r.json()
print('Findings count:', len(diag['findings']))
for item in diag['findings']:
    v = item['verdict']
    mid = item['metric_id']
    imp = item['money_impact']
    act = item['action']
    clean_act = act.encode('ascii', 'replace').decode('ascii')
    print(f"  [{v.upper()}] {mid} -> {clean_act} (impact: {imp})")

