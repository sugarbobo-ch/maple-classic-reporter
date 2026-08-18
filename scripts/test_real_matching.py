import requests
import re
import json
import sys
from maple_reporter.sanctions.parser import parse_sanction_html_table, normalize_date_str
from maple_reporter.sanctions.matcher import match_masked_name

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
# 1. Fetch Classic bulletin list
list_url = "https://maplestoryclassic.beanfun.com/api/Bulletin/FindBulletin"
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

all_entries = []
for bid, date, title in sanction_bids[:3]:
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
    print(f"Bid {bid} ({date}): {len(entries)} entries")
    all_entries.extend(entries)

test_names = ["下次我還要玩", "你怎麼知道", "fivefivefive", "有1.4了", "蜂王龍", "蜂小龍", "小豆子", "小麥子", "小丸子"]
print(f"\nTesting {len(test_names)} suspect names against {len(all_entries)} official banned entries:")
for name in test_names:
    matched = [e for e in all_entries if match_masked_name(name, e.masked_name)]
    if matched:
        print(f"  [BANNED] '{name}' MATCHED -> {matched[0].masked_name} ({matched[0].result})")
    else:
        print(f"  [NOT BANNED] '{name}' not found in announcements")
