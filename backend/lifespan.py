"""应用生命周期管理 — startup / shutdown。"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from backend.services.cache import (
    close_multilevel_cache,
    distance_cache,
    general_cache,
    get_multilevel_cache,
    init_multilevel_cache,
    poi_cache,
    profile_cache,
    route_cache,
)
from backend.services.cache_warmup import warmup_memory_caches
from backend.services.data_service import load_data

logger = logging.getLogger(__name__)


async def startup(app: FastAPI) -> None:
    """应用启动时执行的初始化逻辑。"""
    from backend.config import settings
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

    logger.info("CityFlow API 启动完成 | %s", get_config_summary(settings))


async def shutdown(app: FastAPI) -> None:
    """应用关闭时执行的清理逻辑。"""
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


def register_lifecycle(app: FastAPI) -> None:
    """将 startup / shutdown 注册到 FastAPI 应用。"""

    @app.on_event("startup")
    async def _startup():
        await startup(app)

    @app.on_event("shutdown")
    async def _shutdown():
        await shutdown(app)
