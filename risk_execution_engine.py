"""
智能风控与 2串1 稳胆锚点组合引擎 (Smart Risk Control & Anchor Execution Engine)
解决“EV>0就上”导致的逆向选择陷阱，以及“双高赔串关加速亏损”的数学谬误。
三大核心机制:
1. CLV (聪明钱资金流) 一票否决门: 机构升水/资金逃离项坚决不碰；
2. 热门-冷门偏差 (FLB) 方差惩罚曲线: 自动对 >3.2 赔率施加非线性方差惩罚；
3. 2串1 稳胆锚点组合器: 严格执行 [高确定性低赔稳胆 (P>=60%)] + [优质中赔正Edge (1.70~2.35)]，杜绝高赔互串。
"""

import numpy as np

class RiskExecutionEngine:
    def __init__(self, flb_lambda: float = 0.04, min_anchor_prob: float = 0.58):
        """
        :param flb_lambda: 高赔冷门方差惩罚系数
        :param min_anchor_prob: 稳胆锚点腿的最低模型胜率门槛 (默认 58%)
        """
        self.flb_lambda = flb_lambda
        self.min_anchor_prob = min_anchor_prob

    def evaluate_clv_gate(self, option_name: str, initial_odd: float, latest_odd: float) -> dict:
        """
        CLV 聪明钱资金流一票否决门
        :param initial_odd: 初盘公允赔率
        :param latest_odd: 即时/终盘赔率
        :return: 判定结果
        """
        if initial_odd <= 0 or latest_odd <= 0:
            return {"passed": True, "reason": "无初终盘赔率变化数据，默认跳过"}

        # 若赔率显著上升 (升水 > 3%)，说明市场聪明钱正在流向对立项，机构降低赔付压力而上调该项
        odd_drift = (latest_odd - initial_odd) / initial_odd
        if odd_drift > 0.035:
            return {
                "passed": False,
                "reason": f"CLV 一票否决: 盘口大幅升水 (+{odd_drift*100:.1f}%)，资金流撤离，模型Edge判定为伪信号"
            }
        
        return {
            "passed": True,
            "reason": f"CLV 通过: 赔率保持平稳或缩水降水 ({odd_drift*100:+.1f}%)，资金流同向"
        }

    def compute_risk_adjusted_ev(self, prob: float, odd: float) -> dict:
        """
        计算考虑热门-冷门偏差 (FLB) 与方差惩罚后的真实风险调整期望值 (Risk-Adjusted EV)
        EV_raw = P * Odd - 1.0
        EV_adj = EV_raw - lambda * max(0, Odd - 3.2)^2
        """
        ev_raw = prob * odd - 1.0

        # 方差惩罚: 赔率超过 3.20 后方差以二次方增加
        variance_penalty = 0.0
        if odd > 3.20:
            variance_penalty = self.flb_lambda * ((odd - 3.20) ** 2)

        ev_adjusted = ev_raw - variance_penalty

        return {
            "prob": prob,
            "odd": odd,
            "ev_raw": ev_raw,
            "variance_penalty": variance_penalty,
            "ev_adjusted": ev_adjusted,
            "is_tradeable": (ev_adjusted > 0.015 and odd <= 3.80)  # 严格限制单注挂牌赔率 <= 3.80
        }

    def generate_anchor_parlays(self, candidates: list[dict], max_parlays: int = 5) -> list[dict]:
        """
        2串1 稳胆锚点组合生成器
        候选必须分流为两池:
        - Pool A (Anchors 稳胆池): 胜率 >= 58%, 赔率在 [1.25, 1.75], 期望风险低
        - Pool B (Edges 价值池): 风险调整后 EV > 0, 赔率在 [1.65, 2.35], 具备正向 Alpha
        组合规则: 严格 1 Anchor + 1 Edge，复合赔率在 [2.10, 3.80] 黄金盈利带
        """
        anchors = []
        edges = []

        for c in candidates:
            odd = c["sp"]
            prob = c["prob"]
            radj = self.compute_risk_adjusted_ev(prob, odd)
            
            # 稳胆判定: 高胜率、赔率适中、期望不倒贴 (EV >= -0.05)
            if prob >= self.min_anchor_prob and 1.25 <= odd <= 1.78 and radj["ev_raw"] >= -0.05:
                anchors.append({**c, **radj, "role": "ANCHOR"})
            
            # 价值腿判定: 风险调整 EV 为正，中等赔率
            if radj["is_tradeable"] and 1.60 <= odd <= 2.35:
                edges.append({**c, **radj, "role": "EDGE"})

        parlays = []
        for a in anchors:
            for e in edges:
                # 排除同一场比赛
                if a["match_num"] == e["match_num"]:
                    continue

                comb_odds = a["sp"] * e["sp"]
                comb_prob = a["prob"] * e["prob"]
                comb_ev = comb_prob * comb_odds - 1.0

                # 复合赔率限制在 [2.10, 3.80]
                if 2.10 <= comb_odds <= 3.80 and comb_ev > 0.02:
                    # 分数凯利建议仓位
                    # f = (b*p - q) / b
                    b = comb_odds - 1.0
                    p = comb_prob
                    q = 1.0 - p
                    full_kelly = max(0.0, (b * p - q) / b) if b > 0 else 0.0
                    suggested_kelly = min(0.05, full_kelly * 0.15)  # 严格 15% 分数凯利，单注最高 5% 银行本金

                    parlays.append({
                        "anchor_leg": f"[{a['match_num']}] {a['match']} {a['play']}-{a['pick']} @{a['sp']:.2f} (胜率: {a['prob']:.1%})",
                        "edge_leg": f"[{e['match_num']}] {e['match']} {e['play']}-{e['pick']} @{e['sp']:.2f} (胜率: {e['prob']:.1%}, EV: {e['ev_adjusted']:+.1%})",
                        "combined_odds": round(comb_odds, 2),
                        "combined_prob": round(comb_prob, 3),
                        "combined_ev": round(comb_ev, 3),
                        "suggested_stake_pct": round(suggested_kelly, 4)
                    })

        # 按复合 EV 排序
        parlays.sort(key=lambda x: x["combined_ev"], reverse=True)
        return parlays[:max_parlays]
