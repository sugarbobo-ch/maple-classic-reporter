import sys
import json
import shutil
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
from maple_reporter.sanctions.repository import SanctionRepository, HISTORY_FILE, LEGACY_HISTORY_FILE
from maple_reporter.sanctions.coordinator import SanctionSyncCoordinator
from maple_reporter.sanctions.official_api import OfficialSanctionApiClient

user_authentic_records = [
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
    {
        "time": "2026-08-07 21:42:42",
        "suspect_id": "FGqwec",
        "server": "雪吉拉",
        "map": "弓箭手村東部草叢",
        "url": "https://drive.google.com/file/d/1lokRlggA5Ul5h4rCyO_f3UrW7pkk5gU3/view?usp=drivesdk",
        "status": "成功",
    },
    {
        "time": "2026-08-07 21:34:30",
        "suspect_id": "FGqwec",
        "server": "雪吉拉",
        "map": "弓箭手村東部草叢",
        "url": "https://drive.google.com/file/d/1QUCdq911gyfVpgEnFV_hJgY9i0Hubvak/view?usp=drivesdk",
        "status": "成功",
    },
    {
        "time": "2026-08-02 18:06:07",
        "suspect_id": "牛上天了",
        "server": "雪吉拉",
        "map": "魔法森林北郊",
        "url": "https://drive.google.com/file/d/1xAfKMprboe4k1Aybh_fvLtWUjSxnhNKP/view?usp=drivesdk",
        "status": "成功",
    },
    {
        "time": "2026-08-01 20:11:49",
        "suspect_id": "xzcjlka",
        "server": "雪吉拉",
        "map": "南部森林訓練場 I",
        "url": "https://drive.google.com/file/d/10XmxhY02TqXOFnIGRTjYXwcaUwEypYxS/view?usp=drivesdk",
        "status": "成功",
    },
    {
        "time": "2026-08-01 20:08:47",
        "suspect_id": "dsaxsa",
        "server": "雪吉拉",
        "map": "南部森林訓練場 I",
        "url": "https://drive.google.com/file/d/1hKE2cjzAb172kzUeIGiQSVCqcoAGefUy/view?usp=drivesdk",
        "status": "成功",
    },
    {
        "time": "2026-08-01 19:44:09",
        "suspect_id": "伯瓦尔弗塔根",
        "server": "雪吉拉",
        "map": "魔法森林北郊",
        "url": "https://drive.google.com/file/d/1lPlN09F3Ugnhg1zp5mazeluFK7XDd4zs/view?usp=drivesdk",
        "status": "成功",
    },
    {
        "time": "2026-08-01 15:08:49",
        "suspect_id": "伯瓦尔弗塔根",
        "server": "雪吉拉",
        "map": "維多利亞：魔法森林北郊",
        "url": "https://drive.google.com/file/d/1VXyQ1LLtjVgdwCG_Y5ngPi-HmeYZxSIJ/view?usp=drivesdk",
        "status": "成功",
    },
]

repo = SanctionRepository()
repo.save_history(user_authentic_records)

api_client = OfficialSanctionApiClient(random_delay_func=lambda a, b: 0.05)
coordinator = SanctionSyncCoordinator(repository=repo, api_client=api_client)

coordinator.start(trigger='manual')
while coordinator.get_status().running:
    time.sleep(0.5)

records = repo.load_history()
print(f"Successfully restored and synchronized {len(records)} records:")
for r in records:
    print(f"  {r.get('time')} | {r.get('suspect_id'):15s} | server={r.get('server')} | status={r.get('ban_status', ''):10s} | mask={r.get('ban_masked_name')}")

if HISTORY_FILE.is_file():
    shutil.copy2(HISTORY_FILE, LEGACY_HISTORY_FILE)
    print("Copied to LEGACY_HISTORY_FILE successfully.")
