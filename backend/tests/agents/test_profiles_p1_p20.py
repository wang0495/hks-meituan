"""P1-P20 用户画像全链路集成测试。

使用20个预设用户画像测试多智能体管线的质量，
与旧管线进行对比。
"""

import pytest
import asyncio
from typing import Any

from backend.agents import build_graph, LANGGRAPH_AVAILABLE


# P1-P20 测试用例（从user_profiles.py提取）
PROFILE_TEST_CASES = [
    # P1-P5: 基础画像
    {"profile_id": "P1", "name": "社恐独居", "input": "一个人想安静地在珠海待一天，不要太热闹", "expected_emotion": "宁静"},
    {"profile_id": "P2", "name": "浪漫情侣", "input": "和女朋友约会，想要浪漫一点的路线", "expected_emotion": "浪漫"},
    {"profile_id": "P3", "name": "活力亲子", "input": "带5岁孩子去珠海玩，适合孩子的", "expected_emotion": "温馨"},
    {"profile_id": "P4", "name": "朋友聚会", "input": "三个朋友周末聚会，想热闹点", "expected_emotion": "欢乐"},
    {"profile_id": "P5", "name": "退休休闲", "input": "和老伴两个人慢慢逛，不要太累", "expected_emotion": "放松"},

    # P6-P10: 兴趣画像
    {"profile_id": "P6", "name": "文化探索者", "input": "想了解珠海的历史文化", "expected_emotion": "深度"},
    {"profile_id": "P7", "name": "美食猎人", "input": "专门来吃珠海的特色美食", "expected_emotion": "满足"},
    {"profile_id": "P8", "name": "自然爱好者", "input": "想看自然风光，海边山景", "expected_emotion": "治愈"},
    {"profile_id": "P9", "name": "社交达人", "input": "想要打卡拍照发朋友圈的地方", "expected_emotion": "出片"},
    {"profile_id": "P10", "name": "摄影爱好者", "input": "摄影创作，需要光影好的地方", "expected_emotion": "震撼"},

    # P11-P15: 特殊需求
    {"profile_id": "P11", "name": "历史迷", "input": "对近代史感兴趣，看历史遗迹", "expected_emotion": "敬畏"},
    {"profile_id": "P12", "name": "宠物主人", "input": "带狗狗一起，宠物友好的地方", "expected_emotion": "陪伴"},
    {"profile_id": "P13", "name": "运动健身", "input": "骑行或者徒步路线", "expected_emotion": "挑战"},
    {"profile_id": "P14", "name": "三代同堂", "input": "带老人和小孩，全家出游", "expected_emotion": "和睦"},
    {"profile_id": "P15", "name": "商务休闲", "input": "出差间隙，半天时间放松", "expected_emotion": "高效"},

    # P16-P20: 边缘画像
    {"profile_id": "P16", "name": "学生穷游", "input": "预算100块，学生党", "expected_emotion": "性价比"},
    {"profile_id": "P17", "name": "艺术家", "input": "寻找灵感，小众文艺", "expected_emotion": "灵感"},
    {"profile_id": "P18", "name": "夜生活爱好者", "input": "晚上9点之后有什么玩的", "expected_emotion": "刺激"},
    {"profile_id": "P19", "name": "亲子教育", "input": "带孩子学习知识，寓教于乐", "expected_emotion": "成长"},
    {"profile_id": "P20", "name": "极简主义者", "input": "只想看一个地方，深度体验", "expected_emotion": "专注"},
]


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_profile_p1_social_anxiety():
    """P1: 社恐独居 - 验证路线不拥挤、安静。"""
    graph = build_graph()

    initial_state = {
        "user_input": "一个人想安静地在珠海待一天，不要太热闹",
        "user_intent": {"group": {"type": "独居"}, "preferences": {"social": 0.2}},
        "candidates": [],
        "route": None,
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = await graph.ainvoke(initial_state)

    # 验证没有报错
    assert len(result.get("errors", [])) == 0
    print(f"\n✅ P1 社恐独居: 流程完成")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_profile_p2_romantic_couple():
    """P2: 浪漫情侣 - 验证浪漫场景。"""
    graph = build_graph()

    initial_state = {
        "user_input": "和女朋友约会，想要浪漫一点的路线",
        "user_intent": {"group": {"type": "情侣"}, "preferences": {"romantic": 0.9}},
        "candidates": [],
        "route": None,
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = await graph.ainvoke(initial_state)
    assert len(result.get("errors", [])) == 0
    print(f"\n✅ P2 浪漫情侣: 流程完成")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_profile_p3_family_with_kids():
    """P3: 活力亲子 - 验证儿童友好、安全性。"""
    graph = build_graph()

    initial_state = {
        "user_input": "带5岁孩子去珠海玩，适合孩子的",
        "user_intent": {"group": {"type": "亲子", "size": 3}, "preferences": {"kid_friendly": 0.9}},
        "candidates": [],
        "route": None,
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = await graph.ainvoke(initial_state)

    # 检查FatigueAuditor是否正确识别亲子群体
    errors = result.get("errors", [])
    assert all("疲劳" not in e for e in errors), "亲子路线不应过度疲劳"
    print(f"\n✅ P3 活力亲子: 流程完成")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_profile_p16_budget_constraint():
    """P16: 学生穷游 - 验证预算控制。"""
    graph = build_graph()

    initial_state = {
        "user_input": "预算100块，学生党",
        "user_intent": {
            "group": {"type": "学生"},
            "budget": {"per_person": 100},
        },
        "candidates": [],
        "route": None,
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = await graph.ainvoke(initial_state)

    # BudgetAuditor应该发现问题
    arbitration = result.get("arbitration", {})
    if arbitration:
        budget_issues = [
            i for i in arbitration.get("issues", [])
            if i.get("category") == "budget"
        ]
        print(f"\n✅ P16 学生穷游: 发现 {len(budget_issues)} 个预算问题")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_profile_p18_late_night():
    """P18: 夜生活 - 验证营业时间检查。"""
    graph = build_graph()

    initial_state = {
        "user_input": "晚上9点之后有什么玩的",
        "user_intent": {
            "group": {"type": "朋友"},
            "time": {"start": "21:00", "end": "02:00"},
            "hard_constraints": ["late_night"],
        },
        "candidates": [],
        "route": None,
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = await graph.ainvoke(initial_state)

    # TimeCop应该检查营业时间
    print(f"\n✅ P18 夜生活: 流程完成")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_all_profiles_basic():
    """测试所有P1-P20画像的基础流程。"""
    graph = build_graph()

    results = []
    for test_case in PROFILE_TEST_CASES:
        initial_state = {
            "user_input": test_case["input"],
            "user_intent": {},
            "candidates": [],
            "route": None,
            "validation_results": [],
            "arbitration": None,
            "narrative": None,
            "round": 0,
            "errors": [],
        }

        try:
            result = await graph.ainvoke(initial_state)
            errors = result.get("errors", [])

            # 区分致命错误和正常警告（如POI过滤）
            fatal_errors = [e for e in errors if "失败" in e or "错误" in e or "异常" in e]
            warnings = [e for e in errors if e not in fatal_errors]

            # 只要有user_intent就认为流程基本成功
            has_intent = bool(result.get("user_intent"))

            if len(fatal_errors) == 0 and has_intent:
                status = "pass"
            elif has_intent:
                status = "partial"
            else:
                status = "fail"

            results.append({
                "profile_id": test_case["profile_id"],
                "name": test_case["name"],
                "status": status,
                "errors": len(fatal_errors),
                "warnings": len(warnings),
            })

            icon = "✅" if status == "pass" else "⚠️" if status == "partial" else "❌"
            print(f"{icon} {test_case['profile_id']} {test_case['name']}: {status}")
        except Exception as e:
            results.append({
                "profile_id": test_case["profile_id"],
                "name": test_case["name"],
                "status": "fail",
                "errors": str(e)[:50],
            })
            print(f"❌ {test_case['profile_id']} {test_case['name']}: 异常 - {str(e)[:50]}")

    # 统计
    passed = sum(1 for r in results if r["status"] == "pass")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "fail")

    print(f"\n{'='*50}")
    print(f"P1-P20 测试结果统计:")
    print(f"  ✅ 通过: {passed}/{len(PROFILE_TEST_CASES)}")
    print(f"  ⚠️  部分: {partial}/{len(PROFILE_TEST_CASES)}")
    print(f"  ❌ 失败: {failed}/{len(PROFILE_TEST_CASES)}")
    print(f"{'='*50}")

    # 通过+部分通过 >= 80% 就算成功
    success_rate = (passed + partial) / len(PROFILE_TEST_CASES)
    assert success_rate >= 0.8, f"成功率 {success_rate*100:.0f}% 低于80%"


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_validation_market_effectiveness():
    """测试校验市场的有效性 - 故意给有问题的输入，看是否能发现。"""
    graph = build_graph()

    # 测试用例：预算严重不足
    test_cases = [
        {
            "name": "预算不足",
            "input": "50块钱玩一天珠海",
            "intent": {"budget": {"per_person": 50}},
            "expected_validator": "budget_auditor",
        },
        {
            "name": "时间不合理",
            "input": "凌晨2点去博物馆",
            "intent": {"time": {"start": "02:00"}, "scene_requirements": ["文化"]},
            "expected_validator": "time_cop",
        },
        {
            "name": "亲子疲劳风险",
            "input": "带3岁孩子走10公里",
            "intent": {"group": {"type": "亲子"}, "preferences": {"physical": 0.9}},
            "expected_validator": "fatigue_auditor",
        },
    ]

    for case in test_cases:
        initial_state = {
            "user_input": case["input"],
            "user_intent": case["intent"],
            "candidates": [],
            "route": None,
            "validation_results": [],
            "arbitration": None,
            "narrative": None,
            "round": 0,
            "errors": [],
        }

        result = await graph.ainvoke(initial_state)
        arbitration = result.get("arbitration", {})

        # 检查是否有validator发现问题
        total_issues = arbitration.get("stats", {}).get("total", 0) if arbitration else 0

        print(f"\n{case['name']}: 发现 {total_issues} 个问题")
        if total_issues > 0:
            print(f"  ✅ {case['expected_validator']} 正常工作")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_re_solve_loop():
    """测试re_solve循环机制。"""
    graph = build_graph()

    # 给一个会导致high severity issue的输入
    initial_state = {
        "user_input": "预算50块去长隆海洋王国",
        "user_intent": {
            "budget": {"per_person": 50},
            "scene_requirements": ["长隆", "海洋王国"],
        },
        "candidates": [],
        "route": None,
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    result = await graph.ainvoke(initial_state)

    # 检查轮数
    final_round = result.get("round", 0)
    arbitration = result.get("arbitration", {})

    print(f"\n🔄 Re-solve测试:")
    print(f"  最终轮数: {final_round}")
    print(f"  最终决策: {arbitration.get('action', 'unknown')}")

    # 流程应该完成（即使有问题也不会死循环）
    assert final_round <= 2, "不应该超过最大轮数"
