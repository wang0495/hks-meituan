"""竞标市场 - 多智能体并行竞标。

POI Agent / Activity Agent / Food Agent / Transport Agent 各自竞标。
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.agents_v2.state import FederatedState, IntentPackage, SubNeed, Bid


class POIBiddingAgent:
    """POI竞标智能体。"""

    def __init__(self):
        self.agent_type = "poi"

    async def bid(self, sub_need: SubNeed, city: str = "珠海") -> list[Bid]:
        """为子需求竞标POI方案。"""
        from backend.services.data_service import get_data

        all_pois = get_data("city_poi_db")
        city_pois = [p for p in all_pois if p.get("city", "").strip() == city]

        # 根据子需求约束筛选
        constraints = sub_need.get("constraints", {})
        emotion_need = constraints.get("emotion", "")
        activity_type = constraints.get("activity_type", "")

        # 匹配POI
        matched = []
        for poi in city_pois:
            score = self._score_poi(poi, sub_need)
            if score > 0.5:
                matched.append((poi, score))

        # 按分数排序，取前3
        matched.sort(key=lambda x: x[1], reverse=True)
        top3 = matched[:3]

        bids = []
        for i, (poi, score) in enumerate(top3):
            bids.append({
                "agent_type": self.agent_type,
                "agent_id": f"poi_{sub_need['id']}_{i}",
                "sub_need_id": sub_need["id"],
                "proposal": {
                    "poi": poi,
                    "expected_duration": 120,  # 默认2小时
                    "recommended_time": "09:00",
                },
                "confidence": score,
                "cost_estimate": {
                    "entry_fee": poi.get("avg_price", 0),
                    "transport": 20,
                },
            })

        return bids

    def _score_poi(self, poi: dict, sub_need: SubNeed) -> float:
        """评分POI匹配度。"""
        score = 0.5
        constraints = sub_need.get("constraints", {})

        # 情绪匹配
        emotion_tags = poi.get("emotion_tags", {})
        target_emotion = constraints.get("emotion", "")
        if target_emotion and target_emotion in str(emotion_tags):
            score += 0.3

        # 类别匹配
        activity_type = constraints.get("activity_type", "")
        category = poi.get("category", "")
        if activity_type == "静态" and category in ["景点", "文化", "博物馆"]:
            score += 0.2
        elif activity_type == "动态" and category in ["娱乐", "运动", "体验"]:
            score += 0.2

        return min(score, 1.0)


class ActivityBiddingAgent:
    """活动竞标智能体（体验类、课程类）。"""

    def __init__(self):
        self.agent_type = "activity"

    async def bid(self, sub_need: SubNeed) -> list[Bid]:
        """为子需求竞标活动方案。"""
        # 模拟活动数据库
        activities = [
            {"name": "忍者体验", "type": "刺激", "duration": 90, "price": 150},
            {"name": "茶道体验", "type": "宁静", "duration": 60, "price": 80},
            {"name": "陶艺制作", "type": "创作", "duration": 120, "price": 100},
            {"name": "烹饪课程", "type": "美食", "duration": 180, "price": 200},
        ]

        constraints = sub_need.get("constraints", {})
        bids = []

        for act in activities:
            score = 0.5
            if constraints.get("emotion") == "兴奋" and act["type"] == "刺激":
                score = 0.9
            elif constraints.get("emotion") == "宁静" and act["type"] == "宁静":
                score = 0.9

            bids.append({
                "agent_type": self.agent_type,
                "agent_id": f"act_{sub_need['id']}_{act['name']}",
                "sub_need_id": sub_need["id"],
                "proposal": {
                    "activity": act,
                    "expected_duration": act["duration"],
                },
                "confidence": score,
                "cost_estimate": {
                    "activity_fee": act["price"],
                    "materials": 30,
                },
            })

        return bids


class FoodBiddingAgent:
    """餐饮竞标智能体。"""

    def __init__(self):
        self.agent_type = "food"

    async def bid(self, sub_need: SubNeed) -> list[Bid]:
        """为子需求竞标餐饮方案。"""
        from backend.services.data_service import get_data

        all_pois = get_data("city_poi_db")
        restaurants = [p for p in all_pois if p.get("category") == "餐饮"]

        # 简化：返回3个不同价位的
        restaurants.sort(key=lambda x: x.get("avg_price", 0))

        bids = []
        for i, rest in enumerate(restaurants[:3]):
            bids.append({
                "agent_type": self.agent_type,
                "agent_id": f"food_{sub_need['id']}_{i}",
                "sub_need_id": sub_need["id"],
                "proposal": {
                    "restaurant": rest,
                    "meal_type": "午餐" if i == 0 else "晚餐",
                },
                "confidence": 0.7,
                "cost_estimate": {
                    "meal_cost": rest.get("avg_price", 50),
                },
            })

        return bids


class TransportBiddingAgent:
    """交通竞标智能体。"""

    def __init__(self):
        self.agent_type = "transport"

    async def bid(self, from_poi: dict, to_poi: dict) -> list[Bid]:
        """竞标两点间交通方案。"""
        # 简化：提供3种交通方式
        return [
            {
                "agent_type": self.agent_type,
                "agent_id": f"trans_walk_{from_poi.get('id','?')}_{to_poi.get('id','?')}",
                "sub_need_id": "transport",
                "proposal": {
                    "mode": "步行",
                    "distance_m": 500,
                    "time_min": 8,
                },
                "confidence": 0.9,
                "cost_estimate": {"transport": 0},
            },
            {
                "agent_type": self.agent_type,
                "agent_id": f"trans_bus_{from_poi.get('id','?')}_{to_poi.get('id','?')}",
                "sub_need_id": "transport",
                "proposal": {
                    "mode": "公交",
                    "distance_m": 2000,
                    "time_min": 15,
                },
                "confidence": 0.8,
                "cost_estimate": {"transport": 2},
            },
            {
                "agent_type": self.agent_type,
                "agent_id": f"trans_taxi_{from_poi.get('id','?')}_{to_poi.get('id','?')}",
                "sub_need_id": "transport",
                "proposal": {
                    "mode": "打车",
                    "distance_m": 2000,
                    "time_min": 10,
                },
                "confidence": 0.95,
                "cost_estimate": {"transport": 25},
            },
        ]


# 竞标市场主函数
async def bidding_market(state: FederatedState) -> FederatedState:
    """竞标市场节点：多Agent并行竞标。"""
    try:
        intent_package = state.get("intent_package")
        if not intent_package:
            state["errors"].append("意图包为空")
            return state

        sub_needs = intent_package.get("decomposed_sub_needs", [])
        if not sub_needs:
            # 没有子需求，用核心意图
            sub_needs = [{
                "id": "core",
                "description": "核心需求",
                "constraints": intent_package.get("core_intent", {}),
                "priority": 10,
            }]

        all_bids = []

        # 为每个子需求并行竞标
        for sub_need in sub_needs:
            # 创建竞标Agent
            poi_agent = POIBiddingAgent()
            activity_agent = ActivityBiddingAgent()
            food_agent = FoodBiddingAgent()

            # 并行竞标
            bids = await asyncio.gather(
                poi_agent.bid(sub_need),
                activity_agent.bid(sub_need),
                food_agent.bid(sub_need),
                return_exceptions=True,
            )

            for bid_result in bids:
                if isinstance(bid_result, list):
                    all_bids.extend(bid_result)

        # 按置信度排序
        all_bids.sort(key=lambda x: x["confidence"], reverse=True)

        state["bids"] = all_bids[:20]  # 保留前20个
        return state

    except Exception as e:
        state["errors"].append(f"竞标市场错误: {e}")
        return state
