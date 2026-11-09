"""
二元负二项分布比分矩阵与动态相关性模型 (Bivariate Negative Binomial Matrix Generator)
针对传统双泊松模型方差=均值、无法刻画比分过度离散 (Overdispersion) 的理论缺陷。
引入离散度参数 r 与动态低比分相关系数 rho(lambda + mu)，提升平局与极端比分的贴合度。
"""

import numpy as np
from scipy.special import gammaln

class BivariateNBModel:
    def __init__(self, dispersion_r: float = 6.0):
        """
        :param dispersion_r: 负二项分布离散度参数 (通常足球在 4.5 ~ 8.0 之间，值越小厚尾越明显)
        """
        self.r = dispersion_r

    @staticmethod
    def get_dynamic_rho(total_expected_goals: float) -> float:
        """
        根据全场总期望进球动态调整低比分相关系数 rho
        防守沉闷/小球预期比赛，低比分强耦合 (rho 更负)；大开大合对攻战，低比分影响弱化 (rho 趋近 0)
        """
        if total_expected_goals < 2.2:
            return -0.11
        elif total_expected_goals <= 3.2:
            return -0.06
        else:
            return -0.025

    def nb_pmf(self, k: int, mu: float) -> float:
        """
        负二项分布单变量 PMF 计算 (带 gammaln 数值防溢出)
        E[X] = mu, Var[X] = mu + mu^2 / r
        """
        if mu <= 0:
            return 1.0 if k == 0 else 0.0
        p = self.r / (self.r + mu)
        log_coef = gammaln(k + self.r) - gammaln(k + 1) - gammaln(self.r)
        log_prob = log_coef + self.r * np.log(max(1e-12, p)) + k * np.log(max(1e-12, 1.0 - p))
        return float(np.exp(log_prob))

    @staticmethod
    def tau(x: int, y: int, lambda_val: float, mu_val: float, rho: float) -> float:
        """
        Dixon-Coles 低比分相关性修正因子
        """
        if x == 0 and y == 0:
            return max(0.0, 1.0 - lambda_val * mu_val * rho)
        elif x == 0 and y == 1:
            return max(0.0, 1.0 + lambda_val * rho)
        elif x == 1 and y == 0:
            return max(0.0, 1.0 + mu_val * rho)
        elif x == 1 and y == 1:
            return max(0.0, 1.0 - rho)
        else:
            return 1.0

    def compute_score_matrix(
        self, 
        lambda_val: float, 
        mu_val: float, 
        max_goals: int = 8,
        custom_rho: float = None
    ) -> np.ndarray:
        """
        计算 (max_goals + 1) x (max_goals + 1) 联合比分概率矩阵
        """
        rho = custom_rho if custom_rho is not None else self.get_dynamic_rho(lambda_val + mu_val)

        p_h = np.array([self.nb_pmf(x, lambda_val) for x in range(max_goals + 1)])
        p_a = np.array([self.nb_pmf(y, mu_val) for y in range(max_goals + 1)])

        mat = np.zeros((max_goals + 1, max_goals + 1))
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                t = self.tau(x, y, lambda_val, mu_val, rho)
                mat[x, y] = max(0.0, t * p_h[x] * p_a[y])

        total_p = np.sum(mat)
        if total_p > 0:
            mat /= total_p
        return mat

    def predict_match_probs(
        self, 
        lambda_val: float, 
        mu_val: float, 
        handicap: int = 0,
        max_goals: int = 8
    ) -> dict:
        """
        输出常规胜平负 (1X2)、让球胜平负、大小球及顶序高频比分
        """
        mat = self.compute_score_matrix(lambda_val, mu_val, max_goals=max_goals)

        # 胜平负
        p_h = float(np.sum(np.tril(mat, -1)))
        p_d = float(np.sum(np.diag(mat)))
        p_a = float(np.sum(np.triu(mat, 1)))

        # 让球盘
        diff = np.fromfunction(lambda i, j: i - j, mat.shape)
        p_rh = float(np.sum(mat[diff + handicap > 0]))
        p_rd = float(np.sum(mat[diff + handicap == 0]))
        p_ra = float(np.sum(mat[diff + handicap < 0]))

        # 大小球 (Over / Under 2.5)
        sum_goals = np.fromfunction(lambda i, j: i + j, mat.shape)
        p_over_25 = float(np.sum(mat[sum_goals > 2.5]))
        p_under_25 = float(np.sum(mat[sum_goals < 2.5]))

        # Top 3 比分
        flat_indices = np.argsort(mat.ravel())[::-1][:3]
        top3_scores = []
        for idx in flat_indices:
            hx, ay = np.unravel_index(idx, mat.shape)
            top3_scores.append((f"{hx}:{ay}", float(mat[hx, ay])))

        return {
            "lambda_home": lambda_val,
            "mu_away": mu_val,
            "1x2": [p_h, p_d, p_a],
            "handicap_1x2": [p_rh, p_rd, p_ra],
            "handicap_line": handicap,
            "over_25": p_over_25,
            "under_25": p_under_25,
            "top3_scores": top3_scores
        }
