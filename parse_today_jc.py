import json
import sys

with open(r"G:\BaiduSyncdisk\ai\足球分析\scripts\jc_20261104.json", "r", encoding="utf-8") as f:
    data = json.load(f)

matches = data.get("value", {}).get("matchInfoList", [])
print(f"Total JC matches today: {len(matches)}")

for m in matches:
    num = m.get("matchNumStr")
    lg = m.get("leagueName")
    h = m.get("homeTeam")
    a = m.get("awayTeam")
    t = m.get("matchTime")
    had = m.get("had", {})
    hhad = m.get("hhad", {})
    print(f"[{num}] {t} {lg} | {h} vs {a} | HAD: {had.get('h')}/{had.get('d')}/{had.get('a')} | HHAD({hhad.get('goalLine')}): {hhad.get('h')}/{hhad.get('d')}/{hhad.get('a')}")
