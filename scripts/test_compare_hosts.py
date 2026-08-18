import requests
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

for host in ['https://maplestory.beanfun.com', 'https://maplestoryclassic.beanfun.com']:
    session = requests.Session()
    page_url = f"{host}/bulletin?bid=82428"
    p = session.get(page_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=10)
    match = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', p.text)
    token = match.group(1) if match else ''
    
    r = session.post(
        f"{host}/bulletin?handler=BulletinDetail",
        data={'Bid': 82428},
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'X-CSRF-TOKEN': token,
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': page_url,
            'Origin': host,
        },
        timeout=10
    )
    print(host, 'status:', r.status_code, 'resp length:', len(r.text))
