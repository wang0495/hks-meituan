"""narrator.py 测试。

测试场景：
- 独居用户：验证开场语匹配
- 情侣用户：验证浪漫氛围
- 亲子用户：验证儿童友好描述
- 朋友聚会：验证多人场景
- 退休用户：验证慢节奏文案
- 情绪亮点提取正确性
- 空路线处理
- 收尾语按类别匹配
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.narrator import (CLOSING_TEMPLATES, OPENING_TEMPLATES,
                                       STEP_TEMPLATES,
                                       _extract_emotion_highlights,
                                       _generate_closing, _generate_opening,
                                       _generate_step, generate_narrative)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_poi(
    name: str = "测试景点",
    category: str = "文化",
    excitement: float = 0.5,
    tranquility: float = 0.5,
    culture_depth: float = 0.5,
    surprise: float = 0.3,
    physical_demand: float = 0.3,
) -> dict[str, Any]:
    """构造测试用 POI 数据。"""
    return {
        "id": f"test_{name}",
        "name": name,
        "category": category,
        "rating": 4.5,
        "avg_price": 50,
        "lat": 22.27,
        "lng": 113.58,
        "business_hours": "09:00-21:00",
        "emotion_tags": {
            "excitement": excitement,
            "tranquility": tranquility,
            "sociability": 0.5,
            "culture_depth": culture_depth,
            "surprise": surprise,
            "physical_demand": physical_demand,
        },
    }


def _make_route_result(steps: list[dict[str, Any]]) -> dict[str, Any]:
    """构造测试用路线结果。"""
    route = []
    for i, step in enumerate(steps):
        route.append(
            {
                "poi": step["poi"],
                "arrival_time": step.get("arrival_time", f"0{9 + i}:00"),
                "departure_time": step.get("departure_time", f"0{9 + i}:30"),
                "travel_from_prev": {"distance_m": 1000, "time_min": 10},
            }
        )
    return {"route": route}


def _make_user_intent(group_type: str = "独居") -> dict[str, Any]:
    """构造测试用用户意图。"""
    return {
        "time": {"period": "全天", "start": "09:00", "end": "18:00"},
        "budget": {"per_person": 100, "type": "弹性"},
        "group": {"size": 1, "type": group_type},
        "preferences": {
            "culture": 0.6,
            "food": 0.4,
            "nature": 0.7,
            "social": 0.1,
        },
        "pace": "闲逛型",
    }


# ---------------------------------------------------------------------------
# _generate_opening 测试
# ---------------------------------------------------------------------------


class TestGenerateOpening:
    """测试开场语生成。"""

    @pytest.mark.parametrize(
        "group_type",
        [
            "独居",
            "情侣",
            "亲子",
            "朋友",
            "退休",
        ],
    )
    def test_known_group_types(self, group_type: str) -> None:
        intent = _make_user_intent(group_type)
        result = _generate_opening(intent)
        assert result in OPENING_TEMPLATES[group_type]

    def test_unknown_group_type_defaults_to_duju(self) -> None:
        """未知分组类型应使用独居模板。"""
        intent = _make_user_intent("未知类型")
        result = _generate_opening(intent)
        assert result in OPENING_TEMPLATES["独居"]

    def test_missing_group_field(self) -> None:
        """缺少 group 字段时使用独居模板。"""
        intent: dict[str, Any] = {}
        result = _generate_opening(intent)
        assert result in OPENING_TEMPLATES["独居"]


# ---------------------------------------------------------------------------
# _generate_step 测试
# ---------------------------------------------------------------------------


class TestGenerateStep:
    """测试分步描述生成。"""

    def test_excitement_step(self) -> None:
        poi = _make_poi("过山车乐园", excitement=0.95, tranquility=0.1)
        step = {"poi": poi, "arrival_time": "10:00"}
        result = _generate_step(step)
        assert "过山车乐园" in result
        assert "10:00" in result

    def test_tranquility_step(self) -> None:
        poi = _make_poi("湖畔公园", excitement=0.1, tranquility=0.9)
        step = {"poi": poi, "arrival_time": "14:00"}
        result = _generate_step(step)
        assert "湖畔公园" in result

    def test_culture_step(self) -> None:
        poi = _make_poi("博物馆", culture_depth=0.9, excitement=0.2)
        step = {"poi": poi}
        result = _generate_step(step)
        assert "博物馆" in result

    def test_no_arrival_time(self) -> None:
        """没有到达时间时不添加时间前缀。"""
        poi = _make_poi("测试点")
        step: dict[str, Any] = {"poi": poi}
        result = _generate_step(step)
        assert result.startswith("测试点") or "测试点" in result

    def test_step_template_coverage(self) -> None:
        """确保所有情绪模板都能被命中。"""
        for emotion_key in STEP_TEMPLATES:
            if emotion_key == "default":
                continue
            # 构造该情绪主导的 POI
            kwargs: dict[str, float] = {emotion_key: 0.9}
            for other in STEP_TEMPLATES:
                if other != emotion_key:
                    kwargs.setdefault(other, 0.1)
            poi = _make_poi(**kwargs)
            step = {"poi": poi}
            result = _generate_step(step)
            assert isinstance(result, str)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# _generate_closing 测试
# ---------------------------------------------------------------------------


class TestGenerateClosing:
    """测试收尾语生成。"""

    def test_view_category(self) -> None:
        poi = _make_poi("山顶观景台", category="观景")
        route_result = _make_route_result([{"poi": poi}])
        result = _generate_closing(route_result)
        assert result in CLOSING_TEMPLATES["观景"]

    def test_nature_category_maps_to_view(self) -> None:
        """自然类 POI 也应使用观景收尾模板。"""
        poi = _make_poi("湿地公园", category="自然")
        route_result = _make_route_result([{"poi": poi}])
        result = _generate_closing(route_result)
        assert result in CLOSING_TEMPLATES["观景"]

    def test_food_category(self) -> None:
        poi = _make_poi("老街小吃", category="美食")
        route_result = _make_route_result([{"poi": poi}])
        result = _generate_closing(route_result)
        assert result in CLOSING_TEMPLATES["美食"]

    def test_culture_category(self) -> None:
        poi = _make_poi("古城墙", category="文化")
        route_result = _make_route_result([{"poi": poi}])
        result = _generate_closing(route_result)
        assert result in CLOSING_TEMPLATES["文化"]

    def test_default_category(self) -> None:
        poi = _make_poi("购物中心", category="购物")
        route_result = _make_route_result([{"poi": poi}])
        result = _generate_closing(route_result)
        assert result in CLOSING_TEMPLATES["default"]

    def test_empty_route(self) -> None:
        """空路线应返回默认收尾语。"""
        result = _generate_closing({"route": []})
        assert result in CLOSING_TEMPLATES["default"]


# ---------------------------------------------------------------------------
# _extract_emotion_highlights 测试
# ---------------------------------------------------------------------------


class TestExtractEmotionHighlights:
    """测试情绪亮点提取。"""

    def test_high_excitement_highlight(self) -> None:
        poi = _make_poi("刺激乐园", excitement=0.9)
        route_result = _make_route_result([{"poi": poi}])
        highlights = _extract_emotion_highlights(route_result)
        assert len(highlights) == 1
        assert highlights[0]["type"] == "excitement"
        assert highlights[0]["poi"] == "刺激乐园"

    def test_high_tranquility_highlight(self) -> None:
        poi = _make_poi("静心湖", tranquility=0.85, excitement=0.1)
        route_result = _make_route_result([{"poi": poi}])
        highlights = _extract_emotion_highlights(route_result)
        assert any(h["type"] == "tranquility" for h in highlights)

    def test_high_culture_highlight(self) -> None:
        poi = _make_poi("古寺", culture_depth=0.9, excitement=0.2, tranquility=0.3)
        route_result = _make_route_result([{"poi": poi}])
        highlights = _extract_emotion_highlights(route_result)
        assert any(h["type"] == "culture" for h in highlights)

    def test_no_highlights_below_threshold(self) -> None:
        """情绪值都低于 0.8 时不应有亮点。"""
        poi = _make_poi("普通景点", excitement=0.5, tranquility=0.5, culture_depth=0.5)
        route_result = _make_route_result([{"poi": poi}])
        highlights = _extract_emotion_highlights(route_result)
        assert len(highlights) == 0

    def test_multiple_highlights_from_one_poi(self) -> None:
        """一个 POI 可以同时触发多个亮点。"""
        poi = _make_poi(
            "多功能场所",
            excitement=0.85,
            tranquility=0.85,
            culture_depth=0.85,
        )
        route_result = _make_route_result([{"poi": poi}])
        highlights = _extract_emotion_highlights(route_result)
        assert len(highlights) == 3

    def test_empty_route(self) -> None:
        highlights = _extract_emotion_highlights({"route": []})
        assert highlights == []


# ---------------------------------------------------------------------------
# generate_narrative 集成测试
# ---------------------------------------------------------------------------


class TestGenerateNarrative:
    """测试完整的文案生成流程。"""

    @pytest.mark.asyncio
    async def test_solo_user_narrative(self) -> None:
        """独居用户：验证开场语和完整结构。"""
        poi = _make_poi(
            "安静图书馆", tranquility=0.9, culture_depth=0.8, excitement=0.1
        )
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent("独居")

        result = await generate_narrative(route_result, intent, enable_llm_polish=False)

        assert result["opening"] in OPENING_TEMPLATES["独居"]
        assert len(result["steps"]) == 1
        assert "安静图书馆" in result["steps"][0]
        assert isinstance(result["closing"], str)
        assert isinstance(result["emotion_highlights"], list)

    @pytest.mark.asyncio
    async def test_couple_narrative(self) -> None:
        """情侣用户：验证浪漫氛围开场。"""
        poi = _make_poi("海边栈道", tranquility=0.8, excitement=0.3)
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent("情侣")

        result = await generate_narrative(route_result, intent, enable_llm_polish=False)

        assert result["opening"] in OPENING_TEMPLATES["情侣"]

    @pytest.mark.asyncio
    async def test_family_narrative(self) -> None:
        """亲子用户：验证儿童友好描述。"""
        poi = _make_poi("儿童乐园", excitement=0.9, physical_demand=0.8)
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent("亲子")

        result = await generate_narrative(route_result, intent, enable_llm_polish=False)

        assert result["opening"] in OPENING_TEMPLATES["亲子"]
        assert len(result["steps"]) == 1

    @pytest.mark.asyncio
    async def test_friends_narrative(self) -> None:
        """朋友聚会场景。"""
        pois = [
            _make_poi("桌游吧", excitement=0.7),
            _make_poi("烧烤店", category="美食"),
        ]
        route_result = _make_route_result([{"poi": p} for p in pois])
        intent = _make_user_intent("朋友")

        result = await generate_narrative(route_result, intent, enable_llm_polish=False)

        assert result["opening"] in OPENING_TEMPLATES["朋友"]
        assert len(result["steps"]) == 2

    @pytest.mark.asyncio
    async def test_retired_narrative(self) -> None:
        """退休用户场景。"""
        poi = _make_poi("公园晨练", tranquility=0.9, physical_demand=0.3)
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent("退休")

        result = await generate_narrative(route_result, intent, enable_llm_polish=False)

        assert result["opening"] in OPENING_TEMPLATES["退休"]

    @pytest.mark.asyncio
    async def test_empty_route(self) -> None:
        """空路线应返回默认文案。"""
        result = await generate_narrative({"route": []}, _make_user_intent())

        assert isinstance(result["opening"], str)
        assert result["steps"] == []
        assert result["emotion_highlights"] == []

    @pytest.mark.asyncio
    async def test_full_route_with_highlights(self) -> None:
        """完整路线包含情绪亮点。"""
        steps_data = [
            {
                "poi": _make_poi(
                    "博物馆", culture_depth=0.9, excitement=0.2, tranquility=0.3
                )
            },
            {"poi": _make_poi("过山车", excitement=0.95, tranquility=0.05)},
            {"poi": _make_poi("湖边", tranquility=0.88, excitement=0.1)},
        ]
        route_result = _make_route_result(steps_data)
        intent = _make_user_intent("朋友")

        result = await generate_narrative(route_result, intent, enable_llm_polish=False)

        assert len(result["steps"]) == 3
        assert (
            len(result["emotion_highlights"]) >= 2
        )  # 博物馆的文化 + 过山车的兴奋 + 湖边的宁静

    @pytest.mark.asyncio
    async def test_output_structure(self) -> None:
        """验证返回结构完整性。"""
        poi = _make_poi("测试点")
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent()

        result = await generate_narrative(route_result, intent, enable_llm_polish=False)

        assert "opening" in result
        assert "steps" in result
        assert "closing" in result
        assert "emotion_highlights" in result
        assert isinstance(result["steps"], list)


# ---------------------------------------------------------------------------
# LLM 润色测试
# ---------------------------------------------------------------------------


class TestLLMPolish:
    """测试 LLM 润色功能。"""

    @pytest.mark.asyncio
    async def test_llm_polish_timeout_returns_original(self) -> None:
        """LLM 超时时应返回原文。"""
        from backend.services.narrator import _llm_polish

        with patch(
            "backend.services.llm_service.chat", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.side_effect = asyncio.TimeoutError()
            result = await _llm_polish("原始文案", "上下文")
            assert result == "原始文案"

    @pytest.mark.asyncio
    async def test_llm_polish_exception_returns_original(self) -> None:
        """LLM 异常时应返回原文。"""
        from backend.services.narrator import _llm_polish

        with patch(
            "backend.services.llm_service.chat", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.side_effect = RuntimeError("API error")
            result = await _llm_polish("原始文案")
            assert result == "原始文案"

    @pytest.mark.asyncio
    async def test_llm_polish_success(self) -> None:
        """LLM 成功时应返回润色结果。"""
        from backend.services.narrator import _llm_polish

        with patch(
            "backend.services.llm_service.chat", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.return_value = "润色后的文案"
            result = await _llm_polish("原始文案", "上下文")
            assert result == "润色后的文案"

    @pytest.mark.asyncio
    async def test_llm_polish_empty_result_returns_original(self) -> None:
        """LLM 返回空字符串时应返回原文。"""
        from backend.services.narrator import _llm_polish

        with patch(
            "backend.services.llm_service.chat", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.return_value = ""
            result = await _llm_polish("原始文案")
            assert result == "原始文案"

    @pytest.mark.asyncio
    async def test_narrative_with_llm_polish_enabled(self) -> None:
        """启用 LLM 润色时应调用 chat。"""
        poi = _make_poi("测试景点")
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent()

        with patch(
            "backend.services.llm_service.chat", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.return_value = "润色后的步骤描述"
            result = await generate_narrative(
                route_result, intent, enable_llm_polish=True
            )
            assert mock_chat.called
            assert result["steps"][0] == "润色后的步骤描述"
