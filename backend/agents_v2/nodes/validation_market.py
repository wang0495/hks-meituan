"""Layer 2节点：对抗性校验市场。

完整实现：
- 复用B版本的4个validator
- 增强CriticAgent
- 新增RealtimeValidator
"""

from __future__ import annotations

import uuid
from typing import Any

from backend.agents_v2.state import (
    FederatedState,
    ValidationIssue,
    ValidatorResult,
    ValidationTask,
)


async def validation_market_node(state: FederatedState) -> FederatedState:
    """校验市场入口节点。"""
    state["validation_results"] = []
    state["validation_issues"] = []
    return state


async def individual_validator_node(state: FederatedState) -> FederatedState:
    """单个Validator节点（Send()的目标）。"""
    validation_task = state.get("_validation_task")
    if not validation_task:
        return state

    validator_name = validation_task.get("validator_name", "")
    bids = validation_task.get("bids", [])
    intent_package = validation_task.get("intent_package", {})

    issues = []

    if validator_name == "time_cop":
        issues = await _validate_time(bids, intent_package)
    elif validator_name == "fatigue_auditor":
        issues = await _validate_fatigue(bids, intent_package)
    elif validator_name == "budget_auditor":
        issues = await _validate_budget(bids, intent_package)
    elif validator_name == "local_expert":
        issues = await _validate_local(bids, intent_package)
    elif validator_name == "critic":
        issues = await _validate_critic(bids, intent_package)
    elif validator_name == "realtime":
        issues = await _validate_realtime(bids, intent_package)

    result = {
        "validator": validator_name,
        "issues": issues,
        "confidence": 0.8,
        "metadata": {},
    }

    if "validation_results" not in state:
        state["validation_results"] = []
    state["validation_results"].append(result)

    return state


async def _validate_time(bids: list, intent_package: dict) -> list[ValidationIssue]:
    """时间可行性校验。"""
    issues = []

    for bid in bids:
        if bid.get("agent_type") != "poi":
            continue

        proposal = bid.get("proposal", {})
        poi = proposal.get("poi", {})

        # 检查营业时间
        business_hours = poi.get("business_hours", "09:00-18:00")
        recommended_time = proposal.get("recommended_time", "09:00")

        try:
            bh_start, bh_end = business_hours.split("-")
            bh_start_h = int(bh_start.split(":")[0])
            rec_h = int(recommended_time.split(":")[0])

            if rec_h < bh_start_h:
                issues.append({
                    "issue_id": f"issue_{uuid.uuid4().hex[:6]}",
                    "validator": "time_cop",
                    "severity": "high",
                    "category": "time",
                    "description": f"{poi.get('name', '?')}推荐时间{recommended_time}早于营业时间{bh_start}",
                    "suggestion": f"建议推迟到{bh_start}之后",
                    "affected_bid_ids": [bid.get("bid_id", "")],
                })
        except Exception:
            pass

    return issues


async def _validate_fatigue(bids: list, intent_package: dict) -> list[ValidationIssue]:
    """疲劳度校验。"""
    issues = []

    core_intent = intent_package.get("core_intent", {})
    group_type = core_intent.get("group", {}).get("type", "")

    # 计算总步行距离（简化）
    poi_count = sum(1 for b in bids if b.get("agent_type") == "poi")
    estimated_walking = poi_count * 1500  # 每个POI约1.5km步行

    # 群体疲劳阈值
    thresholds = {
        "亲子": 5000,
        "退休": 4000,
        "情侣": 10000,
        "朋友": 12000,
    }

    threshold = thresholds.get(group_type, 8000)

    if estimated_walking > threshold:
        issues.append({
            "issue_id": f"issue_{uuid.uuid4().hex[:6]}",
            "validator": "fatigue_auditor",
            "severity": "high" if group_type in ["亲子", "退休"] else "medium",
            "category": "fatigue",
            "description": f"{group_type}群体预计步行{estimated_walking}米，超过阈值{threshold}米",
            "suggestion": "减少POI数量或安排更多休息",
            "affected_bid_ids": [b.get("bid_id", "") for b in bids if b.get("agent_type") == "poi"],
        })

    return issues


async def _validate_budget(bids: list, intent_package: dict) -> list[ValidationIssue]:
    """预算校验。"""
    issues = []

    core_intent = intent_package.get("core_intent", {})
    budget_limit = core_intent.get("budget", {}).get("per_person", 500)

    # 计算总费用
    total_cost = sum(b.get("dynamic_price", 0) for b in bids)

    if total_cost > budget_limit * 1.3:
        issues.append({
            "issue_id": f"issue_{uuid.uuid4().hex[:6]}",
            "validator": "budget_auditor",
            "severity": "high",
            "category": "budget",
            "description": f"总费用¥{total_cost:.0f}超出预算¥{budget_limit:.0f} 30%以上",
            "suggestion": "减少高消费项目或调整预算",
            "affected_bid_ids": [b.get("bid_id", "") for b in bids],
        })
    elif total_cost > budget_limit:
        issues.append({
            "issue_id": f"issue_{uuid.uuid4().hex[:6]}",
            "validator": "budget_auditor",
            "severity": "medium",
            "category": "budget",
            "description": f"总费用¥{total_cost:.0f}略超预算¥{budget_limit:.0f}",
            "suggestion": "建议调整部分项目",
            "affected_bid_ids": [b.get("bid_id", "") for b in bids],
        })

    return issues


