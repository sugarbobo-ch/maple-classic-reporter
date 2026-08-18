import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Test payload 1: pageIndex, pageSize
r1 = requests.post(
    'https://maplestory.beanfun.com/api/Bulletin/FindBulletin',
    json={'pageIndex': 1, 'pageSize': 15, 'bulletinTypeId': 0},
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
    timeout=10
)
print('Payload 1 status:', r1.status_code)
d1 = r1.json()
t1 = d1.get('data', {}).get('myDataSet', {}).get('table', [])
print('Payload 1 count:', len(t1))
for item in t1[:5]:
    print(' ', item.get('bullentinId'), item.get('startDate'), item.get('title'))

# Test payload 2: official_api.py's old payload
r2 = requests.post(
    'https://maplestory.beanfun.com/api/Bulletin/FindBulletin',
    json={'pageSize': 10, 'kind': 758, 'page': 1, 'method': 6, 'toAll': 0},
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
    timeout=10
)
print('Payload 2 status:', r2.status_code)
d2 = r2.json()
t2 = d2.get('data', {}).get('myDataSet', {}).get('table', [])
print('Payload 2 count:', len(t2) if isinstance(t2, list) else 0)
