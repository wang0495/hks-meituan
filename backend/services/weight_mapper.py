"""CityFlow 可学习权重映射模型。

将语义"需求向量"转化为求解器"权重调整量"。

核心架构:
  LLM (语义层)          映射模型 (数值层)        求解器 (执行层)
  只提取方向             把方向转成具体权重       只用权重算路线
  不出数值               每人独立参数             不关心权重来源

学习机制:
  - 每个用户持有自己的 delta 参数（独立个性化）
  - 新用户使用全局基线（基于画像模板初始化）
  - 用户反馈后微调 delta（在线学习，每步 ±0.02~0.05）
  - 不突变：渐变渐进
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 全局基线权重映射表
# 每条: [需求向量维度 → 对某个权重的贡献系数]
# 正的系数表示：该需求越强，对应权重越大
# ---------------------------------------------------------------------------

_BASE_MAPPING: dict[str, dict[str, float]] = {
    # 位移成本权重 alpha (default=1.0)
    "alpha": {
        "efficiency_seeking": 0.6,
        "excitement_seeking": -0.1,
        "tranquility_seeking": 0.0,
        "budget_sensitivity": 0.0,
        "novelty_seeking": 0.1,
        "social_desire": -0.1,
        "physical_energy": 0.0,
        "_bias": 1.0,
    },
    # 情绪收益权重 beta (default=0.5)
    "beta": {
        "efficiency_seeking": -0.3,
        "excitement_seeking": 0.5,
        "tranquility_seeking": 0.4,
        "budget_sensitivity": 0.0,
        "novelty_seeking": 0.3,
        "social_desire": 0.2,
        "physical_energy": 0.1,
        "_bias": 0.5,
    },
    # 疲劳惩罚权重 gamma (default=0.2)
    "gamma": {
        "efficiency_seeking": -0.1,
        "excitement_seeking": 0.0,
        "tranquility_seeking": 0.3,
        "budget_sensitivity": 0.0,
        "novelty_seeking": 0.0,
        "social_desire": 0.0,
        "physical_energy": -0.3,
        "_bias": 0.2,
    },
    # 同类惩罚权重 delta (default=0.8)
    "delta": {
        "efficiency_seeking": 0.2,
        "excitement_seeking": 0.1,
        "tranquility_seeking": 0.3,
        "budget_sensitivity": 0.0,
        "novelty_seeking": 0.4,
        "social_desire": 0.1,
        "physical_energy": 0.0,
        "_bias": 0.8,
    },
    # 预算约束严格度 budget_strictness (default=1.0)
    "budget_strictness": {
        "efficiency_seeking": 0.0,
        "excitement_seeking": 0.0,
        "tranquility_seeking": 0.0,
        "budget_sensitivity": 0.6,
        "novelty_seeking": -0.1,
        "social_desire": 0.0,
        "physical_energy": 0.0,
        "_bias": 0.5,
    },
}

# 权重取值范围
_WEIGHT_RANGE = (0.01, 3.0)

# 学习步长
_LEARNING_RATE_POSITIVE = 0.02  # 采纳
_LEARNING_RATE_NEGATIVE = 0.05  # 拒绝


class WeightMapper:
    """需求向量 → 求解器权重的映射器。

    每个用户持有一个独立的偏移量矩阵（_deltas），
    从全局基线开始，随用户反馈渐进调整。

    用法:
        mapper = WeightMapper("user_123")
        # 从 LTM 恢复
        mapper.from_dict(ltm_data)

        # 计算权重
        demand = {"efficiency_seeking": 0.8, "tranquility_seeking": 0.2}
        weights = mapper.compute_weights(demand)

        # 用户反馈后更新
        mapper.update_from_feedback(demand, weights, "accepted")
        # 保存到 LTM
        ltm.save_weight_mapper(user_id, mapper.to_dict())
    """

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        # 用户个人偏移量（与 _BASE_MAPPING 同结构，初始全0）
        self._deltas: dict[str, dict[str, float]] = {}
        self._init_deltas()

    def _init_deltas(self) -> None:
        """初始化用户偏移量（全0）。"""
        self._deltas = {}
        for weight_name, dims in _BASE_MAPPING.items():
            self._deltas[weight_name] = {k: 0.0 for k in dims if not k.startswith("_")}

    def compute_weights(self, demand_vector: dict) -> dict[str, float]:
        """将需求向量映射为求解器权重。

        公式: weight = bias + Σ(dim_value × (base_coef + user_delta))

        参数:
            demand_vector: {"efficiency_seeking": 0.8, "tranquility_seeking": 0.2, ...}

        返回:
            {"alpha": 1.32, "beta": 0.42, "gamma": 0.18, "delta": 1.04, "budget_strictness": 0.56}
        """
        result = {}
        lo, hi = _WEIGHT_RANGE
        for weight_name, dim_map in _BASE_MAPPING.items():
            bias = dim_map.get("_bias", 0.0)
            total = bias
            for dim, value in demand_vector.items():
                if dim.startswith("_"):
                    continue
                if dim in dim_map:
                    base_coef = dim_map[dim]
                    user_delta = self._deltas.get(weight_name, {}).get(dim, 0.0)
                    total += value * (base_coef + user_delta)
            result[weight_name] = max(lo, min(hi, total))
        return result

    def update_from_feedback(
        self,
        demand_vector: dict,
        applied_weights: dict,
        feedback: str,
        modification_hint: str | None = None,
    ) -> dict[str, float]:
        """根据用户反馈更新映射参数（在线学习）。

        更新规则:
        - "accepted": 正强化（小幅增大已使用维度的系数）
        - "rejected": 负强化（减小高贡献维度的系数）
        - "modified": 分析修改方向，调整相关维度的系数

        返回: 更新后的权重
        """
        if feedback == "accepted":
            self._apply_positive(demand_vector)

        elif feedback == "rejected":
            self._apply_negative(demand_vector)

        elif feedback == "modified" and modification_hint:
            self._apply_modified(modification_hint)

        return self.compute_weights(demand_vector)

    # ── 内部学习逻辑 ──────────────────────────────────────────────

    def _apply_positive(self, demand_vector: dict) -> None:
        """正强化：对需求值 > 0.3 的维度，小幅度增加其系数。"""
        for weight_name in _BASE_MAPPING:
            for dim, value in demand_vector.items():
                if dim.startswith("_") or dim not in self._deltas.get(weight_name, {}):
                    continue
                if value > 0.3:
                    self._deltas[weight_name][dim] += _LEARNING_RATE_POSITIVE * value

    def _apply_negative(self, demand_vector: dict) -> None:
        """负强化：降低贡献最大的维度的系数。"""
        for weight_name in _BASE_MAPPING:
            contributions = []
            for dim, value in demand_vector.items():
                if dim.startswith("_") or dim not in self._deltas.get(weight_name, {}):
                    continue
                base_coef = _BASE_MAPPING[weight_name].get(dim, 0.0)
                delta = self._deltas[weight_name].get(dim, 0.0)
                contrib = value * (base_coef + delta)
                contributions.append((dim, abs(contrib)))

            if contributions:
                contributions.sort(key=lambda x: -x[1])
                top_dim = contributions[0][0]
                self._deltas[weight_name][top_dim] -= _LEARNING_RATE_NEGATIVE

    def _apply_modified(self, hint: str) -> None:
        """解析修改提示，调整对应维度的系数。"""
        # 关键词 → (weight_name, dim, delta)
        rule_map: list[tuple[str, str, str, float]] = [
            ("赶", "alpha", "efficiency_seeking", 0.1),
            ("累", "gamma", "physical_energy", 0.1),
            ("贵", "budget_strictness", "budget_sensitivity", 0.1),
            ("便宜", "budget_strictness", "budget_sensitivity", -0.1),
            ("无聊", "delta", "novelty_seeking", 0.1),
            ("兴奋", "beta", "excitement_seeking", 0.1),
            ("安静", "beta", "tranquility_seeking", 0.1),
            ("快", "alpha", "efficiency_seeking", 0.1),
            ("慢", "alpha", "efficiency_seeking", -0.1),
        ]

        for kw, weight_name, dim, delta in rule_map:
            if kw in hint:
                if weight_name in self._deltas and dim in self._deltas[weight_name]:
                    self._deltas[weight_name][dim] += delta

    # ── 序列化 ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """序列化（用于 LTM 存储）。"""
        return {
            "user_id": self.user_id,
            "deltas": self._deltas,
        }

    def from_dict(self, data: dict | None) -> WeightMapper:
        """从 LTM 恢复。"""
        if data and "deltas" in data:
            for weight_name in self._deltas:
                if weight_name in data["deltas"]:
                    for dim in self._deltas[weight_name]:
                        if dim in data["deltas"][weight_name]:
                            self._deltas[weight_name][dim] = data["deltas"][weight_name][dim]
        return self

    def summary(self) -> str:
        """返回人类可读的参数摘要。"""
        parts = []
        for weight_name, dims in self._deltas.items():
            active = {k: round(v, 2) for k, v in dims.items() if abs(v) > 0.01}
            if active:
                parts.append(f"{weight_name}: {active}")
        return "; ".join(parts) if parts else "未调整（默认参数）"


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------


def default_demand_vector() -> dict[str, float]:
    """返回默认需求向量（所有维度中性值 0.5）。"""
    return {
        "efficiency_seeking": 0.5,
        "excitement_seeking": 0.5,
        "tranquility_seeking": 0.5,
        "budget_sensitivity": 0.5,
        "novelty_seeking": 0.5,
        "social_desire": 0.5,
        "physical_energy": 0.5,
    }
