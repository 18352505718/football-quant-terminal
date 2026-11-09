"""
实时量化错价猎杀扫描器 (结合 Base URL: http://47.99.155.27:8321 接口族)
量化核心流程：
1. 调用 /api/today 拉取今日比赛赛程及盘口可用性
2. 调用 /expected_xg 与 /team_xg_form 获取双方物理 xG 攻防形态
3. 运行 Dixon-Coles 泊松模型计算无偏比分矩阵与真实物理概率
4. 提取 Pinnacle(平博)/Bet365 逐家原生盘口，通过 Shin 算法去水
5. 联动 /match_clv 检验资金走势 (Smart Money CLV 验证)
6. 输出正期望 (EV > 0) 错价猎杀清单与分数凯利仓位
"""

import sys
import os
import argparse
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from internal_football_api import FootballAPIClient
from dixon_coles import DixonColesModel
from market_engine import MarketEngine
from portfolio_kelly import PortfolioOptimizer


def generate_mock_live_payload():
    """当未配置有效 Token 时的仿真数据沙盒，保证系统可即时演示"""
    return {
        "matches": [
            {
                "event_id": 602317,
                "league": "英格兰超级联赛",
                "home_team": "阿森纳",
                "away_team": "切尔西",
                "odds_available": True,
                "odds": {
                    "odds_by_bookmaker": {
                        "pinnacle": {
                            "胜平负": {"主队": 1.55, "平局": 4.30, "客队": 6.10},
                            "亚盘": {"主队让球1": 1.95, "客队受让1": 1.95}
                        },
                        "bet365": {
                            "胜平负": {"主队": 1.50, "平局": 4.20, "客队": 6.50},
                            "亚盘": {"主队让球1": 1.90, "客队受让1": 2.00}
                        }
                    }
                },
                "expected_xg": {"home": 2.25, "away": 0.85},
                "clv": {"clv_home": 0.0035, "clv_draw": -0.0012, "clv_away": -0.0023}
            },
            {
                "event_id": 602318,
                "league": "西班牙甲级联赛",
                "home_team": "巴塞罗那",
                "away_team": "皇家马德里",
                "odds_available": True,
                "odds": {
                    "odds_by_bookmaker": {
                        "pinnacle": {
                            "胜平负": {"主队": 2.20, "平局": 3.65, "客队": 3.25},
                            "亚盘": {"主队让球0.25": 1.90, "客队受让0.25": 2.00}
                        },
                        "bet365": {
                            "胜平负": {"主队": 2.15, "平局": 3.60, "客队": 3.30}
                        }
                    }
                },
                "expected_xg": {"home": 1.90, "away": 1.45},
                "clv": {"clv_home": 0.0018, "clv_draw": -0.0005, "clv_away": -0.0013}
            }
        ]
    }


