"""CityFlow filters 模块测试。

使用10个模拟POI验证各种边界情况。
"""

from __future__ import annotations

import pytest

from backend.services.filters import (emotion_compatibility,
                                      emotion_compatibility_with_consecutive,
                                      fatigue_penalty, filter_candidates)

# ---------------------------------------------------------------------------
# Fixtures: 10 个模拟 POI
# ---------------------------------------------------------------------------


@pytest.fixture()
def pois() -> list[dict]:
    """10个模拟POI，覆盖各种场景。"""
    return [
        # 0: 正常POI - 文化类，所有条件都满足
        {
            "id": "poi_00001",
            "name": "珠海渔女",
            "category": "文化",
            "rating": 3.9,
            "avg_price": 27,
            "lat": 22.265,
            "lng": 113.583,
            "business_hours": "09:00-17:00",
            "tags": ["免费", "值得去"],
            "queue_prone": False,
            "avg_stay_min": 75,
            "emotion_tags": {
                "excitement": 0.3,
                "tranquility": 0.8,
                "sociability": 0.2,
                "culture_depth": 0.9,
                "surprise": 0.1,
                "physical_demand": 0.2,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 5,
                "opening_hours": "09:00-17:00",
                "has_restroom": True,
            },
        },
        # 1: 时间窗不匹配 - 下午才开门
        {
            "id": "poi_00002",
            "name": "晚开博物馆",
            "category": "文化",
            "rating": 4.5,
            "avg_price": 50,
            "lat": 22.270,
            "lng": 113.590,
            "business_hours": "14:00-21:00",
            "tags": ["博物馆"],
            "queue_prone": False,
            "avg_stay_min": 90,
            "emotion_tags": {
                "excitement": 0.2,
                "tranquility": 0.9,
                "sociability": 0.1,
                "culture_depth": 0.95,
                "surprise": 0.2,
                "physical_demand": 0.1,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 10,
                "opening_hours": "14:00-21:00",
                "has_restroom": True,
            },
        },
        # 2: 排队时间超标
        {
            "id": "poi_00003",
            "name": "热门主题乐园",
            "category": "娱乐",
            "rating": 4.8,
            "avg_price": 80,
            "lat": 22.280,
            "lng": 113.600,
            "business_hours": "09:00-22:00",
            "tags": ["刺激", "排队"],
            "queue_prone": True,
            "avg_stay_min": 180,
            "emotion_tags": {
                "excitement": 0.95,
                "tranquility": 0.0,
                "sociability": 0.7,
                "culture_depth": 0.1,
                "surprise": 0.9,
                "physical_demand": 0.8,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 45,
                "opening_hours": "09:00-22:00",
                "has_restroom": True,
            },
        },
        # 3: 不支持无障碍
        {
            "id": "poi_00004",
            "name": "山间步道",
            "category": "自然",
            "rating": 4.6,
            "avg_price": 0,
            "lat": 22.290,
            "lng": 113.570,
            "business_hours": "06:00-18:00",
            "tags": ["登山", "免费"],
            "queue_prone": False,
            "avg_stay_min": 120,
            "emotion_tags": {
                "excitement": 0.5,
                "tranquility": 0.7,
                "sociability": 0.1,
                "culture_depth": 0.0,
                "surprise": 0.3,
                "physical_demand": 0.9,
            },
            "constraints": {
                "accessible": False,
                "pet_friendly": True,
                "queue_time_min": 0,
                "opening_hours": "06:00-18:00",
                "has_restroom": False,
            },
        },
        # 4: 不支持宠物
        {
            "id": "poi_00005",
            "name": "高端西餐厅",
            "category": "美食",
            "rating": 4.7,
            "avg_price": 150,
            "lat": 22.260,
            "lng": 113.585,
            "business_hours": "11:00-22:00",
            "tags": ["西餐", "约会"],
            "queue_prone": False,
            "avg_stay_min": 60,
            "emotion_tags": {
                "excitement": 0.4,
                "tranquility": 0.6,
                "sociability": 0.5,
                "culture_depth": 0.3,
                "surprise": 0.2,
                "physical_demand": 0.1,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 5,
                "opening_hours": "11:00-22:00",
                "has_restroom": True,
            },
        },
        # 5: 预算超标
        {
            "id": "poi_00006",
            "name": "豪华SPA会所",
            "category": "休闲",
            "rating": 4.9,
            "avg_price": 300,
            "lat": 22.255,
            "lng": 113.595,
            "business_hours": "10:00-23:00",
            "tags": ["SPA", "高端"],
            "queue_prone": False,
            "avg_stay_min": 120,
            "emotion_tags": {
                "excitement": 0.1,
                "tranquility": 0.95,
                "sociability": 0.1,
                "culture_depth": 0.0,
                "surprise": 0.0,
                "physical_demand": 0.1,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 0,
                "opening_hours": "10:00-23:00",
                "has_restroom": True,
            },
        },
        # 6: 高兴奋度POI（情绪兼容性测试）
        {
            "id": "poi_00007",
            "name": "过山车乐园",
            "category": "娱乐",
            "rating": 4.4,
            "avg_price": 60,
            "lat": 22.275,
            "lng": 113.610,
            "business_hours": "09:00-20:00",
            "tags": ["刺激"],
            "queue_prone": True,
            "avg_stay_min": 90,
            "emotion_tags": {
                "excitement": 0.9,
                "tranquility": 0.0,
                "sociability": 0.6,
                "culture_depth": 0.0,
                "surprise": 0.8,
                "physical_demand": 0.7,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 8,
                "opening_hours": "09:00-20:00",
                "has_restroom": True,
            },
        },
        # 7: 高文化+宁静POI（情绪兼容性测试）
        {
            "id": "poi_00008",
            "name": "古琴艺术馆",
            "category": "文化",
            "rating": 4.3,
            "avg_price": 30,
            "lat": 22.262,
            "lng": 113.580,
            "business_hours": "09:00-17:00",
            "tags": ["文化", "安静"],
            "queue_prone": False,
            "avg_stay_min": 45,
            "emotion_tags": {
                "excitement": 0.1,
                "tranquility": 0.9,
                "sociability": 0.1,
                "culture_depth": 0.95,
                "surprise": 0.1,
                "physical_demand": 0.1,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 0,
                "opening_hours": "09:00-17:00",
                "has_restroom": True,
            },
        },
        # 8: 宠物友好 + 无障碍
        {
            "id": "poi_00009",
            "name": "海滨公园",
            "category": "自然",
            "rating": 4.2,
            "avg_price": 0,
            "lat": 22.268,
            "lng": 113.575,
            "business_hours": "00:00-23:59",
            "tags": ["公园", "遛狗"],
            "queue_prone": False,
            "avg_stay_min": 60,
            "emotion_tags": {
                "excitement": 0.2,
                "tranquility": 0.7,
                "sociability": 0.4,
                "culture_depth": 0.0,
                "surprise": 0.1,
                "physical_demand": 0.3,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": True,
                "queue_time_min": 0,
                "opening_hours": "00:00-23:59",
                "has_restroom": True,
            },
        },
        # 9: 高体力消耗POI（疲劳测试）
        {
            "id": "poi_00010",
            "name": "海岛徒步",
            "category": "自然",
            "rating": 4.6,
            "avg_price": 20,
            "lat": 22.300,
            "lng": 113.550,
            "business_hours": "07:00-16:00",
            "tags": ["徒步", "户外"],
            "queue_prone": False,
            "avg_stay_min": 240,
            "emotion_tags": {
                "excitement": 0.6,
                "tranquility": 0.5,
                "sociability": 0.2,
                "culture_depth": 0.0,
                "surprise": 0.4,
                "physical_demand": 0.95,
            },
            "constraints": {
                "accessible": False,
                "pet_friendly": True,
                "queue_time_min": 0,
                "opening_hours": "07:00-16:00",
                "has_restroom": False,
            },
        },
    ]


