"""arbitrate 节点。

裁决节点：汇总所有validator结果，做出最终决策。
决策类型：pass / adjust / re_solve

增强功能：
1. 多validator冲突检测与解决
2. 按category聚合问题
3. 智能调整建议生成
4. Validator置信度加权
"""

from __future__ import annotations

from typing import Any

from backend.agents.state import PlanningState, ArbitrationResult, AgentIssue, ValidatorResult


# Category优先级（高优先级的问题优先处理）
CATEGORY_PRIORITY = {
    "time": 0,      # 时间问题最紧急
    "budget": 1,    # 预算问题次之
    "fatigue": 2,   # 疲劳问题
    "local": 3,     # 本地建议优先级较低
}


def _sort_issues_by_severity(issues: list[AgentIssue]) -> list[AgentIssue]:
    """按严重度排序：high > medium > low，同严重度按category优先级。"""
    def sort_key(issue: AgentIssue) -> tuple:
        severity_order = {"high": 0, "medium": 1, "low": 2}
        severity = severity_order.get(issue.get("severity", "low"), 3)
        category = CATEGORY_PRIORITY.get(issue.get("category", "local"), 99)
        return (severity, category)

    return sorted(issues, key=sort_key)


def _aggregate_by_category(issues: list[AgentIssue]) -> dict[str, list[AgentIssue]]:
    """按category聚合问题。"""
    aggregated: dict[str, list[AgentIssue]] = {}
    for issue in issues:
        cat = issue.get("category", "unknown")
        if cat not in aggregated:
            aggregated[cat] = []
        aggregated[cat].append(issue)
    return aggregated


def _detect_conflicts(issues: list[AgentIssue]) -> list[dict]:
    """检测validator之间的冲突建议。

    例如：TimeCop建议移除POI A，但LocalExpert强烈建议保留。
    """
    conflicts = []

    # 收集每个POI的建议
    poi_suggestions: dict[int, list[dict]] = {}
    for issue in issues:
        for idx in issue.get("affected_indices", []):
            if idx not in poi_suggestions:
                poi_suggestions[idx] = []
            poi_suggestions[idx].append({
                "severity": issue.get("severity"),
                "category": issue.get("category"),
                "suggestion": issue.get("suggestion"),
            })

    # 检测冲突（同一POI既有移除建议又有保留建议）
    for poi_idx, suggestions in poi_suggestions.items():
        has_remove = any("移除" in s["suggestion"] or "跳过" in s["suggestion"] for s in suggestions)
        has_keep = any("保留" in s["suggestion"] or "值得一去" in s["suggestion"] for s in suggestions)

        if has_remove and has_keep:
            # 冲突 detected
            high_severity = [s for s in suggestions if s["severity"] == "high"]
            if high_severity:
                conflicts.append({
                    "poi_index": poi_idx,
                    "type": "remove_vs_keep",
                    "severity": "high",
                    "suggestions": suggestions,
                })

    return conflicts


def _collect_adjustments(issues: list[AgentIssue], conflicts: list[dict]) -> dict:
    """从issues中提取调整建议，考虑冲突解决。"""
    adjustments = {
        "excluded_poi_ids": [],
        "time_adjustments": {},
        "budget_adjustments": {},
        "general_suggestions": [],
        "conflict_resolutions": [],
    }

    # 处理冲突（优先采纳high severity的建议）
    for conflict in conflicts:
        if conflict["severity"] == "high":
            # 冲突且涉及high severity，保守处理：移除该POI
            adjustments["excluded_poi_ids"].append(conflict["poi_index"])
            adjustments["conflict_resolutions"].append({
                "type": "conservative_remove",
                "poi_index": conflict["poi_index"],
                "reason": "Validator建议冲突，保守处理",
            })

    # 处理非冲突的建议
    for issue in issues:
        affected = issue.get("affected_indices", [])
        suggestion = issue.get("suggestion", "")
        category = issue.get("category", "")
        severity = issue.get("severity", "")

        # 跳过已处理的冲突POI
        if any(idx in adjustments["excluded_poi_ids"] for idx in affected):
            continue

        if "移除" in suggestion or "跳过" in suggestion:
            for idx in affected:
                if idx not in adjustments["excluded_poi_ids"]:
                    adjustments["excluded_poi_ids"].append(idx)

        if "延后" in suggestion or "提前" in suggestion:
            for idx in affected:
                adjustments["time_adjustments"][str(idx)] = suggestion

        if "预算" in suggestion or "价格" in suggestion:
            adjustments["budget_adjustments"]["general"] = suggestion

        adjustments["general_suggestions"].append({
            "category": category,
            "severity": severity,
            "suggestion": suggestion,
        })

    return adjustments


