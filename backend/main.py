"""CityFlow API -- 前后端集成 + SSE 流式路线规划。"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from backend.config import settings
from backend.schemas import AdjustRequest, HealthResponse, PlanRequest
from backend.docs import custom_openapi, register_docs_endpoints
from backend.errors import CityFlowException, ErrorCode
from backend.middleware import (APIVersionMiddleware, ConfigMiddleware,
                                InputValidationMiddleware,
                                PrometheusMiddleware, RateLimitMiddleware,
                                SecurityHeadersMiddleware, SessionMiddleware,
                                ShutdownMiddleware, setup_error_handlers)
from backend.middleware.auth import APIKeyAuthMiddleware
from backend.routers import (audit, data, health, llm, mq, poi, pool, registry,
                             session, sse, tasks, v1, v2, websocket)
from backend.routers.graphql import router as graphql_router
from backend.routers.metrics import router as metrics_router
from backend.services.cache import (close_multilevel_cache, distance_cache,
                                    general_cache, get_multilevel_cache,
                                    init_multilevel_cache, poi_cache,
                                    profile_cache, route_cache)
from backend.services.cache_warmup import warmup_memory_caches
from backend.services.data_service import get_data, load_data

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSE 并发连接限制（防止连接耗尽攻击）
# ---------------------------------------------------------------------------
_plan_concurrent = 0
_PLAN_MAX_CONCURRENT = 20

# ---------------------------------------------------------------------------
# Tags 元数据（OpenAPI 文档分组说明）
# ---------------------------------------------------------------------------

_tags_metadata = [
    {
        "name": "路线规划",
        "description": (
            "核心路线规划接口。根据用户自然语言描述，通过意图解析、POI筛选、"
            "TSPTW算法求解、文案生成四个阶段，以SSE流式返回个性化路线。"
        ),
    },
    {
        "name": "路线管理",
        "description": "路线的查询、缓存与调整接口。",
    },
    {
        "name": "对话",
        "description": (
            "对话式路线调整接口。支持替换景点、调整节奏、调整预算、"
            "调整时间、重新规划等指令类型。"
        ),
    },
    {
        "name": "POI",
        "description": (
            "兴趣点（Point of Interest）查询与距离计算接口。"
            "支持多维度筛选、详情查询、距离矩阵计算。"
        ),
    },
    {
        "name": "数据",
        "description": "底层数据集查询接口（POI、订单、道路流量等）。",
    },
    {
        "name": "LLM",
        "description": "大语言模型对话接口，支持普通与流式响应。",
    },
    {
        "name": "审计日志",
        "description": (
            "审计日志查询与导出接口。记录系统中所有关键操作（路线规划、"
            "对话调整、POI搜索等），支持按用户、动作类型、时间范围过滤，"
            "以及 JSON/CSV 格式导出。"
        ),
    },
    {
        "name": "监控",
        "description": (
            "Prometheus 指标端点。以 exposition format 返回请求计数、"
            "延迟分布、活跃会话数、路线规划次数等自定义指标，"
            "供 Prometheus server 抓取。"
        ),
    },
    {
        "name": "系统",
        "description": "健康检查等运维接口。",
    },
    {
        "name": "任务",
        "description": (
            "异步后台任务管理接口。支持提交后台任务、查询任务状态、"
            "取消任务、列出所有任务。任务通过白名单机制控制可执行函数。"
        ),
    },
    {
        "name": "WebSocket",
        "description": (
            "WebSocket 实时通信接口。支持路线更新订阅、心跳检测、"
            "实时消息推送。客户端通过 /ws/{session_id} 建立长连接。"
        ),
    },
    {
        "name": "GraphQL",
        "description": (
            "GraphQL 查询与变更接口。支持按条件查询 POI、路线，"
            "以及通过自然语言规划路线和对话式调整路线。"
            "端点: POST /graphql，同时提供 GraphiQL 交互式文档。"
        ),
    },
    {
        "name": "消息队列",
        "description": (
            "Redis 消息队列接口。支持消息发布（单条/批量）、"
            "消费者启动、队列状态查询与清空。"
            "用于异步任务分发（路线规划回调、通知推送、分析埋点）。"
        ),
    },
    {
        "name": "连接池",
        "description": (
            "连接池监控接口。提供数据库和 HTTP 连接池的实时统计、"
            "健康检查、告警查询和仪表盘数据。"
            "支持阈值告警（warning/critical）和历史趋势数据。"
        ),
    },
]

# ---------------------------------------------------------------------------
# FastAPI 实例
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CityFlow API",
    description=(
        "# CityFlow - 智能城市出行规划系统\n\n"
        "基于情绪感知的个性化城市路线规划API。\n\n"
        "## 核心功能\n\n"
        "- **意图解析** - 理解用户自然语言需求，自动匹配用户画像\n"
        "- **路线规划** - TSPTW（带时间窗约束的旅行商问题）算法优化路线\n"
        "- **对话调整** - 支持多轮对话实时调整已规划路线\n"
        "- **文案生成** - 自动生成路线描述与情绪曲线\n\n"
        "## 情绪标签\n\n"
        "每个POI携带6维情绪标签（取值 0~1）：\n\n"
        "| 维度 | 字段 | 说明 |\n"
        "|------|------|------|\n"
        "| 兴奋度 | `excitement` | 该地点带来的兴奋刺激感 |\n"
        "| 宁静度 | `tranquility` | 该地点的安静平和程度 |\n"
        "| 社交性 | `sociability` | 该地点适合社交互动的程度 |\n"
        "| 文化深度 | `culture_depth` | 该地点的文化内涵丰富度 |\n"
        "| 惊喜度 | `surprise` | 该地点带来意外惊喜的可能性 |\n"
        "| 体力消耗 | `physical_demand` | 该地点对体力的要求 |\n\n"
        "## 用户画像\n\n"
        "系统内置20种典型用户画像，自动从自然语言中推断匹配：\n\n"
        "| ID | 名称 | 群体 | 节奏 |\n"
        "|----|------|------|------|\n"
        "| P1 | 社恐独居 | 独居 | 闲逛型 |\n"
        "| P2 | 浪漫情侣 | 情侣 | 平衡型 |\n"
        "| P3 | 活力亲子 | 亲子 | 平衡型 |\n"
        "| P4 | 朋友聚会 | 朋友 | 特种兵型 |\n"
        "| P5 | 退休休闲 | 退休 | 闲逛型 |\n"
        "| P6 | 文化探索者 | 独居 | 平衡型 |\n"
        "| P7 | 美食猎人 | 朋友 | 特种兵型 |\n"
        "| P8 | 自然爱好者 | 独居 | 闲逛型 |\n"
        "| P9 | 社交达人 | 朋友 | 特种兵型 |\n"
        "| P10 | 摄影爱好者 | 独居 | 平衡型 |\n"
        "| P11-P20 | ... | ... | ... |\n\n"
        "## 节奏模式\n\n"
        "| 模式 | 说明 |\n"
        "|------|------|\n"
        "| 闲逛型 | 悠闲步行，每个景点停留较久，穿插休息 |\n"
        "| 平衡型 | 适度紧凑，兼顾体验与效率 |\n"
        "| 特种兵型 | 高密度打卡，时间利用率最高 |\n\n"
        "## 价格区间\n\n"
        "| 区间 | 条件 |\n"
        "|------|------|\n"
        "| 免费 | avg_price = 0 |\n"
        "| 便宜 | avg_price <= 50 |\n"
        "| 中等 | avg_price <= 150 |\n"
        "| 较贵 | avg_price <= 500 |\n"
        "| 高端 | avg_price > 500 |\n"
    ),
    version="1.0.0",
    contact={
        "name": "CityFlow Team",
        "email": "team@cityflow.com",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=_tags_metadata,
    servers=[
        {"url": "http://localhost:8000", "description": "本地开发"},
        {"url": "https://api.cityflow.com", "description": "生产环境"},
    ],
    docs_url=None,
    redoc_url=None,
)

# ---- 自定义 OpenAPI schema + 文档页面 ----
app.openapi = lambda: custom_openapi(app)  # type: ignore[method-assign]
register_docs_endpoints(app)

# ---- 全局异常处理（必须在中间件之前注册） ----
setup_error_handlers(app)

# ---- 中间件（按添加顺序从外到内执行） ----

# CORS -- 最外层，处理 OPTIONS 预检请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

# API Key 认证（CORS 之后、限速之前，未配置 api_key 时不生效）
app.add_middleware(APIKeyAuthMiddleware, api_key=settings.security.api_key)

# 停机感知（尽早拒绝停机期间的请求）
app.add_middleware(ShutdownMiddleware)

# Prometheus 指标采集
app.add_middleware(PrometheusMiddleware)

# 速率限制
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.security.rate_limit_per_minute,
    trusted_proxies=settings.security.trusted_proxies,
)

# 输入验证
app.add_middleware(
    InputValidationMiddleware,
    max_body_size=settings.security.max_request_size,
)

# 安全响应头
app.add_middleware(SecurityHeadersMiddleware)

# 会话管理
app.add_middleware(SessionMiddleware)

# API 版本控制
app.add_middleware(APIVersionMiddleware)

# 配置注入
app.add_middleware(ConfigMiddleware)

app.include_router(audit.router)
app.include_router(data.router)
app.include_router(health.router)
app.include_router(llm.router)
app.include_router(mq.router)
app.include_router(poi.router)
app.include_router(session.router)
app.include_router(tasks.router)
app.include_router(websocket.router)
app.include_router(registry.router)
app.include_router(metrics_router)
app.include_router(pool.router)
app.include_router(sse.router)

# 版本化路由
app.include_router(v1.router)
app.include_router(v2.router)

# GraphQL 端点
app.include_router(graphql_router)

# NOTE: 静态文件挂载在文件末尾（所有 API 路由之后），
# 否则 "/" 的 catch-all mount 会拦截所有 API 请求。


# ---------------------------------------------------------------------------
# 路由缓存（使用 cache 模块的 route_cache，带 TTL 自动过期）
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 超时 + 兜底
# ---------------------------------------------------------------------------


async def _with_timeout(coro, timeout_seconds: float = 12.0, fallback=None):
    """给协程加超时，超时返回 fallback。"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning("操作超时 (%.1fs)，使用兜底", timeout_seconds)
        return fallback


