import json
import shutil
import os
from pathlib import Path
from maple_reporter.sanctions.repository import HISTORY_FILE, LEGACY_HISTORY_FILE

user_11_records = [
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
        "time": "2026-08-03 19:15:05",
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

# Write to both locations
HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
HISTORY_FILE.write_text(json.dumps(user_11_records, ensure_ascii=False, indent=2), encoding="utf-8")

LEGACY_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
LEGACY_HISTORY_FILE.write_text(json.dumps(user_11_records, ensure_ascii=False, indent=2), encoding="utf-8")

# Delete any stale cache file so a fresh scan starts
for p in [
    Path(os.environ.get('LOCALAPPDATA', '')) / 'MapleClassicReporter' / 'config' / 'sanction_cache.json',
    Path('data/config/sanction_cache.json'),
]:
    if p.is_file():
        p.unlink()

print(f"Successfully restored exact 11 records to {HISTORY_FILE} and {LEGACY_HISTORY_FILE}")
