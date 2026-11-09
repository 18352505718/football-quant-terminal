import os

p = r"G:\BaiduSyncdisk\ai\足球分析"
for f in os.listdir(p):
    if "11-04" in f or "26158" in f:
        print(f)
