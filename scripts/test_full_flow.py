import requests
import re
import json
import sys
from maple_reporter.sanctions.parser import parse_sanction_html_table, normalize_date_str

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
list_url = "https://maplestory.beanfun.com/api/Bulletin/FindBulletin"
r = session.post(list_url, json={"pageIndex": 1, "pageSize": 30, "bulletinTypeId": 0}, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
data = r.json()
table = data.get("data", {}).get("myDataSet", {}).get("table", [])

sanction_bids = []
for item in table:
    title = item.get("title", "")
    if "遊戲異常行為制裁公告" in title:
        bid = int(item.get("bullentinId"))
        date = normalize_date_str(item.get("startDate", ""))
        sanction_bids.append((bid, date, title))

print(f"Total sanction bulletins found: {len(sanction_bids)}")
for bid, date, title in sanction_bids:
    print(f"  {date} [Bid {bid}]: {title}")

# Fetch the latest bulletin detail
if sanction_bids:
    bid, date, title = sanction_bids[0]
    page_url = f"https://maplestory.beanfun.com/bulletin?bid={bid}"
    p_resp = session.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    match = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', p_resp.text)
    token = match.group(1) if match else ""
    
    d_resp = session.post(
        "https://maplestory.beanfun.com/bulletin?handler=BulletinDetail",
        data={"Bid": bid},
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-CSRF-TOKEN": token,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": page_url,
            "Origin": "https://maplestory.beanfun.com",
        },
        timeout=15,
    )
    d_json = d_resp.json()
    content = d_json.get("data", {}).get("myDataSet", {}).get("table", {}).get("content", "")
    entries = parse_sanction_html_table(content)
    print(f"\nExtracted {len(entries)} banned entries from latest bulletin.")
    print("Sample 5 entries:")
    for e in entries[:5]:
        print(f"  ID: {e.masked_name} | Result: {e.result}")
