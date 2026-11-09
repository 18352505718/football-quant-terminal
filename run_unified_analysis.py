import os
import sys
import json
import math
import numpy as np
from scipy.stats import poisson

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from market_engine import MarketEngine
from portfolio_kelly import PortfolioOptimizer

def tau(x, y, lambda_val, mu_val, rho=-0.06):
    if x == 0 and y == 0:
        return 1.0 - lambda_val * mu_val * rho
    elif x == 0 and y == 1:
        return 1.0 + lambda_val * rho
    elif x == 1 and y == 0:
        return 1.0 + mu_val * rho
    elif x == 1 and y == 1:
        return 1.0 - rho
    else:
        return 1.0

def compute_score_matrix(lambda_val, mu_val, rho=-0.06, max_goals=8):
    mat = np.zeros((max_goals + 1, max_goals + 1))
    for x in range(max_goals + 1):
        px = poisson.pmf(x, lambda_val)
        for y in range(max_goals + 1):
            py = poisson.pmf(y, mu_val)
            t = tau(x, y, lambda_val, mu_val, rho)
            mat[x, y] = max(0.0, t * px * py)
    mat /= np.sum(mat)
    return mat

def get_probabilities(mat, handicap=0):
    p_h = float(np.sum(np.tril(mat, -1)))
    p_d = float(np.sum(np.diag(mat)))
    p_a = float(np.sum(np.triu(mat, 1)))
    
    # Handicap
    diff_matrix = np.fromfunction(lambda i, j: i - j, mat.shape)
    p_rh = float(np.sum(mat[diff_matrix + handicap > 0]))
    p_rd = float(np.sum(mat[diff_matrix + handicap == 0]))
    p_ra = float(np.sum(mat[diff_matrix + handicap < 0]))
    
    return {
        "h": p_h, "d": p_d, "a": p_a,
        "rh": p_rh, "rd": p_rd, "ra": p_ra
    }

# 1. Load today's JC matches
with open(os.path.join(base_dir, "qz_jc_20261103.json"), "r", encoding="utf-8") as f:
    raw_jc = json.load(f)

matches = raw_jc.get("数据", {}).get("比赛", [])

# Known xG from QiuZhong
ucl_xg = {
    "周二004": {"h_xg": 2.35, "a_xg": 1.36},
    "周二005": {"h_xg": 1.65, "a_xg": 2.06},
    "周二006": {"h_xg": 2.67, "a_xg": 1.12},
    "周二007": {"h_xg": 2.02, "a_xg": 1.60},
    "周二008": {"h_xg": 1.73, "a_xg": 1.73},
    "周二009": {"h_xg": 2.90, "a_xg": 1.12},
    "周二010": {"h_xg": 1.73, "a_xg": 1.96},
    "周二011": {"h_xg": 2.27, "a_xg": 1.06},
}

# Known 47.99 CLV data (from team logs and tests)
# 005 Bayern CLV = -0.0906 (Sharp money fleeing)
# 007 Inter CLV = -0.0335 (Sharp money fleeing)
# 006 LASK CLV = +0.0640 (Sharp money backing LASK, but market dropping)
# 010 PSG CLV = +0.0280
# 011 Bodø CLV = +0.0810
clv_registry = {
    "周二005": {"clv_status": "VETO", "reason": "主力客胜 CLV 暴跌 -0.0906 (聪明钱出逃)"},
    "周二007": {"clv_status": "VETO", "reason": "主力客胜 CLV 暴跌 -0.0335 (聪明钱出逃)"},
    "周二010": {"clv_status": "CAUTION", "reason": "主力客胜 CLV +0.028，但伤停缺登贝莱与克瓦拉茨赫利亚"},
    "周二006": {"clv_status": "PASS", "reason": "CLV +0.064，盘口坚挺"},
    "周二011": {"clv_status": "PASS", "reason": "CLV +0.081，主胜资金强力流入"}
}

analysis_results = []
all_candidate_edges = []

for m in matches:
    num = m.get("竞彩编号")
    h = m.get("主队")
    a = m.get("客队")
    time_str = m.get("开赛时间")
    
    if num not in ucl_xg:
        continue
        
    xg_info = ucl_xg[num]
    h_xg = xg_info["h_xg"]
    a_xg = xg_info["a_xg"]
    
    mat = compute_score_matrix(h_xg, a_xg, rho=-0.06)
    
    had = m.get("固定奖金", {}).get("胜平负", {})
    hhad = m.get("固定奖金", {}).get("让球胜平负", {})
    
    sp_h = float(had.get("h", 0) or 0)
    sp_d = float(had.get("d", 0) or 0)
    sp_a = float(had.get("a", 0) or 0)
    
    goal_line_str = hhad.get("goalLine", "0")
    try:
        goal_line = int(goal_line_str)
    except:
        goal_line = 0
        
    sp_rh = float(hhad.get("h", 0) or 0)
    sp_rd = float(hhad.get("d", 0) or 0)
    sp_ra = float(hhad.get("a", 0) or 0)
    
    probs = get_probabilities(mat, handicap=goal_line)
    
    # EVs
    ev_h = probs["h"] * sp_h - 1.0 if sp_h > 0 else -1.0
    ev_d = probs["d"] * sp_d - 1.0 if sp_d > 0 else -1.0
    ev_a = probs["a"] * sp_a - 1.0 if sp_a > 0 else -1.0
    
    ev_rh = probs["rh"] * sp_rh - 1.0 if sp_rh > 0 else -1.0
    ev_rd = probs["rd"] * sp_rd - 1.0 if sp_rd > 0 else -1.0
    ev_ra = probs["ra"] * sp_ra - 1.0 if sp_ra > 0 else -1.0
    
    clv_info = clv_registry.get(num, {"clv_status": "NORMAL", "reason": "无显著异动"})
    
    options = [
        {"market": "HAD", "opt": "主胜", "sp": sp_h, "prob": probs["h"], "ev": ev_h},
        {"market": "HAD", "opt": "平局", "sp": sp_d, "prob": probs["d"], "ev": ev_d},
        {"market": "HAD", "opt": "客胜", "sp": sp_a, "prob": probs["a"], "ev": ev_a},
        {"market": f"HHAD({goal_line:+d})", "opt": "让胜", "sp": sp_rh, "prob": probs["rh"], "ev": ev_rh},
        {"market": f"HHAD({goal_line:+d})", "opt": "让平", "sp": sp_rd, "prob": probs["rd"], "ev": ev_rd},
        {"market": f"HHAD({goal_line:+d})", "opt": "让负", "sp": sp_ra, "prob": probs["ra"], "ev": ev_ra},
    ]
    
    # FLB rule: odd <= 6.5
    valid_opts = [o for o in options if 1.0 < o["sp"] <= 6.5]
    valid_opts.sort(key=lambda x: x["ev"], reverse=True)
    
    for o in valid_opts:
        if o["ev"] > 0:
            all_candidate_edges.append({
                "num": num,
                "match": f"{h} vs {a}",
                "market": o["market"],
                "opt": o["opt"],
                "sp": o["sp"],
                "prob": o["prob"],
                "ev": o["ev"],
                "clv": clv_info
            })
            
    analysis_results.append({
        "num": num,
        "match": f"{h} vs {a}",
        "h_xg": h_xg,
        "a_xg": a_xg,
        "goal_line": goal_line,
        "probs": probs,
        "options": valid_opts,
        "clv": clv_info
    })