@pytest.fixture()
def base_intent() -> dict:
    """基础用户意图，适用于大部分正常场景。"""
    return {
        "time": {"period": "上午", "start": "09:00", "end": "12:00"},
        "budget": {"per_person": 100, "type": "硬约束"},
        "group": {"size": 2, "type": "情侣"},
        "preferences": {"culture": 0.8, "food": 0.5, "nature": 0.3, "social": 0.2},
        "pace": "平衡型",
        "hard_constraints": ["排队容忍度<10min"],
    }


# ---------------------------------------------------------------------------
# filter_candidates 测试
# ---------------------------------------------------------------------------


class TestFilterCandidates:
    """filter_candidates 函数测试。"""

    def test_normal_filter(self, pois: list[dict], base_intent: dict) -> None:
        """正常过滤：只保留满足所有条件的POI。"""
        result = filter_candidates(pois, base_intent)
        result_ids = {p["id"] for p in result}
        # poi_00001(珠海渔女), poi_00007(过山车), poi_00008(古琴), poi_00009(海滨公园) 应通过
        assert "poi_00001" in result_ids  # 全部满足
        assert "poi_00008" in result_ids  # 排队0, 价格30, 时间匹配
        assert "poi_00009" in result_ids  # 全天开放, 无障碍, 排队0

    def test_time_window_rejected(self, pois: list[dict], base_intent: dict) -> None:
        """时间窗不匹配：poi_00002 下午才开门，上午时段应被过滤。"""
        result = filter_candidates(pois, base_intent)
        result_ids = {p["id"] for p in result}
        assert "poi_00002" not in result_ids

    def test_queue_tolerance_rejected(
        self, pois: list[dict], base_intent: dict
    ) -> None:
        """排队超限：poi_00003 排队45min，容忍度<10min应被过滤。"""
        result = filter_candidates(pois, base_intent)
        result_ids = {p["id"] for p in result}
        assert "poi_00003" not in result_ids

    def test_accessibility_filter(self, pois: list[dict]) -> None:
        """无障碍需求：需要无障碍时，poi_00003/00004/00010应被过滤。"""
        intent = {
            "time": {"period": "上午", "start": "09:00", "end": "12:00"},
            "budget": {"per_person": 100, "type": "硬约束"},
            "group": {"size": 2, "type": "情侣"},
            "preferences": {},
            "pace": "平衡型",
            "hard_constraints": ["无障碍通行"],
        }
        result = filter_candidates(pois, intent)
        result_ids = {p["id"] for p in result}
        # poi_00004 和 poi_00010 的 accessible=False
        assert "poi_00004" not in result_ids
        assert "poi_00010" not in result_ids
        # poi_00001 accessible=True 应保留
        assert "poi_00001" in result_ids

    def test_pet_friendly_filter(self, pois: list[dict]) -> None:
        """宠物友好需求：需要宠物友好时，poi_00004和poi_00009/00010应保留。"""
        intent = {
            "time": {"period": "上午", "start": "09:00", "end": "12:00"},
            "budget": {"per_person": 100, "type": "硬约束"},
            "group": {"size": 2, "type": "情侣"},
            "preferences": {},
            "pace": "平衡型",
            "hard_constraints": ["宠物友好"],
        }
        result = filter_candidates(pois, intent)
        result_ids = {p["id"] for p in result}
        # poi_00009 和 poi_00010 是 pet_friendly=True
        assert "poi_00009" in result_ids
        assert "poi_00010" in result_ids
        # poi_00001 pet_friendly=False
        assert "poi_00001" not in result_ids

    def test_budget_filter(self, pois: list[dict], base_intent: dict) -> None:
        """预算超限：poi_00006(300元) > 100*1.2=120应被过滤。"""
        result = filter_candidates(pois, base_intent)
        result_ids = {p["id"] for p in result}
        assert "poi_00006" not in result_ids

    def test_combined_hard_constraints(self, pois: list[dict]) -> None:
        """同时有多个硬约束：无障碍+排队容忍度<10min。"""
        intent = {
            "time": {"period": "上午", "start": "09:00", "end": "12:00"},
            "budget": {"per_person": 100, "type": "硬约束"},
            "group": {"size": 2, "type": "情侣"},
            "preferences": {},
            "pace": "平衡型",
            "hard_constraints": ["排队容忍度<10min", "无障碍通行"],
        }
        result = filter_candidates(pois, intent)
        result_ids = {p["id"] for p in result}
        # poi_00001: accessible=True, queue=5, price=27, time ok
        assert "poi_00001" in result_ids
        # poi_00004: accessible=False → 过滤
        assert "poi_00004" not in result_ids
        # poi_00003: queue=45 → 过滤
        assert "poi_00003" not in result_ids

    def test_edge_budget_exact_limit(self, pois: list[dict]) -> None:
        """预算边界：avg_price正好等于per_person*1.2时应通过。"""
        intent = {
            "time": {"period": "上午", "start": "09:00", "end": "12:00"},
            "budget": {"per_person": 25, "type": "硬约束"},  # 25*1.2=30
            "group": {"size": 1, "type": "独行"},
            "preferences": {},
            "pace": "平衡型",
            "hard_constraints": [],
        }
        result = filter_candidates(pois, intent)
        result_ids = {p["id"] for p in result}
        # poi_00008 avg_price=30 == 25*1.2=30 → 应通过
        assert "poi_00008" in result_ids

    def test_empty_pois(self, base_intent: dict) -> None:
        """空POI列表应返回空结果。"""
        result = filter_candidates([], base_intent)
        assert result == []


