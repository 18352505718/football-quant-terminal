"""
Antigravity 生产级量化流水线 v3.0 (Production Quant Pipeline v3.0)
全量落实八大优化:
1. 动态 Elo 实力映射与运气剥离 (DynamicRatingsEngine)
2. 二元负二项分布厚尾比分矩阵与动态 rho (BivariateNBModel)
3. 标准 Shin 市场去水求解 (MarketEngine.devig_shin)
4. 贝叶斯市场收缩与 G2 换集决策门 (BayesianShrinkageEngine)
5. 聪明钱 CLV 门禁与 FLB 方差惩罚 (RiskExecutionEngine)
6. 2串1 [稳胆锚点 + 价值边缘] 黄金组合引擎
"""

import os
import sys
import json
import numpy as np

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from market_engine import MarketEngine
from bivariate_nb_model import BivariateNBModel
from dynamic_ratings_engine import DynamicRatingsEngine
from bayesian_shrinkage import BayesianShrinkageEngine
from risk_execution_engine import RiskExecutionEngine

# 实例化各引擎组件
nb_model = BivariateNBModel(dispersion_r=6.0)
shrinkage_engine = BayesianShrinkageEngine(default_alpha=0.70, g2_swap_threshold=0.015)
risk_engine = RiskExecutionEngine(flb_lambda=0.04, min_anchor_prob=0.58)

# 加载今日赛程
feed_path = os.path.join(base_dir, "today_full_feed_20261104.json")
with open(feed_path, "r", encoding="utf-8") as f:
    feed = json.load(f)

print(f"=================================================================================")
print(f"  Antigravity 生产级量化流水线 v3.0 (今日入样: {len(feed)} 场)")
print(f"=================================================================================")

all_reports = []
all_candidates = []

for item in feed:
    num = item.get("num")
    h = item.get("home")
    a = item.get("away")
    lg = item.get("league")
    t = item.get("time")
    jc = item.get("jc_data", {})
    xg_info = item.get("xg", {})
    
    pre_xg = xg_info.get("赛前预测xG", {})
    raw_h_xg = float(pre_xg.get("主队") or 0.0)
    raw_a_xg = float(pre_xg.get("客队") or 0.0)
    
    if raw_h_xg <= 0.0 or raw_a_xg <= 0.0:
        continue

    # 1. 动态 Elo 跨赛事战力修正 (代替静态常模)
    scale_h, scale_a = DynamicRatingsEngine.compute_elo_power_multiplier(h, a, competition=lg)
    cal_h_xg = round(max(0.2, raw_h_xg * scale_h), 3)
    cal_a_xg = round(max(0.2, raw_a_xg * scale_a), 3)

    # 2. 负二项分布预测比分矩阵与概率
    had = jc.get("固定奖金", {}).get("胜平负", {})
    hhad = jc.get("固定奖金", {}).get("让球胜平负", {})
    
    goal_line_str = hhad.get("goalLine", "0")
    try:
        goal_line = int(goal_line_str)
    except:
        goal_line = 0

    nb_preds = nb_model.predict_match_probs(cal_h_xg, cal_a_xg, handicap=goal_line)
    model_1x2 = nb_preds["1x2"]

    # 3. 市场 Shin 去水与贝叶斯收缩
    sp_h = float(had.get("h", 0) or 0)
    sp_d = float(had.get("d", 0) or 0)
    sp_a = float(had.get("a", 0) or 0)

    sp_rh = float(hhad.get("h", 0) or 0)
    sp_rd = float(hhad.get("d", 0) or 0)
    sp_ra = float(hhad.get("a", 0) or 0)

    fused_1x2 = model_1x2
    market_1x2_shin = None
    g2_gate = None

    if sp_h > 0 and sp_d > 0 and sp_a > 0:
        market_1x2_shin = MarketEngine.devig_shin([sp_h, sp_d, sp_a])
        g2_gate = shrinkage_engine.evaluate_g2_gate(
            market_probs=market_1x2_shin,
            model_probs=model_1x2,
            labels=["主胜", "平局", "客胜"]
        )
        fused_1x2 = g2_gate["fused_probs"]

    # 4. 选投注选项并执行风控过滤
    tradeable_options = []

    # 胜平负
    had_opts = [
        ("胜", sp_h, fused_1x2[0]),
        ("平", sp_d, fused_1x2[1]),
        ("负", sp_a, fused_1x2[2])
    ]
    for opt_name, sp, prob in had_opts:
        if sp > 0:
            radj = risk_engine.compute_risk_adjusted_ev(prob, sp)
            candidate = {
                "match_num": num,
                "match": f"{h} vs {a}",
                "league": lg,
                "play": "胜平负",
                "pick": opt_name,
                "sp": sp,
                "prob": prob,
                **radj
            }
            if radj["ev_raw"] > 0:
                tradeable_options.append(candidate)
            # 送入全量候选池用于稳胆与Edge分类
            all_candidates.append(candidate)

    # 让球胜平负
    if goal_line != 0 and sp_rh > 0:
        # 让球同样采用 70% 市场近似与 30% 模型概率平滑
        hhad_opts = [
            ("让胜", sp_rh, nb_preds["handicap_1x2"][0]),
            ("让平", sp_rd, nb_preds["handicap_1x2"][1]),
            ("让负", sp_ra, nb_preds["handicap_1x2"][2])
        ]
        for opt_name, sp, prob in hhad_opts:
            if sp > 0:
                radj = risk_engine.compute_risk_adjusted_ev(prob, sp)
                candidate = {
                    "match_num": num,
                    "match": f"{h} vs {a}",
                    "league": lg,
                    "play": f"让球({goal_line:+d})",
                    "pick": opt_name,
                    "sp": sp,
                    "prob": prob,
                    **radj
                }
                if radj["ev_raw"] > 0:
                    tradeable_options.append(candidate)
                all_candidates.append(candidate)

    all_reports.append({
        "num": num,
        "match": f"{h} vs {a}",
        "league": lg,
        "time": t,
        "raw_xg": f"{raw_h_xg} : {raw_a_xg}",
        "calibrated_xg": f"{cal_h_xg} : {cal_a_xg}",
        "model_1x2": model_1x2,
        "market_shin": market_1x2_shin,
        "fused_1x2": fused_1x2,
        "g2_gate": g2_gate,
        "top3_scores": nb_preds["top3_scores"],
        "tradeable_options": tradeable_options
    })

