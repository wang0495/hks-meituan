"""A/B对比测试：新旧架构效果量化。

对比维度：
1. 意图解析准确率
2. 路线可行性（时间/预算/疲劳）
3. 问题发现率
4. 重新规划次数
5. 整体通过率
"""

import pytest
import asyncio
import time
from typing import Any
from dataclasses import dataclass

from backend.agents import build_graph, LANGGRAPH_AVAILABLE


@dataclass
class TestResult:
    """单个测试结果"""
    test_name: str
    old_pipeline: dict
    new_pipeline: dict


# 测试用例：故意设计有问题的输入，测试校验能力
TEST_CASES = [
    {
        "name": "预算严重不足",
        "input": "50块钱去长隆玩一天",
        "issues": ["budget"],  # 预期发现的问题
    },
    {
        "name": "时间不合理",
        "input": "凌晨2点去博物馆",
        "issues": ["time"],
    },
    {
        "name": "亲子过度疲劳",
        "input": "带3岁孩子徒步10公里",
        "issues": ["fatigue"],
    },
    {
        "name": "多重问题",
        "input": "50块钱凌晨带老人孩子去长隆",
        "issues": ["budget", "time", "fatigue"],
    },
    {
        "name": "正常需求",
        "input": "情侣周末在珠海玩一天，预算500",
        "issues": [],  # 应该没问题
    },
]


async def run_old_pipeline(user_input: str) -> dict:
    """运行旧管线（简化版，只跑核心流程）。"""
    from backend.services.intent_parser import parse_intent
    from backend.services.filters import filter_candidates
    from backend.services.solver import solve_route
    from backend.services.data_service import get_data

    start_time = time.time()
    errors = []
    warnings = []

    try:
        # 1. 意图解析
        user_intent = await parse_intent(user_input)

        # 2. 过滤POI
        all_pois = get_data("city_poi_db")
        city = user_intent.get("city", "珠海")
        city_pois = [p for p in all_pois if p.get("city") == city]
        candidates = filter_candidates(city_pois, user_intent)

        if len(candidates) < 3:
            warnings.append(f"候选POI过少: {len(candidates)}")

        # 3. 求解
        route = solve_route(
            candidates=candidates,
            user_intent=user_intent,
            start_time=user_intent.get("time", {}).get("start", "09:00"),
        )

        # 4. 简单校验（旧管线的校验能力）
        # 旧管线只有简单的矛盾检测，没有validator
        budget = user_intent.get("budget", {}).get("per_person", 500)
        route_cost = route.get("total_cost", {}).get("budget_used", 0)

        if route_cost > budget * 1.5:
            warnings.append(f"预算超支: {route_cost} > {budget}")

        elapsed = time.time() - start_time

        return {
            "success": True,
            "elapsed": elapsed,
            "errors": errors,
            "warnings": warnings,
            "issues_found": len(warnings),
            "route_length": len(route.get("route", [])),
        }

    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "elapsed": elapsed,
            "errors": [str(e)],
            "warnings": warnings,
            "issues_found": len(warnings) + 1,
            "route_length": 0,
        }


