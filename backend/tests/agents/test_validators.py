"""Validator节点单元测试。"""

import pytest
from datetime import datetime

from backend.agents.state import PlanningState, AgentIssue


class TestTimeCop:
    """TimeCop校验器测试。"""

    def test_business_hours_check(self):
        """测试营业时间检查。"""
        from backend.agents.nodes.time_cop import _check_business_hours

        poi = {
            "name": "测试景点",
            "business_hours": "09:00-17:00",
        }

        # 正常时间
        issues = _check_business_hours(poi, "10:00", "11:00")
        assert len(issues) == 0

        # 早于开门
        issues = _check_business_hours(poi, "08:00", "09:00")
        assert len(issues) == 1
        assert issues[0]["severity"] == "high"

        # 接近关门
        issues = _check_business_hours(poi, "16:45", "17:00")
        assert len(issues) == 1
        assert issues[0]["severity"] == "medium"

    def test_time_cop_node_empty_route(self):
        """测试空路线情况。"""
        from backend.agents.nodes.time_cop import node

        state: PlanningState = {
            "user_input": "",
            "user_intent": {},
            "candidates": [],
            "route": None,
            "validation_results": [],
            "arbitration": None,
            "narrative": None,
            "round": 0,
            "errors": [],
        }

        result = node(state)
        assert "validation_results" in result
        assert len(result["validation_results"]) == 1
        assert result["validation_results"][0]["agent"] == "time_cop"


class TestFatigueAuditor:
    """FatigueAuditor校验器测试。"""

    def test_fatigue_thresholds(self):
        """测试疲劳阈值。"""
        from backend.agents.nodes.fatigue_auditor import FATIGUE_THRESHOLDS

        assert "亲子" in FATIGUE_THRESHOLDS
        assert "退休" in FATIGUE_THRESHOLDS
        assert FATIGUE_THRESHOLDS["亲子"]["max_walk"] < FATIGUE_THRESHOLDS["朋友"]["max_walk"]

    def test_fatigue_node_empty_route(self):
        """测试空路线情况。"""
        from backend.agents.nodes.fatigue_auditor import node

        state: PlanningState = {
            "user_input": "",
            "user_intent": {"group": {"type": "亲子"}},
            "candidates": [],
            "route": None,
            "validation_results": [],
            "arbitration": None,
            "narrative": None,
            "round": 0,
            "errors": [],
        }

        result = node(state)
        assert "validation_results" in result


class TestBudgetAuditor:
    """BudgetAuditor校验器测试。"""

    def test_budget_overrun(self):
        """测试预算超支检测。"""
        from backend.agents.nodes.budget_auditor import node

        state: PlanningState = {
            "user_input": "",
            "user_intent": {"budget": {"per_person": 100}},
            "candidates": [],
            "route": {
                "total_cost": {"budget_used": 150},
                "route": [],
            },
            "validation_results": [],
            "arbitration": None,
            "narrative": None,
            "round": 0,
            "errors": [],
        }

        result = node(state)
        assert "validation_results" in result
        vr = result["validation_results"][0]
        assert vr["agent"] == "budget_auditor"


class TestArbitrate:
    """Arbitrate裁决节点测试。"""

    def test_high_severity_triggers_resolve(self):
        """测试high severity触发re_solve。"""
        from backend.agents.nodes.arbitrate import node

        state: PlanningState = {
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
                        "description": "测试",
                        "suggestion": "测试",
                        "affected_indices": [],
                    }],
                    "confidence": 0.8,
                }
            ],
            "arbitration": None,
            "narrative": None,
            "round": 0,
            "errors": [],
        }

        result = node(state)
        assert result["arbitration"]["action"] == "re_solve"

    def test_max_rounds_forces_pass(self):
        """测试超过最大轮数强制pass。"""
        from backend.agents.nodes.arbitrate import node

        state: PlanningState = {
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
                        "description": "测试",
                        "suggestion": "测试",
                        "affected_indices": [],
                    }],
                    "confidence": 0.8,
                }
            ],
            "arbitration": None,
            "narrative": None,
            "round": 2,  # 已经超过max rounds
            "errors": [],
        }

        result = node(state)
        assert result["arbitration"]["action"] == "pass"
