"""
完整演示流水线:
1. 生成真实的五大联赛量化历史数据 (具备攻防实力梯队与时间衰减)
2. 训练 Dixon-Coles 独立概率模型 (极大似然估计)
3. 预测今晚焦点赛事比分联合概率矩阵
4. 对标竞彩真实挂牌赔率 (约 88% 返还率)，检测市场错价与正期望 (Edge)
5. 运行分数凯利公式与 2串1 投资组合优化
"""

import sys
import io

# 强制 UTF-8 输出以兼容 Windows 控制台
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
from datetime import datetime
from dixon_coles import DixonColesModel
from market_engine import MarketEngine
from portfolio_kelly import PortfolioOptimizer


def generate_mock_league_data(n_matches: int = 300) -> pd.DataFrame:
    """生成具备真实梯队特征的模拟联赛历史赛程数据"""
    np.random.seed(42)
    teams = [
        "阿森纳", "曼城", "利物浦", "阿斯顿维拉", 
        "热刺", "切尔西", "纽卡斯尔", "曼联", 
        "布莱顿", "西汉姆联", "狼队", "水晶宫"
    ]
    
    # 设定真实隐含实力 (进攻能力，防守能力)
    true_att = {
        "曼城": 1.15, "阿森纳": 1.10, "利物浦": 1.08, "阿斯顿维拉": 0.85,
        "热刺": 0.82, "切尔西": 0.75, "纽卡斯尔": 0.70, "曼联": 0.65,
        "布莱顿": 0.55, "西汉姆联": 0.50, "狼队": 0.40, "水晶宫": 0.35
    }
    true_def = {
        "阿森纳": -0.45, "曼城": -0.40, "利物浦": -0.35, "阿斯顿维拉": -0.10,
        "纽卡斯尔": -0.05, "切尔西": 0.05, "热刺": 0.10, "曼联": 0.15,
        "水晶宫": 0.20, "狼队": 0.25, "布莱顿": 0.30, "西汉姆联": 0.35
    }
    home_adv = 0.28

    records = []
    for i in range(n_matches):
        h, a = np.random.choice(teams, size=2, replace=False)
        days_ago = np.random.uniform(1, 240)

        # 真实期望进球数
        lam = np.exp(true_att[h] + true_def[a] + home_adv)
        mu = np.exp(true_att[a] + true_def[h])

        # 泊松生成进球
        hg = np.random.poisson(lam)
        ag = np.random.poisson(mu)

        records.append({
            "home_team": h,
            "away_team": a,
            "home_goals": hg,
            "away_goals": ag,
            "days_ago": days_ago
        })

    return pd.DataFrame(records)


