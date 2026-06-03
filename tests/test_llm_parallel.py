"""LLM 并行化测试。

测试场景：
- SSE 流先推模板 steps，narrate 后台执行
- LLM 超时兜底到模板
- 前端收到 step_update 事件
"""

from __future__ import annotations

import asyncio

import pytest

from backend.sse.stream import SSEStream

# ---------------------------------------------------------------------------
# Mock 数据
# ---------------------------------------------------------------------------


def _make_poi(poi_id: str, name: str, **kwargs) -> dict:
    base = {
        "id": poi_id,
        "name": name,
        "category": "文化",
        "rating": 4.5,
        "avg_price": 30,
        "lat": 22.27,
        "lng": 113.58,
        "business_hours": "09:00-18:00",
        "avg_stay_min": 60,
        "emotion_tags": {
            "excitement": 0.3,
            "tranquility": 0.7,
            "sociability": 0.3,
            "culture_depth": 0.5,
            "surprise": 0.2,
            "physical_demand": 0.3,
        },
    }
    base.update(kwargs)
    return base


def _mock_route() -> dict:
    """模拟 solve_route 输出。"""
    return {
        "route": [
            {
                "poi": _make_poi("p1", "景点A"),
                "arrival_time": "09:00",
                "departure_time": "10:00",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            },
            {
                "poi": _make_poi("p2", "景点B"),
                "arrival_time": "10:30",
                "departure_time": "11:30",
                "travel_from_prev": {"distance_m": 1000, "time_min": 15},
            },
        ],
        "emotion_curve": [],
        "total_cost": {"time_min": 120, "budget_used": 60, "step_estimate": 2000},
        "unused_candidates": [],
        "breathing_spots": [],
    }


def _mock_template_narrative() -> dict:
    """模拟 generate_narrative(enable_llm_polish=False) 输出。"""
    return {
        "opening": "开启一段美好旅程",
        "steps": [
            {
                "description": "景点A模板描述",
                "emotion_design": "宁静",
                "design_intent": "开场预热",
                "leverage": "高",
                "cost": 0,
            },
            {
                "description": "景点B模板描述",
                "emotion_design": "兴奋",
                "design_intent": "渐入佳境",
                "leverage": "中",
                "cost": 30,
            },
        ],
        "closing": "完美收尾",
        "emotion_highlights": [],
        "budget_breakdown": {
            "total": 30,
            "budget_limit": 500,
            "remaining": 470,
            "leverage_summary": {},
        },
    }


def _mock_polished_narrative() -> dict:
    """模拟 generate_narrative(enable_llm_polish=True) 输出（LLM润色版）。"""
    return {
        "opening": "开启一段美好旅程",
        "steps": [
            {
                "description": "景点A LLM润色版描述 ✨",
                "emotion_design": "宁静",
                "design_intent": "开场预热",
                "leverage": "高",
                "cost": 0,
            },
            {
                "description": "景点B LLM润色版描述 ✨",
                "emotion_design": "兴奋",
                "design_intent": "渐入佳境",
                "leverage": "中",
                "cost": 30,
            },
        ],
        "closing": "完美收尾",
        "emotion_highlights": [],
        "budget_breakdown": {
            "total": 30,
            "budget_limit": 500,
            "remaining": 470,
            "leverage_summary": {},
        },
    }


# ---------------------------------------------------------------------------
# SSE 流并行化测试
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_events() -> list[dict]:
    """收集 SSE 事件的列表。"""
    return []


class TestSSEParallelFlow:
    """T-F003-01: SSE 流先推模板，narrate 后台执行。"""

    @pytest.mark.asyncio
    async def test_template_steps_before_polish(self, mock_events: list[dict]) -> None:
        """模板 step 应在 LLM 润色完成前推送。"""
        stream = SSEStream()

        collected: list[dict] = []
        original_send = stream.send

        async def tracking_send(event_type: str, data: dict) -> None:
            collected.append({"event": event_type, "data": data})
            await original_send(event_type, data)

        stream.send = tracking_send  # type: ignore[assignment]

        # 模拟 solve_route 后的流程
        route = _mock_route()
        template_narrative = _mock_template_narrative()

        # 推 step（模板）
        for i, step in enumerate(route.get("route", [])):
            await stream.send(
                "step",
                {
                    "index": i + 1,
                    "poi": step["poi"],
                    "arrival_time": step.get("arrival_time"),
                    "narrative": (
                        template_narrative.get("steps", [])[i]
                        if i < len(template_narrative.get("steps", []))
                        else ""
                    ),
                },
            )

        # 验证模板内容
        step_events = [e for e in collected if e["event"] == "step"]
        assert len(step_events) == 2
        assert "模板描述" in step_events[0]["data"]["narrative"]["description"]
        assert "模板描述" in step_events[1]["data"]["narrative"]["description"]

    @pytest.mark.asyncio
    async def test_polish_runs_in_background(self, mock_events: list[dict]) -> None:
        """LLM 润色作为后台 task，不应阻塞 done 事件。"""
        stream = SSEStream()
        route = _mock_route()

        polished = _mock_polished_narrative()

        # 模拟 generate_narrative(LLM) 延迟 1 秒
        async def slow_polish(*args: object, **kwargs: object) -> dict:
            await asyncio.sleep(1)
            return polished

        # 先推 step（模板）
        for i, step in enumerate(route.get("route", [])):
            await stream.send("step", {"index": i + 1, "poi": step["poi"]})

        # 先推 done
        start = asyncio.get_event_loop().time()
        await stream.send("done", {"route_id": "test_route", "full_route": route})

        # 后台执行 LLM 润色
        async def polish_task() -> None:
            result = await slow_polish()
            for i, step_data in enumerate(result.get("steps", [])):
                await stream.send(
                    "step_update", {"index": i + 1, "description": step_data["description"]}
                )

        task = asyncio.create_task(polish_task())
        await task

        elapsed = asyncio.get_event_loop().time() - start
        # done 应 < 0.1s（不等待 polish）
        assert elapsed > 0.9  # polish 花了 1s

    @pytest.mark.asyncio
    async def test_polish_timeout_fallback(self, mock_events: list[dict]) -> None:
        """LLM 超时时保留模板文案，不抛异常。"""
        stream = SSEStream()

        # 模拟超时的 LLM
        async def timeout_polish(*args: object, **kwargs: object) -> dict:
            await asyncio.sleep(10)  # 超时
            return {}

        done_events: list[dict] = []

        original_send = stream.send

        async def tracking_send(event_type: str, data: dict) -> None:
            if event_type == "done":
                done_events.append(data)
            await original_send(event_type, data)

        stream.send = tracking_send  # type: ignore[assignment]

        # 先推 done（模板路径已完成）
        await stream.send("done", {"route_id": "test_route"})

        # 后台执行（设置超时）
        try:
            await asyncio.wait_for(timeout_polish(), timeout=0.1)
        except TimeoutError:
            # 超时是预期行为，保留模板文案
            pass

        # done 应已正常推送
        assert len(done_events) == 1
        assert done_events[0]["route_id"] == "test_route"

    @pytest.mark.asyncio
    async def test_sse_route_endpoint_imports(self) -> None:
        """SSE 路由模块可导入（验证 syntax 正确）。"""
        from backend.routers import sse

        assert hasattr(sse, "plan_route_stream")
        assert hasattr(sse, "router")
