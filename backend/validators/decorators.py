"""校验装饰器。

为 FastAPI 路由函数提供声明式的数据校验能力：
- validate_request: 在函数执行前校验请求参数
- validate_response: 在函数执行后校验返回值
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Type

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from backend.errors import CityFlowException

logger = logging.getLogger(__name__)


def validate_request(model: Type[BaseModel]) -> Any:
    """请求校验装饰器。

    将函数的 kwargs 按 model 进行校验，校验通过后用清理后的值替换原参数。

    Usage::

        @validate_request(PlanRequestValidator)
        async def plan_route(user_input: str):
            ...

    Args:
        model: Pydantic 模型类，用于校验请求数据。

    Returns:
        装饰后的异步函数。
    """

    def decorator(func: Any) -> Any:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                validated = model(**kwargs)
                # 用校验后的值覆盖原始参数
                kwargs.update(validated.model_dump())
                return await func(*args, **kwargs)
            except ValidationError as e:
                errors = e.errors()
                detail = "; ".join(
                    f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                    for err in errors
                )
                logger.warning("请求校验失败: %s", detail)
                raise HTTPException(status_code=422, detail=detail) from e
            except CityFlowException:
                raise
            except Exception as e:
                logger.exception("请求校验异常")
                raise HTTPException(status_code=500, detail="请求处理异常") from e

        return wrapper

    return decorator


def validate_response(model: Type[BaseModel]) -> Any:
    """响应校验装饰器。

    将函数的返回值按 model 进行校验，确保响应数据结构正确。

    Usage::

        @validate_response(SearchResponse)
        async def search_pois(request: SearchRequest):
            return {"pois": [...], "total": 10}

    Args:
        model: Pydantic 模型类，用于校验响应数据。

    Returns:
        装饰后的异步函数。
    """

    def decorator(func: Any) -> Any:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            try:
                validated = model(**result)
                return validated.model_dump()
            except ValidationError as e:
                logger.error(
                    "响应校验失败 [%s]: %s",
                    func.__qualname__,
                    e.errors(),
                )
                raise HTTPException(
                    status_code=500,
                    detail="响应数据格式错误",
                ) from e

        return wrapper

    return decorator
