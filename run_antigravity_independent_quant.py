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

# 1. Load the full feed
with open(os.path.join(base_dir, "today_full_feed_20261104.json"), "r", encoding="utf-8") as f:
    feed = json.load(f)

print(f"Loaded {len(feed)} matches from today_full_feed_20261104.json")

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

def compute_dixon_coles_matrix(lambda_val, mu_val, rho=-0.06, max_goals=8):
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
    
    diff_matrix = np.fromfunction(lambda i, j: i - j, mat.shape)
    p_rh = float(np.sum(mat[diff_matrix + handicap > 0]))
    p_rd = float(np.sum(mat[diff_matrix + handicap == 0]))
    p_ra = float(np.sum(mat[diff_matrix + handicap < 0]))
    
    return {
        "h": p_h, "d": p_d, "a": p_a,
        "rh": p_rh, "rd": p_rd, "ra": p_ra
    }

market_engine = MarketEngine()
kelly_opt = PortfolioOptimizer(total_bankroll=10000.0, kelly_fraction=0.15)

quant_reports = []
all_edges = []

for item in feed:
    num = item.get("num")
    h = item.get("home")
    a = item.get("away")
    lg = item.get("league")
    t = item.get("time")
    jc = item.get("jc_data", {})
    xg_info = item.get("xg", {})
    odds_info = item.get("market_odds", {})
    
    # 1. Extract xG
    pre_xg = xg_info.get("赛前预测xG", {})
    h_xg = pre_xg.get("主队")
    a_xg = pre_xg.get("客队")
    
    # If no xG, fallback or skip
    if not h_xg or not a_xg:
        continue
        
    h_xg = float(h_xg)
    a_xg = float(a_xg)
    
    # 2. Run Dixon-Coles model
    mat = compute_dixon_coles_matrix(h_xg, a_xg, rho=-0.06)
    
    # 3. Extract JC odds
    had = jc.get("固定奖金", {}).get("胜平负", {})
    hhad = jc.get("固定奖金", {}).get("让球胜平负", {})
    
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
    
    # 4. Extract Pinnacle or best market odds from odds_info
    pinny_odds = None
    bookmakers = odds_info.get("公司列表", []) or odds_info.get("bookmakers", []) or []
    for bk in bookmakers:
        name = bk.get("公司名称") or bk.get("name") or ""
        if "Pinnacle" in name or "平博" in name or "Bet365" in name:
            markets = bk.get("玩法列表", []) or bk.get("markets", []) or []
            for mkt in markets:
                if mkt.get("玩法") == "1x2" or mkt.get("name") == "1x2":
                    o = mkt.get("赔率", {})
                    pinny_odds = (float(o.get("h", 0) or 0), float(o.get("d", 0) or 0), float(o.get("a", 0) or 0))
                    break
        if pinny_odds:
            break
            
    # Calculate market de-vig probabilities if available
    market_probs = None
    if pinny_odds and pinny_odds[0] > 1.0:
        sp_list = [pinny_odds[0], pinny_odds[1], pinny_odds[2]]
        mk_res = market_engine.devig_shin(sp_list)
        market_probs = {"home": mk_res[0], "draw": mk_res[1], "away": mk_res[2]}
    elif sp_h > 1.0 and sp_d > 1.0 and sp_a > 1.0:
        sp_list = [sp_h, sp_d, sp_a]
        mk_res = market_engine.devig_shin(sp_list)
        market_probs = {"home": mk_res[0], "draw": mk_res[1], "away": mk_res[2]}
        
    # 5. Compute EVs against JC SP
    ev_h = probs["h"] * sp_h - 1.0 if sp_h > 0 else -1.0
    ev_d = probs["d"] * sp_d - 1.0 if sp_d > 0 else -1.0
    ev_a = probs["a"] * sp_a - 1.0 if sp_a > 0 else -1.0
    
    ev_rh = probs["rh"] * sp_rh - 1.0 if sp_rh > 0 else -1.0
    ev_rd = probs["rd"] * sp_rd - 1.0 if sp_rd > 0 else -1.0
    ev_ra = probs["ra"] * sp_ra - 1.0 if sp_ra > 0 else -1.0
    
    options = [
        {"market": "HAD", "opt": "主胜", "sp": sp_h, "prob": probs["h"], "ev": ev_h},
        {"market": "HAD", "opt": "平局", "sp": sp_d, "prob": probs["d"], "ev": ev_d},
        {"market": "HAD", "opt": "客胜", "sp": sp_a, "prob": probs["a"], "ev": ev_a},
        {"market": f"HHAD({goal_line:+d})", "opt": "让胜", "sp": sp_rh, "prob": probs["rh"], "ev": ev_rh},
        {"market": f"HHAD({goal_line:+d})", "opt": "让平", "sp": sp_rd, "prob": probs["rd"], "ev": ev_rd},
        {"market": f"HHAD({goal_line:+d})", "opt": "让负", "sp": sp_ra, "prob": probs["ra"], "ev": ev_ra},
    ]
    
    # Filter: 1.0 < sp <= 6.5
    valid_opts = [o for o in options if 1.0 < o["sp"] <= 6.5]
    valid_opts.sort(key=lambda x: x["ev"], reverse=True)
    
    for o in valid_opts:
        if o["ev"] > 0:
            all_edges.append({
                "num": num,
                "match": f"{h} vs {a}",
                "league": lg,
                "market": o["market"],
                "opt": o["opt"],
                "sp": o["sp"],
                "prob": o["prob"],
                "ev": o["ev"]
            })
            
    quant_reports.append({
        "num": num,
        "match": f"{h} vs {a}",
        "league": lg,
        "time": t,
        "h_xg": h_xg,
        "a_xg": a_xg,
        "goal_line": goal_line,
        "model_probs": probs,
        "market_probs": market_probs,
        "options": valid_opts
    })