# ---------------------------------------------------------------------------
# emotion_compatibility 测试
# ---------------------------------------------------------------------------


class TestEmotionCompatibility:
    """emotion_compatibility 函数测试。"""

    def test_excitement_overload(self, pois: list[dict]) -> None:
        """两个高兴奋度POI → -0.5过载惩罚。"""
        # poi_00003 excitement=0.95, poi_00007 excitement=0.9
        score = emotion_compatibility(pois[2], pois[6])
        assert score == -0.5

    def test_same_category_penalty(self, pois: list[dict]) -> None:
        """同category → -0.3连续同类惩罚。"""
        # poi_00001(文化) 和 poi_00008(文化)
        score = emotion_compatibility(pois[0], pois[7])
        assert score == -0.3

    def test_culture_to_tranquility_enhanced(self, pois: list[dict]) -> None:
        """文化>=0.7 → 宁静>=0.7 → +0.4增强型。"""
        # poi_00001(文化, culture_depth=0.9) → poi_00009(自然, tranquility=0.7)
        # 不同category，不会触发同类惩罚
        score = emotion_compatibility(pois[0], pois[8])
        assert score == 0.4

    def test_excitement_to_tranquility_contrast(self, pois: list[dict]) -> None:
        """兴奋>=0.7 → 宁静>=0.7 → +0.3反差型。"""
        # poi_00007(excitement=0.9) → poi_00008(tranquility=0.9)
        score = emotion_compatibility(pois[6], pois[7])
        assert score == 0.3

    def test_neutral_pair(self, pois: list[dict]) -> None:
        """不满足任何特殊规则 → 0.0。"""
        # poi_00008(文化) → poi_00009(自然)，不同类，文化→自然但tranquility=0.7
        # culture_depth of poi_00008 = 0.95 >= 0.7, tranquility of poi_00009 = 0.7 >= 0.7
        # 所以实际是 +0.4 增强型。换一对测试。
        # poi_00005(美食, excitement=0.4) → poi_00009(自然, tranquility=0.7)
        # excitement < 0.7, culture_depth=0.3 < 0.7 → 0.0
        score = emotion_compatibility(pois[4], pois[8])
        assert score == 0.0

    def test_boundary_excitement_exactly_08(self, pois: list[dict]) -> None:
        """兴奋度刚好0.8（不>0.8）时不触发过载惩罚。"""
        a = {**pois[0], "emotion_tags": {**pois[0]["emotion_tags"], "excitement": 0.8}}
        b = {**pois[6], "emotion_tags": {**pois[6]["emotion_tags"], "excitement": 0.8}}
        score = emotion_compatibility(a, b)
        # 0.8 不 > 0.8，但同category? a是文化b是娱乐，不同类
        # 且excitement_a=0.8 >= 0.7, tranquility_b=0.0 < 0.7 → 0.0
        assert score == 0.0

    def test_consecutive_triple_penalty(self, pois: list[dict]) -> None:
        """3个连续同类POI → 第3个惩罚应为-0.6。"""
        # 构造3个文化类POI
        p1 = {**pois[0], "category": "文化"}
        p2 = {**pois[7], "category": "文化"}
        p3 = {**pois[0], "id": "poi_x", "category": "文化"}
        score = emotion_compatibility_with_consecutive([p1, p2, p3])
        # p1→p2: 同类 -0.3, p2→p3: 连续第3个 -0.6
        assert score == pytest.approx(-0.9)


