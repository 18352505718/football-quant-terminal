import json

with open(r"G:\BaiduSyncdisk\ai\足球分析\scripts\jc_20261104.json", "r", encoding="utf-8") as f:
    data = json.load(f)

m = data["value"]["matchInfoList"][0]["subMatchList"][0]
print("Submatch keys:", m.keys())
print("Teams:", m.get("homeTeamName"), m.get("awayTeamName"), m.get("homeTeamAbbName"), m.get("awayTeamAbbName"))
print("MatchNumStr:", m.get("matchNumStr"))
