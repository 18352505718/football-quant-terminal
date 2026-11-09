import os
import sys
import json
import numpy as np

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
with open(os.path.join(base_dir, "antigravity_independent_quant_results.json"), "r", encoding="utf-8") as f:
    raw = json.load(f)

reports = raw["reports"]

# League tiers:
# Tier 1: Premier League (EPL), La Liga, Bundesliga, Serie A
# Tier 2: Ligue 1, Liga Portugal, Eredivisie, English Championship (high)
# Tier 3: Belgian Pro League, Scottish Prem, Turkish Super Lig, Norwegian Eliteserien
# Tier 4: Czech First League, Azerbaijan Prem League

# Let's inspect the matches that are SAME TIER or domestic:
# 周三006: 波尔图 (Tier 2) vs 那不勒斯 (Tier 1/2) - Close tier!
# 周三007: PSV (Tier 2) vs 布鲁日 (Tier 3) - Neighboring tier!
# 周三008: 多特蒙德 (Tier 1) vs 皇家贝蒂斯 (Tier 1) - PERFECT SAME TIER!
# 周三012: 布里斯托尔城 vs 狼队 - Both English football!

print("=== Tier-Safe Matches (No massive cross-league distortion) ===")
safe_matches = ["周三006", "周三007", "周三008", "周三012"]

safe_edges = []
for r in reports:
    if r["num"] in safe_matches:
        print(f"\n[{r['num']}] {r['league']} {r['match']} (xG {r['h_xg']} : {r['a_xg']})")
        print(f"  模型: 主 {r['model_probs']['h']:.1%} | 平 {r['model_probs']['d']:.1%} | 客 {r['model_probs']['a']:.1%}")
        if r["market_probs"]:
            print(f"  市场: 主 {r['market_probs']['home']:.1%} | 平 {r['market_probs']['draw']:.1%} | 客 {r['market_probs']['away']:.1%}")
        for o in r["options"]:
            if o["ev"] > 0:
                print(f"    * {o['market']}-{o['opt']} @{o['sp']:.2f} | prob: {o['prob']:.1%} | EV: {o['ev']:+.1%}")
                safe_edges.append({
                    "num": r["num"],
                    "match": r["match"],
                    "league": r["league"],
                    "market": o["market"],
                    "opt": o["opt"],
                    "sp": o["sp"],
                    "prob": o["prob"],
                    "ev": o["ev"]
                })

import itertools
from portfolio_kelly import PortfolioOptimizer
opt = PortfolioOptimizer(total_bankroll=10000.0, kelly_fraction=0.15)

from collections import defaultdict
grouped_safe = defaultdict(list)
for e in safe_edges:
    grouped_safe[e["num"]].append(e)

safe_parlays = []
for n1, n2 in itertools.combinations(list(grouped_safe.keys()), 2):
    for c1 in grouped_safe[n1]:
        for c2 in grouped_safe[n2]:
            comb_odds = c1["sp"] * c2["sp"]
            comb_prob = c1["prob"] * c2["prob"]
            comb_ev = comb_prob * comb_odds - 1.0
            
            # Kelly stake
            k = opt.calculate_single_kelly(comb_prob, comb_odds)
            
            safe_parlays.append({
                "leg1": f"[{c1['num']}] {c1['match']} {c1['market']}-{c1['opt']} @{c1['sp']}",
                "leg2": f"[{c2['num']}] {c2['match']} {c2['market']}-{c2['opt']} @{c2['sp']}",
                "comb_odds": comb_odds,
                "comb_prob": comb_prob,
                "comb_ev": comb_ev,
                "suggested_stake_pct": k["suggested_kelly_pct"]
            })

safe_parlays.sort(key=lambda x: x["comb_ev"], reverse=True)

print("\n=== Antigravity 校准版 2串1 推荐方案 (消除跨级别偏置) ===")
for idx, p in enumerate(safe_parlays[:6], 1):
    print(f"\n方案 {idx} (复合 EV: {p['comb_ev']:+.1%}):")
    print(f"  腿1: {p['leg1']}")
    print(f"  腿2: {p['leg2']}")
    print(f"  复合赔率: {p['comb_odds']:.2f} | 复合胜率: {p['comb_prob']:.1%} | 建议仓位: {p['suggested_stake_pct']:.2%}")