def main():
    print("=" * 80)
    print(" 竞彩足球量化预测与错价猎杀系统 (Dixon-Coles + Market Edge Engine) ")
    print("=" * 80)

    # 1. 历史数据与模型训练
    print("\n[Step 1] 加载历史物理赛程数据并训练 Dixon-Coles 模型...")
    df_history = generate_mock_league_data(380)
    print(f"历史比赛场次: {len(df_history)} 场，参与球队数: {len(set(df_history['home_team']))}")

    model = DixonColesModel(xi=0.003)  # 半衰期约 230 天
    model.fit(df_history)

    print(f"-> 拟合完成！联赛平均主场优势 (Home Advantage): {model.home_advantage:+.3f}")
    print(f"-> 低比分修正因子 rho (Low-score correlation): {model.rho:+.3f}")
    
    # 打印前三强与后三弱球队画像
    ranked_teams = sorted(model.attacks.keys(), key=lambda t: model.attacks[t] - model.defenses[t], reverse=True)
    print("-> 球队净战力榜 (Attack - Defense):")
    for t in ranked_teams[:3]:
        print(f"   [强队] {t:<6} 进攻指数: {model.attacks[t]:+.2f} | 防守漏洞: {model.defenses[t]:+.2f}")
    for t in ranked_teams[-3:]:
        print(f"   [弱队] {t:<6} 进攻指数: {model.attacks[t]:+.2f} | 防守漏洞: {model.defenses[t]:+.2f}")

    # 2. 模拟今晚竞彩开盘赛事 (胜平负 + 让球胜平负)
    # 竞彩由于公众情绪狂热追捧豪门，常常导致强队主胜赔率被过度压低，而冷门/让球盘出现严重错价
    today_fixtures = [
        {
            "match_id": "周六001",
            "home": "阿森纳",
            "away": "切尔西",
            "handicap_val": -1,
            # 市场竞彩赔率 (返还率约 88%)
            # 市场大众疯狂追捧阿森纳，压低主胜；平局和客胜赔率被推高
            "odds_1x2": [1.45, 4.10, 5.20],
            "odds_handicap": [2.30, 3.45, 2.45]
        },
        {
            "match_id": "周六002",
            "home": "阿斯顿维拉",
            "away": "曼联",
            "handicap_val": -1,
            # 曼联名气大，大众盲目下注曼联，导致维拉主胜赔率虚高具备极强 Edge
            "odds_1x2": [2.15, 3.40, 2.75],
            "odds_handicap": [4.30, 3.85, 1.55]
        },
        {
            "match_id": "周六003",
            "home": "曼城",
            "away": "水晶宫",
            "handicap_val": -2,
            # 曼城极强，竞彩主胜 1.15 无单关，让2球盘口成为博弈焦点
            "odds_1x2": [1.16, 6.20, 11.50],
            "odds_handicap": [2.25, 4.10, 2.30]
        }
    ]

    print("\n" + "=" * 80)
    print("[Step 2] 独立概率计算 vs 市场赔率对比 (寻找错价 Edge)")
    print("=" * 80)

    all_value_bets = []

    for f in today_fixtures:
        home, away = f["home"], f["away"]
        preds = model.predict_match_probabilities(home, away, handicap=f["handicap_val"])
        
        odds_data = {
            "1x2": f["odds_1x2"],
            "handicap": {
                "hcp": f["handicap_val"],
                "odds": f["odds_handicap"]
            }
        }

        # 分析盘口抽水
        margin_info = MarketEngine.calculate_margin(f["odds_1x2"])

        print(f"\n【{f['match_id']}】{home} vs {away}")
        print(f"  模型预期进球: {home} {preds['lambda_home']:.2f}球 vs {away} {preds['mu_away']:.2f}球")
        print(f"  物理真实概率 (胜/平/负): {preds['prob_1x2']['Home']*100:.1f}% | {preds['prob_1x2']['Draw']*100:.1f}% | {preds['prob_1x2']['Away']*100:.1f}%")
        print(f"  让球({f['handicap_val']:+d})概率 (让胜/让平/让负): {preds['prob_handicap']['H_Home']*100:.1f}% | {preds['prob_handicap']['H_Draw']*100:.1f}% | {preds['prob_handicap']['H_Away']*100:.1f}%")
        print(f"  竞彩返还率 (Payout Ratio): {margin_info['payout_ratio']*100:.1f}% (抽水水钱: {margin_info['vig']*100:.1f}%)")

        # 扫描该场比赛的所有正期望下注项 (EV > 0)
        edges = MarketEngine.scan_match_edges(preds, odds_data, min_ev=0.02)
        for e in edges:
            e["match_id"] = f["match_id"]
            e["home_team"] = home
            e["away_team"] = away
            all_value_bets.append(e)

            print(f"  >>> [发现错价 Edge!] 玩法: {e['play_type']:<10} 选项: {e['selection']:<12} "
                  f"赔率: {e['market_odd']:.2f} | 物理概率: {e['model_prob']*100:.1f}% | "
                  f"公允去水概率: {e['fair_prob']*100:.1f}% | 期望收益(EV): +{e['ev_pct']:.1f}%")

    # 3. 仓位管理与 2串1 优化
    print("\n" + "=" * 80)
    print("[Step 3] 仓位规划与竞彩 2串1 (Parlay) 正期望组合推荐")
    print("=" * 80)

    bankroll = 10000.0  # 假设本金 10000 元
    optimizer = PortfolioOptimizer(total_bankroll=bankroll, kelly_fraction=0.15, max_single_bet_pct=0.04)

    print(f"\n当前策略账户总资金: {bankroll:.2f} 元 | 凯利执行比例: {optimizer.kelly_fraction*100}% 分数凯利")

    # 3.1 单场单关建议
    print("\n--- [单关推荐 (如有可投场次)] ---")
    if not all_value_bets:
        print("未发现单注期望收益大于 2% 的单关错价。")
    else:
        for b in all_value_bets:
            k_res = optimizer.calculate_single_kelly(b["model_prob"], b["market_odd"])
            print(f"  * {b['match_id']} {b['home_team']} vs {b['away_team']} | {b['play_type']} [{b['selection']}] "
                  f"@ {b['market_odd']:.2f} -> 建议下注: {k_res['suggested_stake']} 元 ({k_res['suggested_kelly_pct']:.1f}% 仓位, EV: +{b['ev_pct']:.1f}%)")

    # 3.2 2串1 强力正期望组合 (竞彩最核心玩法)
    print("\n--- [竞彩 2串1 复合正期望精选] ---")
    parlays = optimizer.generate_parlay_2x1_candidates(all_value_bets, min_parlay_ev=0.05)

    if not parlays:
        print("暂无由正期望单腿构成的优质 2串1 组合。")
    else:
        for idx, p in enumerate(parlays[:3], 1):
            print(f"\n  [组合 #{idx}] 复合赔率: {p['combined_odds']} | 复合中奖率: {p['combined_prob']*100:.1f}% | 复合 EV: +{p['combined_ev_pct']}%")
            print(f"    - 第一腿: {p['leg1']['match']} {p['leg1']['play']} [{p['leg1']['selection']}] (单腿赔率: {p['leg1']['odds']}, EV: +{p['leg1']['ev']*100:.1f}%)")
            print(f"    - 第二腿: {p['leg2']['match']} {p['leg2']['play']} [{p['leg2']['selection']}] (单腿赔率: {p['leg2']['odds']}, EV: +{p['leg2']['ev']*100:.1f}%)")
            print(f"    => 建议注单金额: {p['suggested_stake']} 元 ({p['stake_pct']}% 资金分配)")

    print("\n" + "=" * 80)
    print("模型决策研报生成完毕。")
    print("=" * 80)


if __name__ == "__main__":
    main()
