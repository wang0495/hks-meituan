"""第二层：对抗性校验市场。

多位"裁判"智能体同时上场，对竞标方案进行校验。
- TimeCop: 时间可行性
- FatigueAuditor: 疲劳度
- BudgetAuditor: 预算
- LocalExpert: 本地知识
- CriticAgent: 专门挑刺的对抗智能体 (新增)
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.agents_v2.state import FederatedState, Bid, ValidationIssue


class TimeCopValidator:
    """时间警察智能体。"""

    def __init__(self):
        self.name = "time_cop"

    async def validate(self, bids: list[Bid], intent_package: dict) -> list[ValidationIssue]:
        """校验时间可行性。"""
        issues = []

        for bid in bids:
            proposal = bid.get("proposal", {})
            poi = proposal.get("poi", {})

            # 检查营业时间
            business_hours = poi.get("business_hours", "09:00-18:00")
            recommended_time = proposal.get("recommended_time", "09:00")

            # 简化：检查推荐时间是否在营业时间内
            try:
                bh_start, bh_end = business_hours.split("-")
                bh_h = int(bh_start.split(":")[0])
                rec_h = int(recommended_time.split(":")[0])

                if rec_h < bh_h:
                    issues.append({
                        "validator": self.name,
                        "severity": "high",
                        "description": f"{poi.get('name', '?')}推荐时间{recommended_time}早于营业时间{bh_start}",
                        "affected_bid_ids": [bid["agent_id"]],
                    })
            except:
                pass

        return issues


class BudgetAuditorValidator:
    """预算审计智能体。"""

    def __init__(self):
        self.name = "budget_auditor"

    async def validate(self, bids: list[Bid], intent_package: dict) -> list[ValidationIssue]:
        """校验预算。"""
        issues = []

        core_intent = intent_package.get("core_intent", {})
        budget_limit = core_intent.get("budget", {}).get("per_person", 500)

        # 计算总预算
        total_cost = 0
        for bid in bids:
            costs = bid.get("cost_estimate", {})
            total_cost += sum(costs.values())

        if total_cost > budget_limit * 1.2:
            issues.append({
                "validator": self.name,
                "severity": "high",
                "description": f"总费用¥{total_cost:.0f}超出预算¥{budget_limit:.0f} 20%以上",
                "affected_bid_ids": [b["agent_id"] for b in bids],
            })
        elif total_cost > budget_limit:
            issues.append({
                "validator": self.name,
                "severity": "medium",
                "description": f"总费用¥{total_cost:.0f}略超预算¥{budget_limit:.0f}",
                "affected_bid_ids": [b["agent_id"] for b in bids],
            })

        return issues


class FatigueAuditorValidator:
    """疲劳度审计智能体。"""

    def __init__(self):
        self.name = "fatigue_auditor"

    async def validate(self, bids: list[Bid], intent_package: dict) -> list[ValidationIssue]:
        """校验疲劳度。"""
        issues = []

        core_intent = intent_package.get("core_intent", {})
        group_type = core_intent.get("group", {}).get("type", "")

        # 计算总步行距离
        total_walking = 0
        for bid in bids:
            proposal = bid.get("proposal", {})
            if "poi" in proposal:
                # 模拟步行距离
                total_walking += 1000

        # 亲子群体疲劳阈值
        if group_type == "亲子" and total_walking > 5000:
            issues.append({
                "validator": self.name,
                "severity": "high",
                "description": f"亲子路线步行距离{total_walking}米过长，建议控制在5公里内",
                "affected_bid_ids": [b["agent_id"] for b in bids],
            })

        return issues


class CriticAgent:
    """对抗智能体 - 专门挑刺。"""

    def __init__(self):
        self.name = "critic"

    async def validate(self, bids: list[Bid], intent_package: dict) -> list[ValidationIssue]:
        """以挑剔的导游视角找问题。"""
        issues = []

        core_intent = intent_package.get("core_intent", {})
        raw_input = intent_package.get("raw_input", "")

        # 挑剔1: 检查是否都是热门景点（缺乏独特性）
        popular_count = 0
        for bid in bids:
            poi = bid.get("proposal", {}).get("poi", {})
            rating = poi.get("rating", 0)
            review_count = poi.get("review_count", 0)
            if rating > 4.5 and review_count > 1000:
                popular_count += 1

        if popular_count >= 3:
            issues.append({
                "validator": self.name,
                "severity": "medium",
                "description": "路线全是热门打卡点，缺乏独特性和探索感，像跟团游",
                "affected_bid_ids": [b["agent_id"] for b in bids],
            })

        # 挑剔2: 检查场景多样性
        categories = set()
        for bid in bids:
            cat = bid.get("proposal", {}).get("poi", {}).get("category", "")
            if cat:
                categories.add(cat)

        if len(categories) <= 2 and len(bids) >= 4:
            issues.append({
                "validator": self.name,
                "severity": "low",
                "description": f"场景类型单一（只有{categories}），建议增加多样性",
                "affected_bid_ids": [b["agent_id"] for b in bids],
            })

        # 挑剔3: 检查是否考虑天气/时间
        if "雨天" in raw_input or "下雨" in raw_input:
            indoor_count = 0
            for bid in bids:
                tags = bid.get("proposal", {}).get("poi", {}).get("tags", [])
                if "室内" in tags:
                    indoor_count += 1

            if indoor_count < len(bids) / 2:
                issues.append({
                    "validator": self.name,
                    "severity": "high",
                    "description": "用户提到雨天，但路线中室内场所不足",
                    "affected_bid_ids": [b["agent_id"] for b in bids if "室内" not in b.get("proposal", {}).get("poi", {}).get("tags", [])],
                })

        return issues


# 校验市场主函数
async def layer2_validation_market(state: FederatedState) -> FederatedState:
    """第二层节点：对抗性校验市场。"""
    try:
        bids = state.get("bids", [])
        intent_package = state.get("intent_package")

        if not bids or not intent_package:
            state["errors"].append("校验市场缺少输入")
            state["surviving_bids"] = bids
            return state

        # 创建所有Validator
        validators = [
            TimeCopValidator(),
            BudgetAuditorValidator(),
            FatigueAuditorValidator(),
            CriticAgent(),
        ]

        # 并行校验
        validation_results = await asyncio.gather(
            *[v.validate(bids, intent_package) for v in validators],
            return_exceptions=True,
        )

        # 汇总所有问题
        all_issues = []
        for result in validation_results:
            if isinstance(result, list):
                all_issues.extend(result)

        state["validation_issues"] = all_issues

        # 过滤：移除有high severity issue的bid
        high_issue_bids = set()
        for issue in all_issues:
            if issue.get("severity") == "high":
                high_issue_bids.update(issue.get("affected_bid_ids", []))

        surviving = [b for b in bids if b["agent_id"] not in high_issue_bids]

        # 如果过滤后太少，保留medium的
        if len(surviving) < 5:
            medium_issue_bids = set()
            for issue in all_issues:
                if issue.get("severity") == "medium":
                    medium_issue_bids.update(issue.get("affected_bid_ids", []))
            surviving = [b for b in bids if b["agent_id"] not in high_issue_bids]

        state["surviving_bids"] = surviving[:10]  # 保留前10个
        return state

    except Exception as e:
        state["errors"].append(f"Layer2错误: {e}")
        state["surviving_bids"] = state.get("bids", [])
        return state
