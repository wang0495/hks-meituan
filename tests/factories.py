"""CityFlow 测试数据工厂。

提供 POI、意图、路线等测试对象的快速生成，
避免在每个测试文件中重复构造样板数据。
"""

from __future__ import annotations

import random
from typing import Any


class POIFactory:
    """POI 测试数据工厂。"""

    _counter = 0

    @classmethod
    def create(cls, **kwargs: Any) -> dict[str, Any]:
        """创建单个测试 POI。

        Args:
            **kwargs: 覆盖任意字段的默认值。

        Returns:
            一个完整的 POI 字典。
        """
        cls._counter += 1

        defaults: dict[str, Any] = {
            "id": f"test_{cls._counter:04d}",
            "name": f"测试POI {cls._counter}",
            "category": random.choice(["文化", "美食", "娱乐", "自然", "景点"]),
            "city": "珠海",
            "rating": round(random.uniform(3.0, 5.0), 1),
            "avg_price": random.randint(0, 200),
            "avg_stay_min": random.choice([30, 60, 90, 120]),
            "lat": 22.27 + random.uniform(-0.05, 0.05),
            "lng": 113.58 + random.uniform(-0.05, 0.05),
            "business_hours": "08:00-22:00",
            "tags": ["测试"],
            "queue_prone": False,
            "emotion_tags": {
                "excitement": round(random.random(), 2),
                "tranquility": round(random.random(), 2),
                "sociability": round(random.random(), 2),
                "culture_depth": round(random.random(), 2),
                "surprise": round(random.random(), 2),
                "physical_demand": round(random.random(), 2),
            },
            "constraints": {
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 0,
                "opening_hours": "08:00-22:00",
                "has_restroom": True,
            },
        }

        defaults.update(kwargs)
        return defaults

    @classmethod
    def create_batch(cls, count: int, **kwargs: Any) -> list[dict[str, Any]]:
        """批量创建 POI。

        Args:
            count: 创建数量。
            **kwargs: 覆盖每个 POI 的默认字段。

        Returns:
            POI 列表。
        """
        return [cls.create(**kwargs) for _ in range(count)]

    @classmethod
    def reset(cls) -> None:
        """重置计数器。"""
        cls._counter = 0


class IntentFactory:
    """用户意图测试数据工厂。"""

    @classmethod
    def create(cls, **kwargs: Any) -> dict[str, Any]:
        """创建单个测试意图。

        Args:
            **kwargs: 覆盖任意字段的默认值。

        Returns:
            一个完整的意图字典。
        """
        defaults: dict[str, Any] = {
            "time": {"period": "全天", "start": "09:00", "end": "18:00"},
            "budget": {"per_person": 500, "type": "弹性"},
            "group": {"size": 1, "type": "独居"},
            "preferences": {
                "culture": 0.5,
                "food": 0.5,
                "nature": 0.5,
                "social": 0.5,
            },
            "pace": "平衡型",
            "hard_constraints": [],
            "matched_profile_id": "P1",
        }

        defaults.update(kwargs)
        return defaults

    @classmethod
    def create_solo_quiet(cls) -> dict[str, Any]:
        """社恐独居、闲逛型意图。"""
        return cls.create(
            group={"size": 1, "type": "独居"},
            preferences={"culture": 0.6, "food": 0.3, "nature": 0.7, "social": 0.1},
            pace="闲逛型",
            hard_constraints=["低人流"],
            matched_profile_id="P1",
        )

    @classmethod
    def create_couple_romantic(cls) -> dict[str, Any]:
        """情侣约会、平衡型意图。"""
        return cls.create(
            group={"size": 2, "type": "情侣"},
            preferences={"culture": 0.4, "food": 0.7, "nature": 0.5, "social": 0.5},
            pace="平衡型",
            hard_constraints=[],
            matched_profile_id="P2",
        )

    @classmethod
    def create_family_kids(cls) -> dict[str, Any]:
        """亲子出游、平衡型意图。"""
        return cls.create(
            group={"size": 3, "type": "亲子"},
            preferences={"culture": 0.3, "food": 0.5, "nature": 0.6, "social": 0.6},
            pace="平衡型",
            hard_constraints=["儿童友好"],
            matched_profile_id="P3",
        )

    @classmethod
    def create_friends_party(cls) -> dict[str, Any]:
        """朋友聚会、特种兵型意图。"""
        return cls.create(
            group={"size": 4, "type": "朋友"},
            preferences={"culture": 0.2, "food": 0.8, "nature": 0.3, "social": 0.9},
            pace="特种兵型",
            hard_constraints=[],
            matched_profile_id="P4",
        )


class RouteFactory:
    """路线测试数据工厂。"""

    @classmethod
    def create(cls, poi_count: int = 3, **kwargs: Any) -> dict[str, Any]:
        """创建测试路线结果。

        Args:
            poi_count: 路线中包含的 POI 数量。
            **kwargs: 覆盖任意顶层字段。

        Returns:
            一个模拟 solver.solve_route() 输出的字典。
        """
        route_steps: list[dict[str, Any]] = []
        for i in range(poi_count):
            poi = POIFactory.create()
            hour = 9 + i * 2
            route_steps.append(
                {
                    "poi": poi,
                    "arrival_time": f"{hour:02d}:00",
                    "departure_time": f"{hour + 1:02d}:30",
                    "travel_from_prev": (
                        {"distance_m": 2000, "time_min": 10} if i > 0 else None
                    ),
                }
            )

        defaults: dict[str, Any] = {
            "route": route_steps,
            "emotion_curve": [
                {"time": s["arrival_time"], "excitement": 0.5, "tranquility": 0.5}
                for s in route_steps
            ],
            "total_cost": {
                "time_min": poi_count * 120,
                "budget_used": poi_count * 80,
                "step_estimate": poi_count * 2000,
            },
            "unused_candidates": [],
            "breathing_spots": [],
        }

        defaults.update(kwargs)
        return defaults

    @classmethod
    def create_minimal(cls) -> dict[str, Any]:
        """创建最小可用路线（1个POI）。"""
        return cls.create(poi_count=1)
