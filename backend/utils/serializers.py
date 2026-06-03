"""CityFlow 序列化装饰器。

为函数/路由提供自动序列化/反序列化能力。
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from backend.utils.serialization import serializer

F = TypeVar("F", bound=Callable[..., Any])


def serialize_output(compress: bool = False) -> Callable[[F], F]:
    """将函数返回值自动序列化为 bytes。

    适用于需要直接返回序列化数据的场景（如缓存、消息队列）。

    Args:
        compress: 是否启用 gzip 压缩。

    Example::

        @serialize_output(compress=True)
        async def get_large_data() -> dict:
            return {"items": list(range(10000))}
    """

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> bytes:
                result = await func(*args, **kwargs)
                return serializer.dumps(result, compress=compress)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> bytes:
            result = func(*args, **kwargs)
            return serializer.dumps(result, compress=compress)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def deserialize_input(compressed: bool = False) -> Callable[[F], F]:
    """将函数的 bytes 类型参数自动反序列化。

    仅处理位置参数中 `bytes` 类型的值，其他参数原样传递。

    Args:
        compressed: 输入数据是否经过 gzip 压缩。

    Example::

        @deserialize_input(compressed=True)
        async def process_data(payload: dict) -> dict:
            return {"processed": True, **payload}
    """

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                new_args = _deserialize_args(args, compressed)
                return await func(*new_args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            new_args = _deserialize_args(args, compressed)
            return func(*new_args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _deserialize_args(args: tuple[Any, ...], compressed: bool) -> list[Any]:
    """反序列化参数中的 bytes 值。"""
    result: list[Any] = []
    for arg in args:
        if isinstance(arg, bytes):
            try:
                result.append(serializer.loads(arg, compressed=compressed))
            except Exception:
                # 无法反序列化的 bytes 原样保留
                result.append(arg)
        else:
            result.append(arg)
    return result
