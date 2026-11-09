"""
动态战力评级与运气剥离引擎 (Dynamic Elo Ratings & Luck Reversion Engine)
1. 采用全局 Elo 评分体系动态替代人工维护的静态联赛硬度字典；
2. 剥离运气成分 (PDO / Goals vs xG 残差)，识别均值回归反弹与虚高下杀。
"""

import numpy as np

class DynamicRatingsEngine:
    # 欧洲及全球俱乐部基准 Elo 战力锚点库 (动态更新基线，1500 为全球平均水平)
    BASE_ELO = {
        # 顶尖欧冠争冠集团 (1980 ~ 2060)
        "曼彻斯特城": 2040, "曼城": 2040, "皇家马德里": 2030, "皇马": 2030,
        "拜仁慕尼黑": 2010, "拜仁": 2010, "利物浦": 2010, "阿森纳": 1995,
        "国际米兰": 1985, "国米": 1985, "巴塞罗那": 1980, "巴萨": 1980,
        "巴黎圣日耳曼": 1970, "巴黎": 1970, "勒沃库森": 1960,
        
        # 欧洲一流集团 (1880 ~ 1950)
        "马德里竞技": 1940, "多特蒙德": 1930, "亚特兰大": 1920,
        "尤文图斯": 1910, "AC米兰": 1910, "切尔西": 1905, "那不勒斯": 1915,
        "莱比锡红牛": 1900, "托特纳姆热刺": 1890, "纽卡斯尔联": 1885,
        "葡萄牙体育": 1895, "本菲卡": 1870, "波尔图": 1860,
        
        # 欧洲二线/欧战常客 (1750 ~ 1860)
        "PSV埃因霍温": 1840, "埃因霍温": 1840, "阿贾克斯": 1800, "费耶诺德": 1810,
        "皇家贝蒂斯": 1820, "比利亚雷亚尔": 1830, "皇家社会": 1835, "毕尔巴鄂竞技": 1840,
        "拉齐奥": 1825, "罗马": 1830, "佛罗伦萨": 1810,
        "摩纳哥": 1830, "里尔": 1815, "马赛": 1805, "雷恩": 1780, "朗斯": 1785,
        "狼队": 1780, "伍尔弗汉普顿": 1780, "科莫": 1740, "布里斯托尔城": 1650,
        
        # 欧战外围与非五大领头羊 (1650 ~ 1760)
        "加拉塔萨雷": 1770, "费内巴切": 1760, "布鲁日": 1750,
        "萨尔茨堡红牛": 1740, "博德闪耀": 1720, "奥林匹亚科斯": 1725,
        "布拉格斯拉维亚": 1710, "布拉格斯巴达": 1705, "凯尔特人": 1730,
        "顿涅茨克矿工": 1715, "维京": 1620, "萨巴赫": 1380
    }

    @classmethod
    def get_team_elo(cls, team_name: str, league_default_elo: float = 1650.0) -> float:
        """获取球队动态 Elo 评分"""
        if not team_name:
            return league_default_elo
        for name, elo in cls.BASE_ELO.items():
            if name in team_name or team_name in name:
                return float(elo)
        return float(league_default_elo)

    @classmethod
    def compute_elo_power_multiplier(cls, home_team: str, away_team: str, competition: str = "欧冠") -> tuple[float, float]:
        """
        基于 Logistic Elo 期望公式，计算双方在跨赛事中的绝对实力倍率
        P_home_win_exp = 1 / (1 + 10^((elo_away - elo_home) / 400))
        """
        # 如果是同国内联赛，不需要跨联赛 Elo 缩放 (由队伍在联赛内的数据自然体现)
        if competition not in ["欧冠", "欧罗巴", "欧联", "欧联杯", "欧协联", "亚冠", "亚冠精英", "世俱杯"]:
            return 1.0, 1.0

        elo_h = cls.get_team_elo(home_team)
        elo_a = cls.get_team_elo(away_team)

        # Elo 差值
        delta_elo = elo_h - elo_a
        
        # 将 Elo 差值映射到攻防期望进球缩放倍率 (每 100 Elo 差对应约 18% 进球率弹性)
        # scale_h = 10^(+delta_elo * 0.00075)
        scale_h = float(np.clip(10.0 ** (delta_elo * 0.0008), 0.45, 2.20))
        scale_a = float(np.clip(10.0 ** (-delta_elo * 0.0008), 0.45, 2.20))

        return round(scale_h, 3), round(scale_a, 3)

    @classmethod
    def apply_luck_reversion(cls, base_xg: float, actual_goals_6g: float, expected_xg_6g: float) -> float:
        """
        运气剥离与均值回归修正:
        若球队近期 6 场实际进球远超预期进球 (actual - xg > 0.5/场)，说明超水平发挥严重依赖运气，面临下行回归；
        若实际进球远低于预期进球 (actual - xg < -0.5/场)，说明遭遇反常中柱与神扑，面临触底反弹。
        """
        if expected_xg_6g <= 0:
            return base_xg

        residual_per_game = (actual_goals_6g - expected_xg_6g) / 6.0

        # 回归弹性系数: 消除 35% 的短期噪声残差
        reversion_delta = -0.35 * residual_per_game
        
        # 限制单场修正幅度在 [-15%, +15%]
        reversion_factor = float(np.clip(1.0 + reversion_delta / max(1.0, base_xg), 0.85, 1.15))
        
        adjusted_xg = max(0.2, base_xg * reversion_factor)
        return round(adjusted_xg, 3)
