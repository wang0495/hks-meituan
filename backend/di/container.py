"""CityFlow 依赖注入容器。

支持三种注册方式：
- 实例注册：直接传入已构造的对象（可选单例）
- 工厂注册：传入 callable，每次 resolve 时调用
- 类型注册：传入类，容器自动构造（通过 inspect 解析 __init__ 参数）
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DIContainer:
    """依赖注入容器。"""

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}
        self._singletons: dict[str, Any] = {}
        self._factories: dict[str, Callable[..., Any]] = {}
        self._classes: dict[str, type] = {}

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------

    def register(self, name: str, instance: Any, *, singleton: bool = False) -> None:
        """注册一个已构造的服务实例。

        Parameters
        ----------
        name:
            服务名称，resolve 时使用。
        instance:
            服务实例。
        singleton:
            若为 True，实例存入单例池，多次 resolve 返回同一对象。
        """
        if singleton:
            self._singletons[name] = instance
        else:
            self._instances[name] = instance
        logger.info("服务注册: %s (singleton=%s)", name, singleton)

    def register_factory(self, name: str, factory: Callable[..., Any]) -> None:
        """注册工厂函数。

        每次 resolve 时都会调用 factory()，适合需要短生命周期的对象
        （如数据库会话、HTTP 客户端）。
        """
        self._factories[name] = factory
        logger.info("工厂注册: %s", name)

    def register_class(self, name: str, cls: type, *, singleton: bool = False) -> None:
        """注册一个类，容器在 resolve 时自动构造。

        构造参数通过递归解析 __init__ 的类型注解自动注入。
        """
        self._classes[name] = cls
        # 预热：如果是单例，立即构造并缓存
        if singleton:
            self._singletons[name] = self._build(cls)
            logger.info("类注册(单例): %s", name)
        else:
            logger.info("类注册: %s", name)

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def resolve(self, name: str) -> Any:
        """按名称解析服务。

        查找顺序：单例 -> 实例 -> 工厂 -> 类型自动构造。
        """
        if name in self._singletons:
            return self._singletons[name]

        if name in self._instances:
            return self._instances[name]

        if name in self._factories:
            return self._factories[name]()

        if name in self._classes:
            return self._build(self._classes[name])

        raise ServiceNotFoundError(f"服务未注册: {name}")

    def resolve_type(self, cls: type[T]) -> T:
        """按类型解析服务（使用类名作为键）。"""
        return self.resolve(cls.__name__)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _build(self, cls: type) -> Any:
        """通过类型注解递归构造实例。"""
        sig = inspect.signature(cls.__init__)  # type: ignore[misc]
        kwargs: dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param.annotation is inspect.Parameter.empty:
                raise ServiceNotFoundError(
                    f"类 {cls.__name__} 的参数 {param_name} 缺少类型注解，"
                    "无法自动注入"
                )
            # 从类型注解推断服务名
            dep_name = param.annotation.__name__
            kwargs[param_name] = self.resolve(dep_name)
        return cls(**kwargs)

    def reset(self) -> None:
        """清空所有注册（用于测试）。"""
        self._instances.clear()
        self._singletons.clear()
        self._factories.clear()
        self._classes.clear()
        logger.info("DI 容器已重置")


class ServiceNotFoundError(KeyError):
    """服务未注册时抛出。"""

    pass


# ------------------------------------------------------------------
# 全局容器
# ------------------------------------------------------------------

_container: DIContainer | None = None


def get_container() -> DIContainer:
    """获取全局 DI 容器（懒初始化）。"""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def reset_container() -> None:
    """重置全局容器（用于测试）。"""
    global _container
    _container = None


# ------------------------------------------------------------------
# 注入装饰器
# ------------------------------------------------------------------


def inject(*names: str) -> Callable[..., Any]:
    """注入装饰器：自动从容器中解析服务并传入函数。

    用法::

        @inject("intent_parser", "route_solver")
        async def plan_route(intent_parser, route_solver, user_input: str):
            ...

    装饰后调用 ``plan_route(user_input="...")`` 即可，
    intent_parser 和 route_solver 会自动注入。
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                container = get_container()
                services = [container.resolve(n) for n in names]
                return await func(*services, *args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            container = get_container()
            services = [container.resolve(n) for n in names]
            return func(*services, *args, **kwargs)

        return sync_wrapper

    return decorator
