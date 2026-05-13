"""budget_auditor 节点。

预算校验器（算法节点，无需LLM）。
检查：
1. 可见成本总和是否超预算
2. 隐性成本估算
3. 单一POI是否占比过高
"""

from __future__ import annotations

from backend.agents.state import PlanningState, AgentIssue


def _estimate_hidden_costs(route_steps: list) -> int:
    """估算隐性成本（交通、停车、小费等）。"""
    hidden = 0
    for step in route_steps:
        travel = step.get("travel_from_prev", {})
        distance_m = travel.get("distance_m", 0)
        # 估算交通费：每公里约2元
        hidden += int(distance_m / 1000 * 2)
    return hidden


def node(state: PlanningState) -> dict:
    """预算校验。

    检查路线总成本是否在用户预算内。

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
                "agent": "budget_auditor",
                "issues": [],
                "confidence": 0.0,
            }]
        }

    # 获取预算
    budget = user_intent.get("budget", {}).get("per_person", 500)
    # 考虑15%缓冲
    effective_budget = budget * 1.15

    issues = []
    route_steps = route.get("route", [])

    # 可见成本
    visible_cost = route.get("total_cost", {}).get("budget_used", 0)

    # 隐性成本
    hidden_cost = _estimate_hidden_costs(route_steps)

    # 总成本
    total_cost = visible_cost + hidden_cost

    # 检查总成本
    if total_cost > budget:
        issues.append({
            "severity": "high",
            "category": "budget",
            "description": f"预估总成本 {total_cost}元 超过预算 {budget}元（含交通等隐性成本约{hidden_cost}元）",
            "suggestion": f"移除高消费POI或缩短路线，目标控制在 {int(budget * 0.9)}元以内",
            "affected_indices": list(range(len(route_steps))),
        })
    elif total_cost > budget * 0.9:
        issues.append({
            "severity": "medium",
            "category": "budget",
            "description": f"预估总成本 {total_cost}元 接近预算上限（预算的{int(total_cost/budget*100)}%）",
            "suggestion": "准备一个备选低消费方案",
            "affected_indices": [],
        })

    # 检查单一POI是否占比过高
    for i, step in enumerate(route_steps):
        poi_cost = step.get("poi", {}).get("avg_price", 0)
        if poi_cost > budget * 0.4:
            issues.append({
                "severity": "medium",
                "category": "budget",
                "description": f"{step.get('poi', {}).get('name')} 消费 {poi_cost}元 占预算 {int(poi_cost/budget*100)}%",
                "suggestion": "此POI消费偏高，建议确认用户是否愿意为该体验支付",
                "affected_indices": [i],
            })

    confidence = 1.0 - (len([i for i in issues if i["severity"] == "high"]) * 0.3)
    confidence = max(0.0, confidence)

    result = {
        "agent": "budget_auditor",
        "issues": issues,
        "confidence": confidence,
    }

    return {
        "validation_results": state.get("validation_results", []) + [result]
    }
