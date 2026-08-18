import sys
import requests
import json
import re
from maple_reporter.sanctions.models import BulletinHeader, BulletinDetail, SanctionEntry
from maple_reporter.sanctions.parser import parse_sanction_html_table, normalize_date_str

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
# 1. Fetch bulletin list
list_url = "https://maplestoryclassic.beanfun.com/api/Bulletin/FindBulletin"
resp = session.post(list_url, json={"pageIndex": 1, "pageSize": 20, "bulletinTypeId": 0}, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
data = resp.json()
table = data.get("data", {}).get("myDataSet", {}).get("table", [])

headers = []
for item in table:
    title = item.get("title", "")
    if "遊戲異常行為制裁公告" in title or "制裁公告" in title:
        bid = int(item.get("bullentinId") or item.get("bulletinId"))
        pub_date = normalize_date_str(item.get("startDate", ""))
        headers.append((bid, title, pub_date))

print(f"Found {len(headers)} sanction bulletins:")
for bid, title, pub_date in headers:
    print(f"  Bid: {bid} | Date: {pub_date} | Title: {title}")

# 2. Fetch detail for the first bulletin
if headers:
    bid, title, pub_date = headers[0]
    page_url = f"https://maplestoryclassic.beanfun.com/bulletin?bid={bid}"
    p_resp = session.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    match = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', p_resp.text)
    token = match.group(1) if match else ""
    
    d_resp = session.post(
        "https://maplestoryclassic.beanfun.com/bulletin?handler=BulletinDetail",
        data={"Bid": bid},
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-CSRF-TOKEN": token,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": page_url,
        },
        timeout=10,
    )
    d_data = d_resp.json()
    content = d_data.get("data", {}).get("myDataSet", {}).get("table", {}).get("content", "")
    entries = parse_sanction_html_table(content)
    print(f"\nBulletin {bid} extracted {len(entries)} banned entries.")
    print("Sample entries:")
    for e in entries[:10]:
        print(f"  {e.masked_name} => {e.result}")