def _generate_simplified_route(
    pois: list[dict[str, Any]], count: int = 3, start_time: str = "09:00"
) -> dict[str, Any]:
    """生成简化路线（兜底方案）。"""
    sorted_pois = sorted(pois, key=lambda p: p.get("rating", 0), reverse=True)[:count]
    try:
        sh, sm = start_time.split(":")
        start_h = int(sh)
        start_m = int(sm)
    except (ValueError, AttributeError):
        start_h, start_m = 9, 0
    return {
        "route": [
            {
                "poi": poi,
                "arrival_time": f"{(start_h + i) % 24:02d}:{start_m:02d}",
                "departure_time": f"{(start_h + i + 1) % 24:02d}:{start_m:02d}",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            }
            for i, poi in enumerate(sorted_pois)
        ],
        "emotion_curve": [],
        "total_cost": {"time_min": 180, "budget_used": 0, "step_estimate": 3000},
        "unused_candidates": [],
        "breathing_spots": [],
    }


# ---------------------------------------------------------------------------
# SSE 辅助
# ---------------------------------------------------------------------------


def _sse(event: str, data_obj: Any) -> str:
    """构造一条 SSE 消息。"""
    return f"event: {event}\ndata: {json.dumps(data_obj, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# POST /api/plan -- 流式路线规划
