import sys
import requests
import json
import re
from maple_reporter.sanctions.parser import parse_sanction_html_table, normalize_date_str
from maple_reporter.sanctions.matcher import match_masked_name

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
# 1. Fetch all sanction bulletins across first 5 pages
all_headers = []
for page in range(1, 10):
    url = "https://maplestoryclassic.beanfun.com/api/Bulletin/FindBulletin"
    resp = session.post(url, json={"pageIndex": page, "pageSize": 30, "bulletinTypeId": 0}, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    data = resp.json()
    table = data.get("data", {}).get("myDataSet", {}).get("table", [])
    if not table:
        break
    for item in table:
        title = item.get("title", "")
        if "遊戲異常行為制裁公告" in title or "制裁公告" in title or "懲處名單" in title or "異常公告" in title:
            bid = int(item.get("bullentinId") or item.get("bulletinId"))
            pub_date = normalize_date_str(item.get("startDate", ""))
            all_headers.append((bid, pub_date, title))

print(f"Discovered {len(all_headers)} sanction bulletins across pages:")
for bid, pub_date, title in all_headers:
    print(f"  Bid: {bid} | Date: {pub_date} | Title: {title}")

# 2. Fetch all details for these bulletins
all_entries_by_bid = {}
for bid, pub_date, title in all_headers:
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
    if d_resp.status_code == 200:
        d_json = d_resp.json()
        content = d_json.get("data", {}).get("myDataSet", {}).get("table", {}).get("content", "")
        entries = parse_sanction_html_table(content)
        all_entries_by_bid[bid] = (pub_date, title, entries)
        print(f"  Loaded Bid {bid} ({pub_date}): {len(entries)} entries")

# 3. Check suspect targets
suspects = ["FGqwec", "牛上天了", "xzcjlka", "伯瓦尔弗塔根", "下次我還要玩", "你怎麼知道", "fivefivefive", "有1.4了", "dsaxsa"]
print("\n--- Matching Analysis ---")
for suspect in suspects:
    found_matches = []
    for bid, (pub_date, title, entries) in all_entries_by_bid.items():
        for e in entries:
            # Check exact match
            if match_masked_name(suspect, e.masked_name):
                found_matches.append((pub_date, bid, e.masked_name, e.result, "exact_mask"))
            # Also check case-insensitive match or substring / pattern variations
            elif len(suspect) == len(e.masked_name) and suspect.lower()[0] == e.masked_name.lower()[0] and suspect.lower()[-1] == e.masked_name.lower()[-1]:
                found_matches.append((pub_date, bid, e.masked_name, e.result, "fuzzy_case"))
            elif suspect in e.masked_name or e.masked_name.replace("*", "") in suspect:
                # check partial
                cleaned_mask = e.masked_name.replace("*", "")
                if len(cleaned_mask) >= 2 and cleaned_mask in suspect:
                    found_matches.append((pub_date, bid, e.masked_name, e.result, "partial_char_match"))

    if found_matches:
        print(f"Suspect '{suspect}':")
        for m in found_matches:
            print(f"  => {m[0]} (Bid {m[1]}): {m[2]} [{m[3]}] (type: {m[4]})")
    else:
        print(f"Suspect '{suspect}': NO MATCH FOUND")
