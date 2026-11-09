import json
import sys

# Force utf-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

with open(r"G:\BaiduSyncdisk\ai\足球分析\scripts\jc_20261104.json", "r", encoding="utf-8") as f:
    data = json.load(f)

match_info_list = data["value"]["matchInfoList"]
all_matches = []

for group in match_info_list:
    for m in group.get("subMatchList", []):
        num = m.get("matchNumStr")
        lg = m.get("leagueAbbName") or m.get("leagueAllName")
        h = m.get("homeTeamAbbName") or m.get("homeTeamAllName")
        a = m.get("awayTeamAbbName") or m.get("awayTeamAllName")
        t = m.get("matchTime")
        bdate = m.get("businessDate")
        had = m.get("had", {})
        hhad = m.get("hhad", {})
        
        all_matches.append({
            "num": num,
            "bdate": bdate,
            "time": t,
            "league": lg,
            "home": h,
            "away": a,
            "had": had,
            "hhad": hhad,
            "all_m": m
        })

print(f"Loaded {len(all_matches)} matches for today:")
for m in all_matches:
    num = m["num"]
    lg = m["league"]
    h = m["home"]
    a = m["away"]
    t = m["time"]
    had = m["had"]
    hhad = m["hhad"]
    print(f"[{num}] {t} {lg} | {h} vs {a} | HAD: {had.get('h')}/{had.get('d')}/{had.get('a')} | HHAD({hhad.get('goalLine')}): {hhad.get('h')}/{hhad.get('d')}/{hhad.get('a')}")