print(f"\n================ Antigravity 独立量化模型扫描结果 (共 {len(quant_reports)} 场) ================")
for r in quant_reports:
    print(f"\n[{r['num']}] {r['league']} {r['match']} (xG: {r['h_xg']} : {r['a_xg']})")
    mp = r["model_probs"]
    print(f"  模型预测无水概率: 主胜 {mp['h']:.1%} | 平局 {mp['d']:.1%} | 客胜 {mp['a']:.1%}")
    if r["market_probs"]:
        mkp = r["market_probs"]
        print(f"  市场去水共识概率: 主胜 {mkp['home']:.1%} | 平局 {mkp['draw']:.1%} | 客胜 {mkp['away']:.1%}")
    for o in r["options"]:
        star = "[POSITIVE EV]" if o["ev"] > 0 else "             "
        print(f"    {star} {o['market']}-{o['opt']} @{o['sp']:.2f} | prob: {o['prob']:.1%} | EV: {o['ev']:+.1%}")

print(f"\n================ 所有正期望 Edge (按 EV 降序) ================")
all_edges.sort(key=lambda x: x["ev"], reverse=True)
for e in all_edges:
    print(f"[{e['num']}] {e['match']} | {e['market']}-{e['opt']} @{e['sp']:.2f} | 胜率: {e['prob']:.1%} | EV: {e['ev']:+.1%}")

# Parlay optimization (2x1)
from collections import defaultdict
import itertools

grouped = defaultdict(list)
for e in all_edges:
    grouped[e["num"]].append(e)

matches_avail = list(grouped.keys())
parlay_combos = []

for n1, n2 in itertools.combinations(matches_avail, 2):
    for c1 in grouped[n1]:
        for c2 in grouped[n2]:
            comb_odds = c1["sp"] * c2["sp"]
            comb_prob = c1["prob"] * c2["prob"]
            comb_ev = comb_prob * comb_odds - 1.0
            
            # Apply Kelly
            kelly_res = kelly_opt.calculate_single_kelly(comb_prob, comb_odds)
            
            parlay_combos.append({
                "leg1": f"[{c1['num']}] {c1['match']} {c1['market']}-{c1['opt']} @{c1['sp']}",
                "leg2": f"[{c2['num']}] {c2['match']} {c2['market']}-{c2['opt']} @{c2['sp']}",
                "comb_odds": comb_odds,
                "comb_prob": comb_prob,
                "comb_ev": comb_ev,
                "suggested_stake_pct": kelly_res["suggested_kelly_pct"]
            })

parlay_combos.sort(key=lambda x: x["comb_ev"], reverse=True)

print(f"\n================ Antigravity 独立量化模型推荐 Top 5 (2串1) ================")
for idx, p in enumerate(parlay_combos[:5], 1):
    print(f"\n方案 {idx} (复合 EV: {p['comb_ev']:+.1%}):")
    print(f"  腿1: {p['leg1']}")
    print(f"  腿2: {p['leg2']}")
    print(f"  复合赔率: {p['comb_odds']:.2f} | 复合胜率: {p['comb_prob']:.1%} | 建议凯利仓位: {p['suggested_stake_pct']:.2%}")

with open(os.path.join(base_dir, "antigravity_independent_quant_results.json"), "w", encoding="utf-8") as f:
    json.dump({
        "reports": quant_reports,
        "edges": all_edges,
        "parlays": parlay_combos
    }, f, ensure_ascii=False, indent=2)

print("\nSaved antigravity_independent_quant_results.json successfully!")
