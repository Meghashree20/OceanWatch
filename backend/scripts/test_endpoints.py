import requests
import json

base = 'http://127.0.0.1:8000/api/data'

print('=== TEST: GET /api/data/stats ===')
r = requests.get(f'{base}/stats')
print(f'Status: {r.status_code}')
print(f'Body: {r.json()}')

print()
print('=== TEST: GET /api/data (paginated, limit=3) ===')
r = requests.get(f'{base}?limit=3&skip=0')
d = r.json()
print(f'Status: {r.status_code}')
print(f'Total records in DB: {d["total"]}')
print(f'Records returned: {len(d["data"])}')
first_id = d['data'][0]['unique_id']
print(f'First unique_id: {first_id}')

print()
print(f'=== TEST: GET /api/data/{first_id} ===')
r = requests.get(f'{base}/{first_id}')
print(f'Status: {r.status_code}')
obs = r.json()
print(f'unique_id: {obs.get("unique_id")}')
print(f'ocean: {obs.get("ocean")}')
print(f'region: {obs.get("region")}')
print(f'measurement: {obs.get("measurement")} {obs.get("unit")}')

print()
print('=== TEST: GET /api/data?ocean=Pacific+Ocean (filter) ===')
r = requests.get(f'{base}?ocean=Pacific Ocean&limit=5')
d = r.json()
print(f'Status: {r.status_code}')
print(f'Total matching: {d["total"]}')

print()
print('=== TEST: GET /api/data?region=Asia ===')
r = requests.get(f'{base}?region=Asia&limit=5')
d = r.json()
print(f'Status: {r.status_code}')
print(f'Total matching region=Asia: {d["total"]}')

print()
print('=== TEST: GET /api/data/INVALID_ID (404 check) ===')
r = requests.get(f'{base}/INVALID_ID_99999')
print(f'Status: {r.status_code}')
print(f'Body: {r.json()}')