# ---------------------------------------------------------------------------
# fatigue_penalty 测试
# ---------------------------------------------------------------------------


class TestFatiguePenalty:
    """fatigue_penalty 函数测试。"""

    def test_low_steps(self) -> None:
        """步数<5000，无惩罚。"""
        assert fatigue_penalty(3000, 1) == 0.0

    def test_medium_steps(self) -> None:
        """步数5000-10000，轻微惩罚。"""
        penalty = fatigue_penalty(8000, 1)
        assert penalty == pytest.approx(-0.2)

    def test_high_steps(self) -> None:
        """步数10000-15000，中度惩罚。"""
        penalty = fatigue_penalty(12000, 1)
        assert penalty == pytest.approx(-0.5)

    def test_extreme_steps_force_rest(self) -> None:
        """步数>15000，强制休息返回-999。"""
        assert fatigue_penalty(16000, 1) == -999

    def test_consecutive_mental_fatigue(self) -> None:
        """连续3个POI，额外-0.2心理疲劳。"""
        penalty = fatigue_penalty(3000, 3)
        assert penalty == pytest.approx(-0.2)

    def test_combined_fatigue(self) -> None:
        """步数12000 + 连续3个POI → -0.5 + -0.2 = -0.7。"""
        penalty = fatigue_penalty(12000, 3)
        assert penalty == pytest.approx(-0.7)

    def test_boundary_5000_steps(self) -> None:
        """步数刚好5000，进入中等疲劳区间。"""
        penalty = fatigue_penalty(5000, 1)
        assert penalty == pytest.approx(-0.2)

    def test_boundary_10000_steps(self) -> None:
        """步数刚好10000，进入高疲劳区间。"""
        penalty = fatigue_penalty(10000, 1)
        assert penalty == pytest.approx(-0.5)

    def test_boundary_15000_steps(self) -> None:
        """步数刚好15000，仍在高疲劳区间（不是强制休息）。"""
        penalty = fatigue_penalty(15000, 1)
        assert penalty == pytest.approx(-0.5)

    def test_boundary_15001_steps_force_rest(self) -> None:
        """步数15001，强制休息。"""
        assert fatigue_penalty(15001, 1) == -999
