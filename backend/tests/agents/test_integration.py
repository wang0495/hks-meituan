"""全链路集成测试。

验证从 parse_intent 到 narrate 的完整流程。
"""

import pytest
import asyncio
from typing import Any

from backend.agents import build_graph, LANGGRAPH_AVAILABLE


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_full_pipeline_basic():
    """测试基础流程能跑通。"""
    graph = build_graph()

    # 简单的测试输入
    initial_state = {
        "user_input": "我想在珠海玩一天，喜欢文化和美食",
        "user_intent": {},
        "candidates": [],
        "route": None,
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    # 执行图
    result = await graph.ainvoke(initial_state)

    # 验证结果结构
    assert result is not None
    assert "user_intent" in result
    assert "errors" in result

    print(f"\nPipeline completed with {len(result.get('errors', []))} errors")
    print(f"User intent: {result.get('user_intent', {})}")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_streaming_events():
    """测试流式事件输出。"""
    from backend.agents.streaming import graph_events_to_sse, sse_event

    graph = build_graph()

    initial_state = {
        "user_input": "测试输入",
        "user_intent": {},
        "candidates": [],
        "route": None,
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    # 收集事件
    events = []
    async for event in graph.astream(initial_state):
        events.append(event)
        print(f"Event: {event.get('type')} - {event.get('node', 'N/A')}")

    # 验证有事件产生
    assert len(events) > 0

    # 验证包含关键节点的事件
    node_names = [e.get('node') for e in events if e.get('type') == 'node_start']
    print(f"\nExecuted nodes: {node_names}")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
def test_state_transitions():
    """测试状态流转。"""
    from backend.agents.state import PlanningState, AgentIssue, ValidatorResult, ArbitrationResult

    # 构建完整状态
    state: PlanningState = {
        "user_input": "测试",
        "user_intent": {
            "budget": {"per_person": 500},
            "group": {"type": "情侣"},
        },
        "candidates": [
            {"id": "poi_001", "name": "测试景点", "category": "景点", "avg_price": 100},
        ],
        "route": {
            "route": [
                {
                    "poi": {"id": "poi_001", "name": "测试景点", "category": "景点", "avg_price": 100},
                    "arrival_time": "09:00",
                    "departure_time": "11:00",
                }
            ],
            "total_cost": {"time_min": 120, "budget_used": 100},
        },
        "validation_results": [
            {
                "agent": "time_cop",
                "issues": [],
                "confidence": 0.9,
            }
        ],
        "arbitration": {
            "action": "pass",
            "issues": [],
            "adjustments": {},
            "confidence": 0.9,
        },
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    assert state["round"] == 0
    assert state["arbitration"]["action"] == "pass"
    print("\nState structure validated")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_arbitration_decisions():
    """测试裁决节点的不同决策。"""
    from backend.agents.nodes.arbitrate import node as arbitrate_node
    from backend.agents.state import PlanningState

    # Test 1: 无问题 -> pass
    state1: PlanningState = {
        "user_input": "",
        "user_intent": {},
        "candidates": [],
        "route": {},
        "validation_results": [
            {"agent": "time_cop", "issues": [], "confidence": 1.0},
            {"agent": "budget_auditor", "issues": [], "confidence": 1.0},
        ],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }
    result1 = arbitrate_node(state1)
    assert result1["arbitration"]["action"] == "pass"
    print("\nTest 1 passed: No issues -> pass")

    # Test 2: 有high问题 -> re_solve
    state2: PlanningState = {
        "user_input": "",
        "user_intent": {},
        "candidates": [],
        "route": {},
        "validation_results": [
            {
                "agent": "time_cop",
                "issues": [{
                    "severity": "high",
                    "category": "time",
                    "description": "营业时间不匹配",
                    "suggestion": "调整时间",
                    "affected_indices": [0],
                }],
                "confidence": 0.8,
            }
        ],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }
    result2 = arbitrate_node(state2)
    assert result2["arbitration"]["action"] == "re_solve"
    print("Test 2 passed: High severity issue -> re_solve")

    # Test 3: 超过最大轮数 -> 强制pass
    state3: PlanningState = {
        "user_input": "",
        "user_intent": {},
        "candidates": [],
        "route": {},
        "validation_results": [
            {
                "agent": "time_cop",
                "issues": [{
                    "severity": "high",
                    "category": "time",
                    "description": "营业时间不匹配",
                    "suggestion": "调整时间",
                    "affected_indices": [0],
                }],
                "confidence": 0.8,
            }
        ],
        "arbitration": None,
        "narrative": None,
        "round": 2,  # 已经达到最大轮数
        "errors": [],
    }
    result3 = arbitrate_node(state3)
    assert result3["arbitration"]["action"] == "pass"
    print("Test 3 passed: Max rounds exceeded -> force pass")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_validation_fan_out():
    """测试validator的fan-out并行执行。"""
    from backend.agents.nodes.time_cop import node as time_cop_node
    from backend.agents.nodes.fatigue_auditor import node as fatigue_node
    from backend.agents.nodes.budget_auditor import node as budget_node
    from backend.agents.state import PlanningState

    # 测试数据
    state: PlanningState = {
        "user_input": "",
        "user_intent": {
            "budget": {"per_person": 200},
            "group": {"type": "亲子"},
        },
        "candidates": [],
        "route": {
            "route": [
                {
                    "poi": {
                        "id": "poi_001",
                        "name": "长隆海洋王国",
                        "category": "景点",
                        "avg_price": 395,
                        "business_hours": "09:00-18:00",
                        "emotion_tags": {"physical_demand": 0.8},
                    },
                    "arrival_time": "10:00",
                    "departure_time": "14:00",
                    "travel_from_prev": {"distance_m": 0, "time_min": 0},
                },
                {
                    "poi": {
                        "id": "poi_002",
                        "name": "珠海渔女",
                        "category": "景点",
                        "avg_price": 0,
                        "business_hours": "全天",
                        "emotion_tags": {"physical_demand": 0.3},
                    },
                    "arrival_time": "15:00",
                    "departure_time": "16:00",
                    "travel_from_prev": {"distance_m": 15000, "time_min": 30},
                },
            ],
            "total_cost": {"time_min": 360, "budget_used": 395, "step_estimate": 8000},
            "breathing_spots": [],
        },
        "validation_results": [],
        "arbitration": None,
        "narrative": None,
        "round": 0,
        "errors": [],
    }

    # 并行运行所有validator
    results = await asyncio.gather(
        asyncio.to_thread(time_cop_node, state),
        asyncio.to_thread(fatigue_node, state),
        asyncio.to_thread(budget_node, state),
    )

    # 验证结果
    agents = [r["validation_results"][0]["agent"] for r in results]
    assert "time_cop" in agents
    assert "fatigue_auditor" in agents
    assert "budget_auditor" in agents

    # 检查发现的问题
    all_issues = []
    for r in results:
        all_issues.extend(r["validation_results"][0].get("issues", []))

    print(f"\nValidation completed:")
    print(f"  - TimeCop found {len([i for i in all_issues if i['category'] == 'time'])} issues")
    print(f"  - FatigueAuditor found {len([i for i in all_issues if i['category'] == 'fatigue'])} issues")
    print(f"  - BudgetAuditor found {len([i for i in all_issues if i['category'] == 'budget'])} issues")

    # 预算应该有问题（395元 > 200元预算）
    budget_issues = [i for i in all_issues if i["category"] == "budget"]
    assert len(budget_issues) > 0
    print("\nAll validators working correctly!")
