"""CityFlow 意图解析 Mock 测试。

不依赖真实 LLM 服务，通过 Mock 验证意图解析的各个分支：
- LLM 正常返回
- LLM 超时降级
- LLM 异常降级
- 规则匹配兜底

"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.intent_parser import _rule_based_parse, parse_intent
from tests.factories import IntentFactory

# ---------------------------------------------------------------------------
# Mock LLM 调用测试
# ---------------------------------------------------------------------------


class TestParseIntentWithMockLLM:
    """通过 Mock LLM 测试意图解析。"""

    @pytest.mark.asyncio
    async def test_llm_returns_valid_json(self) -> None:
        """LLM 返回合法 JSON 时，直接使用 LLM 结果。"""
        mock_response = {
            "time": {"period": "全天", "start": "09:00", "end": "18:00"},
            "budget": {"per_person": 300, "type": "弹性"},
            "group": {"size": 1, "type": "独居"},
            "preferences": {
                "culture": 0.6,
                "food": 0.4,
                "nature": 0.7,
                "social": 0.1,
            },
            "pace": "闲逛型",
            "hard_constraints": [],
        }

        with patch(
            "backend.services.intent_parser._call_llm",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = mock_response
            result = await parse_intent("周末想一个人安静走走")

            assert result["group"]["type"] == "独居"
            assert result["pace"] == "闲逛型"
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_returns_json_in_markdown(self) -> None:
        """LLM 返回 markdown 包裹的 JSON 时，也能正确解析。"""
        # _call_llm 内部已处理 markdown 提取，这里 Mock 直接返回 dict
        mock_response = {
            "time": {"period": "下午", "start": "13:00", "end": "18:00"},
            "budget": {"per_person": 500, "type": "弹性"},
            "group": {"size": 2, "type": "情侣"},
            "preferences": {
                "culture": 0.4,
                "food": 0.7,
                "nature": 0.3,
                "social": 0.5,
            },
            "pace": "平衡型",
            "hard_constraints": [],
        }

        with patch(
            "backend.services.intent_parser._call_llm",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = mock_response
            result = await parse_intent("和女朋友下午约会")

            assert result["group"]["type"] == "情侣"


# ---------------------------------------------------------------------------
# LLM 超时/异常降级测试
# ---------------------------------------------------------------------------


class TestParseIntentLLMFallback:
    """测试 LLM 失败时的降级行为。"""

    @pytest.mark.asyncio
    async def test_llm_timeout_falls_back_to_rules(self) -> None:
        """LLM 超时 → 降级为规则匹配。"""
        with patch(
            "backend.services.intent_parser._call_llm",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.side_effect = asyncio.TimeoutError("LLM timeout")

            result = await parse_intent("周末想出去走走，不想去人多的地方")

            # 应该降级到规则匹配
            assert "time" in result
            assert "group" in result
            assert result["preferences"]["social"] <= 0.2
            assert "低人流" in result.get("hard_constraints", [])

    @pytest.mark.asyncio
    async def test_llm_connection_error_falls_back(self) -> None:
        """LLM 连接异常 → 降级为规则匹配。"""
        with patch(
            "backend.services.intent_parser._call_llm",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.side_effect = ConnectionError("Connection refused")

            result = await parse_intent("带狗子出去转转")

            assert "pet_friendly" in result.get("hard_constraints", [])

    @pytest.mark.asyncio
    async def test_llm_returns_none_falls_back(self) -> None:
        """LLM 返回 None → 降级为规则匹配。"""
        with patch(
            "backend.services.intent_parser._call_llm",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = None

            result = await parse_intent("和女朋友约会，想找有氛围的地方")

            assert result["group"]["type"] == "情侣"


# ---------------------------------------------------------------------------
# 规则匹配详细测试
# ---------------------------------------------------------------------------


class TestRuleBasedParseDetailed:
    """测试规则匹配的各种边界情况。"""

    def test_combined_scenario_pet_and_budget(self) -> None:
        """同时包含宠物和预算信息。"""
        result = _rule_based_parse("带狗子出去转转，预算200元以内")
        assert "pet_friendly" in result["hard_constraints"]
        assert result["budget"]["per_person"] == 200
        assert result["budget"]["type"] == "硬约束"

    def test_special_force_pace(self) -> None:
        """特种兵模式。"""
        result = _rule_based_parse("特种兵打卡，一天去10个地方")
        assert result["pace"] == "特种兵型"

    def test_accessible_constraint(self) -> None:
        """无障碍约束。"""
        result = _rule_based_parse("推轮椅出门，要无障碍的地方")
        assert "accessible" in result["hard_constraints"]

    def test_no_queue_constraint(self) -> None:
        """不想排队约束。"""
        result = _rule_based_parse("出去玩但是不想排队")
        assert "排队容忍度<10min" in result["hard_constraints"]

    def test_nature_preference_high(self) -> None:
        """自然偏好高。"""
        result = _rule_based_parse("想去公园爬山，看看湖")
        assert result["preferences"]["nature"] >= 0.8

    def test_friends_group(self) -> None:
        """朋友聚会。"""
        result = _rule_based_parse("和朋友一起聚会，想去热闹的地方")
        assert result["group"]["type"] == "朋友"
        assert result["group"]["size"] == 4
        assert result["preferences"]["social"] >= 0.8


# ---------------------------------------------------------------------------
# 使用 Factory 的测试
# ---------------------------------------------------------------------------


class TestIntentWithFactory:
    """使用 IntentFactory 的意图测试。"""

    def test_factory_solo_quiet(self) -> None:
        """Factory 生成的社恐独居意图结构正确。"""
        intent = IntentFactory.create_solo_quiet()
        assert intent["group"]["type"] == "独居"
        assert intent["pace"] == "闲逛型"
        assert intent["preferences"]["social"] <= 0.2

    def test_factory_couple_romantic(self) -> None:
        """Factory 生成的情侣意图结构正确。"""
        intent = IntentFactory.create_couple_romantic()
        assert intent["group"]["type"] == "情侣"
        assert intent["group"]["size"] == 2

    def test_factory_family_kids(self) -> None:
        """Factory 生成的亲子意图结构正确。"""
        intent = IntentFactory.create_family_kids()
        assert intent["group"]["type"] == "亲子"
        assert "儿童友好" in intent["hard_constraints"]

    def test_factory_friends_party(self) -> None:
        """Factory 生成的朋友聚会意图结构正确。"""
        intent = IntentFactory.create_friends_party()
        assert intent["group"]["type"] == "朋友"
        assert intent["pace"] == "特种兵型"

    def test_factory_override_fields(self) -> None:
        """Factory 支持字段覆盖。"""
        intent = IntentFactory.create(
            pace="特种兵型",
            budget={"per_person": 100, "type": "硬约束"},
        )
        assert intent["pace"] == "特种兵型"
        assert intent["budget"]["per_person"] == 100
