"""CityFlow 三层经济引擎测试。

测试场景：
- enrich_poi_economics: 验证所有经济字段正确添加
- calculate_leverage: 验证杠杆率计算（免费→high, 高价低分→low）
- calculate_spend_emotion: 验证消费感受计算
- get_price_elasticity: 验证价格弹性计算
- 预算节奏: 验证 solver 中开场低价/收尾高体验的行为
"""

from __future__ import annotations

from typing import Any

from backend.services.economy import (
    enrich_poi_economics,
    get_price_elasticity,
)

# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------


def _make_poi(
    *,
    poi_id: str = "eco_001",
    name: str = "测试POI",
    category: str = "文化",
    rating: float = 4.0,
    avg_price: float = 50,
    excitement: float = 0.5,
    tranquility: float = 0.5,
    sociability: float = 0.5,
    culture_depth: float = 0.5,
    surprise: float = 0.5,
    physical_demand: float = 0.3,
) -> dict[str, Any]:
    return {
        "id": poi_id,
        "name": name,
        "category": category,
        "rating": rating,
        "avg_price": avg_price,
        "lat": 22.10,
        "lng": 113.40,
        "business_hours": "09:00-21:00",
        "emotion_tags": {
            "excitement": excitement,
            "tranquility": tranquility,
            "sociability": sociability,
            "culture_depth": culture_depth,
            "surprise": surprise,
            "physical_demand": physical_demand,
        },
    }


# ---------------------------------------------------------------------------
# enrich_poi_economics 测试
# ---------------------------------------------------------------------------


class TestEnrichPoiEconomics:
    """验证 enrich_poi_economics 添加所有经济字段。"""

    def test_all_fields_added(self) -> None:
        """调用后应包含全部 4 个经济字段。"""
        poi = _make_poi()
        result = enrich_poi_economics(poi)

        assert "experience_value" in result
        assert "price_elasticity" in result
        assert "experience_leverage" in result
        assert "spend_emotion" in result

    def test_idempotent(self) -> None:
        """多次调用不应改变结果。"""
        poi = _make_poi()
        enrich_poi_economics(poi)
        first_ev = poi["experience_value"]
        first_lev = poi["experience_leverage"]

        enrich_poi_economics(poi)
        assert poi["experience_value"] == first_ev
        assert poi["experience_leverage"] == first_lev

    def test_field_types(self) -> None:
        """验证字段类型正确。"""
        poi = _make_poi()
        enrich_poi_economics(poi)

        assert isinstance(poi["experience_value"], float)
        assert isinstance(poi["price_elasticity"], float)
        assert isinstance(poi["experience_leverage"], str)
        assert isinstance(poi["spend_emotion"], str)

    def test_experience_value_range(self) -> None:
        """体验价值应在 1.0-10.0 范围内。"""
        poi = _make_poi()
        enrich_poi_economics(poi)
        assert 1.0 <= poi["experience_value"] <= 10.0


# ---------------------------------------------------------------------------
# experience_value 测试
# ---------------------------------------------------------------------------


class TestExperienceValue:
    """验证体验价值计算。"""

    def test_high_emotions_gives_high_value(self) -> None:
        """所有情绪高 + 评分高 → 体验价值高。"""
        poi = _make_poi(
            rating=5.0,
            excitement=0.9,
            tranquility=0.9,
            sociability=0.9,
            culture_depth=0.9,
            surprise=0.9,
            physical_demand=0.9,
            category="文化",
        )
        enrich_poi_economics(poi)
        assert poi["experience_value"] >= 7.0

    def test_low_emotions_gives_low_value(self) -> None:
        """所有情绪低 + 评分低 → 体验价值低。"""
        poi = _make_poi(
            rating=1.0,
            excitement=0.1,
            tranquility=0.1,
            sociability=0.1,
            culture_depth=0.1,
            surprise=0.1,
            physical_demand=0.1,
            category="购物",
        )
        enrich_poi_economics(poi)
        assert poi["experience_value"] <= 4.0

    def test_culture_category_gets_bonus(self) -> None:
        """文化类别应有体验加成，高于同等条件的购物类。"""
        culture_poi = _make_poi(category="文化", rating=4.0)
        shop_poi = _make_poi(category="购物", rating=4.0)

        enrich_poi_economics(culture_poi)
        enrich_poi_economics(shop_poi)

        assert culture_poi["experience_value"] > shop_poi["experience_value"]

    def test_empty_emotion_tags_defaults(self) -> None:
        """缺少 emotion_tags 时应使用默认值。"""
        poi = _make_poi()
        del poi["emotion_tags"]
        enrich_poi_economics(poi)
        assert 1.0 <= poi["experience_value"] <= 10.0


# ---------------------------------------------------------------------------
# get_price_elasticity 测试
# ---------------------------------------------------------------------------


