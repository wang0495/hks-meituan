"""心理学规则: 峰终定律 + 享乐适应 + 损失厌恶 + 选择过载。

这些规则影响路线评分，模拟人类心理对行程体验的影响。
"""

from __future__ import annotations

from typing import Any


class PsychologyRules:
    """心理学规则: 影响路线评分。

    1. 峰终定律 (Peak-End Rule):
       - 路线最后一段 POI 的体验权重 +20%
       - 路线中体验最强的 POI 权重 +15%

    2. 享乐适应 (Hedonic Adaptation):
       - 连续 3 个 POI 的 excitement > 0.6 → 第 4 个评分折扣 30%
       - 用户对持续高刺激会快速适应，需要降级

    3. 损失厌恶 (Loss Aversion):
       - 价格波动 > 30% (avg_price 对比当前 POI) 触发 -0.1 评分惩罚
       - 用户对价格突然上涨更敏感

    4. 选择过载 (Choice Overload):
       - 候选列表 > 10 个时，只返回前 5 个
       - 每次呈现给用户的选项不超过 5 个
    """

    @staticmethod
    def apply_peak_end(
        route: list[dict[str, Any]],
        scores: list[float],
    ) -> list[float]:
        """应用峰终定律。

        路线最后一段 POI 的体验权重 +20%。
        路线中体验最强的 POI 权重 +15%。

        Args:
            route: 路线步骤列表（含 poi.emotion_tags）
            scores: 评分列表，每个 POI 对应的评分

        Returns:
            调整后的评分列表
        """
        if not route or not scores:
            return list(scores)

        result = list(scores)

        # 最后一段 POI +20%
        result[-1] = result[-1] * 1.2

        # 体验最强的 POI +15%（取 emotion_tags 综合评分最高的）
        emotion_scores = []
        for step in route:
            emo = step.get("poi", {}).get("emotion_tags", {})
            avg_emotion = sum(emo.values()) / len(emo) if emo else 0.0
            emotion_scores.append(avg_emotion)

        if emotion_scores:
            max_idx = emotion_scores.index(max(emotion_scores))
            result[max_idx] = result[max_idx] * 1.15

        return result

    @staticmethod
    def apply_hedonic_adaptation(
        route: list[dict[str, Any]],
        scores: list[float],
    ) -> list[float]:
        """应用享乐适应。

        连续 3 个 POI 的 excitement > 0.6 → 第 4 个评分折扣 30%。

        Args:
            route: 路线步骤列表（含 poi.emotion_tags）
            scores: 评分列表

        Returns:
            调整后的评分列表
        """
        if len(route) < 4:
            return list(scores)

        result = list(scores)
        consecutive_count = 0

        for i, step in enumerate(route):
            excitement = (
                step.get("poi", {})
                .get("emotion_tags", {})
                .get("excitement", 0)
            )

            if excitement > 0.6:
                consecutive_count += 1
                if consecutive_count >= 4:
                    result[i] = result[i] * 0.7
            else:
                consecutive_count = 0

        return result

    @staticmethod
    def apply_loss_aversion(
        route: list[dict[str, Any]],
        scores: list[float],
    ) -> list[float]:
        """应用损失厌恶。

        价格波动 > 30% (avg_price 对比当前 POI) 触发 -0.1 评分惩罚。

        Args:
            route: 路线步骤列表（含 poi.avg_price）
            scores: 评分列表

        Returns:
            调整后的评分列表
        """
        if not route or not scores:
            return list(scores)

        prices = [
            step.get("poi", {}).get("avg_price", 0) for step in route
        ]

        # 过滤价格为 0 的（免费景点不影响基准线）
        non_zero = [p for p in prices if p > 0]
        if not non_zero:
            return list(scores)

        avg_price = sum(non_zero) / len(non_zero)
        result = list(scores)

        for i, price in enumerate(prices):
            if avg_price == 0:
                continue
            # 免费景点（price=0）不触发损失厌恶（无消费决策）
            if price <= 0:
                continue
            deviation = abs(price - avg_price) / avg_price
            if deviation > 0.3:
                result[i] = result[i] - 0.1

        return result

    @staticmethod
    def apply_choice_overload(
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """应用选择过载规则。

        候选列表超过 10 个时只返回前 5 个。
        每次呈现给用户的选项不超过 5 个。

        Args:
            candidates: 候选 POI 列表

        Returns:
            筛选后的候选列表（最多 5 个）
        """
        return candidates[:5]
