import json

with open(r"G:\BaiduSyncdisk\ai\足球分析\scripts\jc_20261104.json", "r", encoding="utf-8") as f:
    data = json.load(f)

val = data.get("value", {})
match_info_list = val.get("matchInfoList", [])

total_matches = []
for group in match_info_list:
    bdate = group.get("businessDate")
    sub = group.get("subMatchList", [])
    print(f"Group {bdate}: {len(sub)} matches")
    for m in sub:
        total_matches.append(m)
        num = m.get("matchNumStr")
        lg = m.get("leagueName")
        h = m.get("homeTeam")
        a = m.get("awayTeam")
        t = m.get("matchTime")
        had = m.get("had", {})
        hhad = m.get("hhad", {})
        print(f"  [{num}] {t} {lg} | {h} vs {a} | HAD: {had.get('h')}/{had.get('d')}/{had.get('a')} | HHAD({hhad.get('goalLine')}): {hhad.get('h')}/{hhad.get('d')}/{hhad.get('a')}")

print(f"\nTotal matches loaded: {len(total_matches)}")
