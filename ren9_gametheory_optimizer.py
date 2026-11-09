"""
任九与传统胜负彩博弈优化器 (Ren 9 & Pari-Mutuel Game-Theoretic Optimizer)
解决传统胜负彩“与公众彩民博弈、而非与庄家博弈”的奖池分配特征。
核心逻辑:
公众彩民存在极端的“豪门偏执与冷平忽视”，导致全正路奖金极度缩水 (倒挂至几十元)；
本模块通过计算 [物理公允概率] / [公众投注比例] 的奖池价值比 (Value Ratio)，
采用博弈论组合树构建【核心稳胆 + 高价值冷平对冲】的正期望任九票面。
"""

import numpy as np

class Ren9GameTheoryOptimizer:
    def __init__(self, target_budget_yuan: int = 64):
        """
        :param target_budget_yuan: 目标票面预算 (如 16 元 / 32 元 / 64 元 / 128 元)
        """
        self.target_budget_yuan = target_budget_yuan

    @staticmethod
    def estimate_public_bet_ratio(fair_probs: list[float], sp_odds: list[float]) -> list[float]:
        """
        根据竞彩返还率与大众投注心理，估算公众彩民在 [胜, 平, 负] 上的真实资金投注比例
        公众普遍追捧低赔热门 (放大高胜率偏置)，压低冷平与冷负比例
        """
        # 公众倾斜幂律: gamma > 1.0 放大热门
        raw_p = np.array(fair_probs, dtype=float)
        # 大众倾向对胜率最高项赋予额外 +8%~15% 的过度集中
        max_idx = int(np.argmax(raw_p))
        public_p = raw_p ** 1.35
        public_p /= np.sum(public_p)
        return public_p.tolist()

    def evaluate_game_theoretic_nodes(self, match_data: dict) -> dict:
        """
        评估一场比赛三项结果的物理概率与奖池价值比 (Value Ratio)
        """
        fair_probs = match_data["fair_probs"]  # [p_h, p_d, p_a]
        sp_odds = match_data.get("sp_odds", [2.0, 3.0, 3.0])
        public_probs = self.estimate_public_bet_ratio(fair_probs, sp_odds)

        # 价值比 Value Ratio = 物理概率 / 公众投注比例
        # VR > 1.25 表示大众严重弃选、具有极高奖池杠杆价值；VR < 0.70 表示大众过度拥挤、奖金缩水
        value_ratios = [fair_probs[i] / max(0.02, public_probs[i]) for i in range(3)]

        labels = ["3", "1", "0"]  # 胜平负
        options = []
        for i in range(3):
            options.append({
                "opt": labels[i],
                "fair_prob": round(fair_probs[i], 3),
                "public_prob": round(public_probs[i], 3),
                "value_ratio": round(value_ratios[i], 2),
                "is_pool_gem": (value_ratios[i] >= 1.25 and fair_probs[i] >= 0.20),
                "is_overcrowded": (value_ratios[i] < 0.75)
            })

        # 挑选最稳单选与最佳双选
        sorted_by_prob = sorted(options, key=lambda x: x["fair_prob"], reverse=True)
        primary_pick = sorted_by_prob[0]["opt"]
        
        # 次选: 排除首选后，优先考虑兼具胜率与高奖池价值比的防冷项 (防冷平通常优先于防无溢价死冷)
        remaining_options = [opt for opt in options if opt["opt"] != primary_pick]
        second_candidates = sorted(remaining_options, key=lambda x: (x["fair_prob"] * x["value_ratio"]), reverse=True)
        secondary_pick = second_candidates[0]["opt"] if second_candidates else "1"

        return {
            "match_num": match_data.get("match_num", ""),
            "match": match_data.get("match", ""),
            "league": match_data.get("league", ""),
            "primary_pick": primary_pick,
            "secondary_pick": secondary_pick,
            "options": options,
            "top_prob": sorted_by_prob[0]["fair_prob"]
        }

    def build_optimal_ren9_ticket(self, evaluated_matches: list[dict]) -> dict:
        """
        从候选赛事中精选 9 场，构建符合预算的最优博弈任九方案
        """
        # 1. 过滤并按可控度排序
        # 稳胆类场次: 最高概率越高越好 (排在最前作为单选)
        matches_ranked = sorted(evaluated_matches, key=lambda m: m["top_prob"], reverse=True)

        if len(matches_ranked) < 9:
            raise ValueError(f"候选场次不足 9 场 (仅 {len(matches_ranked)} 场)")

        selected_9 = matches_ranked[:9]

        # 2. 预算分配: 64 元 = 2^5 = 5 个双选 + 4 个单选 (32注 = 64元)
        # 若预算 16 元 = 2^3 = 3 个双选 + 6 个单选 (8注 = 16元)
        max_doubles = int(np.log2(self.target_budget_yuan / 2))
        max_doubles = max(0, min(6, max_doubles))

        # 最稳的 (9 - max_doubles) 场作为单选；其余场次双选防冷
        num_singles = 9 - max_doubles
        ticket_legs = []

        for idx, m in enumerate(selected_9):
            if idx < num_singles:
                # 单选
                picks = [m["primary_pick"]]
                leg_type = "单选"
            else:
                # 双选 (主推 + 高价值防冷)
                picks = sorted(list(set([m["primary_pick"], m["secondary_pick"]])))
                leg_type = "双选防冷"

            ticket_legs.append({
                "match_num": m["match_num"],
                "match": m["match"],
                "league": m["league"],
                "picks": "/".join(picks),
                "leg_type": leg_type,
                "top_prob": m["top_prob"]
            })

        total_combinations = int(2 ** max_doubles)
        cost_yuan = total_combinations * 2

        return {
            "selected_matches_count": 9,
            "num_singles": num_singles,
            "num_doubles": max_doubles,
            "total_combinations": total_combinations,
            "cost_yuan": cost_yuan,
            "ticket_legs": ticket_legs
        }
