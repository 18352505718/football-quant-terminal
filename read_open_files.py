import os
import sys

# Force utf-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

p = r"G:\BaiduSyncdisk\ai\足球分析"
for root, dirs, files in os.walk(p):
    for f in files:
        if "2026-11-04" in f and "open" in f:
            full = os.path.join(root, f)
            print("=== File:", full)
            with open(full, "r", encoding="utf-8", errors="ignore") as fp:
                print(fp.read()[:1500])
