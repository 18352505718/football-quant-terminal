import os
import sys
import json
import time

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from qiuzhong_client import QiuZhongClient
qz = QiuZhongClient()

with open(os.path.join(base_dir, "qz_jc_20261104.json"), "r", encoding="utf-8") as f:
    raw = json.load(f)

matches = raw.get("数据", {}).get("比赛", [])
print(f"Total matches to process: {len(matches)}")

detailed_matches = []

for m in matches:
    num = m.get("竞彩编号")
    mid = m.get("比赛ID")
    h = m.get("主队")
    a = m.get("客队")
    lg = m.get("联赛")
    t = m.get("开赛时间")
    
    # pull xG
    xg_data = {}
    try:
        xg_res = qz.get_match_prematch_xg(mid)
        xg_data = xg_res.get("数据", {})
    except Exception as e:
        xg_data = {"error": str(e)}
        
    time.sleep(0.4)
    
    # pull market odds
    odds_data = {}
    try:
        odds_res = qz.get_match_odds(mid)
        odds_data = odds_res.get("数据", {})
    except Exception as e:
        odds_data = {"error": str(e)}
        
    time.sleep(0.4)
    
    item = {
        "num": num,
        "matchId": mid,
        "league": lg,
        "home": h,
        "away": a,
        "time": t,
        "jc_data": m,
        "xg": xg_data,
        "market_odds": odds_data
    }
    detailed_matches.append(item)
    print(f"Processed [{num}] {h} vs {a}: xg={bool(xg_data.get('赛前预测xG'))}, odds={bool(odds_data)}")

with open(os.path.join(base_dir, "today_full_feed_20261104.json"), "w", encoding="utf-8") as f:
    json.dump(detailed_matches, f, ensure_ascii=False, indent=2)

print("\nSaved today_full_feed_20261104.json successfully!")
