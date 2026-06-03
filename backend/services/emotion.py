"""CityFlow 情绪评分公共模块。

提供主导情绪判断、情绪兼容性评分、情绪曲线计算等函数，
消除 narrator.py / filters.py 中的重复实现。
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 疲劳阈值常量
# ---------------------------------------------------------------------------
_FATIGUE_FORCE_REST_STEPS = 15000  # 超过此步数强制休息
_FATIGUE_HIGH_PENALTY_STEPS = 10000  # 高疲劳惩罚阈值
_FATIGUE_LOW_PENALTY_STEPS = 5000  # 低疲劳惩罚阈值
_FATIGUE_CONSECUTIVE_POIS = 3  # 连续POI疲劳阈值

# ---------------------------------------------------------------------------
# 主导情绪
# ---------------------------------------------------------------------------


def get_dominant_emotion(emotion_tags: dict[str, float]) -> str:
    """获取主导情绪类型。

    强度 > 0.6 的最高情绪标签为主导情绪，否则返回 "default"。

    Args:
        emotion_tags: 情绪标签字典，键为情绪类型，值为 0-1 的强度

    Returns:
        主导情绪名称
    """
    if not emotion_tags:
        return "default"

    max_key, max_val = max(emotion_tags.items(), key=lambda x: x[1])
    if max_val > 0.6:
        return max_key
    return "default"


# ---------------------------------------------------------------------------
# 感官类型映射（用于感官交替约束）
# ---------------------------------------------------------------------------

SENSORY_TAGS: dict[str, str] = {
    "文化": "visual",  # 博物馆/美术馆 → 视觉型
    "景点": "visual",  # 景点 → 视觉型
    "自然": "visual",  # 公园/海滨 → 视觉型
    "公园": "visual",  # 公园 → 视觉型
    "餐饮": "tactile",  # 餐厅 → 味觉触觉型
    "美食": "tactile",  # 美食(别名) → 味觉触觉型
    "购物": "tactile",  # 购物 → 触觉型
    "运动": "dynamic",  # 运动 → 动态型
    "娱乐": "dynamic",  # 娱乐 → 动态型
    "休息": "static",  # 休息 → 静态型
    "酒店": "static",  # 酒店 → 静态型
    "其他": "static",  # 其他 → 静态型
}

# ---------------------------------------------------------------------------
# 化学反应矩阵
# ---------------------------------------------------------------------------


def chemical_reaction(poi_a: dict, poi_b: dict) -> float:
    """计算两个 POI 之间的化学反应评分。

    在 emotion_compatibility 基础情绪兼容性之上，增加化学反应层：
    - 认知超载型: transition 中 culture_depth > 0.6 → sociability > 0.6 → -0.6
      (用户同时处理文化深度+社交互动切换会认知超载)
    - 互补型: poi_a.excitement > 0.7 AND poi_b.tranquility > 0.7 → +0.2
      (兴奋→宁静: 从热闹到安静的自然过渡)
    - 场景型: category sequence 符合 (餐饮→文化) OR (运动→餐饮) → +0.5
      (自然场景流程: 吃饭后逛博物馆, 运动后吃饭)

    Args:
        poi_a: 前一个 POI
        poi_b: 后一个 POI

    Returns:
        -1.0 到 1.0 的化学反应评分
    """
    emo_a = poi_a.get("emotion_tags", {})
    emo_b = poi_b.get("emotion_tags", {})
    cat_a = poi_a.get("category", "")
    cat_b = poi_b.get("category", "")

    # 认知超载型: 从高文化深度到高社交互动
    if emo_a.get("culture_depth", 0) > 0.6 and emo_b.get("sociability", 0) > 0.6:
        return -0.6

    # 场景型: 自然场景流程 (餐饮→文化) OR (运动→餐饮)
    _food_cats = {"餐饮", "美食"}
    _culture_cats = {"文化", "景点"}
    _sport_cats = {"运动", "公园", "自然"}
    if (cat_a in _food_cats and cat_b in _culture_cats) or (
        cat_a in _sport_cats and cat_b in _food_cats
    ):
        return 0.5

    # 互补型: 兴奋→宁静 过渡 (注意低于 emotion_compatibility 中的 0.3 反差型)
    if emo_a.get("excitement", 0) > 0.7 and emo_b.get("tranquility", 0) > 0.7:
        return 0.2

    return 0.0


# ---------------------------------------------------------------------------
# 感官交替约束
# ---------------------------------------------------------------------------


def _get_sensory_type(step_or_poi: dict) -> str:
    """从步骤或 POI 字典中提取感官类型。"""
    if "poi" in step_or_poi:
        cat = step_or_poi["poi"].get("category", "其他")
    else:
        cat = step_or_poi.get("category", "其他")
    return SENSORY_TAGS.get(cat, "static")


def sensory_alternation(route: list[dict]) -> float:
    """检查路线中的感官交替情况并返回评分。

    Rules:
    - 相邻 POI 感官类型不同 → +0.1 (每对)
    - 连续 3 个 POI 同感官类型 → -0.3 (从第 3 个起每多一个惩罚)
    - 感官类型交替次数 > 3 → +0.5 bonus (路线至少 4 个 POI)

    Args:
        route: 路线步骤列表（每步含 "poi" 键）或 POI 字典列表

    Returns:
        感官交替评分
    """
    if len(route) < 2:
        return 0.0

    types = [_get_sensory_type(step) for step in route]

    score = 0.0
    consecutive_same = 1

    for i in range(1, len(types)):
        if types[i] != types[i - 1]:
            score += 0.1  # 不同感官类型 → +0.1
            consecutive_same = 1
        else:
            consecutive_same += 1
            if consecutive_same >= 3:
                score -= 0.3  # 连续 3+ 同感官类型 → -0.3

    # 感官类型交替次数 > 3 → bonus
    changes = sum(1 for i in range(1, len(types)) if types[i] != types[i - 1])
    if changes > 3 and len(route) >= 4:
        score += 0.5

    return score


# ---------------------------------------------------------------------------
# 情绪兼容性
# ---------------------------------------------------------------------------


def emotion_compatibility(poi_a: dict[str, Any], poi_b: dict[str, Any]) -> float:
    """计算两个 POI 之间的情绪兼容性评分。

    规则：
    - 两个 POI 兴奋度都 > 0.8 -> -0.5（过载惩罚）
    - 同 category -> -0.3（连续同类惩罚）
    - 文化 >= 0.7 后面跟宁静 >= 0.7 -> +0.4（增强型）
    - 兴奋 >= 0.7 后面跟宁静 >= 0.7 -> +0.3（反差型）
    - 其他 -> 0.0

    Args:
        poi_a: 前一个 POI
        poi_b: 后一个 POI

    Returns:
        -1.0 到 1.0 的兼容性评分
    """
    emo_a = poi_a.get("emotion_tags", {})
    emo_b = poi_b.get("emotion_tags", {})

    exc_a = emo_a.get("excitement", 0)
    exc_b = emo_b.get("excitement", 0)
    tran_b = emo_b.get("tranquility", 0)
    cult_a = emo_a.get("culture_depth", 0)

    # 兴奋过载
    if exc_a > 0.8 and exc_b > 0.8:
        return -0.5

    # 同类惩罚
    if poi_a.get("category") == poi_b.get("category"):
        return -0.3

    # 文化 -> 宁静 增强型
    if cult_a >= 0.7 and tran_b >= 0.7:
        return 0.4

    # 兴奋 -> 宁静 反差型
    if exc_a >= 0.7 and tran_b >= 0.7:
        return 0.3

    return 0.0


def emotion_compatibility_with_consecutive(pois: list[dict[str, Any]]) -> float:
    """计算 POI 序列的总情绪兼容性，处理连续同类惩罚升级。

    Args:
        pois: 按顺序排列的 POI 列表

    Returns:
        总兼容性评分
    """
    if len(pois) < 2:
        return 0.0

    total = 0.0
    consecutive_count = 1

    for i in range(1, len(pois)):
        if pois[i].get("category") == pois[i - 1].get("category"):
            consecutive_count += 1
            if consecutive_count >= 3:
                total -= 0.6
            else:
                total -= 0.3
        else:
            consecutive_count = 1
            total += emotion_compatibility(pois[i - 1], pois[i])

    return total


# ---------------------------------------------------------------------------
# 情绪曲线
# ---------------------------------------------------------------------------


def calculate_emotion_curve(route: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """计算情绪曲线。

    Args:
        route: 路线步骤列表，每步需含 poi.emotion_tags 和 arrival_time

    Returns:
        情绪曲线数据列表
    """
    return [
        {
            "time": step.get("arrival_time"),
            **step["poi"].get("emotion_tags", {}),
        }
        for step in route
    ]


# ---------------------------------------------------------------------------
# 疲劳惩罚
# ---------------------------------------------------------------------------


def fatigue_penalty(step_count: int, consecutive_pois: int) -> float:
    """根据步数和连续 POI 数量计算疲劳惩罚。

    Args:
        step_count: 当前步数
        consecutive_pois: 连续访问的 POI 数量

    Returns:
        疲劳惩罚系数（0 表示无惩罚，-999 表示强制休息）
    """
    if step_count > _FATIGUE_FORCE_REST_STEPS:
        return -999

    penalty = 0.0

    if step_count >= _FATIGUE_HIGH_PENALTY_STEPS:
        penalty -= 0.5
    elif step_count >= _FATIGUE_LOW_PENALTY_STEPS:
        penalty -= 0.2

    if consecutive_pois >= _FATIGUE_CONSECUTIVE_POIS:
        penalty -= 0.2

    return penalty
