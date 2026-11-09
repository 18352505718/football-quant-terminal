import os
import sys
import json

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from qiuzhong_client import QiuZhongClient

qz = QiuZhongClient()
today_str = "2026-11-03"
res = qz.get_jc_matches(today_str)
print("Keys in response:", res.keys())

matches = res.get("数据", [])
print(f"Total JC matches from QiuZhong: {len(matches)}")

for m in matches:
    num = m.get("比赛编号") or m.get("matchNumStr") or m.get("编号")
    h = m.get("主队名称") or m.get("homeTeamName")
    a = m.get("客队名称") or m.get("awayTeamName")
    mid = m.get("比赛ID") or m.get("matchId")
    league = m.get("联赛名称") or m.get("leagueName")
    print(f"[{num}] {league}: {h} vs {a} (matchId: {mid})")
    
    # Try prematch-xg
    if mid:
        try:
            xg_res = qz.get_match_prematch_xg(mid)
            xg_data = xg_res.get("数据", {})
            h_xg = xg_data.get("主队预期进球")
            a_xg = xg_data.get("客队预期进球")
            print(f"    --> xG: {h} {h_xg} vs {a} {a_xg}")
        except Exception as e:
            print(f"    --> xG error: {e}")
