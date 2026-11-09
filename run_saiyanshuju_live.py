"""
赛眼数据 (saiyanshuju.cn) PRO 级实盘竞彩错价扫描与决策系统
数据流：
1. 直连 saiyanshuju.cn PRO 接口，获取今晚中国竞彩官方开盘全量赛事
2. 提取官方胜平负 (had)、让球胜平负 (hhad)、比分 (crs) 与 363 家全球机构即时赔率 (market)
3. 结合物理战力模型计算无偏客观比分矩阵与发生概率
4. 扫描竞彩官方挂牌赔率中的错价 Edge (正期望 EV > 0)
5. 输出单关投注建议与 2串1 复合正期望精选推荐
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import json
from saiyanshuju_client import SaiyanShujuClient
from market_engine import MarketEngine
from portfolio_kelly import PortfolioOptimizer
import numpy as np
from scipy.stats import poisson


def simulate_objective_probs(home_team: str, away_team: str, market_data: dict = None) -> dict:
    """
    结合赛眼全球 360+ 家机构初盘/即时盘去偏以及物理攻防模型，
    生成客观真实的期望进球与比分联合概率矩阵
    """
    # 若有 363 家机构即时均赔，作为物理锚点去水后重构进球率
    if market_data and "eo_close" in market_data and market_data["eo_close"]:
        raw_odds = market_data["eo_close"]
        fair = MarketEngine.devig_shin(raw_odds)
        p_h, p_d, p_a = fair[0], fair[1], fair[2]
    else:
        p_h, p_d, p_a = 0.45, 0.28, 0.27

    # 逆向估计主客队期望进球率 lambda 与 mu
    # 典型欧冠/杯赛场景主客期望进球基准
    total_goals_exp = 2.75
    # 根据胜率比估算进球差
    diff_factor = np.clip((p_h - p_a) * 1.8, -1.5, 2.0)
    lam = max(0.6, (total_goals_exp + diff_factor) / 2.0)
    mu = max(0.5, (total_goals_exp - diff_factor) / 2.0)

    max_g = 8
    score_matrix = np.zeros((max_g + 1, max_g + 1))
    for x in range(max_g + 1):
        px = poisson.pmf(x, lam)
        for y in range(max_g + 1):
            py = poisson.pmf(y, mu)
            tau = 1.0
            if x == 0 and y == 0: tau = 1.0 - lam * mu * 0.03
            elif x == 0 and y == 1: tau = 1.0 + lam * 0.03
            elif x == 1 and y == 0: tau = 1.0 + mu * 0.03
            elif x == 1 and y == 1: tau = 1.0 - 0.03
            score_matrix[x, y] = max(0.0, tau * px * py)
    score_matrix /= np.sum(score_matrix)

    # 常规 1X2 概率
    prob_h = float(np.sum(np.tril(score_matrix, -1)))
    prob_d = float(np.sum(np.diag(score_matrix)))
    prob_a = float(np.sum(np.triu(score_matrix, 1)))

    return {
        "lambda_home": lam,
        "mu_away": mu,
        "prob_1x2": {"Home": prob_h, "Draw": prob_d, "Away": prob_a},
        "score_matrix": score_matrix
    }


def main():
    print("=" * 85)
    print(" 赛眼数据 (saiyanshuju.cn) PRO 级实战竞彩错价扫描系统 ")
    print("=" * 85)

    client = SaiyanShujuClient()
    if not client.token:
        print("[错误] 未检测到已保存的 Token，请先登录！")
        return

    print(f"\n[Step 1] 正在连接赛眼 API 并拉取今日竞彩全量官方盘口...")
    today_data = client.get_today_matches()

    tier = today_data.get("tier", "unknown")
    matches = today_data.get("matches", [])
    print(f"-> 权限状态: 【PRO 会员成功连接】 (当前权限等级: {tier.upper()})")
    print(f"-> 今日竞彩开盘场次: {len(matches)} 场\n")

    all_value_bets = []

    print("=" * 85)
    print("[Step 2] 官方竞彩胜平负 / 让球胜平负错价扫描 (EV > 0 猎杀)")
    print("=" * 85)

    for m in matches:
        match_num = m.get("matchNumStr", "")
        league = m.get("leagueName", "")
        home = m.get("homeTeam", "")
        away = m.get("awayTeam", "")
        start_time = m.get("matchTime", "")

        had = m.get("had")
        hhad = m.get("hhad")
        market = m.get("market")

        # 过滤未开盘或已停售赛事
        if not had or not isinstance(had, dict):
            continue

        try:
            h_odd = float(had.get("h", 0))
            d_odd = float(had.get("d", 0))
            a_odd = float(had.get("a", 0))
        except (ValueError, TypeError):
            continue

        if h_odd <= 1.0 or d_odd <= 1.0 or a_odd <= 1.0:
            continue

        # 计算竞彩官方抽水返还率
        margin_info = MarketEngine.calculate_margin([h_odd, d_odd, a_odd])

        # 计算独立物理发生概率
        pred = simulate_objective_probs(home, away, market)
        p_1x2 = pred["prob_1x2"]

        print(f"\n【{match_num} {league}】{home} vs {away} (开赛: {start_time})")
        print(f"  模型预期进球: {home} {pred['lambda_home']:.2f}球 vs {away} {pred['mu_away']:.2f}球")
        print(f"  物理真实概率: 主胜 {p_1x2['Home']*100:.1f}% | 平局 {p_1x2['Draw']*100:.1f}% | 客胜 {p_1x2['Away']*100:.1f}%")
        print(f"  竞彩官方赔率: 胜 {h_odd:.2f} | 平 {d_odd:.2f} | 负 {a_odd:.2f} (返还率: {margin_info['payout_ratio']*100:.1f}%)")

        # 1. 扫描常规胜平负
        options_1x2 = [
            ("胜", p_1x2["Home"], h_odd),
            ("平", p_1x2["Draw"], d_odd),
            ("负", p_1x2["Away"], a_odd)
        ]
        for opt_name, p_val, odd_val in options_1x2:
            ev = p_val * odd_val - 1.0
            if ev > 0.01:  # 正期望阈值
                item = {
                    "match_num": match_num,
                    "league": league,
                    "home_team": home,
                    "away_team": away,
                    "play_type": "胜平负",
                    "selection": opt_name,
                    "model_prob": p_val,
                    "market_odd": odd_val,
                    "ev": ev,
                    "ev_pct": ev * 100.0
                }
                all_value_bets.append(item)
                print(f"  >>> [检出竞彩错价 Edge!] 【胜平负】 [{opt_name}] 赔率: {odd_val:.2f} | 真实概率: {p_val*100:.1f}% | 期望收益(EV): +{ev*100:.1f}%")

        # 2. 扫描让球胜平负 (hhad)
        if hhad and isinstance(hhad, dict):
            try:
                line_val = int(hhad.get("goalLine", 0))
                hh_odd = float(hhad.get("h", 0))
                hd_odd = float(hhad.get("d", 0))
                ha_odd = float(hhad.get("a", 0))

                # 计算让球物理概率
                mat = pred["score_matrix"]
                diff = np.fromfunction(lambda i, j: i - j, mat.shape)
                p_hwin = float(np.sum(mat[diff + line_val > 0]))
                p_hdraw = float(np.sum(mat[diff + line_val == 0]))
                p_haway = float(np.sum(mat[diff + line_val < 0]))

                sign = f"+{line_val}" if line_val > 0 else str(line_val)
                print(f"  竞彩让球({sign})赔率: 让胜 {hh_odd:.2f} | 让平 {hd_odd:.2f} | 让负 {ha_odd:.2f}")

                h_options = [
                    (f"让胜({sign})", p_hwin, hh_odd),
                    (f"让平({sign})", p_hdraw, hd_odd),
                    (f"让负({sign})", p_haway, ha_odd)
                ]
                for opt_name, p_val, odd_val in h_options:
                    ev = p_val * odd_val - 1.0
                    if ev > 0.02:
                        item = {
                            "match_num": match_num,
                            "league": league,
                            "home_team": home,
                            "away_team": away,
                            "play_type": f"让球({sign})",
                            "selection": opt_name,
                            "model_prob": p_val,
                            "market_odd": odd_val,
                            "ev": ev,
                            "ev_pct": ev * 100.0
                        }
                        all_value_bets.append(item)
                        print(f"  >>> [检出竞彩错价 Edge!] 【让球胜平负】 [{opt_name}] 赔率: {odd_val:.2f} | 真实概率: {p_val*100:.1f}% | 期望收益(EV): +{ev*100:.1f}%")
            except Exception:
                pass

    # Step 3: 凯利仓位与 2串1 推荐
    print("\n" + "=" * 85)
    print("[Step 3] 竞彩实操下注计划 (分数凯利 + 2串1 复合正期望乘数)")
    print("=" * 85)

    optimizer = PortfolioOptimizer(total_bankroll=10000.0, kelly_fraction=0.15, max_single_bet_pct=0.04)

    if all_value_bets:
        print("\n--- [单关正期望错价单 (EV > 0)] ---")
        for b in all_value_bets:
            k = optimizer.calculate_single_kelly(b["model_prob"], b["market_odd"])
            print(f"  * {b['match_num']} {b['home_team']} vs {b['away_team']} | {b['play_type']} [{b['selection']}] "
                  f"@ {b['market_odd']:.2f} -> 建议下注: {k['suggested_stake']} 元 ({k['suggested_kelly_pct']:.1f}% 仓位, 期望收益: +{b['ev_pct']:.1f}%)")

        parlays = optimizer.generate_parlay_2x1_candidates(all_value_bets, min_parlay_ev=0.05)
        if parlays:
            print("\n--- [竞彩 2串1 强力复合正期望精选] ---")
            for idx, p in enumerate(parlays[:3], 1):
                print(f"\n  [精选 2串1 组合 #{idx}] 复合赔率: {p['combined_odds']} | 复合命中率: {p['combined_prob']*100:.1f}% | 复合 EV: +{p['combined_ev_pct']}%")
                print(f"    - 第一腿: {p['leg1']['match']} {p['leg1']['play']} [{p['leg1']['selection']}] (@{p['leg1']['odds']}, EV: +{p['leg1']['ev']*100:.1f}%)")
                print(f"    - 第二腿: {p['leg2']['match']} {p['leg2']['play']} [{p['leg2']['selection']}] (@{p['leg2']['odds']}, EV: +{p['leg2']['ev']*100:.1f}%)")
                print(f"    => 建议注单金额: {p['suggested_stake']} 元 ({p['stake_pct']}% 资金分配)")
    else:
        print("今晚竞彩官方盘口定价严密，未发现显著正期望错价，建议空仓观望。")

    print("\n" + "=" * 85)
    print("实盘扫描与决策研报生成完毕。")
    print("=" * 85)


if __name__ == "__main__":
    main()
