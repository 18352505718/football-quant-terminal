"""
时滞套利与 CLV 捕食引擎 (Latency Arbitrage & Sharp Lag Hunter)
捕获海外锐度机构 (Pinnacle/Betfair) 资金变动与中国竞彩官方调价时滞之间的确定性价差。
核心逻辑:
当 Pinnacle/海外主流盘口某项发生剧烈缩水/资金涌入 (Delta_P > +2.5% 或 赔率下降 > 5%)，
而竞彩官方 SP 处于调价真空期 (未跟跌) 时，该项对竞彩产生瞬时纯正期望 (Free EV)。
"""

import numpy as np

class LatencyArbitrageEngine:
    def __init__(self, min_arb_edge: float = 0.02, min_sharp_drift: float = 0.025):
        """
        :param min_arb_edge: 触发时滞套利预警的最低公允期望值 (默认 +2%)
        :param min_sharp_drift: 海外锐度盘口隐含概率的最低正向漂移幅度 (默认 2.5pp)
        """
        self.min_arb_edge = min_arb_edge
        self.min_sharp_drift = min_sharp_drift

    @staticmethod
    def devig_pinnacle(odds: list[float]) -> list[float]:
        """
        对 Pinnacle 初/终盘赔率进行乘法去水，提取全球公允概率 (True Implied Probability)
        """
        invs = [1.0 / o for o in odds if o > 0]
        s = sum(invs)
        if s <= 0:
            return [1.0/3, 1.0/3, 1.0/3]
        return [inv / s for inv in invs]

    def scan_latency_opportunity(
        self,
        match_name: str,
        match_num: str,
        sharp_open_odds: list[float],   # [h, d, a] 海外初盘
        sharp_latest_odds: list[float], # [h, d, a] 海外最新终盘
        sporttery_odds: list[float],    # [h, d, a] 竞彩当前挂牌 SP
        labels: list[str] = None
    ) -> list[dict]:
        """
        扫描单场比赛中的时滞错价与捕食机会
        """
        if labels is None:
            labels = ["主胜", "平局", "客胜"]

        p_open = self.devig_pinnacle(sharp_open_odds)
        p_latest = self.devig_pinnacle(sharp_latest_odds)

        opportunities = []

        for idx in range(3):
            drift = p_latest[idx] - p_open[idx]  # 海外公允概率漂移
            odd_change_pct = (sharp_latest_odds[idx] - sharp_open_odds[idx]) / sharp_open_odds[idx]
            
            sp = sporttery_odds[idx]
            if sp <= 1.0:
                continue

            # 瞬时 EV: 用全球最新公允概率乘竞彩挂牌 SP
            instant_ev = p_latest[idx] * sp - 1.0

            # 判定是否形成时滞套利窗口:
            # 1. 海外锐度资金强力杀入 (概率上升超过门槛，或赔率显著下行)
            # 2. 竞彩挂牌赔率相对海外公允概率依然具备正期望
            is_arb = (drift >= self.min_sharp_drift and instant_ev >= self.min_arb_edge)
            
            # 判定是否形成“接盘陷阱” (海外资金疯狂出逃，而竞彩彩民还在盲打)
            is_trap = (drift <= -0.030 and instant_ev < -0.08)

            opportunities.append({
                "match_num": match_num,
                "match": match_name,
                "pick": labels[idx],
                "sharp_open": sharp_open_odds[idx],
                "sharp_latest": sharp_latest_odds[idx],
                "sharp_prob_open": round(p_open[idx], 4),
                "sharp_prob_latest": round(p_latest[idx], 4),
                "prob_drift": round(drift, 4),
                "odd_change_pct": round(odd_change_pct, 4),
                "sporttery_sp": sp,
                "instant_ev": round(instant_ev, 4),
                "is_arbitrage_target": is_arb,
                "is_toxic_trap": is_trap,
                "action": "STRONG_BUY_LAG" if is_arb else ("STRONG_AVOID_TRAP" if is_trap else "HOLD")
            })

        return opportunities