# ---------------------------------------------------------------------------


@app.post(
    "/api/plan",
    summary="流式规划路线",
    description=(
        "根据用户自然语言描述，以SSE（Server-Sent Events）流式返回规划结果。\n\n"
        "## 处理流程\n\n"
        "1. **解析意图** (`phase: parsing`) - 理解用户需求，匹配用户画像\n"
        "2. **搜索候选** (`phase: searching`) - 根据意图筛选合适POI\n"
        "3. **求解路线** (`phase: solving`) - TSPTW算法优化路线顺序与时间\n"
        "4. **生成文案** (`phase: narrating`) - 为每个站点生成描述文案\n"
        "5. **逐步返回** (`step`) - 逐个返回路线步骤\n"
        "6. **完成** (`done`) - 返回路线ID和完整数据\n\n"
        "## SSE 事件类型\n\n"
        "| 事件 | data 字段 | 说明 |\n"
        "|------|-----------|------|\n"
        "| `phase` | `{phase, message}` | 当前处理阶段 |\n"
        "| `step` | `{index, poi, arrival_time, departure_time, narrative}` | 单个路线步骤 |\n"
        "| `done` | `{route_id, full_route}` | 规划完成，route_id 可用于后续对话 |\n"
        "| `error` | `{error}` | 错误信息 |\n\n"
        "## 阶段标识\n\n"
        "| phase 值 | 含义 |\n"
        "|-----------|------|\n"
        "| `parsing` | 正在解析用户意图 |\n"
        "| `searching` | 正在搜索候选POI |\n"
        "| `solving` | 正在求解最优路线 |\n"
        "| `narrating` | 正在生成文案 |\n\n"
        "## 超时与兜底\n\n"
        "- 意图解析超时（8s）→ 返回错误\n"
        "- 候选为空 → 返回错误\n"
        "- 路线求解超时（10s）→ 使用简化路线兜底\n"
        "- 文案生成超时（5s）→ 使用空白文案兜底"
    ),
    response_description="SSE 事件流（text/event-stream），事件格式为 `event: <type>\\ndata: <json>\\n\\n`",
    responses={
        200: {
            "description": "SSE事件流",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "examples": {
                        "phase": {
                            "summary": "阶段事件",
                            "value": 'event: phase\ndata: {"phase":"parsing","message":"正在理解你的需求..."}\n\n',
                        },
                        "step": {
                            "summary": "步骤事件",
                            "value": (
                                'event: step\ndata: {"index":1,"poi":{"id":"poi_001",'
                                '"name":"故宫","category":"景点"},'
                                '"arrival_time":"09:00","departure_time":"11:00",'
                                '"narrative":"走进六百年的紫禁城..."}\n\n'
                            ),
                        },
                        "done": {
                            "summary": "完成事件",
                            "value": 'event: done\ndata: {"route_id":"a1b2c3d4","full_route":{...}}\n\n',
                        },
                        "error": {
                            "summary": "错误事件",
                            "value": 'event: error\ndata: {"error":"意图解析超时，请重试"}\n\n',
                        },
                    },
                }
            },
        }
    },
    tags=["路线规划"],
)
async def plan_route(request: PlanRequest):
    """
    流式规划路线。

    根据用户自然语言输入，经过意图解析、候选搜索、路线求解、文案生成四个阶段，
    以 SSE 事件流的形式逐步返回结果。

    返回的 `route_id` 可用于后续的 `/api/route/{route_id}` 查询和
    `/api/dialogue/{session_id}` 对话调整。
    """

    async def event_stream():
        global _plan_concurrent
        if _plan_concurrent >= _PLAN_MAX_CONCURRENT:
            yield _sse("error", {"error": "服务繁忙，请稍后再试"})
            return
        _plan_concurrent += 1
        try:
            # Phase 1: 解析意图
            yield _sse("phase", {"phase": "parsing", "message": "正在理解你的需求..."})

            from backend.services.intent_parser import parse_intent
            from backend.services.user_profiles import USER_PROFILES

            user_intent = await _with_timeout(
                parse_intent(request.user_input, USER_PROFILES),
                timeout_seconds=35.0,
            )
            if user_intent is None:
                yield _sse("error", {"error": "意图解析超时，请重试"})
                return

            # Debug: LLM 调用详情（仅开发环境）
            if settings.debug:
                llm_used = user_intent.get("_llm_used", False)
                llm_err = user_intent.get("_llm_error", "")
                llm_debug = {
                    "used": llm_used,
                    "method": "llm" if llm_used else f"rule（{llm_err or '未配置'}）",
                }
                if user_intent.get("_llm_raw_response"):
                    llm_debug["raw_response"] = user_intent["_llm_raw_response"][:300]
                if user_intent.get("_llm_model"):
                    llm_debug["model"] = user_intent["_llm_model"]
                yield _sse("debug_llm", llm_debug)

            # Debug: 画像匹配 TOP3（仅开发环境）
            if settings.debug:
                top3 = user_intent.get("_profile_top3", [])
                if top3:
                    yield _sse("debug_profile", {
                        "top3": top3,
                        "selected": user_intent.get("matched_profile_id", "?"),
                    })

            # V2: PreferenceManager 偏好融合 + 权重计算
            dynamic_weights = None
            demand_vector = user_intent.get("_demand_vector", {})
            pref_manager = None
            if request.user_id:
                yield _sse("phase", {"phase": "identifying", "message": "正在识别用户身份..."})
                from backend.services.preference_manager import PreferenceManager
                from backend.services.holiday_utils import build_context
                from backend.services.perception import PerceptionService

                pref_manager = PreferenceManager.from_user_id(request.user_id)

                # 构建当前上下文
                if request.current_context:
                    current_context = request.current_context
                else:
                    # 自动采集
                    perception = PerceptionService()
                    pctx = await perception.get_context()
                    current_context = build_context(
                        weather=pctx.weather,
                        temperature=pctx.temperature,
                        hour_of_day=pctx.hour_of_day,
                        day_of_week=pctx.day_of_week,
                        season=pctx.season,
                    )

                # 获取用户状态用于调试（仅开发环境）
                if settings.debug:
                    user_status = await pref_manager.get_user_status(current_context)
                    yield _sse("debug_preference", {
                        "user_id": request.user_id,
                        "is_new": user_status.get("is_new", True),
                        "interaction_count": user_status.get("interaction_count", 0),
                        "context_info": user_status.get("context_info", ""),
                        "context_hints": user_status.get("context_hints", []),
                        "greeting": user_status.get("greeting", ""),
                    })

                # Phase: LTM 预测
                yield _sse("phase", {"phase": "ltm_predict", "message": "正在根据历史预测偏好..."})

                # 用 LTM 预测合并偏好
                prediction = await pref_manager.ltm.predict_preferences(
                    request.user_id, current_context
                )
                if prediction.get("data_points", 0) > 0:
                    from backend.services.intent_parser import merge_user_preference
                    user_intent = merge_user_preference(
                        user_intent,
                        user_stated_prefs=None,
                        ltm_prediction=prediction,
                    )

                if settings.debug:
                    yield _sse("debug_ltm", {
                        "data_points": prediction.get("data_points", 0),
                        "confidence": prediction.get("confidence", 0.0),
                        "predicted_pace": prediction.get("predicted_pace"),
                        "predicted_budget": prediction.get("predicted_budget", 0),
                        "predicted_categories": prediction.get("predicted_categories", []),
                        "predicted_emotion_need": prediction.get("predicted_emotion_need"),
                        "context_matched": prediction.get("data_points", 0) > 0,
                    })

                # Phase: 权重映射
                yield _sse("phase", {"phase": "weight_mapping", "message": "正在计算求解权重..."})

                # 用 WeightMapper 算动态权重（demand_vector 已在 parse_intent 中提取）
                demand_vector = user_intent.get("_demand_vector", {})
                dynamic_weights = pref_manager.compute_solver_weights(demand_vector)
                if settings.debug:
                    yield _sse("debug_weight_mapper", {
                        "demand_vector": demand_vector,
                        "computed_weights": dynamic_weights,
                        "user_deltas": pref_manager.mapper._deltas if pref_manager.mapper else {},
                        "summary": pref_manager.mapper.summary() if pref_manager.mapper else "默认（新用户）",
                        "confidence": {},
                    })

            # 在 user_intent 中保存动态权重、需求向量、用户ID和出发位置（供对话阶段使用）
            user_intent["_dynamic_weights"] = dynamic_weights
            user_intent["_demand_vector"] = demand_vector
            if request.user_id:
                user_intent["_user_id"] = request.user_id
            if request.start_location:
                user_intent["start_location"] = request.start_location
            user_intent["_raw_input"] = request.user_input

            # Phase 2: 搜索候选 + 城市过滤
            yield _sse("phase", {"phase": "searching", "message": f"正在为你寻找合适的地方..."})

            # ══════════════════════════════════════════════════
            # C版本主路径：分布式智能体网络
            # ══════════════════════════════════════════════════
            try:
                from backend.agents_v3 import get_graph_c, TravelState

                yield _sse("phase", {"phase": "agents", "message": "7个智能体正在并行规划..."})

                c_graph = get_graph_c()

                # SSE queue for real-time agent events
                sse_queue: asyncio.Queue = asyncio.Queue()
                c_state: TravelState = {
                    "user_input": request.user_input,
                    "proposals": [],
                    "negotiation_msgs": [],
                    "errors": [],
                    "sse_queue": sse_queue,
                }

                # Run graph + drain SSE queue in parallel
                async def _run_graph():
                    return await asyncio.wait_for(c_graph.ainvoke(c_state), timeout=120)

                graph_task = asyncio.create_task(_run_graph())

                # Drain SSE events from agents while graph runs
                while not graph_task.done():
                    try:
                        event_type, event_data = await asyncio.wait_for(sse_queue.get(), timeout=0.3)
                        yield _sse(event_type, event_data)
                        await asyncio.sleep(0)  # yield control → flush to network
                    except asyncio.TimeoutError:
                        continue

                # Drain remaining events after graph completes
                while not sse_queue.empty():
                    event_type, event_data = sse_queue.get_nowait()
                    yield _sse(event_type, event_data)
                    await asyncio.sleep(0)

                c_result = await graph_task

                c_route = c_result.get("route", {})
                c_narrative = c_result.get("narrative", {})
                c_steps = c_route.get("route", []) if c_route else []

                if not c_steps:
                    logger.warning("C版本返回空路线，降级到原管线")
                    raise RuntimeError("C版本空路线")

                # 发送C版本Agent信息（仅开发环境）
                if settings.debug:
                    proposals = c_result.get("proposals", [])
                    agent_types = list(set(p.get("agent", "?") for p in proposals))
                    yield _sse("debug_agents", {
                        "version": "C",
                        "agent_count": len(proposals),
                        "agents": agent_types,
                        "conflicts": len(c_result.get("conflicts", [])),
                    })

                # 逐步返回步骤（兼容前端SSE格式）
                n_steps = c_narrative.get("steps", []) if c_narrative else []
                for i, step in enumerate(c_steps):
                    ns = n_steps[i] if i < len(n_steps) else {}
                    step_data = {
                        "index": i + 1,
                        "poi": step.get("poi", {}),
                        "arrival_time": step.get("arrival_time"),
                        "departure_time": step.get("departure_time"),
                        "narrative": ns.get("description", "") if isinstance(ns, dict) else str(ns),
                        "emotion_design": ns.get("emotion_design", "") if isinstance(ns, dict) else "",
                        "scene_tags": step.get("poi", {}).get("_scene_tags", []),
                    }
                    yield _sse("step", step_data)
                    await asyncio.sleep(0.05)

                # 完成
                route_id = uuid.uuid4().hex[:8]
                yield _sse("done", {
                    "route_id": route_id,
                    "full_route": c_route,
                    "version": "C-分布式智能体",
                })

                # 缓存route用于对话
                c_route["narrative"] = c_narrative
                c_route["user_intent"] = user_intent
                route_cache.set(route_id, c_route)

                return  # C版本路径结束，不走老管线

            except Exception as c_err:
                logger.error(f"C版本执行失败: {c_err}")
                yield _sse("error", {"error": "路线规划失败，请重试"})
                return

        except Exception:
            logger.exception("规划路线时出错")
            # 不向客户端暴露内部错误详情
            yield _sse("error", {"error": "服务器内部错误，请稍后重试"})
        finally:
            _plan_concurrent -= 1

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /api/route/{route_id} -- 获取路线详情
# ---------------------------------------------------------------------------


