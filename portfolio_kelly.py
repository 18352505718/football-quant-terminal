"""
资金管理与仓位规划引擎 (Kelly Criterion & Parlay Optimizer)
支持单关分数凯利计算、2串1 组合正期望筛选与多注单下注分配。
"""

import itertools
from typing import List, Dict


class PortfolioOptimizer:
    def __init__(self, total_bankroll: float = 10000.0, kelly_fraction: float = 0.15, max_single_bet_pct: float = 0.05):
        """
        :param total_bankroll: 总本金 (如 10,000 元)
        :param kelly_fraction: 分数凯利系数 (推荐 0.10 ~ 0.25，控制回撤与估计误差)
        :param max_single_bet_pct: 单笔投注最大本金上限比例 (默认不超过 5%)
        """
        self.total_bankroll = total_bankroll
        self.kelly_fraction = kelly_fraction
        self.max_single_bet_pct = max_single_bet_pct

    def calculate_single_kelly(self, model_prob: float, odds: float) -> dict:
        """
        计算单注的标准凯利比例与分数凯利仓位
        公式: f* = (p * b - q) / b = (p * odds - 1) / (odds - 1) = EV / (odds - 1)
        """
        ev = model_prob * odds - 1.0
        if ev <= 0 or odds <= 1.0:
            return {
                "full_kelly_pct": 0.0,
                "suggested_kelly_pct": 0.0,
                "suggested_stake": 0.0,
                "ev": ev
            }

        # 全凯利下注比例
        full_kelly = ev / (odds - 1.0)

        # 应用分数凯利
        frac_kelly = full_kelly * self.kelly_fraction

        # 施加硬性风控上限 (如不超过总资金 5%)
        safe_kelly = min(frac_kelly, self.max_single_bet_pct)
        suggested_stake = round(self.total_bankroll * safe_kelly, 2)

        return {
            "full_kelly_pct": full_kelly * 100.0,
            "suggested_kelly_pct": safe_kelly * 100.0,
            "suggested_stake": suggested_stake,
            "ev": ev
        }

    def generate_parlay_2x1_candidates(self, value_bets: List[Dict], min_parlay_ev: float = 0.05) -> List[Dict]:
        """
        针对竞彩必须串关的特点，寻找具备极高复合正期望的优质 2串1 组合。
        数学原理:
        对于两场独立赛事 Leg 1 和 Leg 2:
        P_parlay = P1 * P2
        Odds_parlay = O1 * O2
        EV_parlay = P_parlay * Odds_parlay - 1 = (1 + EV1) * (1 + EV2) - 1
        当且仅当每一腿都是真实正期望时，复合串关会成倍放大 Edge！
        """
        # 按照场次分组，确保同一场比赛不互串
        bets_by_match = {}
        for b in value_bets:
            m_key = f"{b['home_team']}_vs_{b['away_team']}"
            if m_key not in bets_by_match:
                bets_by_match[m_key] = []
            bets_by_match[m_key].append(b)

        match_keys = list(bets_by_match.keys())
        if len(match_keys) < 2:
            return []

        parlay_candidates = []

        # 遍历不同比赛的组合对
        for m1, m2 in itertools.combinations(match_keys, 2):
            for bet1 in bets_by_match[m1]:
                for bet2 in bets_by_match[m2]:
                    p1 = bet1["model_prob"]
                    o1 = bet1["market_odd"]
                    p2 = bet2["model_prob"]
                    o2 = bet2["market_odd"]

                    comb_prob = p1 * p2
                    comb_odds = o1 * o2
                    comb_ev = (1.0 + bet1["ev"]) * (1.0 + bet2["ev"]) - 1.0

                    if comb_ev >= min_parlay_ev:
                        # 计算 2串1 的凯利仓位
                        kelly_res = self.calculate_single_kelly(comb_prob, comb_odds)

                        parlay_candidates.append({
                            "leg1": {
                                "match": m1,
                                "play": bet1["play_type"],
                                "selection": bet1["selection"],
                                "odds": o1,
                                "ev": bet1["ev"]
                            },
                            "leg2": {
                                "match": m2,
                                "play": bet2["play_type"],
                                "selection": bet2["selection"],
                                "odds": o2,
                                "ev": bet2["ev"]
                            },
                            "combined_odds": round(comb_odds, 2),
                            "combined_prob": round(comb_prob, 4),
                            "combined_ev_pct": round(comb_ev * 100.0, 2),
                            "suggested_stake": kelly_res["suggested_stake"],
                            "stake_pct": round(kelly_res["suggested_kelly_pct"], 2)
                        })

        # 按复合 EV 从高到低排序
        parlay_candidates.sort(key=lambda x: x["combined_ev_pct"], reverse=True)
        return parlay_candidates
