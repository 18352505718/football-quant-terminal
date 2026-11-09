import os
import sys
import json

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from qiuzhong_client import QiuZhongClient

qz = QiuZhongClient()
res = qz.get_jc_matches("2026-11-03")

print("Keys:", list(res.keys()))
data = res.get("数据")
print("Type of data:", type(data))
if isinstance(data, dict):
    print("Data keys:", list(data.keys()))
    for k, v in list(data.items())[:3]:
        print(f"Key: {k}, Type: {type(v)}, Val: {v}")
elif isinstance(data, list):
    print("Data length:", len(data))
    if len(data) > 0:
        print("First item type:", type(data[0]))
        print("First item:", data[0])
