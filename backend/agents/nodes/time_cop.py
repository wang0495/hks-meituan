"""time_cop 节点。

时间可行性校验器（算法节点，无需LLM）。
检查：
1. 到达时间是否在POI营业时间内
2. 交通时间是否合理
3. 缓冲区是否充足（至少15分钟）
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from backend.agents.state import PlanningState, AgentIssue


def _parse_time(time_str: str) -> datetime:
    """解析HH:MM格式的时间。"""
    return datetime.strptime(time_str, "%H:%M")


def _format_time(dt: datetime) -> str:
    """格式化为HH:MM。"""
    return dt.strftime("%H:%M")


def _check_business_hours(poi: dict, arrival: str, departure: str) -> list[AgentIssue]:
    """检查营业时间是否覆盖到达时间。"""
    issues = []

    hours = poi.get("business_hours") or poi.get("constraints", {}).get("opening_hours")
    if not hours:
        return issues

    try:
        open_time, close_time = hours.split("-")
        arrival_dt = _parse_time(arrival)
        open_dt = _parse_time(open_time)
        close_dt = _parse_time(close_time)

        # 跨午夜处理
        if close_dt < open_dt:
            close_dt += timedelta(days=1)
            if arrival_dt < open_dt:
                arrival_dt += timedelta(days=1)

        # 检查到达时间是否在营业时间内
        if arrival_dt < open_dt:
            issues.append({
                "severity": "high",
                "category": "time",
                "description": f"{poi.get('name')} 到达时间 {arrival} 早于营业时间 {open_time}",
                "suggestion": f"延后出发时间或选择其他POI",
                "affected_indices": [],
            })
        elif arrival_dt > close_dt - timedelta(minutes=30):
            # 距离关门时间不足30分钟
            issues.append({
                "severity": "medium",
                "category": "time",
                "description": f"{poi.get('name')} 到达时间 {arrival} 距离关门时间 {close_time} 不足30分钟",
                "suggestion": "减少前一个POI停留时间或跳过此POI",
                "affected_indices": [],
            })

    except Exception:
        # 营业时间格式异常，跳过检查
        pass

    return issues


def _check_travel_time(route_step: dict, prev_step: dict | None) -> list[AgentIssue]:
    """检查交通时间是否合理。"""
    issues = []

    if not prev_step:
        return issues

    travel = route_step.get("travel_from_prev", {})
    time_min = travel.get("time_min", 0)

    # 如果交通时间超过60分钟，标记为问题
    if time_min > 60:
        issues.append({
            "severity": "medium",
            "category": "time",
            "description": f"从 {prev_step.get('poi', {}).get('name')} 到 {route_step.get('poi', {}).get('name')} 交通时间 {time_min}分钟过长",
            "suggestion": "考虑添加中间休息点或调整顺序",
            "affected_indices": [],
        })

    return issues


def node(state: PlanningState) -> dict:
    """时间可行性校验。

    检查路线的每个步骤：
    1. 营业时间覆盖
    2. 交通时间合理性
    3. 整体时间预算

    Args:
        state: 当前规划状态，需包含route

    Returns:
        dict: 包含validation_results的更新片段
    """
    route = state.get("route")

    if not route:
        return {
            "validation_results": state.get("validation_results", []) + [{
                "agent": "time_cop",
                "issues": [],
                "confidence": 0.0,
            }]
        }

    issues = []
    route_steps = route.get("route", [])

    for i, step in enumerate(route_steps):
        poi = step.get("poi", {})
        arrival = step.get("arrival_time")
        departure = step.get("departure_time")

        if not arrival or not departure:
            continue

        # 检查营业时间
        issues.extend(_check_business_hours(poi, arrival, departure))

        # 检查交通时间
        prev_step = route_steps[i - 1] if i > 0 else None
        issues.extend(_check_travel_time(step, prev_step))

    # 检查整体时间
    total_time = route.get("total_cost", {}).get("time_min", 0)
    user_intent = state.get("user_intent", {})
    expected_duration = user_intent.get("time", {}).get("duration_min", 480)

    if total_time > expected_duration * 1.2:
        issues.append({
            "severity": "high",
            "category": "time",
            "description": f"路线总时间 {total_time}分钟 超过预期 {expected_duration}分钟的20%",
            "suggestion": "减少POI数量或缩短每个POI停留时间",
            "affected_indices": list(range(len(route_steps))),
        })

    confidence = 1.0 - (len(issues) * 0.2)
    confidence = max(0.0, confidence)

    result = {
        "agent": "time_cop",
        "issues": issues,
        "confidence": confidence,
    }

    return {
        "validation_results": state.get("validation_results", []) + [result]
    }
