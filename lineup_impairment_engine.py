"""
赛前 60 分钟阵容冲击与战力折损引擎 (Lineup Impairment & Rotation Shock Engine)
开赛前 50~60 分钟抓取官方确认首发 11 人名单 (Confirmed Lineup)，量化轮换与核心伤停的战力折损。
核心逻辑:
豪门球队若因欧战出线或赛程密集进行 4~5 人轮换，战力会发生 15%~30% 的阶跃式下跌。
纯赛季历史统计数据无法感知该断崖，本模块通过球员级评分修正攻防期望值 (lambda, mu)。
"""

import os
import json
import numpy as np

class LineupImpairmentEngine:
    def __init__(self, lineups_dir: str = None):
        """
        :param lineups_dir: 本地或云盘阵容缓存目录 (如 edge/data/lineups/YYYYMMDD/)
        """
        self.lineups_dir = lineups_dir

    @staticmethod
    def calculate_xi_strength(players: list[dict]) -> dict:
        """
        计算单队首发 11 人的进攻中轴与防守中轴综合实力评分
        """
        if not players:
            return {"attack_power": 1.0, "defense_power": 1.0, "overall_power": 1.0, "count": 0}

        att_scores = []
        def_scores = []
        all_scores = []

        for p in players:
            score = float(p.get("ai_score") or 0.65)
            pos = p.get("position", "")
            all_scores.append(score)

            if pos in ["F", "M"]:  # 前锋与中场核心
                att_scores.append(score)
            if pos in ["D", "G"]:  # 后卫与门将
                def_scores.append(score)

        # 全主力基准均分约为 0.72 (五大联赛豪门主力常在 0.75~0.85，替补常在 0.60~0.65)
        baseline_score_per_player = 0.72
        
        avg_att = np.mean(att_scores) if att_scores else baseline_score_per_player
        avg_def = np.mean(def_scores) if def_scores else baseline_score_per_player
        avg_overall = np.mean(all_scores) if all_scores else baseline_score_per_player

        # 战力倍率
        att_ratio = float(np.clip(avg_att / baseline_score_per_player, 0.70, 1.25))
        def_ratio = float(np.clip(avg_def / baseline_score_per_player, 0.70, 1.25))
        overall_ratio = float(np.clip(avg_overall / baseline_score_per_player, 0.70, 1.25))

        return {
            "attack_power": round(att_ratio, 3),
            "defense_power": round(def_ratio, 3),
            "overall_power": round(overall_ratio, 3),
            "count": len(players)
        }

    def load_confirmed_lineup(self, event_id: str, date_str: str = "20261104") -> dict:
        """
        尝试从本地镜像加载指定场次的确认首发
        """
        if not self.lineups_dir or not os.path.exists(self.lineups_dir):
            return None

        # 检查日目录
        date_dir = os.path.join(self.lineups_dir, date_str)
        target_file = os.path.join(date_dir, f"{event_id}.json")
        if not os.path.exists(target_file):
            return None

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception:
            return None

    def apply_lineup_impairment(
        self,
        base_lambda: float,
        base_mu: float,
        home_players: list[dict] = None,
        away_players: list[dict] = None
    ) -> tuple[float, float, dict]:
        """
        根据双方首发 11 人阵容，修正主客期望进球率 lambda 与 mu
        :return: (adjusted_lambda, adjusted_mu, shock_report)
        """
        h_profile = self.calculate_xi_strength(home_players)
        a_profile = self.calculate_xi_strength(away_players)

        # 进攻折损: 主队进攻实力影响 lambda；客队防守减弱则提升主队 lambda
        # lambda_adj = base_lambda * (h_att / a_def)
        h_att_factor = h_profile["attack_power"]
        a_def_factor = a_profile["defense_power"]
        
        a_att_factor = a_profile["attack_power"]
        h_def_factor = h_profile["defense_power"]

        adj_lambda = max(0.2, base_lambda * (h_att_factor / max(0.5, a_def_factor)))
        adj_mu = max(0.2, base_mu * (a_att_factor / max(0.5, h_def_factor)))

        # 轮换警报: 任一方战力折损低于 0.88 (轮换超过 3~4 名主力)
        h_shock = (h_profile["overall_power"] < 0.88)
        a_shock = (a_profile["overall_power"] < 0.88)

        shock_report = {
            "home_lineup_power": h_profile["overall_power"],
            "away_lineup_power": a_profile["overall_power"],
            "home_rotation_shock": h_shock,
            "away_rotation_shock": a_shock,
            "warning": "豪门重大轮换预警: 核心战力显著折损！" if (h_shock or a_shock) else "阵容正常，主力基本齐整"
        }

        return round(adj_lambda, 3), round(adj_mu, 3), shock_report