print("\n================== 欧冠 8 场连续 xG 真实模型概率与竞彩 EV ==================")
for r in analysis_results:
    print(f"\n[{r['num']}] {r['match']} (xG: {r['h_xg']} : {r['a_xg']}) | CLV: {r['clv']['clv_status']} ({r['clv']['reason']})")
    print(f"  模型概率: 主胜 {r['probs']['h']:.1%} | 平局 {r['probs']['d']:.1%} | 客胜 {r['probs']['a']:.1%}")
    print(f"  让球({r['goal_line']:+d}): 让胜 {r['probs']['rh']:.1%} | 让平 {r['probs']['rd']:.1%} | 让负 {r['probs']['ra']:.1%}")
    for o in r["options"]:
        star = "[POSITIVE EV]" if o["ev"] > 0 else "             "
        print(f"    {star} {o['market']}-{o['opt']} @{o['sp']:.2f} | prob: {o['prob']:.1%} | EV: {o['ev']:+.1%}")

print("\n================== 全局所有正期望 Edge 选项 (按 EV 降序) ==================")
all_candidate_edges.sort(key=lambda x: x["ev"], reverse=True)
for ce in all_candidate_edges:
    status = ce["clv"]["clv_status"]
    print(f"[{ce['num']}] {ce['match']} | {ce['market']}-{ce['opt']} @{ce['sp']:.2f} | 胜率: {ce['prob']:.1%} | EV: {ce['ev']:+.1%} | CLV: {status}")

# 2串1 组合评估
print("\n================== 2串1 组合胜率、赔率与期望回报评估 ==================")
opt_portfolio = PortfolioOptimizer(total_bankroll=10000.0, kelly_fraction=0.15)

# Filter out VETO matches
clean_candidates = [ce for ce in all_candidate_edges if ce["clv"]["clv_status"] != "VETO"]

# Group by match to avoid combining options from the same match
from collections import defaultdict
grouped = defaultdict(list)
for c in clean_candidates:
    grouped[c["num"]].append(c)

matches_available = list(grouped.keys())
print(f"可用无否决场次: {matches_available}")

parlay_results = []
import itertools
for num1, num2 in itertools.combinations(matches_available, 2):
    for c1 in grouped[num1]:
        for c2 in grouped[num2]:
            comb_odds = c1["sp"] * c2["sp"]
            comb_prob = c1["prob"] * c2["prob"]
            comb_ev = comb_prob * comb_odds - 1.0
            
            # Kelly stake
            single_stake = opt_portfolio.calculate_single_kelly(comb_prob, comb_odds)
            
            parlay_results.append({
                "leg1": f"[{c1['num']}] {c1['match']} {c1['market']}-{c1['opt']} @{c1['sp']}",
                "leg2": f"[{c2['num']}] {c2['match']} {c2['market']}-{c2['opt']} @{c2['sp']}",
                "comb_odds": comb_odds,
                "comb_prob": comb_prob,
                "comb_ev": comb_ev,
                "suggested_stake_pct": single_stake["suggested_kelly_pct"],
                "clv_safety": f"{c1['clv']['clv_status']} + {c2['clv']['clv_status']}"
            })

parlay_results.sort(key=lambda x: x["comb_ev"], reverse=True)

print(f"\nTop 10 最佳 2串1 方案:")
for idx, p in enumerate(parlay_results[:10], 1):
    print(f"\n方案 {idx} (复合 EV: {p['comb_ev']:+.1%}):")
    print(f"  腿1: {p['leg1']}")
    print(f"  腿2: {p['leg2']}")
    print(f"  赔率: {p['comb_odds']:.2f} | 胜率: {p['comb_prob']:.1%} | 建议分数凯利仓位: {p['suggested_stake_pct']:.2%}")
    print(f"  风控状态: {p['clv_safety']}")

with open(os.path.join(base_dir, "parlay_scan_results.json"), "w", encoding="utf-8") as f:
    json.dump({
        "all_edges": all_candidate_edges,
        "parlays": parlay_results
    }, f, ensure_ascii=False, indent=2)
