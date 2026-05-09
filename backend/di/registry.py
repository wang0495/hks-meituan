"""CityFlow 服务注册表。

集中注册所有核心服务到 DI 容器。
应用启动时调用 ``register_services()`` 完成初始化。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_services() -> None:
    """注册所有核心服务到 DI 容器。

    - 单例服务：intent_parser, route_solver, narrator（函数级服务）
    - 工厂服务：db_session, http_pool（每次 resolve 创建新实例）

    使用延迟导入避免循环依赖和模块级副作用。
    """
    from backend.di.container import get_container
    from backend.services.http_pool import get_http_pool
    from backend.services.intent_parser import parse_intent
    from backend.services.narrator import generate_narrative
    from backend.services.solver import solve_route

    container = get_container()

    # ------------------------------------------------------------------
    # 单例服务（函数级，注册为 callable）
    # ------------------------------------------------------------------
    container.register("intent_parser", parse_intent, singleton=True)
    container.register("route_solver", solve_route, singleton=True)
    container.register("narrator", generate_narrative, singleton=True)

    # ------------------------------------------------------------------
    # 工厂服务（短生命周期，每次 resolve 创建新实例）
    # ------------------------------------------------------------------
    def _db_session_factory() -> Any:
        from backend.database.base import async_session_factory

        return async_session_factory()

    container.register_factory("db_session", _db_session_factory)
    container.register_factory("http_pool", get_http_pool)

    logger.info("DI 服务注册完成")
