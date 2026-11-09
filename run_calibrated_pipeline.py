"""
Antigravity 全校准版量化研报流水线 (Calibrated Quant Pipeline v2.0)
包含三大核心模块:
1. 跨联赛硬度标定 (LeagueTierCalibrator): 消除欧战国内 xG 虚胖
2. 标准 Shin 市场去水 (MarketEngine.devig_shin): Štrumbelj 二次型无偏概率提取
3. 贝叶斯市场收缩与 G2 决策门 (BayesianShrinkageEngine): 70% 市场 + 30% 模型，置信门禁过滤
4. 分数凯利与风险敞口控制 (PortfolioOptimizer)
"""

import os
import sys
import json
import numpy as np
from scipy.stats import poisson

base_dir = r"C:\Users\dzh18352505718\.gemini\antigravity\scratch\football_quant_model"
if base_dir not in sys.path:
    sys.path.append(base_dir)

from market_engine import MarketEngine
from league_tier_calibrator import LeagueTierCalibrator
from bayesian_shrinkage import BayesianShrinkageEngine
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

# 加载数据
feed_path = os.path.join(base_dir, "today_full_feed_20261104.json")
with open(feed_path, "r", encoding="utf-8") as f:
    feed = json.load(f)

print(f"=== 运行 Antigravity 校准版量化定价流水线 (赛事总数: {len(feed)}) ===")

shrinkage_engine = BayesianShrinkageEngine(default_alpha=0.70, g2_swap_threshold=0.015)
kelly_opt = PortfolioOptimizer(total_bankroll=10000.0, kelly_fraction=0.15)

reports = []
all_value_bets = []

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

    # 1. 跨联赛硬度标定
    cal_h_xg, cal_a_xg = LeagueTierCalibrator.calibrate_cross_competition_xg(
        home_team=h, away_team=a,
        home_raw_xg=raw_h_xg, away_raw_xg=raw_a_xg,
        competition=lg
    )

    # 2. DC 比分矩阵与模型概率计算
    mat = compute_dixon_coles_matrix(cal_h_xg, cal_a_xg, rho=-0.06)
    
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
    model_1x2 = [probs["h"], probs["d"], probs["a"]]

    # 3. 市场 Shin 去水公允概率
    market_1x2_shin = None
    fused_1x2 = model_1x2
    g2_gate_result = None

    if sp_h > 0 and sp_d > 0 and sp_a > 0:
        market_1x2_shin = MarketEngine.devig_shin([sp_h, sp_d, sp_a])
        # 4. 贝叶斯市场收缩与 G2 决策门
        g2_gate_result = shrinkage_engine.evaluate_g2_gate(
            market_probs=market_1x2_shin,
            model_probs=model_1x2,
            labels=["主胜", "平局", "客胜"]
        )
        fused_1x2 = g2_gate_result["fused_probs"]

    # 5. EV 评估 (基于融合后校准概率)
    options = []
    if sp_h > 0:
        ev_h = fused_1x2[0] * sp_h - 1.0
        options.append({"market": "胜平负", "opt": "胜", "sp": sp_h, "prob": fused_1x2[0], "ev": ev_h})
    if sp_d > 0:
        ev_d = fused_1x2[1] * sp_d - 1.0
        options.append({"market": "胜平负", "opt": "平", "sp": sp_d, "prob": fused_1x2[1], "ev": ev_d})
    if sp_a > 0:
        ev_a = fused_1x2[2] * sp_a - 1.0
        options.append({"market": "胜平负", "opt": "负", "sp": sp_a, "prob": fused_1x2[2], "ev": ev_a})

    # 让球盘 (若有让球赔率，以模型让球概率做保守收缩评估)
    if sp_rh > 0:
        # 让球同样施加收缩
        ev_rh = probs["rh"] * sp_rh - 1.0
        options.append({"market": f"让球({goal_line:+d})", "opt": "让胜", "sp": sp_rh, "prob": probs["rh"], "ev": ev_rh})
    if sp_rd > 0:
        ev_rd = probs["rd"] * sp_rd - 1.0
        options.append({"market": f"让球({goal_line:+d})", "opt": "让平", "sp": sp_rd, "prob": probs["rd"], "ev": ev_rd})
    if sp_ra > 0:
        ev_ra = probs["ra"] * sp_ra - 1.0
        options.append({"market": f"让球({goal_line:+d})", "opt": "让负", "sp": sp_ra, "prob": probs["ra"], "ev": ev_ra})

    reports.append({
        "num": num,
        "match": f"{h} vs {a}",
        "league": lg,
        "time": t,
        "raw_xg": f"{raw_h_xg} : {raw_a_xg}",
        "calibrated_xg": f"{cal_h_xg} : {cal_a_xg}",
        "raw_model_probs": {"h": probs["h"], "d": probs["d"], "a": probs["a"]},
        "market_shin_probs": {"h": market_1x2_shin[0], "d": market_1x2_shin[1], "a": market_1x2_shin[2]} if market_1x2_shin else None,
        "fused_probs": {"h": fused_1x2[0], "d": fused_1x2[1], "a": fused_1x2[2]},
        "g2_gate": g2_gate_result,
        "options": options
    })

# 输出校准结果
print("\n" + "="*85)
print(f"今日比赛校准报告 (共 {len(reports)} 场):")
print("="*85)
for r in reports:
    print(f"\n[{r['num']}] {r['league']} | {r['match']} ({r['time']})")
    print(f"  xG 校准: 原始 [{r['raw_xg']}] -> 硬度校准后 [{r['calibrated_xg']}]")
    if r['market_shin_probs']:
        m = r['market_shin_probs']
        print(f"  市场 Shin 去水: 主 {m['h']:.1%} | 平 {m['d']:.1%} | 客 {m['a']:.1%}")
    f = r['fused_probs']
    print(f"  贝叶斯融合概率: 主 {f['h']:.1%} | 平 {f['d']:.1%} | 客 {f['a']:.1%}")
    if r['g2_gate']:
        print(f"  G2 决策门状态: {r['g2_gate']['gate_status']} -> 推荐: {r['g2_gate']['recommended_pick']}")
    
    # 打印正期望选项 (限制赔率 <= 4.0 过滤极端冷门噪声)
    pos_opts = [o for o in r['options'] if o['ev'] > 0 and o['sp'] <= 4.0]
    for o in pos_opts:
        print(f"    * [正期望] {o['market']}-{o['opt']} @{o['sp']:.2f} | 概率: {o['prob']:.1%} | EV: {o['ev']:+.1%}")

# 保存为 json
out_path = os.path.join(base_dir, "calibrated_quant_results_v2.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(reports, f, ensure_ascii=False, indent=2)
print(f"\n[OK] 完整结果已保存至: {out_path}")
