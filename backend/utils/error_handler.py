"""CityFlow 错误处理装饰器。

为 service 层函数提供统一的异常包装，把底层异常
转换为 CityFlowException 子类，避免在每个函数里重复 try/except。
"""

from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any

from backend.errors import CityFlowException, ErrorCode, LLMServiceError

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def handle_errors(default_message: str = "操作失败") -> Callable:
    """通用错误处理装饰器。

    - CityFlowException 原样抛出（不做二次包装）。
    - 其他异常包装为 CityFlowException(INTERNAL_ERROR)。

    用法::

        @handle_errors("意图解析失败")
        async def parse_intent(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except CityFlowException:
                raise
            except Exception as e:
                logger.exception("Error in %s: %s", func.__name__, e)
                raise CityFlowException(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=default_message,
                    details={"original_error": str(e)},
                ) from e

        return wrapper

    return decorator


def handle_llm_errors(func: Callable) -> Callable:
    """LLM 调用专用错误处理装饰器。

    - TimeoutError -> LLM_SERVICE_ERROR (超时)
    - 其他异常 -> LLM_SERVICE_ERROR (通用)

    用法::

        @handle_llm_errors
        async def call_llm(prompt: str) -> str:
            ...
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except TimeoutError:
            logger.warning("LLM timeout in %s", func.__name__)
            raise LLMServiceError(
                message="LLM服务超时",
                details={"timeout": True},
            ) from None
        except CityFlowException:
            raise
        except Exception as e:
            logger.exception("LLM error in %s: %s", func.__name__, e)
            raise LLMServiceError(
                message="LLM服务异常",
                details={"original_error": str(e)},
            ) from e

    return wrapper