def _calculate_weighted_confidence(results: list[ValidatorResult]) -> float:
    """计算加权置信度（高severity issue多的validator权重降低）。"""
    if not results:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    for result in results:
        issues = result.get("issues", [])
        high_count = sum(1 for i in issues if i.get("severity") == "high")

        # 基础权重
        weight = 1.0
        # 每有一个high issue，权重降低20%
        weight *= (0.8 ** high_count)

        weighted_sum += result.get("confidence", 0.0) * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _generate_summary(action: str, issues: list[AgentIssue], aggregated: dict) -> str:
    """生成裁决摘要。"""
    summaries = []

    if action == "pass":
        summaries.append("✅ 路线校验通过")
    elif action == "adjust":
        summaries.append(f"⚠️ 建议调整（{len(issues)}个问题）")
    elif action == "re_solve":
        summaries.append(f"🔄 需要重新规划（{len(issues)}个严重问题）")

    # 按category统计
    for cat, cat_issues in aggregated.items():
        high = sum(1 for i in cat_issues if i["severity"] == "high")
        medium = sum(1 for i in cat_issues if i["severity"] == "medium")
        low = sum(1 for i in cat_issues if i["severity"] == "low")

        cat_names = {
            "time": "⏰ 时间",
            "budget": "💰 预算",
            "fatigue": "😮‍💨 疲劳",
            "local": "📍 本地",
        }
        cat_name = cat_names.get(cat, cat)

        summary_parts = []
        if high > 0:
            summary_parts.append(f"{high}个高")
        if medium > 0:
            summary_parts.append(f"{medium}个中")
        if low > 0:
            summary_parts.append(f"{low}个低")

        if summary_parts:
            summaries.append(f"  {cat_name}: {', '.join(summary_parts)}")

    return "\n".join(summaries)


def node(state: PlanningState) -> dict:
    """裁决节点。

    读取所有validation_results，按severity汇总，做出决策。

    Args:
        state: 当前规划状态，需包含validation_results

    Returns:
        dict: 包含arbitration的更新片段
    """
    validation_results = state.get("validation_results", [])
    round_num = state.get("round", 0)

    # 收集所有issues
    all_issues: list[AgentIssue] = []

    for result in validation_results:
        all_issues.extend(result.get("issues", []))

    # 排序
    sorted_issues = _sort_issues_by_severity(all_issues)

    # 按category聚合
    aggregated = _aggregate_by_category(sorted_issues)

    # 检测冲突
    conflicts = _detect_conflicts(sorted_issues)

    # 计算加权置信度
    weighted_confidence = _calculate_weighted_confidence(validation_results)

    # 统计
    high_count = sum(1 for i in sorted_issues if i.get("severity") == "high")
    medium_count = sum(1 for i in sorted_issues if i.get("severity") == "medium")
    low_count = sum(1 for i in sorted_issues if i.get("severity") == "low")

    # 决策逻辑（增强版）
    if round_num >= 2:
        # 超过max rounds，强制pass但保留warnings
        action = "pass"
    elif high_count > 0:
        # 有high severity问题，必须re_solve
        action = "re_solve"
    elif medium_count >= 3 or (medium_count > 0 and low_count > 3):
        # 多个medium或medium+low组合，建议adjust
        action = "adjust"
    elif conflicts:
        # 有冲突建议，保守处理：adjust
        action = "adjust"
    else:
        action = "pass"

    # 生成调整建议
    adjustments = _collect_adjustments(sorted_issues, conflicts)

    # 生成摘要
    summary = _generate_summary(action, sorted_issues, aggregated)

    arbitration: ArbitrationResult = {
        "action": action,
        "issues": sorted_issues,
        "adjustments": adjustments,
        "confidence": weighted_confidence,
        "summary": summary,
        "stats": {
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "total": len(sorted_issues),
            "conflicts": len(conflicts),
            "round": round_num,
        },
    }

    # 清空validation_results（防止下一轮fan-in时累积）
    return {
        "arbitration": arbitration,
        "validation_results": [],  # 清空，为下一轮准备
    }