@app.get(
    "/api/route/{route_id}",
    summary="获取路线详情",
    description=(
        "根据路线ID获取已规划路线的完整数据。\n\n"
        "路线数据由 `/api/plan` 接口生成并缓存，`route_id` 在规划完成时返回。\n\n"
        "返回内容包括：路线步骤、情绪曲线、费用估算、未使用候选、文案等。"
    ),
    response_description="完整路线数据",
    responses={
        200: {
            "description": "路线详情",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/RouteResult"},
                }
            },
        },
        404: {
            "description": "路线不存在",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {"detail": "Route not found"},
                }
            },
        },
    },
    tags=["路线管理"],
)
async def get_route(route_id: str):
    """
    获取已规划路线的完整数据。

    路线数据保存在内存缓存中，服务重启后失效。
    """
    route_data = route_cache.get(route_id)
    if route_data is None:
        raise CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="Route not found",
            details={"route_id": route_id},
        )
    return route_data


# ---------------------------------------------------------------------------
# GET /api/route/{route_id}/adjust -- 调整路线（query param）
# ---------------------------------------------------------------------------


@app.get(
    "/api/route/{route_id}/adjust",
    summary="通过指令调整路线（快捷方式）",
    description=(
        "通过GET请求的query参数传入指令来调整已规划的路线。\n\n"
        "这是 `/api/dialogue/{session_id}` 的快捷方式，session_id 即 route_id。\n\n"
        "## 支持的指令\n\n"
        "| 类型 | 示例 |\n"
        "|------|------|\n"
        '| 替换景点 | "换掉故宫"、"不要第二个" |\n'
        '| 调整节奏 | "太赶了"、"轻松一点" |\n'
        '| 调整预算 | "太贵了"、"便宜点" |\n'
        '| 调整时间 | "早一点"、"5点前结束" |\n'
        '| 重新规划 | "重新来"、"再来一次" |'
    ),
    response_description="调整结果，包含系统回复、更新后的路线和变更记录",
    responses={
        200: {
            "description": "调整成功",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/DialogueResult"},
                }
            },
        },
        400: {
            "description": "指令无法识别或对话轮次超限",
        },
        404: {
            "description": "路线不存在",
        },
    },
    tags=["对话"],
)
async def adjust_route(route_id: str, instruction: str):
    """
    通过对话指令调整路线（GET快捷方式）。

    自动创建对话会话（如果不存在），然后处理用户的调整指令。
    """
    route = route_cache.get(route_id)
    if route is None:
        raise CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="Route not found",
            details={"route_id": route_id},
        )
    user_intent = route.get("user_intent", {})

    from backend.services.dialogue import dialogue_engine

    # 确保有会话
    session = await dialogue_engine.get_session(route_id)
    if not session:
        session = await dialogue_engine.create_session(route_id, route, user_intent)

    result = await dialogue_engine.process_instruction(route_id, instruction)

    # 更新缓存
    if "route" in result:
        route_cache.set(route_id, result["route"])

    # 记录反馈到 LTM
    if result.get("changes_made") and user_intent.get("_user_id"):
        try:
            from backend.services.preference_manager import PreferenceManager
            pref_mgr = PreferenceManager.from_user_id(user_intent["_user_id"])
            await pref_mgr._ensure_init()
            await pref_mgr.record_feedback(
                demand_vector=user_intent.get("_demand_vector", {}),
                applied_weights=user_intent.get("_dynamic_weights", {}),
                feedback="modified",
                modification_hint=instruction,
            )
        except Exception as fb_err:
            logger.warning(f"反馈记录失败（不影响主流程）: {fb_err}")

    return result