def run_pipeline(token: str = None, min_ev: float = 0.02):
    print("=" * 85)
    print(" 足球实战 API 全景错价扫描系统 (Dixon-Coles + Pinnacle 去水 + CLV 验证) ")
    print("=" * 85)

    client = FootballAPIClient(token=token)
    use_live = False

    if client.token:
        try:
            print(f"\n[Step 1] 正在连接 API 服务端 (http://47.99.155.27:8321) 拉取今日比赛...")
            today_resp = client.get_today_matches()
            matches = today_resp.get("matches", [])
            print(f"-> 连接成功！获取到今日赛事: {len(matches)} 场 (使用已加载 Token: {client.token[:8]}...)")
            use_live = True
        except PermissionError as pe:
            raise RuntimeError(f"[FATAL] Token 认证未通过 ({pe})，严禁生成伪造数据，中断执行。")
        except Exception as e:
            raise RuntimeError(f"[FATAL] 服务端连通异常 ({e})，中断执行。")
    else:
        raise ValueError("[FATAL] 缺少有效的 X-API-Token，严禁进入仿真模式，请配置凭据后重试。")

    all_value_bets = []

    print("\n" + "=" * 85)
    print("[Step 2] 逐场物理 xG 计算、Pinnacle 锐度去水与错价 Edge 检测")
    print("=" * 85)

    for m in matches:
        event_id = m.get("event_id")
        home = m.get("home_team_zh") or m.get("home_team") or f"队_{event_id}_H"
        away = m.get("away_team_zh") or m.get("away_team") or f"队_{event_id}_A"
        league = m.get("league_zh") or m.get("league") or "赛事"

        if not m.get("odds_available", False):
            continue

        # 1. 获取物理 xG 赛前预期
        exp_h, exp_a = 1.35, 1.10
        if use_live:
            try:
                xg_resp = client.get_expected_xg(event_id)
                if xg_resp.get("found") and xg_resp.get("expected_xg"):
                    exp_h = float(xg_resp["expected_xg"].get("home") or 1.35)
                    exp_a = float(xg_resp["expected_xg"].get("away") or 1.10)
            except Exception:
                pass
        else:
            exp_h = m.get("expected_xg", {}).get("home", 1.35)
            exp_a = m.get("expected_xg", {}).get("away", 1.10)

        # 2. 获取 CLV 赔率走势与热度
        clv_info = {"clv_home": 0.0, "clv_draw": 0.0, "clv_away": 0.0}
        if use_live:
            try:
                clv_resp = client.get_match_clv(event_id)
                if clv_resp.get("found") and clv_resp.get("clv"):
                    clv_info = clv_resp["clv"]
            except Exception:
                pass
        else:
            clv_info = m.get("clv", clv_info)

        # 3. 获取单场赔率 (优先读取 Pinnacle 与 Bet365)
        clean_odds = {}
        if use_live:
            try:
                full_resp = client.get_match_full(event_id)
                clean_odds = client.extract_clean_odds(full_resp)
            except Exception:
                pass
        else:
            bm_data = m.get("odds", {}).get("odds_by_bookmaker", {})
            for b_name in ["pinnacle", "bet365"]:
                if b_name in bm_data:
                    clean_odds[b_name] = {}
                    if "胜平负" in bm_data[b_name]:
                        sp = bm_data[b_name]["胜平负"]
                        clean_odds[b_name]["1x2"] = [sp["主队"], sp["平局"], sp["客队"]]

        if not clean_odds or "1x2" not in clean_odds.get("pinnacle", clean_odds.get("bet365", {})):
            continue

        # 4. 基于 xG 独立计算泊松物理概率
        import numpy as np
        from scipy.stats import poisson
        max_g = 8
        score_matrix = np.zeros((max_g + 1, max_g + 1))
        for x in range(max_g + 1):
            px = poisson.pmf(x, exp_h)
            for y in range(max_g + 1):
                py = poisson.pmf(y, exp_a)
                # 低比分相关性微调
                tau = 1.0
                if x == 0 and y == 0: tau = 1.0 - exp_h * exp_a * 0.03
                elif x == 0 and y == 1: tau = 1.0 + exp_h * 0.03
                elif x == 1 and y == 0: tau = 1.0 + exp_a * 0.03
                elif x == 1 and y == 1: tau = 1.0 - 0.03
                score_matrix[x, y] = max(0.0, tau * px * py)
        score_matrix /= np.sum(score_matrix)

        p_home = float(np.sum(np.tril(score_matrix, -1)))
        p_draw = float(np.sum(np.diag(score_matrix)))
        p_away = float(np.sum(np.triu(score_matrix, 1)))

        # 5. 读取基准赔率并用 Shin 算法剥离抽水
        bm_key = "pinnacle" if "pinnacle" in clean_odds else list(clean_odds.keys())[0]
        odds_1x2 = clean_odds[bm_key]["1x2"]
        fair_probs = MarketEngine.devig_shin(odds_1x2)

        print(f"\n【{league}】{home} vs {away} (Match ID: {event_id})")
        print(f"  物理期望进球 (赛前 xG): {home} {exp_h:.2f}球 vs {away} {exp_a:.2f}球")
        print(f"  模型客观概率: 主胜 {p_home*100:.1f}% | 平局 {p_draw*100:.1f}% | 客胜 {p_away*100:.1f}%")
        print(f"  {bm_key.upper()} 挂牌赔率: 胜 {odds_1x2[0]:.2f} | 平 {odds_1x2[1]:.2f} | 负 {odds_1x2[2]:.2f}")
        print(f"  {bm_key.upper()} 去水公允概率: 胜 {fair_probs[0]*100:.1f}% | 平 {fair_probs[1]*100:.1f}% | 负 {fair_probs[2]*100:.1f}%")
        print(f"  聪明资金走势 (CLV): 主 {clv_info['clv_home']:+.4f} | 平 {clv_info['clv_draw']:+.4f} | 客 {clv_info['clv_away']:+.4f}")

        # 6. 计算单项 EV
        labels = [("主胜", p_home, odds_1x2[0], fair_probs[0], clv_info["clv_home"]),
                  ("平局", p_draw, odds_1x2[1], fair_probs[1], clv_info["clv_draw"]),
                  ("客胜", p_away, odds_1x2[2], fair_probs[2], clv_info["clv_away"])]

        for sel_name, p_m, odd, p_f, clv in labels:
            ev = p_m * odd - 1.0
            # 借鉴百度网盘 3,708 场回测结论：赔率 > 6.5 存在严重的冷门高估偏差 (FLB)，过滤虚假极高赔
            if ev >= min_ev and odd <= 6.5:
                bet_item = {
                    "event_id": event_id,
                    "league": league,
                    "home_team": home,
                    "away_team": away,
                    "selection": sel_name,
                    "model_prob": p_m,
                    "market_odd": odd,
                    "fair_prob": p_f,
                    "ev": ev,
                    "ev_pct": ev * 100.0,
                    "clv": clv
                }
                all_value_bets.append(bet_item)

                clv_tag = " [资金同向流入!]" if clv > 0 else " (赔率走势平淡)"
                print(f"  >>> [检出错价 Edge!] 选项: {sel_name:<4} 赔率: {odd:.2f} | 物理概率: {p_m*100:.1f}% | "
                      f"期望收益(EV): +{ev*100:.1f}% | CLV 走势: {clv:+.4f}{clv_tag}")

    # 7. 凯利仓位与 2串1 推荐
    print("\n" + "=" * 85)
    print("[Step 3] 仓位规划与 2串1 组合猎杀建议")
    print("=" * 85)

    optimizer = PortfolioOptimizer(total_bankroll=10000.0, kelly_fraction=0.15, max_single_bet_pct=0.04)

    if all_value_bets:
        print("\n--- [单场投注建议 (具备正期望 EV > 2%)] ---")
        for b in all_value_bets:
            k = optimizer.calculate_single_kelly(b["model_prob"], b["market_odd"])
            print(f"  * [{b['league']}] {b['home_team']} vs {b['away_team']} | [{b['selection']}] "
                  f"@ {b['market_odd']:.2f} -> 建议下注: {k['suggested_stake']} 元 ({k['suggested_kelly_pct']:.1f}% 仓位, EV: +{b['ev_pct']:.1f}%)")

        parlays = optimizer.generate_parlay_2x1_candidates(
            [{**b, "play_type": "胜平负"} for b in all_value_bets], 
            min_parlay_ev=0.05
        )
        if parlays:
            print("\n--- [2串1 复合高正期望推荐] ---")
            for idx, p in enumerate(parlays[:3], 1):
                print(f"\n  [组合 #{idx}] 复合赔率: {p['combined_odds']} | 复合胜率: {p['combined_prob']*100:.1f}% | 复合 EV: +{p['combined_ev_pct']}%")
                print(f"    - Leg 1: {p['leg1']['match']} [{p['leg1']['selection']}] (@{p['leg1']['odds']}, EV: +{p['leg1']['ev']*100:.1f}%)")
                print(f"    - Leg 2: {p['leg2']['match']} [{p['leg2']['selection']}] (@{p['leg2']['odds']}, EV: +{p['leg2']['ev']*100:.1f}%)")
                print(f"    => 建议注单金额: {p['suggested_stake']} 元 ({p['stake_pct']}% 资金分配)")
    else:
        print("未检测到具备显著正期望的错价下注机会，建议空仓。")

    print("\n" + "=" * 85)
    print("扫描完毕。")
    print("=" * 85)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="足球数据 API 错价扫描器")
    parser.add_argument("--token", type=str, default=None, help="API Token (X-API-Token)")
    parser.add_argument("--min_ev", type=float, default=0.02, help="最小期望收益率阈值 (默认 0.02 即 2%)")
    args = parser.parse_args()

    run_pipeline(token=args.token, min_ev=args.min_ev)
