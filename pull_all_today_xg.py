import os
import sys
import json
import time

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from qiuzhong_client import QiuZhongClient

qz = QiuZhongClient()

with open(os.path.join(base_dir, "qz_jc_20261103.json"), "r", encoding="utf-8") as f:
    raw = json.load(f)

matches = raw.get("数据", {}).get("比赛", [])
print(f"Total JC matches: {len(matches)}")

match_summary = []
for m in matches:
    num = m.get("竞彩编号")
    mid = m.get("比赛ID")
    league = m.get("联赛")
    h = m.get("主队")
    a = m.get("客队")
    time_str = m.get("开赛时间")
    status = m.get("比赛状态")
    
    had = m.get("固定奖金", {}).get("胜平负", {})
    hhad = m.get("固定奖金", {}).get("让球胜平负", {})
    
    # query prematch xG
    xg_h, xg_a = None, None
    if mid:
        try:
            xg_res = qz.get_match_prematch_xg(mid)
            xg_data = xg_res.get("数据", {})
            xg_h = xg_data.get("主队预期进球")
            xg_a = xg_data.get("客队预期进球")
            time.sleep(0.5) # rate limit safe
        except Exception as e:
            print(f"[{num}] xG fetch failed: {e}")
            
    item = {
        "num": num,
        "matchId": mid,
        "league": league,
        "home": h,
        "away": a,
        "time": time_str,
        "status": status,
        "had": {
            "h": had.get("h"),
            "d": had.get("d"),
            "a": had.get("a")
        },
        "hhad": {
            "line": hhad.get("goalLine"),
            "h": hhad.get("h"),
            "d": hhad.get("d"),
            "a": hhad.get("a")
        },
        "xg_h": xg_h,
        "xg_a": xg_a
    }
    match_summary.append(item)
    print(f"[{num}] {time_str} {league} | {h} vs {a} | xG: {xg_h} : {xg_a} | HAD: {had.get('h')}/{had.get('d')}/{had.get('a')} | HHAD({hhad.get('goalLine')}): {hhad.get('h')}/{hhad.get('d')}/{hhad.get('a')}")

with open(os.path.join(base_dir, "today_jc_with_xg.json"), "w", encoding="utf-8") as f:
    json.dump(match_summary, f, ensure_ascii=False, indent=2)

print("\nSaved today_jc_with_xg.json successfully!")
