import os
import sys
import json

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from qiuzhong_client import QiuZhongClient

qz = QiuZhongClient()
res = qz.get_jc_matches("2026-11-04")

with open(os.path.join(base_dir, "qz_jc_20261104.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)

print("Saved qz_jc_20261104.json successfully!")
matches = res.get("数据", {}).get("比赛", [])
print(f"Total matches from QiuZhong: {len(matches)}")
for m in matches:
    print(m.get("竞彩编号"), m.get("联赛"), m.get("主队"), "vs", m.get("客队"), m.get("比赛ID"))
