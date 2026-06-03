"""SSE 流式路线规划路由。

v2 优化（F003）：
- solve_route 完成后立即推送 step（模板文案）
- LLM 润色改为后台 task，完成后推 step_update 事件
- 用户无需等 narrate 完成即可看到路线
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.sse.stream import SSEStream, create_sse_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["SSE"])

_LLM_POLISH_TIMEOUT = 15.0  # LLM 润色超时秒数


class SSERequest(BaseModel):
    user_input: str = Field(..., min_length=1, max_length=500)


@router.post("/api/plan/stream")
async def plan_route_stream(request: Request) -> StreamingResponse:
    """流式路线规划 -- 四阶段 SSE 逐步推送。"""
    from backend.services.data_service import get_data
    from backend.services.intent_parser import parse_intent
    from backend.services.narrator import generate_narrative
    from backend.services.solver import solve_route

    try:
        body = await request.json()
    except Exception:
        from fastapi.responses import JSONResponse

        return JSONResponse({"error": "无效的JSON请求体"}, status_code=400)
    # Pydantic 风格验证
    validated = SSERequest(**body)
    user_input = validated.user_input

    stream = SSEStream()

    async def process() -> None:
        try:
            # 阶段1: 解析意图
            await stream.send("phase", {"phase": "parsing", "message": "正在理解你的需求..."})
            intent = await parse_intent(user_input, {})

            # 阶段2: 搜索POI + 感知上下文
            await stream.send(
                "phase", {"phase": "searching", "message": "正在为你寻找合适的地方..."}
            )
            pois = get_data("city_poi_db")

            # 获取感知上下文
            from backend.services.perception import perception_service

            perception_ctx = await perception_service.get_context()

            # 阶段3: 求解路线（携带感知上下文）
            await stream.send("phase", {"phase": "solving", "message": "正在编排最佳路线..."})
            route = solve_route(pois[:20], intent, perception_ctx=perception_ctx)

            # 检测异常（需要 solver 输出的 emotion_curve）
            anomalies = await perception_service.detect_anomaly(
                perception_ctx, route.get("emotion_curve", [])
            )
            if anomalies:
                for anomaly in anomalies:
                    await stream.send("anomaly", anomaly.to_dict())

            # ---- 优化点: 先用模板推 step，LLM 润色后台执行 ----
            # 从路线中提取城市（内容引擎 D4）
            city = ""
            first_pois = route.get("route", [])
            if first_pois:
                city = first_pois[0].get("poi", {}).get("city", "")

            # 用模板生成文案（同步/低延迟）
            template_narrative = await generate_narrative(
                route, intent, enable_llm_polish=False, city=city
            )

            # 立即推送 step
            await stream.send(
                "phase", {"phase": "narrating", "message": "正在为你写一段行程说明..."}
            )
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
                await asyncio.sleep(0.05)

            # 先推 done（让前端先展示路线）
            await stream.send("done", {"route_id": "test_route", "full_route": route})

            # LLM 润色后台执行（不阻塞 SSE 响应）
            async def _polish_narrative() -> None:
                try:
                    polished = await asyncio.wait_for(
                        generate_narrative(route, intent, enable_llm_polish=True, city=city),
                        timeout=_LLM_POLISH_TIMEOUT,
                    )
                    for i, step_data in enumerate(polished.get("steps", [])):
                        await stream.send(
                            "step_update",
                            {
                                "index": i + 1,
                                "description": step_data.get("description", ""),
                                "emotion_design": step_data.get("emotion_design", ""),
                            },
                        )
                    await stream.send("polish_done", {})
                except TimeoutError:
                    logger.warning("[SSE] LLM 润色超时，保留模板文案")
                except Exception:
                    logger.exception("[SSE] LLM 润色异常，保留模板文案")

            asyncio.create_task(_polish_narrative())
            # ----------------------------------------------------------------

        except Exception:
            logger.exception("SSE 流式规划出错")
            await stream.send("error", {"error": "路线规划失败，请重试"})

    asyncio.create_task(process())

    return create_sse_response(stream)