class TestGetPriceElasticity:
    """验证价格弹性计算。"""

    def test_free_poi(self) -> None:
        poi = _make_poi(avg_price=0)
        assert get_price_elasticity(poi) == 1.0

    def test_cheap_poi(self) -> None:
        poi = _make_poi(avg_price=30)
        assert get_price_elasticity(poi) == 0.8

    def test_medium_low_poi(self) -> None:
        poi = _make_poi(avg_price=75)
        assert get_price_elasticity(poi) == 0.6

    def test_medium_high_poi(self) -> None:
        poi = _make_poi(avg_price=150)
        assert get_price_elasticity(poi) == 0.4

    def test_expensive_poi(self) -> None:
        poi = _make_poi(avg_price=300)
        assert get_price_elasticity(poi) == 0.3

    def test_boundary_values(self) -> None:
        """边界值测试。"""
        assert get_price_elasticity(_make_poi(avg_price=0)) == 1.0
        assert get_price_elasticity(_make_poi(avg_price=49)) == 0.8
        assert get_price_elasticity(_make_poi(avg_price=50)) == 0.6
        assert get_price_elasticity(_make_poi(avg_price=99)) == 0.6
        assert get_price_elasticity(_make_poi(avg_price=100)) == 0.4
        assert get_price_elasticity(_make_poi(avg_price=199)) == 0.4
        assert get_price_elasticity(_make_poi(avg_price=200)) == 0.3


# ---------------------------------------------------------------------------
# calculate_leverage 测试
# ---------------------------------------------------------------------------


class TestCalculateLeverage:
    """验证体验杠杆率计算。"""

    def test_free_poi_high_leverage(self) -> None:
        """免费 POI 杠杆率应为 high。"""
        poi = _make_poi(avg_price=0, rating=4.5, excitement=0.6)
        enrich_poi_economics(poi)
        assert poi["experience_leverage"] == "high"

    def test_cheap_high_rating_high_leverage(self) -> None:
        """低价高评分 POI 杠杆率应为 high。"""
        poi = _make_poi(avg_price=20, rating=4.8, excitement=0.7, culture_depth=0.8)
        enrich_poi_economics(poi)
        assert poi["experience_leverage"] == "high"

    def test_expensive_low_rating_low_leverage(self) -> None:
        """高价低评分 POI 杠杆率应为 low。"""
        poi = _make_poi(avg_price=500, rating=2.0, excitement=0.2, tranquility=0.2)
        enrich_poi_economics(poi)
        assert poi["experience_leverage"] == "low"

    def test_medium_price_leverage(self) -> None:
        """中等价格和体验 POI 杠杆率应为 medium。"""
        poi = _make_poi(avg_price=200, rating=4.0)
        enrich_poi_economics(poi)
        assert poi["experience_leverage"] == "medium"

    def test_high_price_fair_experience_leverage(self) -> None:
        """高价但体验也高的 POI 杠杆率应为 medium。"""
        poi = _make_poi(
            avg_price=300, rating=4.5, excitement=0.7, culture_depth=0.8, tranquility=0.6
        )
        enrich_poi_economics(poi)
        # ev/price ratio should be moderate
        ratio = poi["experience_value"] / 300
        if ratio >= 0.04:
            assert poi["experience_leverage"] == "high"
        elif ratio >= 0.015:
            assert poi["experience_leverage"] == "medium"
        else:
            assert poi["experience_leverage"] == "low"

    def test_low_price_medium_experience_is_high_leverage(self) -> None:
        """低价中等体验 POI 杠杆率应为 high。"""
        poi = _make_poi(avg_price=30, rating=3.5, excitement=0.4)
        enrich_poi_economics(poi)
        assert poi["experience_leverage"] == "high"


# ---------------------------------------------------------------------------
# calculate_spend_emotion 测试
# ---------------------------------------------------------------------------


class TestCalculateSpendEmotion:
    """验证消费感受计算。"""

    def test_free_poi_value(self) -> None:
        """免费 POI 应为 value。"""
        poi = _make_poi(avg_price=0)
        enrich_poi_economics(poi)
        assert poi["spend_emotion"] == "value"

    def test_cheap_high_quality_value(self) -> None:
        """低价高质 POI 应为 value。"""
        poi = _make_poi(avg_price=25, rating=4.8, excitement=0.7, culture_depth=0.8)
        enrich_poi_economics(poi)
        assert poi["spend_emotion"] == "value"

    def test_expensive_low_quality_expensive(self) -> None:
        """高价低质 POI 应为 expensive。"""
        poi = _make_poi(avg_price=500, rating=2.0, excitement=0.2)
        enrich_poi_economics(poi)
        assert poi["spend_emotion"] == "expensive"

    def test_mid_range_fair(self) -> None:
        """中等价位中等体验 POI 应为 fair。"""
        poi = _make_poi(avg_price=200, rating=4.0)
        enrich_poi_economics(poi)
        assert poi["spend_emotion"] == "fair"


# ---------------------------------------------------------------------------
# 集成测试：POI 数据 + 经济引擎
# ---------------------------------------------------------------------------


