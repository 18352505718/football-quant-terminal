import json
import sys

try:
    with open(r"G:\BaiduSyncdisk\ai\足球分析\scripts\jc_hist_results.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Total matches in hist: {len(data)}")
    wed_matches = [d for d in data if "周三" in d.get("matchNumStr", "")]
    print(f"Total Wednesday matches: {len(wed_matches)}")
    for m in wed_matches[-15:]:
        num = m.get("matchNumStr")
        h = m.get("homeTeam")
        a = m.get("awayTeam")
        score = m.get("sectionsNo999")
        half = m.get("sectionsNo1")
        win = m.get("winFlag")
        print(f"[{num}] {h} vs {a} | 全场: {score} | 半场: {half} | 赛果: {win}")
except Exception as e:
    print("Error reading hist results:", e)
