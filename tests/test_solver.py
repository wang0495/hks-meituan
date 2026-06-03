"""CityFlow solver 模块测试。

测试场景：
- P1 画像（社恐独居）：验证包含安静POI、无连续同类
- P2 画像（情侣）：验证包含可拍照POI、有互动体验环节
- P14 画像（三代同堂）：验证有无障碍POI、有休息节点
- 辅助函数：时间解析、地理计算、时间窗检查
"""

from __future__ import annotations

import pytest

from backend.services.filters import filter_candidates
from backend.services.geo import haversine
from backend.services.solver import (
    _check_time_windows,
    _evaluate_route,
    _phase1_initialize,
    _phase2_improve,
    _phase3_breathing,
    _phase4_finale,
    _recalculate_times,
    estimate_distance,
    estimate_steps,
    estimate_travel_time,
    solve_route,
)
from backend.services.time_utils import get_poi_opening_hours

# ---------------------------------------------------------------------------
# Fixtures: 多样化 POI 池
# 营业时间设置为宽范围，以便 filter_candidates 能保留足够候选
# ---------------------------------------------------------------------------


@pytest.fixture()
def poi_pool() -> list[dict]:
    """返回一个包含多种类型 POI 的候选池。"""
    return [
        # 0: 安静图书馆 - 文化/宁静
        {
            "id": "poi_001",
            "name": "安静图书馆",
            "category": "文化",
            "rating": 4.5,
            "avg_price": 0,
            "lat": 22.270,
            "lng": 113.580,
            "business_hours": "08:00-21:00",
            "tags": ["免费", "安静", "学习"],
            "queue_prone": False,
            "avg_stay_min": 120,
            "emotion_tags": {
                "excitement": 0.1,
                "tranquility": 0.95,
                "sociability": 0.1,
                "culture_depth": 0.9,
                "surprise": 0.05,
                "physical_demand": 0.1,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 0,
                "opening_hours": "08:00-21:00",
                "has_restroom": True,
            },
        },
        # 1: 刺激过山车 - 娱乐/高兴奋
        {
            "id": "poi_002",
            "name": "刺激过山车",
            "category": "娱乐",
            "rating": 4.8,
            "avg_price": 150,
            "lat": 22.280,
            "lng": 113.590,
            "business_hours": "08:00-22:00",
            "tags": ["刺激", "排队", "年轻人"],
            "queue_prone": True,
            "avg_stay_min": 30,
            "emotion_tags": {
                "excitement": 0.95,
                "tranquility": 0.05,
                "sociability": 0.6,
                "culture_depth": 0.1,
                "surprise": 0.8,
                "physical_demand": 0.7,
            },
            "constraints": {
                "accessible": False,
                "pet_friendly": False,
                "queue_time_min": 45,
                "opening_hours": "08:00-22:00",
                "has_restroom": True,
            },
        },
        # 2: 浪漫咖啡厅 - 美食/休息型
        {
            "id": "poi_003",
            "name": "浪漫咖啡厅",
            "category": "美食",
            "rating": 4.6,
            "avg_price": 68,
            "lat": 22.265,
            "lng": 113.575,
            "business_hours": "08:00-23:00",
            "tags": ["浪漫", "约会", "咖啡"],
            "queue_prone": False,
            "avg_stay_min": 90,
            "emotion_tags": {
                "excitement": 0.3,
                "tranquility": 0.7,
                "sociability": 0.5,
                "culture_depth": 0.4,
                "surprise": 0.2,
                "physical_demand": 0.1,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": True,
                "queue_time_min": 5,
                "opening_hours": "08:00-23:00",
                "has_restroom": True,
            },
        },
        # 3: 儿童乐园 - 娱乐/亲子
        {
            "id": "poi_004",
            "name": "儿童乐园",
            "category": "娱乐",
            "rating": 4.3,
            "avg_price": 88,
            "lat": 22.255,
            "lng": 113.565,
            "business_hours": "08:00-18:00",
            "tags": ["亲子", "儿童", "游乐"],
            "queue_prone": True,
            "avg_stay_min": 150,
            "emotion_tags": {
                "excitement": 0.7,
                "tranquility": 0.2,
                "sociability": 0.8,
                "culture_depth": 0.2,
                "surprise": 0.6,
                "physical_demand": 0.5,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 20,
                "opening_hours": "08:00-18:00",
                "has_restroom": True,
            },
        },
        # 4: 历史博物馆 - 文化/宁静
        {
            "id": "poi_005",
            "name": "历史博物馆",
            "category": "文化",
            "rating": 4.7,
            "avg_price": 30,
            "lat": 22.248,
            "lng": 113.558,
            "business_hours": "08:00-17:00",
            "tags": ["历史", "文化", "教育"],
            "queue_prone": False,
            "avg_stay_min": 120,
            "emotion_tags": {
                "excitement": 0.2,
                "tranquility": 0.8,
                "sociability": 0.3,
                "culture_depth": 0.95,
                "surprise": 0.3,
                "physical_demand": 0.2,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 10,
                "opening_hours": "08:00-17:00",
                "has_restroom": True,
            },
        },
        # 5: 海滨公园 - 公园/休息
        {
            "id": "poi_006",
            "name": "海滨公园",
            "category": "公园",
            "rating": 4.4,
            "avg_price": 0,
            "lat": 22.260,
            "lng": 113.570,
            "business_hours": "06:00-22:00",
            "tags": ["公园", "休息", "自然"],
            "queue_prone": False,
            "avg_stay_min": 60,
            "emotion_tags": {
                "excitement": 0.15,
                "tranquility": 0.85,
                "sociability": 0.3,
                "culture_depth": 0.0,
                "surprise": 0.1,
                "physical_demand": 0.2,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": True,
                "queue_time_min": 0,
                "opening_hours": "06:00-22:00",
                "has_restroom": True,
            },
        },
        # 6: 艺术画廊 - 文化/拍照
        {
            "id": "poi_007",
            "name": "艺术画廊",
            "category": "文化",
            "rating": 4.6,
            "avg_price": 50,
            "lat": 22.258,
            "lng": 113.585,
            "business_hours": "08:00-18:00",
            "tags": ["艺术", "文艺", "拍照"],
            "queue_prone": False,
            "avg_stay_min": 90,
            "emotion_tags": {
                "excitement": 0.3,
                "tranquility": 0.7,
                "sociability": 0.3,
                "culture_depth": 0.85,
                "surprise": 0.4,
                "physical_demand": 0.2,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 5,
                "opening_hours": "08:00-18:00",
                "has_restroom": True,
            },
        },
        # 7: 密室逃脱 - 娱乐/互动
        {
            "id": "poi_008",
            "name": "密室逃脱",
            "category": "娱乐",
            "rating": 4.5,
            "avg_price": 80,
            "lat": 22.272,
            "lng": 113.588,
            "business_hours": "08:00-23:00",
            "tags": ["互动", "解谜", "拍照"],
            "queue_prone": False,
            "avg_stay_min": 60,
            "emotion_tags": {
                "excitement": 0.85,
                "tranquility": 0.1,
                "sociability": 0.7,
                "culture_depth": 0.2,
                "surprise": 0.9,
                "physical_demand": 0.3,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 10,
                "opening_hours": "08:00-23:00",
                "has_restroom": True,
            },
        },
        # 8: 高端西餐厅 - 美食/约会
        {
            "id": "poi_009",
            "name": "高端西餐厅",
            "category": "美食",
            "rating": 4.7,
            "avg_price": 200,
            "lat": 22.263,
            "lng": 113.582,
            "business_hours": "08:00-22:00",
            "tags": ["西餐", "约会", "浪漫"],
            "queue_prone": False,
            "avg_stay_min": 90,
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
                "opening_hours": "08:00-22:00",
                "has_restroom": True,
            },
        },
        # 9: 登山步道 - 自然/高体力/无障碍不可
        {
            "id": "poi_010",
            "name": "登山步道",
            "category": "自然",
            "rating": 4.2,
            "avg_price": 0,
            "lat": 22.275,
            "lng": 113.560,
            "business_hours": "00:00-23:59",
            "tags": ["户外", "运动", "自然"],
            "queue_prone": False,
            "avg_stay_min": 180,
            "emotion_tags": {
                "excitement": 0.5,
                "tranquility": 0.6,
                "sociability": 0.3,
                "culture_depth": 0.1,
                "surprise": 0.3,
                "physical_demand": 0.9,
            },
            "constraints": {
                "accessible": False,
                "pet_friendly": True,
                "queue_time_min": 0,
                "opening_hours": "00:00-23:59",
                "has_restroom": False,
            },
        },
        # 10: 街角咖啡馆 - 咖啡馆/休息型
        {
            "id": "poi_011",
            "name": "街角咖啡馆",
            "category": "咖啡馆",
            "rating": 4.3,
            "avg_price": 35,
            "lat": 22.268,
            "lng": 113.578,
            "business_hours": "08:00-22:00",
            "tags": ["咖啡", "休息", "安静"],
            "queue_prone": False,
            "avg_stay_min": 45,
            "emotion_tags": {
                "excitement": 0.1,
                "tranquility": 0.8,
                "sociability": 0.3,
                "culture_depth": 0.2,
                "surprise": 0.05,
                "physical_demand": 0.05,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 0,
                "opening_hours": "08:00-22:00",
                "has_restroom": True,
            },
        },
        # 11: 水上乐园 - 高兴奋/排队
        {
            "id": "poi_012",
            "name": "水上乐园",
            "category": "娱乐",
            "rating": 4.6,
            "avg_price": 120,
            "lat": 22.285,
            "lng": 113.595,
            "business_hours": "08:00-20:00",
            "tags": ["刺激", "水上", "夏天"],
            "queue_prone": True,
            "avg_stay_min": 120,
            "emotion_tags": {
                "excitement": 0.9,
                "tranquility": 0.05,
                "sociability": 0.7,
                "culture_depth": 0.0,
                "surprise": 0.7,
                "physical_demand": 0.8,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 30,
                "opening_hours": "08:00-20:00",
                "has_restroom": True,
            },
        },
        # 12: 广场 - 休息型
        {
            "id": "poi_013",
            "name": "城市广场",
            "category": "广场",
            "rating": 4.0,
            "avg_price": 0,
            "lat": 22.266,
            "lng": 113.576,
            "business_hours": "00:00-23:59",
            "tags": ["广场", "休息", "免费"],
            "queue_prone": False,
            "avg_stay_min": 30,
            "emotion_tags": {
                "excitement": 0.05,
                "tranquility": 0.75,
                "sociability": 0.4,
                "culture_depth": 0.0,
                "surprise": 0.0,
                "physical_demand": 0.1,
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": True,
                "queue_time_min": 0,
                "opening_hours": "00:00-23:59",
                "has_restroom": True,
            },
        },
    ]


