"""第三层：微协商总线。

智能体之间自动协商时间契约，形成连贯路线。
运行时监控，契约破裂时毫秒级重协商。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from backend.agents_v2.state import FederatedState, Bid, Contract


class MicroNegotiationBus:
    """微协商总线 - 协调多个竞标片段形成连贯路线。"""

    def __init__(self):
        self.contracts: list[Contract] = []
        self.conflict_threshold_minutes = 30

    async def negotiate(self, bids: list[Bid], intent_package: dict) -> dict[str, Any]:
        """协商形成最终路线。"""
        if not bids:
            return {"route": [], "contracts": []}

        # 按类型分组
        poi_bids = [b for b in bids if b["agent_type"] == "poi"]
        food_bids = [b for b in bids if b["agent_type"] == "food"]
        activity_bids = [b for b in bids if b["agent_type"] == "activity"]

        # 排序：按置信度和优先级
        poi_bids.sort(key=lambda x: x["confidence"], reverse=True)

        # 构建路线序列
        route_sequence = []
        current_time = self._parse_time(
            intent_package.get("core_intent", {}).get("time", {}).get("start", "09:00")
        )

        # 交替插入POI和餐饮
        used_bids = set()

        for i, poi_bid in enumerate(poi_bids[:5]):  # 最多5个POI
            if poi_bid["agent_id"] in used_bids:
                continue

            # 添加POI
            proposal = poi_bid["proposal"]
            duration = proposal.get("expected_duration", 120)

            route_sequence.append({
                "type": "poi",
                "bid": poi_bid,
                "arrival": current_time.strftime("%H:%M"),
                "departure": (current_time + timedelta(minutes=duration)).strftime("%H:%M"),
            })
            used_bids.add(poi_bid["agent_id"])

            current_time += timedelta(minutes=duration)

            # 每2个POI插入餐饮
            if (i + 1) % 2 == 0 and food_bids:
                food_bid = food_bids[0]
                if food_bid["agent_id"] not in used_bids:
                    route_sequence.append({
                        "type": "food",
                        "bid": food_bid,
                        "arrival": current_time.strftime("%H:%M"),
                        "departure": (current_time + timedelta(minutes=60)).strftime("%H:%M"),
                    })
                    used_bids.add(food_bid["agent_id"])
                    current_time += timedelta(minutes=60)

            # 交通时间
            current_time += timedelta(minutes=20)

        # 生成契约
        contracts = self._generate_contracts(route_sequence)
        self.contracts = contracts

        # 组装最终路线
        final_route = self._assemble_route(route_sequence)

        return {
            "route": final_route,
            "contracts": contracts,
            "sequence": route_sequence,
        }

    def _parse_time(self, time_str: str) -> datetime:
        """解析时间字符串。"""
        try:
            return datetime.strptime(time_str, "%H:%M")
        except:
            return datetime.strptime("09:00", "%H:%M")

    def _generate_contracts(self, sequence: list[dict]) -> list[Contract]:
        """生成智能体间契约。"""
        contracts = []

        for i in range(len(sequence) - 1):
            current = sequence[i]
            next_item = sequence[i + 1]

            contract = {
                "bid_a": current["bid"]["agent_id"],
                "bid_b": next_item["bid"]["agent_id"],
                "handoff_time": current.get("departure", ""),
                "transport_mode": "步行" if i % 2 == 0 else "公交",
                "status": "active",
            }
            contracts.append(contract)

        return contracts

    def _assemble_route(self, sequence: list[dict]) -> dict[str, Any]:
        """组装最终路线。"""
        route_steps = []
        total_cost = 0

        for item in sequence:
            bid = item["bid"]
            proposal = bid["proposal"]

            if item["type"] == "poi":
                poi = proposal.get("poi", {})
                step = {
                    "poi": poi,
                    "arrival_time": item["arrival"],
                    "departure_time": item["departure"],
                    "activity_type": "visit",
                }
                total_cost += poi.get("avg_price", 0)
            elif item["type"] == "food":
                rest = proposal.get("restaurant", {})
                step = {
                    "poi": rest,
                    "arrival_time": item["arrival"],
                    "departure_time": item["departure"],
                    "activity_type": "meal",
                }
                total_cost += rest.get("avg_price", 50)
            else:
                continue

            route_steps.append(step)

        return {
            "route": route_steps,
            "total_cost": {
                "budget_used": total_cost,
                "time_min": len(route_steps) * 120,
                "step_estimate": len(route_steps) * 2000,
            },
            "breathing_spots": [],
        }

    async def monitor_runtime(self, route: dict) -> list[dict]:
        """运行时监控（模拟）。"""
        alerts = []

        # 模拟：检查是否有POI临时关闭
        for step in route.get("route", []):
            poi = step.get("poi", {})
            # 模拟5%概率临时关闭
            if hash(poi.get("name", "")) % 20 == 0:
                alerts.append({
                    "type": "poi_closed",
                    "poi_name": poi.get("name"),
                    "severity": "high",
                    "action": "trigger_renegotiation",
                })

        # 模拟：天气突变
        if len(route.get("route", [])) > 3:
            alerts.append({
                "type": "weather_change",
                "description": "预计下午有雨",
                "severity": "medium",
                "action": "add_indoor_backup",
            })

        return alerts


# LangGraph节点函数
async def layer3_micro_negotiation(state: FederatedState) -> FederatedState:
    """第三层节点：微协商总线。"""
    try:
        surviving_bids = state.get("surviving_bids", [])
        intent_package = state.get("intent_package")

        if not surviving_bids:
            state["errors"].append("没有通过校验的竞标方案")
            return state

        # 微协商
        bus = MicroNegotiationBus()
        result = await bus.negotiate(surviving_bids, intent_package)

        state["final_route"] = result["route"]
        state["contracts"] = result["contracts"]

        # 运行时监控（模拟）
        alerts = await bus.monitor_runtime(result["route"])
        state["runtime_alerts"] = alerts

        return state

    except Exception as e:
        state["errors"].append(f"Layer3错误: {e}")
        return state
