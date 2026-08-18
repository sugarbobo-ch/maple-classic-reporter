import requests
import re
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
url = 'https://maplestory.beanfun.com/bulletin?bid=82428'
page = session.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=10)
match = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page.text)
token = match.group(1) if match else ''
print('CSRF token found:', bool(token))

post_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'X-CSRF-TOKEN': token,
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': 'https://maplestory.beanfun.com',
    'Referer': url,
}

res = session.post(
    'https://maplestory.beanfun.com/bulletin?handler=BulletinDetail',
    data={'Bid': 82428},
    headers=post_headers,
    timeout=10,
)
print('Response status:', res.status_code)
if res.status_code == 200:
    data = res.json()
    table = data.get('data', {}).get('myDataSet', {}).get('table', {})
    print('Title:', table.get('title'))
    content = table.get('content', '')
    print('Content preview:', content[:300])
