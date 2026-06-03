"""内容引擎测试。

测试场景：
- 城市性格查询
- 非标体验获取
- 开场白城市个性化
- 文案风格注入
- 非标体验时间/季节筛选
"""

from __future__ import annotations

import pytest

from backend.services.city_personality import (
    get_cities,
    get_city_based_opening,
    get_city_personality,
    get_nonstandard_experiences,
    get_nse_for_route,
    get_vibe_style_adjectives,
)


class TestCityPersonality:
    """城市性格查询。"""

    def test_get_city_personality_zhuhai(self) -> None:
        p = get_city_personality("珠海")
        assert p is not None
        assert p["personality"] == "慢生活·海滨城市"
        assert p["vibe"] == "relaxed"

    def test_get_city_personality_guangzhou(self) -> None:
        p = get_city_personality("广州")
        assert p is not None
        assert "食" in p["personality"]

    def test_get_city_personality_shenzhen(self) -> None:
        p = get_city_personality("深圳")
        assert p is not None
        assert p["vibe"] == "energetic"

    def test_get_city_personality_zhanjiang(self) -> None:
        p = get_city_personality("湛江")
        assert p is not None
        assert p["vibe"] == "rustic"

    def test_get_city_personality_unknown(self) -> None:
        assert get_city_personality("东京") is None

    def test_get_cities(self) -> None:
        cities = get_cities()
        assert "珠海" in cities
        assert "广州" in cities
        assert len(cities) >= 4


class TestVibeStyleAdjectives:
    """城市 vibe → 风格形容词。"""

    def test_relaxed(self) -> None:
        adj = get_vibe_style_adjectives("relaxed")
        assert "悠闲" in adj

    def test_lively(self) -> None:
        adj = get_vibe_style_adjectives("lively")
        assert "热闹" in adj

    def test_rustic(self) -> None:
        adj = get_vibe_style_adjectives("rustic")
        assert "质朴" in adj

    def test_energetic(self) -> None:
        adj = get_vibe_style_adjectives("energetic")
        assert "炫酷" in adj

    def test_unknown_vibe(self) -> None:
        adj = get_vibe_style_adjectives("nonexistent")
        assert isinstance(adj, list)
        assert len(adj) > 0  # 返回默认风格


class TestCityOpening:
    """城市开场白。"""

    def test_opening_relaxed(self) -> None:
        opening = get_city_based_opening("珠海")
        assert "珠海" in opening
        assert "放松" in opening or "悠闲" in opening

    def test_opening_lively(self) -> None:
        opening = get_city_based_opening("广州")
        assert "广州" in opening

    def test_opening_energetic(self) -> None:
        opening = get_city_based_opening("深圳")
        assert "深圳" in opening

    def test_opening_unknown_city(self) -> None:
        opening = get_city_based_opening("北京")
        assert "北京" in opening  # 降级模板


class TestNonStandardExperiences:
    """非标体验。"""

    def test_get_all(self) -> None:
        nses = get_nonstandard_experiences()
        assert len(nses) >= 8

    def test_filter_by_city(self) -> None:
        guangzhou = get_nonstandard_experiences(city="广州")
        assert len(guangzhou) >= 3
        for nse in guangzhou:
            assert nse["city"] == "广州"

    def test_filter_by_category(self) -> None:
        culture = get_nonstandard_experiences(category="文化")
        for nse in culture:
            assert nse["category"] == "文化"

    def test_filter_by_city_and_category(self) -> None:
        result = get_nonstandard_experiences(city="珠海", category="运动")
        assert len(result) >= 1
        assert result[0]["city"] == "珠海"
        assert result[0]["category"] == "运动"

    def test_get_nse_for_route_time_match(self) -> None:
        """时间匹配的非标体验优先。"""
        result = get_nse_for_route(city="广州", hour_of_day=6, season="spring")
        assert len(result) > 0
        # 清晨菜市场应在推荐中（best_time=06:00-08:00）
        assert any("菜市场" in nse["name"] for nse in result)

    def test_get_nse_for_route_limit(self) -> None:
        result = get_nse_for_route(city="广州", hour_of_day=10, season="spring", limit=2)
        assert len(result) <= 2

    def test_nse_has_all_fields(self) -> None:
        nses = get_nonstandard_experiences()
        for nse in nses:
            assert "id" in nse
            assert "name" in nse
            assert "city" in nse
            assert "emotion_tags" in nse
            assert "experience_value" in nse


class TestNarratorIntegration:
    """narrator 集成测试（验证城市性格影响文案）。"""

    def test_narrator_imports_city_personality(self) -> None:
        """验证 narrator 模块可导入且不报错。"""
        from backend.services.narrator import generate_narrative

        assert generate_narrative is not None

    @pytest.mark.asyncio
    async def test_generate_narrative_with_city(self) -> None:
        """验证生成文案时传入 city 参数不报错。"""
        from backend.services.narrator import generate_narrative

        route = {
            "route": [
                {
                    "poi": {
                        "id": "p1",
                        "name": "景点A",
                        "city": "珠海",
                        "category": "文化",
                        "rating": 4.5,
                        "avg_price": 30,
                        "emotion_tags": {"excitement": 0.3, "tranquility": 0.7},
                    },
                    "arrival_time": "09:00",
                    "departure_time": "10:00",
                    "travel_from_prev": {"distance_m": 0, "time_min": 0},
                },
            ],
            "emotion_curve": [],
        }
        intent = {"group": {"type": "独居"}}

        narrative = await generate_narrative(route, intent, city="珠海")
        assert "opening" in narrative
        assert "steps" in narrative
        assert len(narrative["steps"]) == 1
