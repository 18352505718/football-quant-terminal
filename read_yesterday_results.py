import json
import sys

with open(r"G:\BaiduSyncdisk\ai\足球分析\scripts\jc_hist_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

tue_matches = [d for d in data if "周二" in d.get("matchNumStr", "")]
print(f"Total Tuesday matches in hist: {len(tue_matches)}")

for m in tue_matches[-11:]:
    num = m.get("matchNumStr")
    h = m.get("homeTeam")
    a = m.get("awayTeam")
    half = m.get("sectionsNo1")
    full = m.get("sectionsNo999")
    win = m.get("winFlag")
    line = m.get("goalLine")
    print(f"[{num}] {h} vs {a} | 半场: {half} | 全场: {full} | 胜平负: {win} | 让球: {line}")
