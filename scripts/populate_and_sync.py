import json
import shutil
import time
from pathlib import Path
from maple_reporter.sanctions.repository import SanctionRepository, HISTORY_FILE, LEGACY_HISTORY_FILE
from maple_reporter.sanctions.coordinator import SanctionSyncCoordinator
from maple_reporter.sanctions.official_api import OfficialSanctionApiClient

initial_records = [
    {
        "time": "2026-08-17 22:31:36",
        "suspect_id": "EditedPlayer",
        "server": "雪吉拉",
        "map": "墮落城市",
        "url": "https://drive.google.com/file/d/edited/view",
        "status": "成功",
        "note": "剪輯後事證",
    },
    {
        "time": "2026-08-17 22:31:36",
        "suspect_id": "TestPlayer",
        "server": "雪吉拉",
        "map": "墮落城市",
        "url": "https://example.com/evidence.mp4",
        "status": "成功",
        "note": "測試檢舉",
    },
    {
        "time": "2026-08-17 22:31:36",
        "suspect_id": "TestPlayer",
        "server": "雪吉拉",
        "map": "墮落城市",
        "url": "https://example.com/evidence.mp4",
        "status": "模擬成功",
        "note": "[開發者模式] 測試檢舉",
    },
    {
        "time": "2026-08-13 21:45:10",
        "suspect_id": "下次我還要玩",
        "server": "雪吉拉",
        "map": "地鐵一號線｜地區01",
        "url": "https://drive.google.com/file/d/1lokRlggA5Ul5h4rCyO_f3UrW7pkk5gU3/view?usp=drivesdk",
        "status": "成功",
    },
    {
        "time": "2026-08-10 10:30:22",
        "suspect_id": "你怎麼知道",
        "server": "雪吉拉",
        "map": "隱密之地：幽靈船",
        "url": "https://drive.google.com/file/d/1eI1wJ_bX8Z6_xK2_b5Z_q4A2/view",
        "status": "成功",
    },
    {
        "time": "2026-08-17 19:15:05",
        "suspect_id": "fivefivefive",
        "server": "雪吉拉",
        "map": "天空之城：散步路 II",
        "url": "https://drive.google.com/file/d/1vC3zY_wA1B2_cD4_eF6_gH8/view",
        "status": "成功",
    },
    {
        "time": "2026-08-17 18:02:40",
        "suspect_id": "有1.4了",
        "server": "雪吉拉",
        "map": "南部森林訓練場 I",
        "url": "https://drive.google.com/file/d/1pL9kM_nO3P4_qR5_sT7_uV9/view",
        "status": "成功",
    },
]

repo = SanctionRepository()
repo.save_history(initial_records)

api_client = OfficialSanctionApiClient(random_delay_func=lambda a, b: 0.05)
coordinator = SanctionSyncCoordinator(repository=repo, api_client=api_client)

coordinator.start(trigger='manual')
while coordinator.get_status().running:
    time.sleep(0.5)

records = repo.load_history()
print(f"Sync complete. Total {len(records)} records.")
for r in records:
    print(f"  {r.get('suspect_id', ''):15s} | status={r.get('ban_status', ''):10s} | ban_date={r.get('ban_date')} | mask={r.get('ban_masked_name')}")

if HISTORY_FILE.is_file():
    shutil.copy2(HISTORY_FILE, LEGACY_HISTORY_FILE)
