"""
博彩市场赔率解析、去抽水 (De-vigging)、计算期望值 (EV) 与 Edge 发现引擎。
支持常规比例归一化法、Shin 模型去水法，以及竞彩胜平负/让球胜平负综合扫描。
"""

import numpy as np
from scipy.optimize import root_scalar


class MarketEngine:
    @staticmethod
    def calculate_margin(odds: list) -> dict:
        """
        计算盘口超额抽水率 (Vig) 与 理论返还率 (Payout Ratio)
        :param odds: [主胜赔率, 平局赔率, 客胜赔率]
        """
        inv_sum = sum(1.0 / o for o in odds)
        payout_ratio = 1.0 / inv_sum  # 竞彩通常在 87% ~ 89% 左右，海外高返还率在 95% ~ 98%
        vig = inv_sum - 1.0
        return {
            "payout_ratio": payout_ratio,
            "vig": vig,
            "inv_sum": inv_sum
        }

    @staticmethod
    def devig_proportional(odds: list) -> list:
        """
        标准比例归一化去水法: P_i = (1 / O_i) / sum(1 / O_k)
        """
        invs = [1.0 / o for o in odds]
        s = sum(invs)
        return [inv / s for inv in invs]

    @staticmethod
    def devig_shin(odds: list) -> list:
        """
        Shin 模型去水法 (Shin 1992, 1993, Strumbelj 2014)
        有效解决博彩市场著名的“热门-冷门偏差” (Favorite-Longshot Bias)，
        提取博彩公司内部对真实无偏物理概率的估计。
        求解知情交易比例 z:
        \\sum \\sqrt{z^2 + 4(1-z) \\frac{\\pi_i^2}{\\sum \\pi_j}} = 2 + (n - 2) z
        """
        invs = np.array([1.0 / o for o in odds], dtype=float)
        s = np.sum(invs)
        n = len(invs)
        T = (invs**2) / s

        # 求解 z (知情交易者/内幕交易比例参数)
        def equation(z):
            val = np.sum(np.sqrt(z**2 + 4.0 * (1.0 - z) * T)) - (2.0 + (n - 2) * z)
            return val

        try:
            # 正常博彩市场 z 在 [0, 0.4] 之间
            f0 = equation(0.0)
            f_bracket = equation(0.5)
            if f0 * f_bracket > 0:
                # 若极端盘口超出 0.5，拓展到 0.8
                if equation(0.8) * f0 < 0:
                    sol = root_scalar(equation, bracket=[0.0, 0.8], method='brentq')
                else:
                    return MarketEngine.devig_proportional(odds)
            else:
                sol = root_scalar(equation, bracket=[0.0, 0.5], method='brentq')

            z = sol.root
            p_fair = (np.sqrt(z**2 + 4.0 * (1.0 - z) * T) - z) / (2.0 * (1.0 - z))
            p_fair = p_fair / np.sum(p_fair)
            return p_fair.tolist()
        except Exception:
            # 若数值求解失败，降级退回比例归一化法
            return MarketEngine.devig_proportional(odds)

    @staticmethod
    def evaluate_edge(model_prob: float, market_odd: float, fair_prob: float = None) -> dict:
        """
        计算投注单项的期望值 (Expected Value) 与 相对 Edge
        :param model_prob: 模型独立预测的真实物理概率 (与赔率无关)
        :param market_odd: 机构给出的实际可下注赔率 (如竞彩挂牌赔率)
        :param fair_prob: 市场去水后的公允概率 (可选，用于辅助判断机构倾向)
        :return: 期望收益率 EV, 真实优势 Edge, 是否具备投注价值
        """
        # EV = P * Odds - 1
        ev = model_prob * market_odd - 1.0

        edge_vs_fair = None
        if fair_prob is not None and fair_prob > 0:
            edge_vs_fair = (model_prob - fair_prob) / fair_prob

        return {
            "model_prob": model_prob,
            "market_odd": market_odd,
            "fair_prob": fair_prob,
            "ev": ev,
            "ev_pct": ev * 100.0,  # 百分比期望收益
            "edge_vs_fair": edge_vs_fair,
            "has_value": ev > 0.0
        }

    @classmethod
    def scan_match_edges(cls, match_preds: dict, odds_data: dict, min_ev: float = 0.02) -> list:
        """
        全量扫描一场比赛中的所有可选玩法（胜平负、让球胜平负），找出错价 (Mispriced Bets)
        :param match_preds: 来自 DixonColesModel 的预测结果字典
        :param odds_data: 包含 '1x2' 和 'handicap' 赔率的字典
        :param min_ev: 最小期望值门槛 (默认 2% 纯正期望)
        :return: 所有具备正期望 (Edge) 的可投项列表
        """
        results = []

        # 1. 扫描常规胜平负 (1X2)
        if "1x2" in odds_data and odds_data["1x2"]:
            h_odd, d_odd, a_odd = odds_data["1x2"]
            fair_probs = cls.devig_shin([h_odd, d_odd, a_odd])
            model_probs = match_preds["prob_1x2"]

            labels = [("胜 (Home)", "Home", h_odd, 0), 
                      ("平 (Draw)", "Draw", d_odd, 1), 
                      ("负 (Away)", "Away", a_odd, 2)]

            for name, key, odd, idx in labels:
                eval_res = cls.evaluate_edge(model_probs[key], odd, fair_probs[idx])
                if eval_res["ev"] >= min_ev:
                    results.append({
                        "play_type": "常规胜平负",
                        "selection": name,
                        "key": key,
                        **eval_res
                    })

        # 2. 扫描让球胜平负 (Handicap 1X2)
        if "handicap" in odds_data and odds_data["handicap"]:
            hcp_val = odds_data["handicap"]["hcp"]
            h_odd, d_odd, a_odd = odds_data["handicap"]["odds"]
            fair_probs = cls.devig_shin([h_odd, d_odd, a_odd])
            model_probs = match_preds["prob_handicap"]

            hcp_sign = f"+{hcp_val}" if hcp_val > 0 else str(hcp_val)
            labels = [(f"让胜 ({hcp_sign})", "H_Home", h_odd, 0),
                      (f"让平 ({hcp_sign})", "H_Draw", d_odd, 1),
                      (f"让负 ({hcp_sign})", "H_Away", a_odd, 2)]

            for name, key, odd, idx in labels:
                eval_res = cls.evaluate_edge(model_probs[key], odd, fair_probs[idx])
                if eval_res["ev"] >= min_ev:
                    results.append({
                        "play_type": f"让球胜平负({hcp_sign})",
                        "selection": name,
                        "key": key,
                        **eval_res
                    })

        return results
