"""CityFlow API -- 应用工厂 + 中间件配置。

路由处理在 backend.routers.plan 模块中。
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.docs import custom_openapi, register_docs_endpoints
from backend.middleware import (
    APIVersionMiddleware,
    ConfigMiddleware,
    InputValidationMiddleware,
    PrometheusMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    SessionMiddleware,
    ShutdownMiddleware,
    setup_error_handlers,
)
from backend.middleware.auth import APIKeyAuthMiddleware
from backend.routers import (
    audit,
    data,
    health,
    llm,
    mq,
    plan,
    poi,
    pool,
    registry,
    session,
    sse,
    tasks,
    v1,
    v2,
    websocket,
)
from backend.routers.graphql import router as graphql_router
from backend.routers.metrics import router as metrics_router
from backend.services.cache import (
    close_multilevel_cache,
    init_multilevel_cache,
)
from backend.services.cache_warmup import warmup_memory_caches
from backend.services.data_service import load_data

logger = logging.getLogger(__name__)

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
# 生命周期（lifespan 上下文管理器，替代已废弃的 on_event）
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.config_loader import get_config_summary
    from backend.services.graceful_shutdown import get_shutdown_manager
    from backend.services.message_handlers import start_default_consumers
    from backend.services.session import get_session_manager
    from backend.services.task_queue import get_task_queue

    # ---- startup ----

    # 初始化 Sentry（DSN 未配置时自动跳过）
    try:
        from backend.monitoring.sentry import init_sentry

        init_sentry()
    except Exception as e:
        logger.debug("Sentry初始化失败: %s", e)

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

    async def _flush_audit():
        get_audit_logger().flush()

    shutdown_mgr.register_cleanup("audit_logger_flush", _flush_audit)

    # 注册操作系统信号处理器
    shutdown_mgr.register_signal_handlers()

    # 安全配置校验
    if not settings.security.encryption_key:
        logger.warning("SECURITY_ENCRYPTION_KEY 未设置 — 数据加密功能不可用")
    if settings.security.api_key:
        logger.info("API Key 认证已启用")
    else:
        logger.warning(
            "SECURITY_API_KEY 未设置 — 管理端点无认证保护。" "建议在.env中设置 SECURITY_API_KEY"
        )

    logger.info("CityFlow API 启动完成 | %s", get_config_summary(settings))

    yield  # ---- app is running ----

    # ---- shutdown ----
    from backend.services.graceful_shutdown import get_shutdown_manager as _get_sd

    # 停止缓存预热
    warmup_obj = getattr(app.state, "cache_warmup", None)
    if warmup_obj is not None:
        warmup_obj.stop()

    # 取消定时缓存刷新任务
    refresh_task = getattr(app.state, "cache_refresh_task", None)
    if refresh_task is not None:
        refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task

    # 通过停机管理器执行三阶段停机（排空请求 -> 清理资源）
    shutdown_mgr = _get_sd()
    stats = await shutdown_mgr.shutdown()

    if stats.timed_out:
        logger.warning("停机时有请求超时未完成")
    if stats.cleanup_errors:
        for err in stats.cleanup_errors:
            logger.error(err)

    logger.info("CityFlow API 已关闭")


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
    lifespan=lifespan,
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

# 速率限制（测试时跳过）
if not os.environ.get("TESTING"):
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
app.include_router(plan.router)
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
# 前端静态文件（必须在所有 API 路由之后，否则 "/" 会拦截 API 请求）
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
_static = StaticFiles(directory=str(FRONTEND_DIR), html=True)
app.mount("/", _static, name="frontend")
