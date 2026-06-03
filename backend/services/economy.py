"""CityFlow 三层经济引擎。

POI 经济数据计算模块。
- experience_value: 体验价值 (1.0-10.0)，基于情绪标签强度 + 评分 + 类别
- price_elasticity: 价格弹性 (0.1-1.0)，低价弹性高，高价弹性低
- experience_leverage: 体验杠杆率 (high/medium/low)，体验价值与价格之比
- spend_emotion: 消费感受 (value/fair/expensive)，价格是否物有所值

使用方式：
    import logging; logging.basicConfig(level=logging.INFO)
    from backend.services.economy import enrich_poi_economics
    enriched = enrich_poi_economics(poi)
    logging.getLogger(__name__).info("leverage=%s", enriched["experience_leverage"])
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 类别体验加成系数
_CATEGORY_EXPERIENCE_BONUS: dict[str, float] = {
    "文化": 0.20,
    "景点": 0.15,
    "餐饮": 0.10,
    "运动": 0.10,
    "购物": 0.05,
    "娱乐": 0.20,
}

# 价格弹性阈值（avg_price）
_PRICE_ELASTICITY_BRACKETS: list[tuple[float, float, float]] = [
    (0, 50, 0.8),  # 低价：弹性高
    (50, 100, 0.6),  # 中低价：弹性中高
    (100, 200, 0.4),  # 中价：弹性中低
]

# 体验杠杆率阈值（experience_value / avg_price）
_LEVERAGE_HIGH_THRESHOLD = 0.04
_LEVERAGE_MEDIUM_THRESHOLD = 0.015


def enrich_poi_economics(poi: dict[str, Any]) -> dict[str, Any]:
    """为 POI 添加经济字段（原地修改，幂等）。

    第一次调用时计算并写入以下字段：
    - experience_value
    - price_elasticity
    - experience_leverage
    - spend_emotion

    后续调用直接返回（已有字段则跳过）。

    Args:
        poi: POI 字典，需包含 emotion_tags、rating、avg_price、category。

    Returns:
        添加了经济字段的 POI 字典（与原引用相同）。
    """
    if "experience_value" in poi:
        return poi

    poi["experience_value"] = _calculate_experience_value(poi)
    poi["price_elasticity"] = get_price_elasticity(poi)
    poi["experience_leverage"] = calculate_leverage(poi)
    poi["spend_emotion"] = calculate_spend_emotion(poi)
    return poi


def _calculate_experience_value(poi: dict[str, Any]) -> float:
    """计算体验价值 (1.0-10.0)。

    公式：1.0 + 9.0 * (avg_emotion * 0.5 + rating_norm * 0.3 + cat_bonus * 0.2)

    - avg_emotion: 六维情绪标签的平均值 (0-1)
    - rating_norm: 评分归一化 (rating / 5.0)
    - cat_bonus: 类别体验加成
    """
    et = poi.get("emotion_tags", {})
    if not et:
        avg_emotion = 0.5
    else:
        avg_emotion = sum(et.values()) / len(et)

    rating_norm = poi.get("rating", 0) / 5.0
    cat_bonus = _CATEGORY_EXPERIENCE_BONUS.get(poi.get("category", ""), 0.05)

    raw = avg_emotion * 0.5 + rating_norm * 0.3 + cat_bonus * 0.2
    return round(1.0 + 9.0 * max(0.0, min(1.0, raw)), 2)


def get_price_elasticity(poi: dict[str, Any]) -> float:
    """计算价格弹性 (0.1-1.0)。

    低价 POI 弹性高（对价格敏感），高价 POI 弹性低。
    - 免费: 1.0
    - < 50: 0.8
    - 50-100: 0.6
    - 100-200: 0.4
    - >= 200: 0.3
    """
    price = poi.get("avg_price", 0)
    if price == 0:
        return 1.0
    for lo, hi, val in _PRICE_ELASTICITY_BRACKETS:
        if lo <= price < hi:
            return val
    return 0.3


def calculate_leverage(poi: dict[str, Any]) -> str:
    """计算体验杠杆率 (high/medium/low)。

    基于 experience_value / avg_price 比率判断：
    - high:   花小钱得大体验（免费或低价高体验）
    - medium: 花钱与体验基本匹配
    - low:    花大钱但体验提升有限
    """
    ev = poi.get("experience_value", 5.0)
    price = poi.get("avg_price", 0)

    if price == 0:
        return "high"

    ratio = ev / price

    if ratio >= _LEVERAGE_HIGH_THRESHOLD:
        return "high"
    elif ratio >= _LEVERAGE_MEDIUM_THRESHOLD:
        return "medium"
    else:
        return "low"


def calculate_spend_emotion(poi: dict[str, Any]) -> str:
    """计算消费感受 (value/fair/expensive)。

    基于 experience_value / avg_price 比率判断：
    - value:     物超所值
    - fair:      物有所值
    - expensive: 性价比低
    """
    ev = poi.get("experience_value", 5.0)
    price = poi.get("avg_price", 0)

    if price == 0:
        return "value"

    value_per_yuan = ev / price

    if value_per_yuan >= _LEVERAGE_HIGH_THRESHOLD:
        return "value"
    elif value_per_yuan >= _LEVERAGE_MEDIUM_THRESHOLD:
        return "fair"
    else:
        return "expensive"
