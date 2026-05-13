"""fatigue_auditor 节点。

疲劳度校验器（算法节点，无需LLM）。
检查：
1. 步行距离是否超群体承受能力
2. 连续高强度活动是否过多
3. 休息点是否足够
"""

from __future__ import annotations

from backend.agents.state import PlanningState, AgentIssue


# 群体疲劳阈值（米）
FATIGUE_THRESHOLDS = {
    "亲子": {"max_walk": 5000, "break_every": 90, "high_intensity_max": 2},
    "退休": {"max_walk": 4000, "break_every": 60, "high_intensity_max": 1},
    "情侣": {"max_walk": 8000, "break_every": 120, "high_intensity_max": 3},
    "朋友": {"max_walk": 10000, "break_every": 120, "high_intensity_max": 4},
    "独居": {"max_walk": 12000, "break_every": 150, "high_intensity_max": 4},
    "默认": {"max_walk": 8000, "break_every": 120, "high_intensity_max": 3},
}


def _estimate_walking_distance(route_steps: list) -> int:
    """估算总步行距离（米）。"""
    total = 0
    for step in route_steps:
        travel = step.get("travel_from_prev", {})
        total += travel.get("distance_m", 0)
    return total


def _count_high_intensity_pois(route_steps: list) -> int:
    """统计高强度POI数量（physical_demand > 0.6）。"""
    count = 0
    for step in route_steps:
        poi = step.get("poi", {})
        emotions = poi.get("emotion_tags", {})
        if emotions.get("physical_demand", 0) > 0.6:
            count += 1
    return count


def _count_break_spots(route: dict) -> int:
    """统计休息点数量。"""
    breathing_spots = route.get("breathing_spots", [])
    return len(breathing_spots)


def node(state: PlanningState) -> dict:
    """疲劳度校验。

    根据用户群体类型检查路线的体力消耗是否合理。

    Args:
        state: 当前规划状态，需包含route和user_intent

    Returns:
        dict: 包含validation_results的更新片段
    """
    route = state.get("route")
    user_intent = state.get("user_intent", {})

    if not route:
        return {
            "validation_results": state.get("validation_results", []) + [{
                "agent": "fatigue_auditor",
                "issues": [],
                "confidence": 0.0,
            }]
        }

    # 获取群体类型
    group = user_intent.get("group", {})
    group_type = group.get("type", "默认")
    thresholds = FATIGUE_THRESHOLDS.get(group_type, FATIGUE_THRESHOLDS["默认"])

    issues = []
    route_steps = route.get("route", [])

    # 检查步行距离
    walk_distance = _estimate_walking_distance(route_steps)
    if walk_distance > thresholds["max_walk"]:
        issues.append({
            "severity": "high",
            "category": "fatigue",
            "description": f"预估步行距离 {walk_distance}米 超过 {group_type}群体建议上限 {thresholds['max_walk']}米",
            "suggestion": "增加休息点、减少POI数量或选择更近的POI",
            "affected_indices": list(range(len(route_steps))),
        })
    elif walk_distance > thresholds["max_walk"] * 0.8:
        issues.append({
            "severity": "medium",
            "category": "fatigue",
            "description": f"预估步行距离 {walk_distance}米 接近 {group_type}群体上限",
            "suggestion": "考虑减少一个远距离POI",
            "affected_indices": [],
        })

    # 检查高强度POI数量
    high_intensity = _count_high_intensity_pois(route_steps)
    if high_intensity > thresholds["high_intensity_max"]:
        issues.append({
            "severity": "medium",
            "category": "fatigue",
            "description": f"高强度POI数量 {high_intensity} 超过 {group_type}群体建议 {thresholds['high_intensity_max']}",
            "suggestion": "在高原POI之间插入低强度休息点",
            "affected_indices": [],
        })

    # 检查休息点数量
    breaks = _count_break_spots(route)
    expected_breaks = max(1, len(route_steps) // 3)
    if breaks < expected_breaks:
        issues.append({
            "severity": "low",
            "category": "fatigue",
            "description": f"休息点数量 {breaks} 偏少，建议至少 {expected_breaks} 个",
            "suggestion": "在长距离移动之间添加咖啡馆/公园等休息点",
            "affected_indices": [],
        })

    confidence = 1.0 - (len([i for i in issues if i["severity"] == "high"]) * 0.3)
    confidence = max(0.0, confidence)

    result = {
        "agent": "fatigue_auditor",
        "issues": issues,
        "confidence": confidence,
    }

    return {
        "validation_results": state.get("validation_results", []) + [result]
    }