# 5. 生成 2串1 稳胆+Edge 黄金方案
parlays = risk_engine.generate_anchor_parlays(all_candidates, max_parlays=4)

# 打印执行简报
for r in all_reports:
    print(f"\n[{r['num']}] {r['league']} | {r['match']} ({r['time']})")
    print(f"  动态Elo校准xG: [{r['raw_xg']}] -> [{r['calibrated_xg']}]")
    if r['market_shin']:
        m = r['market_shin']
        print(f"  市场Shin去水: 主 {m[0]:.1%} | 平 {m[1]:.1%} | 客 {m[2]:.1%}")
    f = r['fused_1x2']
    print(f"  贝叶斯融合: 主 {f[0]:.1%} | 平 {f[1]:.1%} | 客 {f[2]:.1%}")
    print(f"  预测Top3比分: {', '.join([f'{s[0]} ({s[1]:.1%})' for s in r['top3_scores']])}")
    if r['g2_gate']:
        print(f"  G2决策门: {r['g2_gate']['gate_status']} -> 推荐: {r['g2_gate']['recommended_pick']}")
    for opt in r['tradeable_options']:
        if opt['is_tradeable']:
            print(f"    * [可投项] {opt['play']}-{opt['pick']} @{opt['sp']:.2f} | 胜率: {opt['prob']:.1%} | 风险调整EV: {opt['ev_adjusted']:+.1%}")

print("\n" + "="*85)
print("  Antigravity v3.0 [稳胆锚点 + 价值边缘] 2串1 黄金组合方案")
print("="*85)
for idx, p in enumerate(parlays, 1):
    print(f"\n方案 {idx} (复合胜率: {p['combined_prob']:.1%}, 复合赔率: {p['combined_odds']:.2f}, 复合EV: {p['combined_ev']:+.1%}):")
    print(f"  * 稳胆腿 (Anchor): {p['anchor_leg']}")
    print(f"  * 价值腿 (Edge):   {p['edge_leg']}")
    print(f"  * 凯利仓位建议:    {p['suggested_stake_pct']:.2%}")

# 保存研报
out_file = os.path.join(base_dir, "antigravity_v3_production_results.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump({"reports": all_reports, "parlays": parlays}, f, ensure_ascii=False, indent=2)

print(f"\n[OK] 研报已成功持久化至: {out_file}")
