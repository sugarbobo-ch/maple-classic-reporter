import sys
import requests
import json
import re
from maple_reporter.sanctions.parser import parse_sanction_html_table, normalize_date_str
from maple_reporter.sanctions.matcher import match_masked_name, find_matching_bulletin
from maple_reporter.sanctions.models import BulletinDetail, SanctionEntry

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()

# The real sanction bulletin Bids discovered from Beanfun
bulletin_list = [
    (82428, "2026-08-17", "0817(一)遊戲異常行為制裁公告"),
    (82421, "2026-08-14", "0814(五)遊戲異常行為制裁公告"),
    (82407, "2026-08-13", "0813(四)遊戲異常行為制裁公告"),
    (82363, "2026-08-10", "0810(一)遊戲異常行為制裁公告"),
    (82351, "2026-08-08", "0807(五)遊戲異常行為制裁公告"),
    (82325, "2026-08-05", "0805(三)遊戲異常行為制裁公告"),
    (82309, "2026-08-04", "0804(二)遊戲異常行為制裁公告"),
    (82289, "2026-08-03", "0803(一)遊戲異常行為制裁公告"),
]

bulletin_details = []

for bid, pub_date, title in bulletin_list:
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
        b_detail = BulletinDetail(
            bid=bid,
            publication_date=pub_date,
            title=title,
            url=f"https://maplestoryclassic.beanfun.com/bulletin?Bid={bid}",
            fetched_at="2026-08-17T23:00:00+08:00",
            entries=tuple(entries),
        )
        bulletin_details.append(b_detail)
        print(f"Loaded Bid {bid} ({pub_date}): {len(entries)} entries")

# Now check each suspect with their actual report date!
test_cases = [
    ("FGqwec", "2026-08-07"),
    ("牛上天了", "2026-08-02"),
    ("xzcjlka", "2026-08-01"),
    ("dsaxsa", "2026-08-01"),
    ("伯瓦尔弗塔根", "2026-08-01"),
    ("下次我還要玩", "2026-08-13"),
    ("你怎麼知道", "2026-08-10"),
    ("fivefivefive", "2026-08-17"),
    ("有1.4了", "2026-08-17"),
]

print("\n--- Matching Results ---")
for suspect, r_date in test_cases:
    # 1. Check find_matching_bulletin
    match = find_matching_bulletin(suspect, r_date, bulletin_details)
    if match:
        print(f"MATCH: '{suspect}' (reported {r_date}) -> {match.bulletin.publication_date} (Bid {match.bulletin.bid}) {match.entry.masked_name} [{match.entry.result}]")
    else:
        # Check why no match: search all bulletins for any partial or similar mask
        print(f"NO MATCH: '{suspect}' (reported {r_date})")
        for b in bulletin_details:
            for e in b.entries:
                # Check if same length and same first/last char
                if len(e.masked_name) == len(suspect) and e.masked_name[0] == suspect[0]:
                    print(f"   Potential mask in {b.publication_date} (Bid {b.bid}): {e.masked_name} vs {suspect}")
