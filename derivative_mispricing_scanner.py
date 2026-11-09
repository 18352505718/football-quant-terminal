"""
衍生盘口错价扫描器 (Derivative Mispricing Scanner)
基于二元负二项分布厚尾比分矩阵，全量扫射竞彩次级衍生盘口 (让球让平、具体比分、总进球数)。
核心逻辑:
机构 90% 的流动性聚焦在 1X2 主盘，衍生盘口往往使用统一的双泊松简易模板机械换算，
在低比分强耦合 (1-0, 1-1, 让平刚好赢1球) 处存在系统性定价盲区。
"""

import numpy as np
from bivariate_nb_model import BivariateNBModel

class DerivativeMispricingScanner:
    def __init__(self, nb_model: BivariateNBModel = None, min_derivative_ev: float = 0.03):
        """
        :param nb_model: 二元负二项分布比分矩阵计算器
        :param min_derivative_ev: 触发衍生错价推荐的最小期望值门槛 (默认 +3%)
        """
        self.nb_model = nb_model if nb_model is not None else BivariateNBModel(dispersion_r=6.0)
        self.min_derivative_ev = min_derivative_ev

    def scan_handicap_draw_mispricing(
        self,
        match_num: str,
        match_name: str,
        lambda_val: float,
        mu_val: float,
        goal_line: int,
        sp_rh: float,
        sp_rd: float,  # 让平 SP (通常在 3.40 ~ 3.95 之间)
        sp_ra: float
    ) -> dict:
        """
        专门扫描高赔“让球让平” (恰好净胜/净负 1 球) 的结构性错价
        """
        mat = self.nb_model.compute_score_matrix(lambda_val, mu_val, max_goals=8)
        
        # 净胜球差矩阵 diff[i, j] = i - j
        diff = np.fromfunction(lambda i, j: i - j, mat.shape)

        # 让球让平判定: diff + goal_line == 0 即 i - j = -goal_line
        # 例1: 主队让 1 球 (goal_line = -1) -> i - j == 1 (主队恰好赢 1 球: 1-0, 2-1, 3-2...)
        # 例2: 主队受让 1 球 (goal_line = +1) -> i - j == -1 (主队恰好输 1 球: 0-1, 1-2, 2-3...)
        p_handicap_draw = float(np.sum(mat[diff + goal_line == 0]))
        p_handicap_home = float(np.sum(mat[diff + goal_line > 0]))
        p_handicap_away = float(np.sum(mat[diff + goal_line < 0]))

        ev_rd = p_handicap_draw * sp_rd - 1.0 if sp_rd > 0 else -1.0
        ev_rh = p_handicap_home * sp_rh - 1.0 if sp_rh > 0 else -1.0
        ev_ra = p_handicap_away * sp_ra - 1.0 if sp_ra > 0 else -1.0

        is_value_rd = (ev_rd >= self.min_derivative_ev and sp_rd >= 3.20)

        # 提取促成“让平”的最主要具体比分贡献
        target_diff = -goal_line
        exact_scores = []
        for x in range(mat.shape[0]):
            y = x - target_diff
            if 0 <= y < mat.shape[1]:
                exact_scores.append((f"{x}:{y}", float(mat[x, y])))
        exact_scores.sort(key=lambda item: item[1], reverse=True)

        return {
            "match_num": match_num,
            "match": match_name,
            "handicap_line": goal_line,
            "p_handicap_draw": round(p_handicap_draw, 4),
            "sp_handicap_draw": sp_rd,
            "ev_handicap_draw": round(ev_rd, 4),
            "is_handicap_draw_gem": is_value_rd,
            "top_contributing_scores": exact_scores[:3],
            "all_handicap_evs": {
                "让胜": round(ev_rh, 4),
                "让平": round(ev_rd, 4),
                "让负": round(ev_ra, 4)
            }
        }

    def scan_correct_scores(
        self,
        match_num: str,
        match_name: str,
        lambda_val: float,
        mu_val: float,
        crs_odds_dict: dict = None
    ) -> list[dict]:
        """
        全量扫描比分盘错价
        :param crs_odds_dict: 形如 {"1:0": 6.5, "1:1": 5.8, "0:0": 9.0...}
        """
        mat = self.nb_model.compute_score_matrix(lambda_val, mu_val, max_goals=6)
        
        score_evals = []
        for x in range(mat.shape[0]):
            for y in range(mat.shape[1]):
                score_str = f"{x}:{y}"
                prob = float(mat[x, y])
                sp = crs_odds_dict.get(score_str, 0.0) if crs_odds_dict else 0.0
                
                ev = prob * sp - 1.0 if sp > 0 else None
                score_evals.append({
                    "score": score_str,
                    "prob": round(prob, 4),
                    "sp": sp,
                    "ev": round(ev, 4) if ev is not None else None,
                    "has_edge": (ev is not None and ev > self.min_derivative_ev)
                })

        score_evals.sort(key=lambda s: s["prob"], reverse=True)
        return score_evals