async def _validate_local(bids: list, intent_package: dict) -> list[ValidationIssue]:
    """本地达人校验。"""
    issues = []

    # 检查是否都是热门景点
    popular_count = 0
    for bid in bids:
        if bid.get("agent_type") != "poi":
            continue
        poi = bid.get("proposal", {}).get("poi", {})
        rating = poi.get("rating", 0)
        review_count = poi.get("review_count", 0)
        if rating > 4.5 and review_count > 1000:
            popular_count += 1

    poi_count = sum(1 for b in bids if b.get("agent_type") == "poi")

    if popular_count >= poi_count * 0.8 and poi_count >= 3:
        issues.append({
            "issue_id": f"issue_{uuid.uuid4().hex[:6]}",
            "validator": "local_expert",
            "severity": "medium",
            "category": "local",
            "description": "路线全是热门打卡点，缺乏独特性",
            "suggestion": "考虑添加一些小众景点",
            "affected_bid_ids": [b.get("bid_id", "") for b in bids if b.get("agent_type") == "poi"],
        })

    return issues


async def _validate_critic(bids: list, intent_package: dict) -> list[ValidationIssue]:
    """对抗性挑刺校验。"""
    issues = []

    raw_input = intent_package.get("raw_input", "")
    core_intent = intent_package.get("core_intent", {})

    # 1. 场景多样性检查
    categories = set()
    for bid in bids:
        if bid.get("agent_type") == "poi":
            cat = bid.get("proposal", {}).get("poi", {}).get("category", "")
            if cat:
                categories.add(cat)

    poi_count = sum(1 for b in bids if b.get("agent_type") == "poi")
    if len(categories) <= 2 and poi_count >= 4:
        issues.append({
            "issue_id": f"issue_{uuid.uuid4().hex[:6]}",
            "validator": "critic",
            "severity": "low",
            "category": "critique",
            "description": f"场景类型单一（只有{categories}），建议增加多样性",
            "suggestion": "尝试添加不同类型的体验",
            "affected_bid_ids": [],
        })

    # 2. 天气适配检查
    if "雨天" in raw_input or "下雨" in raw_input or "大雨" in raw_input:
        indoor_count = 0
        for bid in bids:
            if bid.get("agent_type") != "poi":
                continue
            poi = bid.get("proposal", {}).get("poi", {})
            tags = poi.get("tags", [])
            if "室内" in tags or poi.get("category") in ["餐饮", "博物馆", "购物"]:
                indoor_count += 1

        if indoor_count < poi_count / 2:
            issues.append({
                "issue_id": f"issue_{uuid.uuid4().hex[:6]}",
                "validator": "critic",
                "severity": "high",
                "category": "critique",
                "description": "雨天场景但室内场所不足",
                "suggestion": "增加室内备选方案",
                "affected_bid_ids": [b.get("bid_id", "") for b in bids if b.get("agent_type") == "poi"],
            })

    # 3. 时间合理性检查
    time_info = core_intent.get("time", {})
    if time_info.get("start") and "凌晨" in raw_input:
        issues.append({
            "issue_id": f"issue_{uuid.uuid4().hex[:6]}",
            "validator": "critic",
            "severity": "medium",
            "category": "critique",
            "description": "凌晨时段部分场所可能不营业",
            "suggestion": "确认场所营业时间或调整出发时间",
            "affected_bid_ids": [],
        })

    return issues


async def _validate_realtime(bids: list, intent_package: dict) -> list[ValidationIssue]:
    """实时数据校验。"""
    issues = []

    # 模拟：检查是否有临时关闭的POI
    for bid in bids:
        if bid.get("agent_type") != "poi":
            continue

        poi = bid.get("proposal", {}).get("poi", {})
        poi_id = poi.get("id", "")

        # 模拟5%概率临时关闭
        if hash(poi_id) % 20 == 0:
            issues.append({
                "issue_id": f"issue_{uuid.uuid4().hex[:6]}",
                "validator": "realtime",
                "severity": "high",
                "category": "realtime",
                "description": f"{poi.get('name', '?')}今日临时关闭",
                "suggestion": "寻找替代方案",
                "affected_bid_ids": [bid.get("bid_id", "")],
            })

    return issues


async def validation_aggregation_node(state: FederatedState) -> FederatedState:
    """校验聚合节点。"""
    validation_results = state.get("validation_results", [])
    bids = state.get("bids", [])

    # 汇总所有问题
    all_issues = []
    for result in validation_results:
        all_issues.extend(result.get("issues", []))

    state["validation_issues"] = all_issues

    # 过滤：移除有high severity issue的bid
    high_issue_bids = set()
    for issue in all_issues:
        if issue.get("severity") == "high":
            high_issue_bids.update(issue.get("affected_bid_ids", []))

    surviving = [b for b in bids if b.get("bid_id") not in high_issue_bids]

    # 如果过滤后太少，保留medium
    if len(surviving) < 3:
        medium_issue_bids = set()
        for issue in all_issues:
            if issue.get("severity") == "medium":
                medium_issue_bids.update(issue.get("affected_bid_ids", []))
        surviving = [b for b in bids if b.get("bid_id") not in high_issue_bids]

    state["surviving_bids"] = surviving[:10]

    return state
