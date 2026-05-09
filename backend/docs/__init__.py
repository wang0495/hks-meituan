"""CityFlow 文档子包。

提供 OpenAPI schema 生成和自定义文档页面端点。

用法（main.py 中）::

    from backend.docs import custom_openapi, register_docs_endpoints

    app.openapi = lambda: custom_openapi(app)
    register_docs_endpoints(app)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from backend.docs.config import get_openapi_examples, get_swagger_css_content
from backend.docs.custom_swagger import register_docs_endpoints

__all__ = [
    "custom_openapi",
    "register_docs_endpoints",
    "get_swagger_css_content",
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