@pytest.fixture()
def p1_intent() -> dict:
    """P1 画像意图：社恐独居。"""
    return {
        "time": {"period": "全天", "start": "09:00", "end": "18:00"},
        "budget": {"per_person": 100, "type": "弹性"},
        "group": {"size": 1, "type": "独居"},
        "preferences": {"culture": 0.6, "food": 0.4, "nature": 0.7, "social": 0.1},
        "pace": "闲逛型",
        "hard_constraints": ["排队容忍度<5min", "避开人流高峰"],
    }


@pytest.fixture()
def p2_intent() -> dict:
    """P2 画像意图：浪漫情侣。"""
    return {
        "time": {"period": "下午", "start": "14:00", "end": "22:00"},
        "budget": {"per_person": 300, "type": "弹性"},
        "group": {"size": 2, "type": "情侣"},
        "preferences": {"culture": 0.5, "food": 0.8, "nature": 0.6, "social": 0.5},
        "pace": "平衡型",
        "hard_constraints": ["有氛围感", "可拍照"],
    }


@pytest.fixture()
def p14_intent() -> dict:
    """P14 画像意图：三代同堂。"""
    return {
        "time": {"period": "全天", "start": "09:00", "end": "17:00"},
        "budget": {"per_person": 150, "type": "弹性"},
        "group": {"size": 5, "type": "亲子"},
        "preferences": {"culture": 0.5, "food": 0.6, "nature": 0.6, "social": 0.5},
        "pace": "闲逛型",
        "hard_constraints": ["无障碍通行", "有儿童设施", "有休息区", "老少皆宜"],
    }


