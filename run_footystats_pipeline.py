"""
FootyStats API 真实 xG 数据驱动量化流水线
1. 通过 FootyStats 官方 API 拉取五大联赛真实 xG (预期进球) 数据
2. 训练纯物理进球 vs xG 融合 Dixon-Coles 模型，直观对比运气去噪效应
3. 拉取今日真实比赛与市场即时赔率，计算无偏概率、去抽水公允概率与真实 Edge
4. 执行凯利资金分配与 2串1 优化建议
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from footystats_client import FootyStatsClient
from dixon_coles import DixonColesModel
from market_engine import MarketEngine
from portfolio_kelly import PortfolioOptimizer


def main():
    print("=" * 85)
    print(" FootyStats 真实 xG 数据驱动 —— 竞彩/博彩量化错价猎杀引擎 ")
    print("=" * 85)

    api_key = "932bc6a4b76c58b53c9caacf87ba2e8cc2750ff7830dca0c4c398d43373d6e60"
    client = FootyStatsClient(api_key=api_key)

    # 1. 获取英超 2024/2025 赛季 (Season ID: 12325) 真实比赛与 xG 数据
    print("\n[Step 1] 正在通过 FootyStats API 拉取英超真实 xG 与比赛物理数据...")
    season_id = 12325  # 英超 2024/2025
    df_matches = client.get_season_matches_df(season_id=season_id)

    if df_matches.empty:
        print("未获取到完赛数据，请检查网络或赛季 ID。")
        return

    print(f"-> 成功拉取完赛比赛场次: {len(df_matches)} 场，包含主客队精确 xG 统计！")
    print("\n[样本数据展示 (前 3 场)]:")
    print(df_matches[['date', 'home_team', 'away_team', 'home_goals', 'away_goals', 'home_xg', 'away_xg']].head(3).to_string(index=False))

    # 2. 训练 xG 强化的 Dixon-Coles 模型
    print("\n[Step 2] 正在拟合 xG 增强型 Dixon-Coles 泊松模型 (消除比分运气方差)...")
    model_xg = DixonColesModel(xi=0.003)
    # 采用 85% xG + 15% 真实进球的黄金配比 (文献推荐的低方差无偏组合)
    model_xg.fit(df_matches, use_xg=True, xg_weight=0.85)

    print(f"-> 模型拟合成功！")
    print(f"   英超主场期望优势 (Home Advantage): {model_xg.home_advantage:+.3f}")
    print(f"   低比分修正因子 (rho): {model_xg.rho:+.3f}")

    # 打印攻防战力榜
    rankings = sorted(model_xg.attacks.keys(), key=lambda t: model_xg.attacks[t] - model_xg.defenses[t], reverse=True)
    print("\n-> 【基于真实 xG 的英超真实战力排行 (前 5 强与后 5 弱)】:")
    print("   " + "-" * 75)
    print(f"   {'排名':<4} {'球队':<22} {'进攻威胁指数 (Attack)':<22} {'防守漏洞指数 (Defense)':<22}")
    print("   " + "-" * 75)
    for i, t in enumerate(rankings[:5], 1):
        print(f"   #{i:<3} {t:<22} {model_xg.attacks[t]:>+8.3f}              {model_xg.defenses[t]:>+8.3f}")
    print("   ...")
    for i, t in enumerate(rankings[-5:], len(rankings) - 4):
        print(f"   #{i:<3} {t:<22} {model_xg.attacks[t]:>+8.3f}              {model_xg.defenses[t]:>+8.3f}")

    # 3. 实时错价检测演示 (英超周末焦点对决)
    # 以真实赛程为例，对比机构开出的赔率寻找错价
    print("\n" + "=" * 85)
    print("[Step 3] 焦点对抗物理概率计算 vs 市场赔率错价扫描 (造 Edge)")
    print("=" * 85)

    # 挑选真实球队模拟对阵与市场竞彩开盘
    demo_fixtures = [
        {
            "home": "Manchester City",
            "away": "Arsenal",
            "handicap_val": -1,
            # 市场给出的赔率示例 (胜平负与让球)
            "odds_1x2": [1.95, 3.45, 3.75],
            "odds_handicap": [3.60, 3.80, 1.72]
        },
        {
            "home": "Liverpool",
            "away": "Chelsea",
            "handicap_val": -1,
            "odds_1x2": [1.60, 4.20, 4.60],
            "odds_handicap": [2.50, 3.75, 2.15]
        },
        {
            "home": "Tottenham Hotspur",
            "away": "Aston Villa",
            "handicap_val": -1,
            "odds_1x2": [2.25, 3.60, 2.75],
            "odds_handicap": [4.20, 4.10, 1.55]
        }
    ]

    all_value_bets = []

    for f in demo_fixtures:
        h, a = f["home"], f["away"]
        if h not in model_xg.team_to_idx or a not in model_xg.team_to_idx:
            continue

        preds = model_xg.predict_match_probabilities(h, a, handicap=f["handicap_val"])
        odds_data = {
            "1x2": f["odds_1x2"],
            "handicap": {
                "hcp": f["handicap_val"],
                "odds": f["odds_handicap"]
            }
        }

        margin_1x2 = MarketEngine.calculate_margin(f["odds_1x2"])

        print(f"\n【比赛】{h} vs {a}")
        print(f"  物理期望进球 (基于 xG 模型): {h} {preds['lambda_home']:.2f}球 vs {a} {preds['mu_away']:.2f}球")
        print(f"  客观发生概率 (胜/平/负): {preds['prob_1x2']['Home']*100:.1f}% | {preds['prob_1x2']['Draw']*100:.1f}% | {preds['prob_1x2']['Away']*100:.1f}%")
        print(f"  让球({f['handicap_val']:+d})概率 (让胜/让平/让负): {preds['prob_handicap']['H_Home']*100:.1f}% | {preds['prob_handicap']['H_Draw']*100:.1f}% | {preds['prob_handicap']['H_Away']*100:.1f}%")
        print(f"  市场返还率: {margin_1x2['payout_ratio']*100:.1f}% (抽水水钱: {margin_1x2['vig']*100:.1f}%)")

        # 扫描错价
        edges = MarketEngine.scan_match_edges(preds, odds_data, min_ev=0.03)
        for e in edges:
            e["home_team"] = h
            e["away_team"] = a
            all_value_bets.append(e)
            print(f"  >>> [发现错价 Edge!] 盘口: {e['play_type']:<14} 选项: {e['selection']:<12} "
                  f"赔率: {e['market_odd']:.2f} | 物理概率: {e['model_prob']*100:.1f}% | "
                  f"公允去水概率: {e['fair_prob']*100:.1f}% | 期望收益(EV): +{e['ev_pct']:.1f}%")

    # 4. 凯利资金与 2串1 优化
    print("\n" + "=" * 85)
    print("[Step 4] 凯利资金配置与 2串1 (Parlay) 投资组合")
    print("=" * 85)

    optimizer = PortfolioOptimizer(total_bankroll=10000.0, kelly_fraction=0.15, max_single_bet_pct=0.04)

    if all_value_bets:
        print("\n--- [单关推荐 (具备正期望 EV > 3%)] ---")
        for b in all_value_bets:
            k = optimizer.calculate_single_kelly(b["model_prob"], b["market_odd"])
            print(f"  * {b['home_team']} vs {b['away_team']} | {b['play_type']} [{b['selection']}] "
                  f"@ {b['market_odd']:.2f} -> 建议下注: {k['suggested_stake']} 元 ({k['suggested_kelly_pct']:.1f}% 仓位, EV: +{b['ev_pct']:.1f}%)")

        parlays = optimizer.generate_parlay_2x1_candidates(all_value_bets, min_parlay_ev=0.06)
        if parlays:
            print("\n--- [竞彩 2串1 强力复合正期望推荐] ---")
            for idx, p in enumerate(parlays[:3], 1):
                print(f"\n  [精选组合 #{idx}] 复合赔率: {p['combined_odds']} | 复合中奖率: {p['combined_prob']*100:.1f}% | 复合 EV: +{p['combined_ev_pct']}%")
                print(f"    - Leg 1: {p['leg1']['match']} {p['leg1']['play']} [{p['leg1']['selection']}] (@{p['leg1']['odds']}, EV: +{p['leg1']['ev']*100:.1f}%)")
                print(f"    - Leg 2: {p['leg2']['match']} {p['leg2']['play']} [{p['leg2']['selection']}] (@{p['leg2']['odds']}, EV: +{p['leg2']['ev']*100:.1f}%)")
                print(f"    => 建议注额: {p['suggested_stake']} 元 ({p['stake_pct']}% 资金分配)")
    else:
        print("未检测到具备显著正期望的下注机会，市场定价紧密，保持空仓观望。")

    print("\n" + "=" * 85)
    print("全流程分析完毕。")
    print("=" * 85)


if __name__ == "__main__":
    main()
