"""CityFlow 全局异常处理器。

注册到 FastAPI app 后，所有 CityFlowException 和未捕获异常
都会被统一拦截并返回标准化 JSON 响应。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)


async def cityflow_exception_handler(request: Request, exc: CityFlowException) -> JSONResponse:
    """处理 CityFlowException -- 业务异常。"""
    logger.error(
        "CityFlow error: %s - %s",
        exc.code.name,
        exc.message,
        extra={
            "error_code": exc.code.value,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details,
        },
    )
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底处理未预期异常，不向客户端暴露内部细节。"""
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "服务器内部错误",
            }
        },
    )


def setup_error_handlers(app: FastAPI) -> None:
    """将异常处理器注册到 FastAPI 应用。

    调用一次即可，放在 app 创建之后、路由注册之前或之后均可。
    """
    app.add_exception_handler(CityFlowException, cityflow_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, general_exception_handler)  # type: ignore[arg-type]
