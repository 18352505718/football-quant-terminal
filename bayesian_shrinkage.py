"""
贝叶斯市场收缩与融合校准层 (Bayesian Market Shrinkage & G2 Decision Gate)
解决模型小样本估计方差过大、极端冷门过拟合问题。
融合逻辑: P_final = alpha * P_market + (1 - alpha) * P_model
决策逻辑: G2 换集否决门 (若模型与市场首选不同，需满足超额置信度 swap_conf >= threshold 才允许替换市场)
"""

import numpy as np

class BayesianShrinkageEngine:
    def __init__(self, default_alpha: float = 0.80, g2_swap_threshold: float = 0.015):
        """
        :param default_alpha: 市场公允概率权重 (0.75 ~ 0.85 之间通常使综合 Log-Loss 达到极小值)
        :param g2_swap_threshold: G2 换集门置信度阈值 (默认 1.5pp，防止低置信噪声换丢正确市场答案)
        """
        self.default_alpha = default_alpha
        self.g2_swap_threshold = g2_swap_threshold

    @staticmethod
    def blend_probabilities(market_probs: list[float], model_probs: list[float], alpha: float = 0.80) -> list[float]:
        """
        贝叶斯凸组合概率融合
        :param market_probs: 市场 Shin 去水公允概率 [p_h, p_d, p_a]
        :param model_probs: 物理模型预测概率 [p_h, p_d, p_a]
        :param alpha: 市场先验拉紧系数
        :return: 归一化融合概率
        """
        m_arr = np.array(market_probs, dtype=float)
        p_arr = np.array(model_probs, dtype=float)

        # 凸组合
        blended = alpha * m_arr + (1.0 - alpha) * p_arr
        blended = np.clip(blended, 1e-6, 1.0)
        blended = blended / np.sum(blended)
        return blended.tolist()

    def evaluate_g2_gate(
        self, 
        market_probs: list[float], 
        model_probs: list[float], 
        labels: list[str] = None
    ) -> dict:
        """
        G2 换集否决门评估器
        :return: dict 包含:
          - fused_probs: 最终采纳概率
          - is_swapped: 是否颠覆了市场第一顺位
          - gate_status: 'ACCEPTED' / 'REJECTED_FALLBACK_TO_MARKET' / 'CONCORDANT'
          - swap_conf: 置信度差额
        """
        if labels is None:
            labels = ["胜", "平", "负"]

        m_top_idx = int(np.argmax(market_probs))
        p_top_idx = int(np.argmax(model_probs))

        # 默认融合
        fused = self.blend_probabilities(market_probs, model_probs, self.default_alpha)
        fused_top_idx = int(np.argmax(fused))

        # 检查是否发生换集 (首选推荐与市场不同)
        is_swapped = (fused_top_idx != m_top_idx)

        if not is_swapped:
            return {
                "fused_probs": fused,
                "is_swapped": False,
                "gate_status": "CONCORDANT",
                "recommended_pick": labels[fused_top_idx],
                "confidence_gap": float(fused[fused_top_idx] - fused[m_top_idx])
            }

        # 计算模型的超额置信度: P_model(候选) - P_model(市场第一)
        swap_conf = float(model_probs[fused_top_idx] - model_probs[m_top_idx])

        if swap_conf >= self.g2_swap_threshold:
            # 允许颠覆市场
            return {
                "fused_probs": fused,
                "is_swapped": True,
                "gate_status": "ACCEPTED",
                "recommended_pick": labels[fused_top_idx],
                "swap_conf": swap_conf,
                "reason": f"模型对 [{labels[fused_top_idx]}] 的置信优势 (+{swap_conf*100:.2f}pp) 超过 G2 门槛 (+{self.g2_swap_threshold*100:.2f}pp)"
            }
        else:
            # 置信不足，G2 否决门生效，退回市场去水第一顺位，防止噪声损伤总命中
            return {
                "fused_probs": market_probs,
                "is_swapped": False,
                "gate_status": "REJECTED_FALLBACK_TO_MARKET",
                "recommended_pick": labels[m_top_idx],
                "swap_conf": swap_conf,
                "reason": f"模型置信优势 (+{swap_conf*100:.2f}pp) 未达 G2 门槛 (+{self.g2_swap_threshold*100:.2f}pp)，一票否决回退市场"
            }
