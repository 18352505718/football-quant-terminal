import os

p = r"G:\BaiduSyncdisk\ai\足球分析"
for root, dirs, files in os.walk(p):
    for f in files:
        if "2026-11-04" in f:
            print(os.path.join(root, f))