# ---------------------------------------------------------------------------
# 辅助函数测试
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """辅助函数测试。"""

    def test_haversine_same_point(self) -> None:
        """同一点距离为 0。"""
        assert haversine(22.27, 113.58, 22.27, 113.58) == pytest.approx(0.0)

    def test_haversine_known_distance(self) -> None:
        """已知距离校验（珠海到深圳约 60km）。"""
        d = haversine(22.27, 113.58, 22.54, 114.06)
        assert 50_000 < d < 80_000

    def test_estimate_distance_none_safe(self) -> None:
        """None 输入应返回 0。"""
        assert estimate_distance(None, {"lat": 22.27, "lng": 113.58}) == 0.0
        assert estimate_distance({"lat": 22.27, "lng": 113.58}, None) == 0.0

    def test_estimate_travel_time_reasonable(self, poi_pool: list[dict]) -> None:
        """旅行时间应为正数且合理（<2小时）。"""
        t = estimate_travel_time(poi_pool[0], poi_pool[1])
        assert 0 < t < 120

    def test_estimate_travel_time_none_safe(self) -> None:
        """None 输入应返回 0。"""
        assert estimate_travel_time(None, {"lat": 22.27, "lng": 113.58}) == 0.0

    def test_estimate_steps_basic(self, poi_pool: list[dict]) -> None:
        """步数估算应为正整数。"""
        steps = estimate_steps(poi_pool[0])
        assert steps > 0
        assert isinstance(steps, int)

    def test_estimate_steps_high_physical(self, poi_pool: list[dict]) -> None:
        """高体力需求 POI 步数应更多。"""
        low = estimate_steps(poi_pool[0])  # physical_demand=0.1
        high = estimate_steps(poi_pool[9])  # physical_demand=0.9
        assert high > low

    def test_check_time_windows_valid(self, poi_pool: list[dict]) -> None:
        """正常路线时间窗应通过。"""
        route = [
            {
                "poi": poi_pool[0],
                "arrival_time": "09:30",
                "departure_time": "11:30",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
        ]
        assert _check_time_windows(route) is True

    def test_check_time_windows_before_opening(self, poi_pool: list[dict]) -> None:
        """到达时间早于开门应不通过。"""
        route = [
            {
                "poi": poi_pool[1],  # 08:00 开门
                "arrival_time": "07:00",
                "departure_time": "10:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
        ]
        assert _check_time_windows(route) is False

    def test_check_time_windows_after_closing(self, poi_pool: list[dict]) -> None:
        """到达时间晚于关门应不通过。"""
        route = [
            {
                "poi": poi_pool[3],  # 关门 18:00
                "arrival_time": "19:00",
                "departure_time": "20:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
        ]
        assert _check_time_windows(route) is False

    def test_get_hours(self, poi_pool: list[dict]) -> None:
        """get_poi_opening_hours 应正确解析营业时间。"""
        open_t, close_t = get_poi_opening_hours(poi_pool[0])
        assert open_t.hour == 8
        assert close_t.hour == 21

    def test_recalculate_times_preserves_order(self, poi_pool: list[dict]) -> None:
        """重新计算时间后路线长度不变，且出发时间 >= 到达时间。"""
        route = [
            {
                "poi": poi_pool[0],
                "arrival_time": "09:00",
                "departure_time": "11:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
            {
                "poi": poi_pool[2],
                "arrival_time": "11:30",
                "departure_time": "13:00",
                "travel_from_prev": {"distance_m": 1000, "time_min": 20},
            },
        ]
        new_route = _recalculate_times(route, "09:00")
        assert len(new_route) == 2
        for step in new_route:
            assert step["arrival_time"] <= step["departure_time"]


# ---------------------------------------------------------------------------
# Phase 1 测试
# ---------------------------------------------------------------------------


class TestPhase1Initialize:
    """Phase 1 贪心初始化测试。"""

    def test_returns_nonempty_route(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """有候选 POI 时应返回非空路线。"""
        route = _phase1_initialize(poi_pool, p1_intent, "09:00")
        assert len(route) > 0

    def test_all_pois_from_candidates(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """路线中所有 POI 应来自候选池。"""
        candidate_ids = {p["id"] for p in poi_pool}
        route = _phase1_initialize(poi_pool, p1_intent, "09:00")
        for step in route:
            assert step["poi"]["id"] in candidate_ids

    def test_no_duplicate_pois(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """路线中不应有重复 POI。"""
        route = _phase1_initialize(poi_pool, p1_intent, "09:00")
        ids = [s["poi"]["id"] for s in route]
        assert len(ids) == len(set(ids))

    def test_time_windows_respected(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """路线应满足时间窗约束。"""
        route = _phase1_initialize(poi_pool, p1_intent, "09:00")
        assert _check_time_windows(route)

    def test_arrival_before_departure(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """每一步的出发时间应 >= 到达时间。"""
        route = _phase1_initialize(poi_pool, p1_intent, "09:00")
        for step in route:
            assert step["departure_time"] >= step["arrival_time"]

    def test_empty_candidates(self, p1_intent: dict) -> None:
        """空候选列表应返回空路线。"""
        route = _phase1_initialize([], p1_intent, "09:00")
        assert route == []

    def test_respects_max_pois_by_pace(self, poi_pool: list[dict]) -> None:
        """闲逛型不应超过 5 个 POI。"""
        intent = {
            "pace": "闲逛型",
            "preferences": {"culture": 0.5, "food": 0.5, "nature": 0.5, "social": 0.5},
        }
        route = _phase1_initialize(poi_pool, intent, "09:00")
        assert len(route) <= 5

    def test_respects_closing_time(self, poi_pool: list[dict]) -> None:
        """不应安排在关门之后到达的 POI。"""
        intent = {
            "pace": "特种兵型",
            "preferences": {"culture": 0.5, "food": 0.5, "nature": 0.5, "social": 0.5},
            "time": {"start": "09:00", "end": "18:00"},
        }
        route = _phase1_initialize(poi_pool, intent, "09:00")
        from backend.services.time_utils import parse_time

        for step in route:
            _, close_t = get_poi_opening_hours(step["poi"])
            arrival = parse_time(step["arrival_time"])
            assert arrival <= close_t, (
                f'{step["poi"]["name"]} 到达 {step["arrival_time"]} '
                f'晚于关门 {close_t.strftime("%H:%M")}'
            )


# ---------------------------------------------------------------------------
# Phase 2 测试
# ---------------------------------------------------------------------------


class TestPhase2Improve:
    """Phase 2 局部改进测试。"""

    def test_improve_preserves_length(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """改进后路线长度不变。"""
        route = _phase1_initialize(poi_pool, p1_intent, "09:00")
        original_len = len(route)
        improved = _phase2_improve(route, p1_intent, "09:00")
        assert len(improved) == original_len

    def test_improve_maintains_time_windows(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """改进后仍应满足时间窗。"""
        route = _phase1_initialize(poi_pool, p1_intent, "09:00")
        improved = _phase2_improve(route, p1_intent, "09:00")
        assert _check_time_windows(improved)

    def test_single_poi_route(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """单 POI 路线改进后不变。"""
        single = [
            {
                "poi": poi_pool[0],
                "arrival_time": "09:00",
                "departure_time": "11:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            }
        ]
        improved = _phase2_improve(single, p1_intent, "09:00")
        assert len(improved) == 1


# ---------------------------------------------------------------------------
# Phase 3 测试
# ---------------------------------------------------------------------------


class TestPhase3Breathing:
    """Phase 3 呼吸空间插入测试。"""

    def test_breathing_inserts_rest_for_high_excitement(self, poi_pool: list[dict]) -> None:
        """连续 3 个高兴奋 POI 应触发休息插入。"""
        route = []
        for poi in [poi_pool[1], poi_pool[7], poi_pool[11]]:
            route.append(
                {
                    "poi": poi,
                    "arrival_time": "10:00",
                    "departure_time": "11:00",
                    "travel_from_prev": {"distance_m": 500, "time_min": 10},
                }
            )

        original_len = len(route)
        intent = {"pace": "平衡型"}
        _phase3_breathing(route, poi_pool, intent)
        # _phase3_breathing 修改 route in-place
        assert len(route) > original_len

    def test_breathing_no_insert_for_low_excitement(self, poi_pool: list[dict]) -> None:
        """低兴奋路线不应插入休息。"""
        route = []
        for poi in [poi_pool[0], poi_pool[4], poi_pool[6]]:
            route.append(
                {
                    "poi": poi,
                    "arrival_time": "09:00",
                    "departure_time": "11:00",
                    "travel_from_prev": {"distance_m": 500, "time_min": 10},
                }
            )

        intent = {"pace": "平衡型"}
        _, spots = _phase3_breathing(route, poi_pool, intent)
        assert len(spots) == 0

    def test_idle_pace_inserts_rest(self, poi_pool: list[dict]) -> None:
        """闲逛型节奏应更积极地插入休息。"""
        route = []
        for poi in [poi_pool[0], poi_pool[2], poi_pool[4], poi_pool[6]]:
            route.append(
                {
                    "poi": poi,
                    "arrival_time": "09:00",
                    "departure_time": "10:30",
                    "travel_from_prev": {"distance_m": 500, "time_min": 10},
                }
            )

        intent = {"pace": "闲逛型"}
        _new_route, spots = _phase3_breathing(route, poi_pool, intent)
        assert len(spots) >= 1

    def test_breathing_rest_poi_has_high_tranquility(self, poi_pool: list[dict]) -> None:
        """插入的休息节点应有高宁静度。"""
        route = []
        for poi in [poi_pool[1], poi_pool[7], poi_pool[11]]:
            route.append(
                {
                    "poi": poi,
                    "arrival_time": "10:00",
                    "departure_time": "11:00",
                    "travel_from_prev": {"distance_m": 500, "time_min": 10},
                }
            )

        intent = {"pace": "平衡型"}
        _, spots = _phase3_breathing(route, poi_pool, intent)
        for spot in spots:
            assert spot["emotion_tags"]["tranquility"] > 0.7


# ---------------------------------------------------------------------------
# Phase 4 测试
# ---------------------------------------------------------------------------


class TestPhase4Finale:
    """Phase 4 高潮收尾测试。"""

    def test_finale_replaces_weak_ending(self, poi_pool: list[dict]) -> None:
        """最后一个 POI 兴奋度不足时应替换。"""
        route = [
            {
                "poi": poi_pool[1],  # excitement=0.95
                "arrival_time": "10:00",
                "departure_time": "10:30",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
            {
                "poi": poi_pool[0],  # excitement=0.1
                "arrival_time": "11:00",
                "departure_time": "13:00",
                "travel_from_prev": {"distance_m": 500, "time_min": 10},
            },
        ]

        improved = _phase4_finale(route, poi_pool)
        last_exc = improved[-1]["poi"].get("emotion_tags", {}).get("excitement", 0)
        assert last_exc > 0.1

    def test_finale_keeps_strong_ending(self, poi_pool: list[dict]) -> None:
        """最后一个 POI 兴奋度足够时不应替换。"""
        route = [
            {
                "poi": poi_pool[0],  # excitement=0.1
                "arrival_time": "09:00",
                "departure_time": "11:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
            {
                "poi": poi_pool[1],  # excitement=0.95
                "arrival_time": "11:30",
                "departure_time": "12:00",
                "travel_from_prev": {"distance_m": 500, "time_min": 10},
            },
        ]

        improved = _phase4_finale(route, poi_pool)
        assert improved[-1]["poi"]["id"] == "poi_002"

    def test_finale_single_poi(self, poi_pool: list[dict]) -> None:
        """单 POI 路线不应做任何修改。"""
        route = [
            {
                "poi": poi_pool[0],
                "arrival_time": "09:00",
                "departure_time": "11:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            }
        ]
        improved = _phase4_finale(route, poi_pool)
        assert len(improved) == 1
        assert improved[0]["poi"]["id"] == "poi_001"


# ---------------------------------------------------------------------------
# 路线评分测试
# ---------------------------------------------------------------------------


class TestEvaluateRoute:
    """路线评分函数测试。"""

    def test_multi_poi_nature_beats_food_for_p1(
        self, poi_pool: list[dict], p1_intent: dict
    ) -> None:
        """P1 偏好 nature>food，多POI nature 路线评分应更高。"""
        nature_route = [
            {
                "poi": poi_pool[5],  # 海滨公园
                "arrival_time": "09:00",
                "departure_time": "10:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
            {
                "poi": poi_pool[0],  # 安静图书馆
                "arrival_time": "10:10",
                "departure_time": "12:10",
                "travel_from_prev": {"distance_m": 500, "time_min": 10},
            },
        ]
        food_route = [
            {
                "poi": poi_pool[2],  # 浪漫咖啡厅
                "arrival_time": "09:00",
                "departure_time": "10:30",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
            {
                "poi": poi_pool[8],  # 高端西餐厅
                "arrival_time": "10:40",
                "departure_time": "12:10",
                "travel_from_prev": {"distance_m": 500, "time_min": 10},
            },
        ]

        nature_score = _evaluate_route(nature_route, p1_intent)
        food_score = _evaluate_route(food_route, p1_intent)
        assert nature_score > food_score

    def test_enhanced_compat_beats_overload(self, poi_pool: list[dict]) -> None:
        """文化->宁静 增强型兼容性应比兴奋->兴奋 过载评分更高。"""
        enhanced_route = [
            {
                "poi": poi_pool[4],  # 历史博物馆 culture_depth=0.95
                "arrival_time": "09:00",
                "departure_time": "11:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
            {
                "poi": poi_pool[5],  # 海滨公园 tranquility=0.85
                "arrival_time": "11:10",
                "departure_time": "12:10",
                "travel_from_prev": {"distance_m": 500, "time_min": 10},
            },
        ]
        overload_route = [
            {
                "poi": poi_pool[1],  # 刺激过山车 excitement=0.95
                "arrival_time": "09:00",
                "departure_time": "09:30",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
            {
                "poi": poi_pool[11],  # 水上乐园 excitement=0.9
                "arrival_time": "09:40",
                "departure_time": "11:40",
                "travel_from_prev": {"distance_m": 500, "time_min": 10},
            },
        ]

        intent = {"preferences": {"culture": 0.5, "nature": 0.5}}
        assert _evaluate_route(enhanced_route, intent) > _evaluate_route(overload_route, intent)


# ---------------------------------------------------------------------------
# 主函数集成测试
# ---------------------------------------------------------------------------


class TestSolveRouteIntegration:
    """solve_route 集成测试。"""

    def test_empty_candidates(self, p1_intent: dict) -> None:
        """空候选列表应返回空结果。"""
        result = solve_route([], p1_intent)
        assert result["route"] == []
        assert result["emotion_curve"] == []
        assert result["total_cost"]["time_min"] == 0

    def test_result_structure(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """返回值应包含所有必要字段。"""
        filtered = filter_candidates(poi_pool, p1_intent)
        result = solve_route(filtered, p1_intent, "09:00")
        assert "route" in result
        assert "emotion_curve" in result
        assert "total_cost" in result
        assert "unused_candidates" in result
        assert "breathing_spots" in result

    def test_route_has_required_fields(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """路线每一步应有 poi, arrival_time, departure_time, travel_from_prev。"""
        filtered = filter_candidates(poi_pool, p1_intent)
        result = solve_route(filtered, p1_intent, "09:00")
        for step in result["route"]:
            assert "poi" in step
            assert "arrival_time" in step
            assert "departure_time" in step
            assert "travel_from_prev" in step
            assert "distance_m" in step["travel_from_prev"]
            assert "time_min" in step["travel_from_prev"]

    def test_emotion_curve_matches_route(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """情绪曲线长度应等于路线长度。"""
        filtered = filter_candidates(poi_pool, p1_intent)
        result = solve_route(filtered, p1_intent, "09:00")
        assert len(result["emotion_curve"]) == len(result["route"])

    def test_unused_candidates_not_in_route(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """未使用的候选 POI 应不在路线中。"""
        filtered = filter_candidates(poi_pool, p1_intent)
        result = solve_route(filtered, p1_intent, "09:00")
        used_ids = {s["poi"]["id"] for s in result["route"]}
        for p in result["unused_candidates"]:
            assert p["id"] not in used_ids

    def test_total_cost_nonnegative(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """总成本各项应为非负数。"""
        filtered = filter_candidates(poi_pool, p1_intent)
        result = solve_route(filtered, p1_intent, "09:00")
        assert result["total_cost"]["time_min"] >= 0
        assert result["total_cost"]["budget_used"] >= 0
        assert result["total_cost"]["step_estimate"] >= 0


# ---------------------------------------------------------------------------
# P1 画像测试：社恐独居
# 使用 filter_candidates 预过滤后调用 solve_route
# ---------------------------------------------------------------------------


class TestP1SocialAnxiety:
    """P1 画像（社恐独居）测试。

    使用 filter_candidates 预过滤（排队容忍度<5min），验证：
    - 包含安静/宁静类 POI
    - 无连续同类 POI
    - 闲逛型有休息节点
    """

    def test_contains_quiet_pois(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """路线应包含至少一个宁静 POI（tranquility > 0.7）。"""
        filtered = filter_candidates(poi_pool, p1_intent)
        result = solve_route(filtered, p1_intent, "09:00")
        has_quiet = any(
            step["poi"].get("emotion_tags", {}).get("tranquility", 0) > 0.7
            for step in result["route"]
        )
        assert has_quiet, "路线应包含至少一个宁静POI"

    def test_no_consecutive_same_category(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """路线中不应有连续两个相同类别的 POI。"""
        filtered = filter_candidates(poi_pool, p1_intent)
        result = solve_route(filtered, p1_intent, "09:00")
        route = result["route"]
        for i in range(len(route) - 1):
            cat_a = route[i]["poi"].get("category")
            cat_b = route[i + 1]["poi"].get("category")
            assert cat_a != cat_b, (
                f"连续同类: {route[i]['poi']['name']}({cat_a}) -> "
                f"{route[i+1]['poi']['name']}({cat_b})"
            )

    def test_idle_pace_has_breathing_spots(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """闲逛型路线应有休息节点或已包含休息型POI。"""
        result = solve_route(poi_pool, p1_intent, "09:00")
        # 闲逛型 + 多个POI时应有休息节点或路线本身包含休息型POI
        if len(result["route"]) >= 3:
            has_rest = len(result["breathing_spots"]) >= 1 or any(
                step["poi"].get("category") in {"公园", "咖啡馆", "广场"}
                for step in result["route"]
            )
            assert has_rest, "闲逛型路线应有休息节点或包含休息型POI"

    def test_time_windows_satisfied(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """路线应满足所有时间窗约束。"""
        filtered = filter_candidates(poi_pool, p1_intent)
        result = solve_route(filtered, p1_intent, "09:00")
        assert _check_time_windows(result["route"])

    def test_no_high_queue_pois(self, poi_pool: list[dict], p1_intent: dict) -> None:
        """filter_candidates 已过滤高排队 POI，solver 不应引入新的。"""
        filtered = filter_candidates(poi_pool, p1_intent)
        result = solve_route(filtered, p1_intent, "09:00")
        for step in result["route"]:
            queue = step["poi"].get("constraints", {}).get("queue_time_min", 0)
            assert queue <= 5, f'{step["poi"]["name"]} 排队 {queue}min 超过容忍度'


# ---------------------------------------------------------------------------
# P2 画像测试：浪漫情侣
# ---------------------------------------------------------------------------


class TestP2Couple:
    """P2 画像（浪漫情侣）测试。

    验证：
    - 包含可拍照 POI（tags 含 '拍照' 或 '浪漫'）
    - 包含互动体验环节
    - 情绪曲线有起伏
    """

    def test_contains_photo_spots(self, poi_pool: list[dict], p2_intent: dict) -> None:
        """路线应包含至少一个可拍照 POI。"""
        result = solve_route(poi_pool, p2_intent, "14:00")
        photo_tags = {"拍照", "浪漫", "艺术", "约会"}
        has_photo = any(photo_tags & set(step["poi"].get("tags", [])) for step in result["route"])
        assert has_photo, "情侣路线应包含可拍照POI"

    def test_contains_interactive(self, poi_pool: list[dict], p2_intent: dict) -> None:
        """路线应包含互动体验环节或浪漫/艺术体验。"""
        result = solve_route(poi_pool, p2_intent, "14:00")
        # 情侣路线应包含互动、浪漫或艺术体验
        experience_tags = {"互动", "解谜", "体验", "浪漫", "约会", "艺术", "拍照"}
        has_experience = any(
            experience_tags & set(step["poi"].get("tags", [])) for step in result["route"]
        )
        assert has_experience, "情侣路线应包含互动/浪漫/艺术体验"

    def test_emotion_curve_has_data(self, poi_pool: list[dict], p2_intent: dict) -> None:
        """情绪曲线应有数据，且包含必要情绪字段。"""
        result = solve_route(poi_pool, p2_intent, "14:00")
        assert len(result["emotion_curve"]) > 0
        for point in result["emotion_curve"]:
            assert "time" in point
            assert "excitement" in point
            assert "tranquility" in point

    def test_budget_aware(self, poi_pool: list[dict], p2_intent: dict) -> None:
        """预算使用应合理（不超过候选总价）。"""
        result = solve_route(poi_pool, p2_intent, "14:00")
        max_possible = sum(p.get("avg_price", 0) for p in poi_pool)
        assert result["total_cost"]["budget_used"] <= max_possible

    def test_time_windows_satisfied(self, poi_pool: list[dict], p2_intent: dict) -> None:
        """路线应满足所有时间窗约束。"""
        result = solve_route(poi_pool, p2_intent, "14:00")
        assert _check_time_windows(result["route"])


# ---------------------------------------------------------------------------
# P14 画像测试：三代同堂
# 使用 filter_candidates 预过滤（无障碍通行硬约束）
# ---------------------------------------------------------------------------


class TestP14Family:
    """P14 画像（三代同堂）测试。

    使用 filter_candidates 预过滤（含无障碍通行硬约束），验证：
    - 路线中所有 POI 支持无障碍
    - 有休息节点
    - 无高体力消耗 POI
    """

    def test_all_accessible(self, poi_pool: list[dict], p14_intent: dict) -> None:
        """三代同堂路线所有 POI 应支持无障碍（filter_candidates 保证）。"""
        filtered = filter_candidates(poi_pool, p14_intent)
        result = solve_route(filtered, p14_intent, "09:00")
        for step in result["route"]:
            accessible = step["poi"].get("constraints", {}).get("accessible", False)
            assert accessible, f'{step["poi"]["name"]} 不支持无障碍'

    def test_has_rest_spots(self, poi_pool: list[dict], p14_intent: dict) -> None:
        """三代同堂路线应有休息节点（闲逛型节奏）。"""
        filtered = filter_candidates(poi_pool, p14_intent)
        result = solve_route(filtered, p14_intent, "09:00")
        if len(result["route"]) >= 3:
            has_rest = len(result["breathing_spots"]) > 0 or any(
                step["poi"].get("category") in {"公园", "咖啡馆", "广场"}
                for step in result["route"]
            )
            assert has_rest, "三代同堂路线应有休息节点"

    def test_no_extreme_physical(self, poi_pool: list[dict], p14_intent: dict) -> None:
        """不应包含高体力消耗 POI（physical_demand > 0.8）。"""
        filtered = filter_candidates(poi_pool, p14_intent)
        result = solve_route(filtered, p14_intent, "09:00")
        for step in result["route"]:
            demand = step["poi"].get("emotion_tags", {}).get("physical_demand", 0)
            assert demand <= 0.8, f'{step["poi"]["name"]} 体力需求 {demand} 对三代同堂过高'

    def test_unused_candidates_present(self, poi_pool: list[dict], p14_intent: dict) -> None:
        """未使用的候选 POI 应被正确记录。"""
        filtered = filter_candidates(poi_pool, p14_intent)
        result = solve_route(filtered, p14_intent, "09:00")
        used_ids = {s["poi"]["id"] for s in result["route"]}
        for p in result["unused_candidates"]:
            assert p["id"] not in used_ids

    def test_time_windows_satisfied(self, poi_pool: list[dict], p14_intent: dict) -> None:
        """路线应满足所有时间窗约束。"""
        filtered = filter_candidates(poi_pool, p14_intent)
        result = solve_route(filtered, p14_intent, "09:00")
        assert _check_time_windows(result["route"])
