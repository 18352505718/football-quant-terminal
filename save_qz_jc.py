import os
import sys
import json

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from qiuzhong_client import QiuZhongClient

qz = QiuZhongClient()
res = qz.get_jc_matches("2026-11-03")

with open(os.path.join(base_dir, "qz_jc_20261103.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)

print("Saved qz_jc_20261103.json successfully!")
