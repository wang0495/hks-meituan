"""Validator效果直接测试。

直接测试各validator发现问题能力，不依赖完整pipeline。
"""

import pytest
from backend.agents.state import PlanningState
from backend.agents.nodes.time_cop import node as time_cop_node
from backend.agents.nodes.budget_auditor import node as budget_node
from backend.agents.nodes.fatigue_auditor import node as fatigue_node


def test_time_cop_detects_late_night():
    """TimeCop检测凌晨时段问题。"""
    state: PlanningState = {
        "user_input": "凌晨2点去博物馆",
        "user_intent": {"time": {"start": "02:00"}},
        "candidates": [],
        "route": {
            "route": [
                {
                    "poi": {
                        "id": "poi_001",
                        "name": "珠海博物馆",
                        "business_hours": "09:00-17:00",
                    },
                    "arrival_time": "02:00",
                    "departure_time": "03:00",
                }
            ],
            "total_cost": {"time_min": 60},
        },
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = time_cop_node(state)
    vr = result["validation_results"][0]

    print(f"\nTimeCop发现 {len(vr['issues'])} 个问题")
    for issue in vr["issues"]:
        print(f"  - [{issue['severity']}] {issue['description']}")

    # 应该发现high severity问题
    high_count = sum(1 for i in vr["issues"] if i["severity"] == "high")
    assert high_count >= 1, "应该发现high severity时间问题"


def test_budget_auditor_detects_overrun():
    """BudgetAuditor检测预算超支。"""
    state: PlanningState = {
        "user_input": "50块钱去长隆",
        "user_intent": {"budget": {"per_person": 50}},
        "candidates": [],
        "route": {
            "route": [
                {
                    "poi": {
                        "id": "poi_001",
                        "name": "长隆海洋王国",
                        "avg_price": 395,
                    },
                    "travel_from_prev": {"distance_m": 10000, "time_min": 30},
                }
            ],
            "total_cost": {"budget_used": 395, "time_min": 300},
        },
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = budget_node(state)
    vr = result["validation_results"][0]

    print(f"\nBudgetAuditor发现 {len(vr['issues'])} 个问题")
    for issue in vr["issues"]:
        print(f"  - [{issue['severity']}] {issue['description']}")

    # 应该发现high severity预算问题
    high_count = sum(1 for i in vr["issues"] if i["severity"] == "high")
    assert high_count >= 1, "应该发现high severity预算问题"


def test_fatigue_auditor_detects_overload():
    """FatigueAuditor检测亲子过度疲劳。"""
    state: PlanningState = {
        "user_input": "带3岁孩子徒步10公里",
        "user_intent": {
            "group": {"type": "亲子"},
        },
        "candidates": [],
        "route": {
            "route": [
                {
                    "poi": {
                        "id": "poi_001",
                        "name": "起点",
                        "emotion_tags": {"physical_demand": 0.9},
                    },
                    "travel_from_prev": {"distance_m": 10000, "time_min": 120},
                }
            ],
            "total_cost": {"time_min": 360, "step_estimate": 10000},
            "breathing_spots": [],
        },
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = fatigue_node(state)
    vr = result["validation_results"][0]

    print(f"\nFatigueAuditor发现 {len(vr['issues'])} 个问题")
    for issue in vr["issues"]:
        print(f"  - [{issue['severity']}] {issue['description']}")

    # 亲子群体走10公里应该有问题
    assert len(vr["issues"]) >= 1, "应该发现疲劳问题"


def test_all_validators_combined():
    """综合测试：多重问题同时发现。"""
    state: PlanningState = {
        "user_input": "50块钱凌晨带3岁孩子去长隆徒步10公里",
        "user_intent": {
            "budget": {"per_person": 50},
            "group": {"type": "亲子"},
            "time": {"start": "02:00"},
        },
        "candidates": [],
        "route": {
            "route": [
                {
                    "poi": {
                        "id": "poi_001",
                        "name": "长隆海洋王国",
                        "avg_price": 395,
                        "business_hours": "09:00-18:00",
                        "emotion_tags": {"physical_demand": 0.9},
                    },
                    "arrival_time": "02:00",
                    "departure_time": "06:00",
                    "travel_from_prev": {"distance_m": 10000, "time_min": 120},
                }
            ],
            "total_cost": {"budget_used": 395, "time_min": 360, "step_estimate": 10000},
            "breathing_spots": [],
        },
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    # 并行运行所有validator
    import asyncio

    async def run_all():
        return await asyncio.gather(
            asyncio.to_thread(time_cop_node, state),
            asyncio.to_thread(budget_node, state),
            asyncio.to_thread(fatigue_node, state),
        )

    results = asyncio.run(run_all())

    # 汇总问题
    all_issues = []
    for r in results:
        all_issues.extend(r["validation_results"][0]["issues"])

    print(f"\n综合测试：发现 {len(all_issues)} 个问题")
    for issue in all_issues:
        print(f"  - [{issue['severity']}] [{issue['category']}] {issue['description'][:50]}...")

    # 统计
    time_issues = [i for i in all_issues if i["category"] == "time"]
    budget_issues = [i for i in all_issues if i["category"] == "budget"]
    fatigue_issues = [i for i in all_issues if i["category"] == "fatigue"]
    high_issues = [i for i in all_issues if i["severity"] == "high"]

    print(f"\n问题分类统计:")
    print(f"  - 时间问题: {len(time_issues)}")
    print(f"  - 预算问题: {len(budget_issues)}")
    print(f"  - 疲劳问题: {len(fatigue_issues)}")
    print(f"  - High severity: {len(high_issues)}")

    # 验证发现所有三类问题
    assert len(time_issues) >= 1, "应发现时间问题"
    assert len(budget_issues) >= 1, "应发现预算问题"
    assert len(fatigue_issues) >= 1, "应发现疲劳问题"
    assert len(high_issues) >= 2, "应发现至少2个high severity问题"


def test_validator_improvement_over_old():
    """对比旧管线的简单检查，验证新validator更全面。"""

    # 旧管线只能做简单的预算检查（总费用>预算）
    # 新管线能发现：隐性成本、单个POI超支、时间可行性、疲劳度

    state: PlanningState = {
        "user_input": "测试",
        "user_intent": {
            "budget": {"per_person": 200},
        },
        "candidates": [],
        "route": {
            "route": [
                {
                    "poi": {
                        "id": "poi_001",
                        "name": "高价餐厅",
                        "avg_price": 180,  # 单个POI占90%预算
                    },
                    "travel_from_prev": {"distance_m": 5000, "time_min": 15},
                },
                {
                    "poi": {
                        "id": "poi_002",
                        "name": "普通景点",
                        "avg_price": 50,
                    },
                    "travel_from_prev": {"distance_m": 5000, "time_min": 15},
                },
            ],
            "total_cost": {"budget_used": 230, "time_min": 180},  # 总费用略微超支
        },
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = budget_node(state)
    vr = result["validation_results"][0]

    print(f"\n精细化预算检查:")
    for issue in vr["issues"]:
        print(f"  - [{issue['severity']}] {issue['description']}")

    # 应该发现：总超支 + 单个POI占比过高 + 隐性交通成本
    assert len(vr["issues"]) >= 2, "应发现多个预算相关问题（总超支+单个POI占比+隐性成本）"

    # 验证发现单个POI占比问题（输出中有"占预算90%"）
    single_poi_issues = [i for i in vr["issues"] if "占预算" in i["description"] or "占比" in i["description"]]
    assert len(single_poi_issues) >= 1, "应发现单个POI占比过高问题（旧管线无法发现）"