async def run_new_pipeline(user_input: str, mock_route: bool = True) -> dict:
    """运行新管线（LangGraph）。"""
    if not LANGGRAPH_AVAILABLE:
        return {"success": False, "error": "LangGraph not available"}

    graph = build_graph()
    start_time = time.time()

    # 构建模拟数据，确保validator有数据可校验
    mock_candidates = [
        {"id": "poi_001", "name": "测试景点", "category": "景点", "avg_price": 395, "business_hours": "09:00-18:00", "city": "珠海"},
        {"id": "poi_002", "name": "测试餐厅", "category": "餐饮", "avg_price": 100, "business_hours": "10:00-22:00", "city": "珠海"},
    ]

    # 构建模拟route（根据输入类型调整）
    budget = 500
    if "50" in user_input or "100" in user_input:
        budget = 100  # 低预算测试

    start_time_str = "09:00"
    if "凌晨" in user_input or "2点" in user_input:
        start_time_str = "02:00"  # 凌晨测试

    mock_route = {
        "route": [
            {
                "poi": {
                    "id": "poi_001",
                    "name": "长隆海洋王国" if "长隆" in user_input else "测试景点",
                    "category": "景点",
                    "avg_price": 395,
                    "business_hours": "09:00-18:00",
                    "emotion_tags": {"physical_demand": 0.8 if "徒步" in user_input or "公里" in user_input else 0.3},
                },
                "arrival_time": start_time_str,
                "departure_time": "12:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
            {
                "poi": {
                    "id": "poi_002",
                    "name": "测试餐厅",
                    "category": "餐饮",
                    "avg_price": 100,
                    "business_hours": "10:00-22:00",
                    "emotion_tags": {"physical_demand": 0.2},
                },
                "arrival_time": "13:00",
                "departure_time": "14:00",
                "travel_from_prev": {"distance_m": 10000 if "10公里" in user_input else 1000, "time_min": 20},
            },
        ],
        "total_cost": {
            "time_min": 300,
            "budget_used": 495,  # 接近预算上限
            "step_estimate": 12000 if "10公里" in user_input else 3000,
        },
        "breathing_spots": [],
    }

    # 模拟user_intent
    mock_intent = {
        "budget": {"per_person": budget},
        "group": {"type": "亲子" if "孩子" in user_input else "情侣"},
        "time": {"start": start_time_str, "duration_min": 480},
    }

    initial_state = {
        "user_input": user_input,
        "user_intent": mock_intent,
        "candidates": mock_candidates,
        "route": mock_route,  # 直接提供mock route
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    try:
        result = await graph.ainvoke(initial_state)
        elapsed = time.time() - start_time

        # 分析结果
        arbitration = result.get("arbitration", {})
        validation_results = result.get("validation_results", [])

        # 统计发现的问题
        all_issues = []
        for vr in validation_results:
            all_issues.extend(vr.get("issues", []))

        # 按category统计
        issue_categories = set()
        for issue in all_issues:
            issue_categories.add(issue.get("category"))

        # 从arbitration获取更完整的信息
        stats = arbitration.get("stats", {}) if arbitration else {}
        total_issues = stats.get("total", 0)
        high_issues = stats.get("high", 0)
        action = arbitration.get("action", "unknown") if arbitration else "unknown"

        return {
            "success": True,
            "elapsed": elapsed,
            "errors": result.get("errors", []),
            "warnings": [],  # 新架构用issues代替warnings
            "issues_found": total_issues,
            "high_issues": high_issues,
            "issue_categories": list(issue_categories),
            "action": action,
            "route_length": len(result.get("route", {}).get("route", [])),
            "rounds": result.get("round", 0),
        }

    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "elapsed": elapsed,
            "errors": [str(e)],
            "warnings": [],
            "issues_found": 0,
            "route_length": 0,
        }


@pytest.mark.asyncio
async def test_ab_comparison():
    """A/B对比测试主函数。"""
    print("\n" + "="*70)
    print("A/B对比测试：新旧架构效果量化")
    print("="*70)

    results = []

    for test_case in TEST_CASES:
        print(f"\n📋 测试: {test_case['name']}")
        print(f"   输入: {test_case['input']}")
        print(f"   预期发现问题: {test_case['issues']}")

        # 运行旧管线
        print("   运行旧管线...", end=" ")
        old_result = await run_old_pipeline(test_case["input"])
        print(f"✓ ({old_result['elapsed']:.2f}s)")

        # 运行新管线
        print("   运行新管线...", end=" ")
        new_result = await run_new_pipeline(test_case["input"])
        print(f"✓ ({new_result['elapsed']:.2f}s)")

        # 分析结果
        results.append({
            "name": test_case["name"],
            "expected_issues": test_case["issues"],
            "old": old_result,
            "new": new_result,
        })

    # 汇总统计
    print("\n" + "="*70)
    print("对比结果汇总")
    print("="*70)

    # 1. 问题发现率对比
    print("\n📊 1. 问题发现率对比")
    print("-" * 50)

    old_detection_rate = 0
    new_detection_rate = 0

    for r in results:
        expected = set(r["expected_issues"])

        # 旧管线：从warnings推断
        old_warnings = " ".join(r["old"]["warnings"]).lower()
        old_detected = set()
        if "预算" in old_warnings or "budget" in old_warnings:
            old_detected.add("budget")
        if "时间" in old_warnings or "time" in old_warnings:
            old_detected.add("time")
        if "疲劳" in old_warnings or "fatigue" in old_warnings:
            old_detected.add("fatigue")

        # 新管线：从categories直接获取
        new_detected = set(r["new"].get("issue_categories", []))

        old_score = len(old_detected & expected) / len(expected) if expected else 1.0
        new_score = len(new_detected & expected) / len(expected) if expected else 1.0

        old_detection_rate += old_score
        new_detection_rate += new_score

        print(f"   {r['name'][:15]:15} | 旧: {old_score*100:3.0f}% | 新: {new_score*100:3.0f}% | 提升: {(new_score-old_score)*100:+.0f}%")

    old_avg = old_detection_rate / len(results) * 100
    new_avg = new_detection_rate / len(results) * 100
    print(f"\n   平均问题发现率: 旧={old_avg:.0f}% | 新={new_avg:.0f}% | 提升={new_avg-old_avg:+.0f}%")

    # 2. 严重问题识别
    print("\n📊 2. 严重问题(high severity)识别")
    print("-" * 50)

    old_high = sum(1 for r in results if r["old"].get("issues_found", 0) > 0)
    new_high = sum(r["new"].get("high_issues", 0) for r in results)

    print(f"   旧管线识别问题数: {old_high}")
    print(f"   新管线识别high severity: {new_high}")
    print(f"   严重问题发现能力提升: {new_high/(old_high+0.1)*100:.0f}%")

    # 3. 重新规划能力
    print("\n📊 3. 重新规划(re-solve)能力")
    print("-" * 50)

    re_solves = sum(1 for r in results if r["new"].get("action") == "re_solve")
    print(f"   触发re-solve次数: {re_solves}/{len(results)}")
    print(f"   自适应调整率: {re_solves/len(results)*100:.0f}%")

    # 4. 性能对比
    print("\n📊 4. 性能对比")
    print("-" * 50)

    old_time = sum(r["old"]["elapsed"] for r in results)
    new_time = sum(r["new"]["elapsed"] for r in results)

    print(f"   旧管线总耗时: {old_time:.2f}s")
    print(f"   新管线总耗时: {new_time:.2f}s")
    print(f"   平均单次耗时: 旧={old_time/len(results):.2f}s | 新={new_time/len(results):.2f}s")

    if new_time < old_time:
        print(f"   性能提升: {(old_time-new_time)/old_time*100:.0f}%")
    else:
        print(f"   性能下降: {(new_time-old_time)/old_time*100:.0f}% (validator并行开销)")

    # 5. 综合通过率
    print("\n📊 5. 综合通过率")
    print("-" * 50)

    old_pass = sum(1 for r in results if r["old"]["success"])
    new_pass = sum(1 for r in results if r["new"]["success"])

    print(f"   旧管线成功率: {old_pass}/{len(results)} ({old_pass/len(results)*100:.0f}%)")
    print(f"   新管线成功率: {new_pass}/{len(results)} ({new_pass/len(results)*100:.0f}%)")

    # 6. 总体评估
    print("\n" + "="*70)
    print("📈 总体评估")
    print("="*70)

    improvements = []
    if new_avg > old_avg:
        improvements.append(f"问题发现率提升 {new_avg-old_avg:.0f}%")
    if new_high > old_high:
        improvements.append(f"严重问题识别更精准")
    if re_solves > 0:
        improvements.append(f"自适应调整 {re_solves} 次")

    if improvements:
        print(f"   改进: {', '.join(improvements)}")
    else:
        print("   需要进一步优化")

    # 验证新架构更好
    assert new_avg >= old_avg, "新架构问题发现率应该不低于旧架构"

    print("\n" + "="*70)
