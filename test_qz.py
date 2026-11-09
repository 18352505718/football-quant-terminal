from qiuzhong_client import QiuZhongClient
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

client = QiuZhongClient()
jc_res = client.get_jc_matches('2026-11-03')
matches = jc_res.get('数据', {}).get('比赛', [])
print(f'JC matches count: {len(matches)}')
for m in matches:
    mid = m.get('比赛ID')
    print(f"{m.get('竞彩编号')} {m.get('主队')} vs {m.get('客队')} | 比赛ID: {mid}")

target = next((m for m in matches if m.get('比赛ID')), None)
if target:
    tid = target['比赛ID']
    print(f"\nTesting prematch-xg on {tid} ({target.get('主队')} vs {target.get('客队')})...")
    try:
        xg_res = client.get_match_prematch_xg(tid)
        print('Prematch xG response:', json.dumps(xg_res, ensure_ascii=False)[:300])
    except Exception as e:
        print('Prematch xG error:', e)

    print(f"\nTesting odds on {tid}...")
    try:
        odds_res = client.get_match_odds(tid)
        print('Odds response:', json.dumps(odds_res, ensure_ascii=False)[:300])
    except Exception as e:
        print('Odds error:', e)

    print(f"\nTesting money on {tid}...")
    try:
        money_res = client.get_match_money(tid)
        print('Money response:', json.dumps(money_res, ensure_ascii=False)[:300])
    except Exception as e:
        print('Money error:', e)
