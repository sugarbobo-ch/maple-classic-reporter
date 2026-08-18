import requests
import re
import json
import sys
from maple_reporter.sanctions.parser import parse_sanction_html_table, normalize_date_str

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
# Test bids
for bid in [82428, 82421, 82407]:
    page_url = f'https://maplestory.beanfun.com/bulletin?bid={bid}'
    page_resp = session.get(page_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=10)
    match = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page_resp.text)
    token = match.group(1) if match else ''
    
    api_url = 'https://maplestory.beanfun.com/bulletin?handler=BulletinDetail'
    resp = session.post(
        api_url,
        data={'Bid': bid},
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'X-CSRF-TOKEN': token,
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': page_url,
        },
        timeout=10,
    )
    data = resp.json()
    table = data.get('data', {}).get('myDataSet', {}).get('table', {})
    title = table.get('title', '')
    pub_date = normalize_date_str(table.get('startDate', ''))
    content = table.get('content', '')
    entries = parse_sanction_html_table(content)
    print(f"BID {bid}: {pub_date} | {title} | {len(entries)} banned entries")
