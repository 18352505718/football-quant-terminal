import os
import sys
import json

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from qiuzhong_client import QiuZhongClient
qz = QiuZhongClient()

with open(os.path.join(base_dir, "qz_jc_20261103.json"), "r", encoding="utf-8") as f:
    raw = json.load(f)

matches = raw.get("数据", {}).get("比赛", [])

for m in matches:
    num = m.get("竞彩编号")
    mid = m.get("比赛ID")
    h = m.get("主队")
    a = m.get("客队")
    try:
        res = qz.get_match_prematch_xg(mid)
        print(f"[{num}] {h} vs {a} ({mid}) -> raw: {res}")
    except Exception as e:
        print(f"[{num}] {h} vs {a} ({mid}) -> err: {e}")
