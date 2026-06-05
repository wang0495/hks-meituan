"""CityFlow 文档子包。

提供 OpenAPI schema 生成和自定义文档页面端点。

用法（main.py 中）::

    from backend.docs import custom_openapi, register_docs_endpoints

    app.openapi = lambda: custom_openapi(app)
    register_docs_endpoints(app)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.openapi.utils import get_openapi

from backend.docs.config import get_openapi_examples, get_swagger_css_content
from backend.docs.custom_swagger import register_docs_endpoints

if TYPE_CHECKING:
    from fastapi import FastAPI

__all__ = [
    "custom_openapi",
    "get_swagger_css_content",
    "register_docs_endpoints",
]


def custom_openapi(app: FastAPI) -> dict:
    """生成带自定义扩展字段的 OpenAPI schema（带缓存）。"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )

    # ---- 过滤管理端点，不对外暴露 ----
    admin_prefixes = (
        "/metrics",
        "/pool",
        "/tasks",
        "/mq/",
        "/cache/stats",
        "/health/pools",
        "/health/pool",
    )
    paths = openapi_schema.get("paths", {})
    admin_paths = [p for p in paths if any(p.startswith(pre) for pre in admin_prefixes)]
    for p in admin_paths:
        del paths[p]
    if admin_paths:
        import logging

        logging.getLogger(__name__).debug("OpenAPI: 隐藏了 %d 个管理端点", len(admin_paths))

    # ---- 附加自定义字段 ----

    # Logo（使用 config 中的路径）
    openapi_schema["info"]["x-logo"] = {
        "url": "/static/logo.png",
        "altText": "CityFlow Logo",
    }

    # 常用请求示例（从 config 模块加载）
    examples = get_openapi_examples()
    openapi_schema.setdefault("components", {}).setdefault("examples", {}).update(
        examples,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema
