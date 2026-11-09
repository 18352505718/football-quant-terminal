"""
Dixon-Coles 泊松比赛预测模型 (Dixon-Coles 1997)
完全独立于博彩市场赔率，仅基于比赛进球、主客场与时间权重估算真实比分联合概率。
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson


class DixonColesModel:
    def __init__(self, xi: float = 0.003, l2_reg: float = 0.005):
        """
        初始化 Dixon-Coles 模型
        :param xi: 时间衰减系数 (默认 0.003，对应半衰期约 230 天左右)
        :param l2_reg: L2/Ridge 正则化系数，防止小样本/无界参数发散导致 SLSQP 崩溃或数值溢出
        """
        self.xi = xi
        self.l2_reg = l2_reg
        self.teams = []
        self.team_to_idx = {}
        self.n_teams = 0
        self.params = None
        self.home_advantage = 0.0
        self.rho = 0.0
        self.attacks = {}
        self.defenses = {}
        self.fitted = False

    @staticmethod
    def _tau(x, y, lambda_val, mu_val, rho):
        """
        Dixon-Coles 对低比分 (0-0, 1-0, 0-1, 1-1) 的相关性修正因子
        """
        if x == 0 and y == 0:
            return 1.0 - lambda_val * mu_val * rho
        elif x == 0 and y == 1:
            return 1.0 + lambda_val * rho
        elif x == 1 and y == 0:
            return 1.0 + mu_val * rho
        elif x == 1 and y == 1:
            return 1.0 - rho
        else:
            return 1.0

    def _negative_log_likelihood(self, params, home_indices, away_indices, home_metrics, away_metrics, weights, home_actual_goals=None, away_actual_goals=None):
        """
        加权负对数似然目标函数 (支持 xG 与连续进球指标)
        """
        att = params[:self.n_teams]
        defe = params[self.n_teams: 2 * self.n_teams]
        gamma = params[2 * self.n_teams]
        rho = params[2 * self.n_teams + 1]

        # 期望进球率 lambda (主) 和 mu (客)，引入数值截断防止指数溢出
        home_exp = np.clip(att[home_indices] + defe[away_indices] + gamma, -10.0, 5.0)
        away_exp = np.clip(att[away_indices] + defe[home_indices], -10.0, 5.0)
        lambda_vals = np.exp(home_exp)
        mu_vals = np.exp(away_exp)

        # tau 修正因子使用真实离散比分 (避免连续 xG 破坏低比分边界)
        if home_actual_goals is None:
            home_actual_goals = np.round(home_metrics).astype(int)
        if away_actual_goals is None:
            away_actual_goals = np.round(away_metrics).astype(int)

        taus = np.ones(len(home_metrics))
        mask_00 = (home_actual_goals == 0) & (away_actual_goals == 0)
        mask_01 = (home_actual_goals == 0) & (away_actual_goals == 1)
        mask_10 = (home_actual_goals == 1) & (away_actual_goals == 0)
        mask_11 = (home_actual_goals == 1) & (away_actual_goals == 1)

        taus[mask_00] = 1.0 - lambda_vals[mask_00] * mu_vals[mask_00] * rho
        taus[mask_01] = 1.0 + lambda_vals[mask_01] * rho
        taus[mask_10] = 1.0 + mu_vals[mask_10] * rho
        taus[mask_11] = 1.0 - rho
        taus = np.clip(taus, 1e-12, None)

        # 拟泊松对数似然 + L2 Ridge 正则化惩罚项
        log_prob = (
            np.log(taus)
            + home_metrics * np.log(lambda_vals) - lambda_vals
            + away_metrics * np.log(mu_vals) - mu_vals
        )

        nll = -np.sum(weights * log_prob) + 0.5 * self.l2_reg * np.sum(att**2 + defe**2)
        return nll

    def fit(self, df: pd.DataFrame, use_xg: bool = True, xg_weight: float = 0.85, max_iter: int = 250):
        """
        拟合历史比赛数据 (支持真实进球与 xG 预期进球融合建模)
        :param df: DataFrame，必须包含:
                   - 'home_team': 主队
                   - 'away_team': 客队
                   - 'home_goals', 'away_goals': 实际进球
                   - 可选 'home_xg', 'away_xg': 真实预期进球 (来自 FootyStats API)
                   - 可选 'days_ago': 距今天数
        :param use_xg: 是否启用 xG 进行攻防能力建模 (消除比分运气方差)
        :param xg_weight: xG 权重比例 (0.0~1.0，如 0.85 表示 85% xG + 15% 真实进球)
        """
        teams_set = sorted(list(set(df['home_team']).union(set(df['away_team']))))
        self.teams = teams_set
        self.n_teams = len(teams_set)
        self.team_to_idx = {team: idx for idx, team in enumerate(teams_set)}

        home_idx = df['home_team'].map(self.team_to_idx).values
        away_idx = df['away_team'].map(self.team_to_idx).values
        home_goals = df['home_goals'].values.astype(int)
        away_goals = df['away_goals'].values.astype(int)

        # 攻防测算目标值: 若启用 xG，使用 xG 与真实进球的加权融合值
        if use_xg and 'home_xg' in df.columns and 'away_xg' in df.columns:
            h_metric = xg_weight * df['home_xg'].values + (1.0 - xg_weight) * home_goals
            a_metric = xg_weight * df['away_xg'].values + (1.0 - xg_weight) * away_goals
        else:
            h_metric = home_goals.astype(float)
            a_metric = away_goals.astype(float)

        # 计算时间衰减权重: w = exp(-xi * days_ago)
        if 'days_ago' in df.columns:
            weights = np.exp(-self.xi * df['days_ago'].values)
        else:
            weights = np.ones(len(df))

        # 参数初始化
        init_att = np.zeros(self.n_teams)
        init_defe = np.zeros(self.n_teams)
        init_gamma = 0.25
        init_rho = -0.05
        init_params = np.concatenate([init_att, init_defe, [init_gamma, init_rho]])

        # 约束条件: sum(attacks) = 0
        cons = ({'type': 'eq', 'fun': lambda params: np.sum(params[:self.n_teams])})
        # 攻防参数施加 [-3.0, 3.0] 物理边界约束，杜绝极值溢出与奇异解
        bounds = [(-3.0, 3.0)] * (2 * self.n_teams) + [(0.0, 1.0), (-0.95, 0.95)]

        # 目标似然函数：使用连续 xG/融合进球值计算对数进球率，保留实际低比分用于 tau 修正
        res = minimize(
            self._negative_log_likelihood,
            init_params,
            args=(home_idx, away_idx, h_metric, a_metric, weights, home_goals, away_goals),
            method='SLSQP',
            constraints=cons,
            bounds=bounds,
            options={'maxiter': max_iter, 'disp': False}
        )

        self.params = res.x
        att = self.params[:self.n_teams]
        defe = self.params[self.n_teams: 2 * self.n_teams]
        self.home_advantage = self.params[2 * self.n_teams]
        self.rho = self.params[2 * self.n_teams + 1]

        self.attacks = {team: att[i] for team, i in self.team_to_idx.items()}
        self.defenses = {team: defe[i] for team, i in self.team_to_idx.items()}
        self.fitted = True
        return self


    def predict_score_matrix(self, home_team: str, away_team: str, max_goals: int = 10) -> np.ndarray:
        """
        预测主客队各种比分的概率矩阵 (max_goals x max_goals)
        matrix[x, y] 即为 主队进 x 球、客队进 y 球的真实概率
        """
        if not self.fitted:
            raise ValueError("Model is not fitted yet. Call fit() first.")

        h_idx = self.team_to_idx[home_team]
        a_idx = self.team_to_idx[away_team]

        att_h = self.params[h_idx]
        def_h = self.params[self.n_teams + h_idx]
        att_a = self.params[a_idx]
        def_a = self.params[self.n_teams + a_idx]

        lambda_val = np.exp(att_h + def_a + self.home_advantage)
        mu_val = np.exp(att_a + def_h)

        matrix = np.zeros((max_goals + 1, max_goals + 1))
        for x in range(max_goals + 1):
            p_x = poisson.pmf(x, lambda_val)
            for y in range(max_goals + 1):
                p_y = poisson.pmf(y, mu_val)
                tau = self._tau(x, y, lambda_val, mu_val, self.rho)
                matrix[x, y] = max(0.0, tau * p_x * p_y)

        # 归一化，确保所有比分概率和为 1
        matrix /= np.sum(matrix)
        return matrix, lambda_val, mu_val

    def predict_match_probabilities(self, home_team: str, away_team: str, handicap: int = 0):
        """
        计算常规胜平负 (1X2) 以及 竞彩让球胜平负 真实概率
        :param handicap: 让球数，例如 -1 表示主队让 1 球，+1 表示客队受让 1 球
        :return: 字典，包含胜平负概率、让球胜平负概率、大小球、预期进球等
        """
        matrix, lambda_val, mu_val = self.predict_score_matrix(home_team, away_team)

        # 1. 常规胜平负 (1X2)
        p_home_win = np.sum(np.tril(matrix, -1))
        p_draw = np.sum(np.diag(matrix))
        p_away_win = np.sum(np.triu(matrix, 1))

        # 2. 让球胜平负 (Handicap 1X2)
        # 主队净胜球差 x - y
        diff_matrix = np.fromfunction(lambda i, j: i - j, matrix.shape)
        p_hcp_home = np.sum(matrix[diff_matrix + handicap > 0])
        p_hcp_draw = np.sum(matrix[diff_matrix + handicap == 0])
        p_hcp_away = np.sum(matrix[diff_matrix + handicap < 0])

        # 3. 大小球 (Over / Under 2.5)
        total_goals_matrix = np.fromfunction(lambda i, j: i + j, matrix.shape)
        p_over_25 = np.sum(matrix[total_goals_matrix > 2.5])
        p_under_25 = np.sum(matrix[total_goals_matrix < 2.5])

        return {
            "home_team": home_team,
            "away_team": away_team,
            "lambda_home": lambda_val,
            "mu_away": mu_val,
            "prob_1x2": {
                "Home": float(p_home_win),
                "Draw": float(p_draw),
                "Away": float(p_away_win),
            },
            "prob_handicap": {
                "handicap": handicap,
                "H_Home": float(p_hcp_home),
                "H_Draw": float(p_hcp_draw),
                "H_Away": float(p_hcp_away),
            },
            "prob_over_under_25": {
                "Over": float(p_over_25),
                "Under": float(p_under_25),
            },
            "score_matrix": matrix
        }