# ---------------------------------------------------------------------------
# POST /api/dialogue/{session_id} -- 对话接口
# ---------------------------------------------------------------------------


@app.post(
    "/api/dialogue/{session_id}",
    summary="对话式路线调整",
    description=(
        "通过多轮对话对已规划路线进行调整。\n\n"
        "`session_id` 通常为 `/api/plan` 返回的 `route_id`。\n\n"
        "## 指令分类\n\n"
        "系统基于关键词自动分类用户指令：\n\n"
        "### 替换指令\n"
        "触发词：换、替换、不喜欢、不要、去掉\n\n"
        '- "换掉第二个景点" → 按序号替换\n'
        '- "不喜欢故宫" → 按名称替换\n'
        "- 替换时自动选择同类目、情绪标签最相似的候选项\n\n"
        "### 节奏调整\n"
        "触发词：赶、累、轻松、慢、快、紧凑\n\n"
        '- "太赶了" / "想轻松点" → 切换为闲逛型\n'
        '- "太慢了" / "紧凑一些" → 切换为特种兵型\n'
        "- 调整后自动重新求解路线\n\n"
        "### 预算调整\n"
        "触发词：贵、便宜、省钱、预算\n\n"
        '- "太贵了" / "便宜点" → 预算降低20%\n'
        '- "可以多花点" → 预算提高30%\n'
        "- 调整后重新筛选候选并求解\n\n"
        "### 时间调整\n"
        "触发词：早、晚、时间、点之前\n\n"
        '- "早上8点出发" → 设置出发时间\n'
        '- "5点前结束" → 设置结束时间\n'
        '- "早一点" → 出发时间提前1小时\n\n'
        "### 重新规划\n"
        "触发词：不行、重新、再来\n\n"
        "- 使用当前意图重新求解路线\n\n"
        "## 对话限制\n\n"
        "- 每个会话最多 **10轮** 对话\n"
        "- 超过后需重新调用 `/api/plan` 开始新规划"
    ),
    response_description="调整结果",
    responses={
        200: {
            "description": "调整成功",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/DialogueResult"},
                    "examples": {
                        "replace": {
                            "summary": "替换景点",
                            "value": {
                                "reply": "好的，我已经把'故宫'换成了'颐和园'。",
                                "route": {"route": [], "emotion_curve": []},
                                "changes_made": [
                                    {
                                        "type": "replace",
                                        "original": "故宫",
                                        "replacement": "颐和园",
                                    }
                                ],
                            },
                        },
                        "pace": {
                            "summary": "调整节奏",
                            "value": {
                                "reply": "好的，我帮你调整为轻松型行程，增加休息时间。",
                                "route": {"route": [], "emotion_curve": []},
                                "changes_made": [
                                    {"type": "pace", "new_pace": "闲逛型"}
                                ],
                            },
                        },
                    },
                }
            },
        },
        400: {
            "description": "指令无法识别或对话轮次超限",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "examples": {
                        "unknown": {
                            "summary": "无法识别的指令",
                            "value": {
                                "detail": "抱歉，我没有理解你的意思。你可以试试：\n"
                                "- 换掉某个景点\n- 调整节奏\n- 调整预算\n- 调整时间\n- 重新规划"
                            },
                        },
                        "expired": {
                            "summary": "对话轮次超限",
                            "value": {"detail": "对话轮次已达上限，请重新开始"},
                        },
                    },
                }
            },
        },
        404: {
            "description": "会话不存在",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {"detail": "会话不存在"},
                }
            },
        },
    },
    tags=["对话"],
)
async def dialogue(session_id: str, request: AdjustRequest):
    """
    对话式路线调整。

    通过POST请求发送调整指令，系统自动分类指令类型并执行相应调整。
    """
    from backend.services.dialogue import dialogue_engine

    result = await dialogue_engine.process_instruction(session_id, request.instruction)

    # 同步更新路线缓存
    if "route" in result:
        route_cache.set(session_id, result["route"])

    # 记录反馈到 LTM
    if result.get("changes_made"):
        try:
            session = await dialogue_engine.get_session(session_id)
            if session and session.user_intent.get("_user_id"):
                from backend.services.preference_manager import PreferenceManager
                pref_mgr = PreferenceManager.from_user_id(session.user_intent["_user_id"])
                await pref_mgr._ensure_init()
                await pref_mgr.record_feedback(
                    demand_vector=session.user_intent.get("_demand_vector", {}),
                    applied_weights=session.user_intent.get("_dynamic_weights", {}),
                    feedback="modified",
                    modification_hint=request.instruction,
                )
        except Exception as fb_err:
            logger.warning(f"反馈记录失败（不影响主流程）: {fb_err}")

    return result


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup():
    from backend.config_loader import get_config_summary
    from backend.services.graceful_shutdown import get_shutdown_manager
    from backend.services.message_handlers import start_default_consumers
    from backend.services.session import get_session_manager
    from backend.services.task_queue import get_task_queue

    load_data()

    # 启动连接池管理器（数据库 + HTTP 连接池）
    from backend.services.pool_manager import get_pool_manager

    await get_pool_manager().start_all()

    # 初始化多级缓存（连接 Redis L2）
    await init_multilevel_cache()

    # 预热内存缓存（同步 L1）
    warmup_memory_caches()

    # 预热多级缓存（异步 L1 + L2）+ 启动定时预热
    from backend.startup.warmup import startup_warmup_with_background

    warmup, bg_task = await startup_warmup_with_background(interval=3600)
    app.state.cache_warmup = warmup
    app.state.cache_refresh_task = bg_task

    # 初始化会话管理器（连接 Redis）
    await get_session_manager().connect()

    await get_task_queue().start()

    # 启动消息队列默认消费者
    await start_default_consumers()

    # 启动服务注册中心
    from backend.services.registry import get_service_registry

    await get_service_registry().start()

    # ---- 注册优雅停机 ----
    from backend.services.audit_logger import get_audit_logger
    from backend.services.message_queue import close_message_queue

    shutdown_mgr = get_shutdown_manager()

    # 注册清理回调（按依赖逆序：先启动的后关闭）
    shutdown_mgr.register_cleanup("service_registry", get_service_registry().stop)
    shutdown_mgr.register_cleanup("message_queue", close_message_queue)
    shutdown_mgr.register_cleanup("session_manager", get_session_manager().close)
    shutdown_mgr.register_cleanup("task_queue", get_task_queue().stop)
    shutdown_mgr.register_cleanup("multilevel_cache", close_multilevel_cache)
    shutdown_mgr.register_cleanup("pool_manager", get_pool_manager().close_all)
    shutdown_mgr.register_cleanup(
        "audit_logger_flush",
        lambda: get_audit_logger().flush(),
    )

    # 注册操作系统信号处理器
    shutdown_mgr.register_signal_handlers()

    # 安全配置校验
    if not settings.security.encryption_key:
        logger.warning("SECURITY_ENCRYPTION_KEY 未设置 — 数据加密功能不可用")
    if settings.security.api_key:
        logger.info("API Key 认证已启用")
    else:
        logger.warning("SECURITY_API_KEY 未设置 — 管理端点无认证保护")

    logger.info("CityFlow API 启动完成 | %s", get_config_summary(settings))