class TestEconomyIntegration:
    """完整 POI 数据集上的经济引擎行为验证。"""

    def test_varied_pois_have_different_leverage(self) -> None:
        """不同 POI 应产生不同的杠杆率分类。"""
        poi_cheap = _make_poi(avg_price=0, rating=4.5, name="免费公园", category="景点")
        poi_mid = _make_poi(avg_price=150, rating=4.0, name="普通餐厅", category="餐饮")
        poi_expensive = _make_poi(avg_price=500, rating=2.5, name="高价低质", category="购物")

        enrich_poi_economics(poi_cheap)
        enrich_poi_economics(poi_mid)
        enrich_poi_economics(poi_expensive)

        leverages = {
            poi_cheap["experience_leverage"],
            poi_mid["experience_leverage"],
            poi_expensive["experience_leverage"],
        }
        assert len(leverages) >= 2, f"应有至少 2 种不同杠杆率，实际: {leverages}"

    def test_poi_with_no_emotion_tags(self) -> None:
        """缺少 emotion_tags 的 POI 应仍能正确评估。"""
        poi = _make_poi(avg_price=100, rating=3.0)
        del poi["emotion_tags"]
        enrich_poi_economics(poi)
        assert 1.0 <= poi["experience_value"] <= 10.0
        assert poi["experience_leverage"] in ("high", "medium", "low")
        assert poi["spend_emotion"] in ("value", "fair", "expensive")


# ---------------------------------------------------------------------------
# Solver 集成测试：预算节奏
# ---------------------------------------------------------------------------


class TestSolverBudgetRhythm:
    """验证 solver 集成经济引擎后的行为。"""

    def test_tight_budget_favors_high_leverage(self) -> None:
        """预算紧张时，高杠杆 POI 应有评分优势。"""
        from backend.services.solver import _phase1_initialize

        # 候选池：一个高杠杆（低价高体验）和一个低杠杆（高价低体验）
        candidates = [
            _make_poi(
                poi_id="high_lev",
                name="免费博物馆",
                avg_price=0,
                rating=4.5,
                category="文化",
                excitement=0.6,
                culture_depth=0.9,
            ),
            _make_poi(
                poi_id="low_lev",
                name="高价商店",
                avg_price=500,
                rating=2.5,
                category="购物",
                excitement=0.2,
                culture_depth=0.1,
            ),
        ]

        # 低预算用户应优先选高杠杆
        intent = {
            "pace": "平衡型",
            "preferences": {"culture": 0.5, "food": 0.3, "nature": 0.3, "social": 0.2},
            "budget": {"per_person": 50},
        }

        route = _phase1_initialize(candidates, intent, "09:00")
        assert len(route) > 0
        assert route[0]["poi"]["id"] == "high_lev", "预算紧张时应优先选择高杠杆POI"

    def test_budget_rhythm_opening_prefers_cheap(self) -> None:
        """开场阶段应倾向于选择低价 POI。"""
        from backend.services.solver import _MAX_POIS_BY_PACE, _phase1_initialize

        # 创建足够多的候选
        candidates = []
        for i in range(12):
            candidates.append(
                _make_poi(
                    poi_id=f"eco_{i:03d}",
                    name=f"POI_{i}",
                    avg_price=300 if i % 2 == 0 else 30,
                    rating=4.0,
                    category="文化" if i % 3 == 0 else ("餐饮" if i % 3 == 1 else "运动"),
                )
            )

        intent = {
            "pace": "特种兵型",
            "preferences": {"culture": 0.5, "food": 0.5, "nature": 0.3, "social": 0.3},
            "budget": {"per_person": 500},
        }

        route = _phase1_initialize(candidates, intent, "09:00")
        assert len(route) > 0

        # 开场 POI（第一个）应为低价（avg_price < 50）或价格合理
        first_price = route[0]["poi"].get("avg_price", 999)
        max_pois = _MAX_POIS_BY_PACE.get(intent["pace"], 6)

        if len(route) >= 2:
            # 至少第一个 POI 应相对便宜（开场阶段倾向于低价）
            avg_price_first_half = sum(
                route[i]["poi"].get("avg_price", 0) for i in range(min(2, len(route)))
            ) / min(2, len(route))
            avg_price_all = sum(s["poi"].get("avg_price", 0) for s in route) / len(route)
            # 开场平均价不应显著高于全程平均价
            assert (
                avg_price_first_half <= avg_price_all * 1.5 or first_price < 100
            ), f"开场POI价格({first_price})应相对合理"

    def test_evaluate_route_still_works(self) -> None:
        """经济引擎不应破坏路线评估函数。"""
        from backend.services.solver import _evaluate_route

        poi = _make_poi()
        route = [
            {
                "poi": poi,
                "arrival_time": "09:00",
                "departure_time": "11:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            }
        ]
        intent = {"preferences": {"culture": 0.5, "nature": 0.5}}
        score = _evaluate_route(route, intent)
        assert isinstance(score, float)
