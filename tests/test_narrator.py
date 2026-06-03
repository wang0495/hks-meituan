"""narrator.py 测试。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.narrator import (
    CATEGORY_STEP_TEMPLATES,
    CLOSING_TEMPLATES,
    OPENING_TEMPLATES,
    _extract_emotion_highlights,
    _generate_closing,
    _generate_opening,
    _generate_step,
    generate_narrative,
)


def _make_poi(
    name: str = "测试景点",
    category: str = "文化",
    excitement: float = 0.5,
    tranquility: float = 0.5,
    culture_depth: float = 0.5,
    surprise: float = 0.3,
    physical_demand: float = 0.3,
) -> dict[str, Any]:
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
    return {
        "time": {"period": "全天", "start": "09:00", "end": "18:00"},
        "budget": {"per_person": 100, "type": "弹性"},
        "group": {"size": 1, "type": group_type},
        "preferences": {"culture": 0.6, "food": 0.4, "nature": 0.7, "social": 0.1},
        "pace": "闲逛型",
    }


class TestGenerateOpening:
    @pytest.mark.parametrize("group_type", ["独居", "情侣", "亲子", "朋友", "退休"])
    def test_known_group_types(self, group_type: str) -> None:
        intent = _make_user_intent(group_type)
        result = _generate_opening(intent)
        assert result in OPENING_TEMPLATES[group_type]

    def test_unknown_group_type_defaults_to_duju(self) -> None:
        intent = _make_user_intent("未知类型")
        result = _generate_opening(intent)
        assert result in OPENING_TEMPLATES["独居"]

    def test_missing_group_field(self) -> None:
        intent: dict[str, Any] = {}
        result = _generate_opening(intent)
        assert result in OPENING_TEMPLATES["独居"]


class TestGenerateStep:
    def test_excitement_step(self) -> None:
        poi = _make_poi("过山车乐园", excitement=0.95, tranquility=0.1)
        step = {"poi": poi, "arrival_time": "10:00"}
        result = _generate_step(step, 0, 3)
        assert isinstance(result, dict)
        assert "过山车乐园" in result["description"]
        assert "10:00" in result["description"]

    def test_tranquility_step(self) -> None:
        poi = _make_poi("湖畔公园", excitement=0.1, tranquility=0.9)
        step = {"poi": poi, "arrival_time": "14:00"}
        result = _generate_step(step, 1, 3)
        assert "湖畔公园" in result["description"]

    def test_culture_step(self) -> None:
        poi = _make_poi("博物馆", culture_depth=0.9, excitement=0.2)
        step = {"poi": poi}
        result = _generate_step(step, 0, 1)
        assert "博物馆" in result["description"]

    def test_no_arrival_time(self) -> None:
        poi = _make_poi("测试点")
        step = {"poi": poi}
        result = _generate_step(step, 0, 1)
        assert isinstance(result, dict)
        assert "测试点" in result["description"]

    def test_step_returns_dict_with_all_keys(self) -> None:
        poi = _make_poi("测试点")
        step = {"poi": poi, "arrival_time": "10:00"}
        result = _generate_step(step, 0, 1)
        assert "description" in result
        assert "emotion_design" in result
        assert "design_intent" in result
        assert "leverage" in result
        assert "cost" in result

    def test_step_template_coverage(self) -> None:
        """确保所有category模板都能正常使用。"""
        for cat in CATEGORY_STEP_TEMPLATES:
            poi = _make_poi(f"测试{cat}", category=cat)
            step = {"poi": poi}
            result = _generate_step(step, 0, 1)
            assert isinstance(result, dict)
            assert len(result["description"]) > 0
            assert result["emotion_design"]  # 情绪设计非空


class TestGenerateClosing:
    def test_view_category(self) -> None:
        poi = _make_poi("山顶观景台", category="观景")
        route_result = _make_route_result([{"poi": poi}])
        result = _generate_closing(route_result)
        assert result in CLOSING_TEMPLATES["观景"]

    def test_nature_category_maps_to_view(self) -> None:
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
        result = _generate_closing({"route": []})
        assert result in CLOSING_TEMPLATES["default"]


class TestExtractEmotionHighlights:
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
        poi = _make_poi("普通景点", excitement=0.5, tranquility=0.5, culture_depth=0.5)
        route_result = _make_route_result([{"poi": poi}])
        highlights = _extract_emotion_highlights(route_result)
        assert len(highlights) == 0

    def test_multiple_highlights_from_one_poi(self) -> None:
        poi = _make_poi("多功能场所", excitement=0.85, tranquility=0.85, culture_depth=0.85)
        route_result = _make_route_result([{"poi": poi}])
        highlights = _extract_emotion_highlights(route_result)
        assert len(highlights) == 3

    def test_empty_route(self) -> None:
        highlights = _extract_emotion_highlights({"route": []})
        assert highlights == []


class TestGenerateNarrative:
    @pytest.mark.asyncio
    async def test_solo_user_narrative(self) -> None:
        poi = _make_poi("安静图书馆", tranquility=0.9, culture_depth=0.8, excitement=0.1)
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent("独居")

        result = await generate_narrative(route_result, intent, enable_llm_polish=False)

        assert result["opening"] in OPENING_TEMPLATES["独居"]
        assert len(result["steps"]) == 1
        assert "安静图书馆" in result["steps"][0]["description"]
        assert isinstance(result["closing"], str)
        assert isinstance(result["emotion_highlights"], list)

    @pytest.mark.asyncio
    async def test_couple_narrative(self) -> None:
        poi = _make_poi("海边栈道", tranquility=0.8, excitement=0.3)
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent("情侣")
        result = await generate_narrative(route_result, intent, enable_llm_polish=False)
        assert result["opening"] in OPENING_TEMPLATES["情侣"]

    @pytest.mark.asyncio
    async def test_family_narrative(self) -> None:
        poi = _make_poi("儿童乐园", excitement=0.9, physical_demand=0.8)
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent("亲子")
        result = await generate_narrative(route_result, intent, enable_llm_polish=False)
        assert result["opening"] in OPENING_TEMPLATES["亲子"]
        assert len(result["steps"]) == 1

    @pytest.mark.asyncio
    async def test_friends_narrative(self) -> None:
        pois = [_make_poi("桌游吧", excitement=0.7), _make_poi("烧烤店", category="美食")]
        route_result = _make_route_result([{"poi": p} for p in pois])
        intent = _make_user_intent("朋友")
        result = await generate_narrative(route_result, intent, enable_llm_polish=False)
        assert result["opening"] in OPENING_TEMPLATES["朋友"]
        assert len(result["steps"]) == 2

    @pytest.mark.asyncio
    async def test_retired_narrative(self) -> None:
        poi = _make_poi("公园晨练", tranquility=0.9, physical_demand=0.3)
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent("退休")
        result = await generate_narrative(route_result, intent, enable_llm_polish=False)
        assert result["opening"] in OPENING_TEMPLATES["退休"]

    @pytest.mark.asyncio
    async def test_empty_route(self) -> None:
        result = await generate_narrative({"route": []}, _make_user_intent())
        assert isinstance(result["opening"], str)
        assert result["steps"] == []
        assert result["emotion_highlights"] == []

    @pytest.mark.asyncio
    async def test_full_route_with_highlights(self) -> None:
        steps_data = [
            {"poi": _make_poi("博物馆", culture_depth=0.9, excitement=0.2, tranquility=0.3)},
            {"poi": _make_poi("过山车", excitement=0.95, tranquility=0.05)},
            {"poi": _make_poi("湖边", tranquility=0.88, excitement=0.1)},
        ]
        route_result = _make_route_result(steps_data)
        intent = _make_user_intent("朋友")
        result = await generate_narrative(route_result, intent, enable_llm_polish=False)
        assert len(result["steps"]) == 3
        assert len(result["emotion_highlights"]) >= 2

    @pytest.mark.asyncio
    async def test_output_structure(self) -> None:
        poi = _make_poi("测试点")
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent()
        result = await generate_narrative(route_result, intent, enable_llm_polish=False)
        assert "opening" in result
        assert "steps" in result
        assert "closing" in result
        assert "emotion_highlights" in result
        assert isinstance(result["steps"], list)


class TestLLMDescription:
    """测试 LLM 生成描述功能。"""

    @pytest.mark.asyncio
    async def test_llm_generate_timeout_falls_back(self) -> None:
        """LLM 超时应退回模板。"""
        from backend.services.narrator import _llm_generate_description

        with patch("backend.services.llm_service.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = TimeoutError()
            poi = _make_poi("测试点")
            step = {"poi": poi, "arrival_time": "10:00"}
            result = await _llm_generate_description(step, _make_user_intent(), "珠海")
            assert "测试点" in result

    @pytest.mark.asyncio
    async def test_llm_generate_exception_falls_back(self) -> None:
        """LLM 异常应退回模板。"""
        from backend.services.narrator import _llm_generate_description

        with patch("backend.services.llm_service.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = RuntimeError("API error")
            poi = _make_poi("测试点")
            step = {"poi": poi}
            result = await _llm_generate_description(step, _make_user_intent(), "珠海")
            assert "测试点" in result

    @pytest.mark.asyncio
    async def test_llm_generate_success(self) -> None:
        """LLM 成功时返回生成的描述。"""
        from backend.services.narrator import _llm_generate_description

        with patch("backend.services.llm_service.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "清晨的阳光洒在测试点上，这里的文化氛围让人流连忘返。"
            poi = _make_poi("测试点")
            step = {"poi": poi}
            result = await _llm_generate_description(step, _make_user_intent(), "珠海")
            assert "清晨的阳光洒在测试点上" in result

    @pytest.mark.asyncio
    async def test_llm_generate_empty_falls_back(self) -> None:
        """LLM 返回空字符串时应退回模板。"""
        from backend.services.narrator import _llm_generate_description

        with patch("backend.services.llm_service.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = ""
            poi = _make_poi("测试点")
            step = {"poi": poi}
            result = await _llm_generate_description(step, _make_user_intent(), "珠海")
            assert "测试点" in result

    @pytest.mark.asyncio
    async def test_narrative_with_llm_enabled(self) -> None:
        """启用 LLM 时应调用 chat。"""
        poi = _make_poi("测试景点")
        route_result = _make_route_result([{"poi": poi}])
        intent = _make_user_intent()

        with patch("backend.services.llm_service.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "这是一个详细的测试景点描述，值得慢慢体验。"
            result = await generate_narrative(route_result, intent, enable_llm_polish=True)
            assert mock_chat.called
            assert "这是一个详细的测试景点描述" in result["steps"][0]["description"]