@app.on_event("shutdown")
async def shutdown():
    from backend.services.graceful_shutdown import get_shutdown_manager

    # 停止缓存预热
    warmup = getattr(app.state, "cache_warmup", None)
    if warmup is not None:
        warmup.stop()

    # 取消定时缓存刷新任务
    refresh_task = getattr(app.state, "cache_refresh_task", None)
    if refresh_task is not None:
        refresh_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass

    # 通过停机管理器执行三阶段停机（排空请求 -> 清理资源）
    shutdown_mgr = get_shutdown_manager()
    stats = await shutdown_mgr.shutdown()

    if stats.timed_out:
        logger.warning("停机时有请求超时未完成")
    if stats.cleanup_errors:
        for err in stats.cleanup_errors:
            logger.error(err)

    logger.info("CityFlow API 已关闭")


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


@app.get(
    "/api/health",
    summary="健康检查",
    description="返回服务运行状态，可用于负载均衡器探活。",
    response_model=HealthResponse,
    responses={200: {"description": "服务正常"}},
    tags=["系统"],
)
async def health():
    """健康检查接口。"""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 缓存监控
# ---------------------------------------------------------------------------


@app.get(
    "/api/cache/stats",
    summary="缓存统计",
    description="返回各缓存实例的命中率和使用情况，用于性能监控。",
    tags=["系统"],
)
async def cache_stats():
    """返回缓存命中率统计。"""
    ml_cache = get_multilevel_cache()
    return {
        "l1_caches": {
            "route_cache": route_cache.stats,
            "distance_cache": distance_cache.stats,
            "poi_cache": poi_cache.stats,
            "profile_cache": profile_cache.stats,
            "general_cache": general_cache.stats,
        },
        "multilevel_cache": ml_cache.stats,
    }


# ---------------------------------------------------------------------------
# 前端静态文件（必须在所有 API 路由之后，否则 "/" 会拦截 API 请求）
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
_static = StaticFiles(directory=str(FRONTEND_DIR), html=True)
app.mount("/", _static, name="frontend")
