"""自定义 Swagger UI / ReDoc 文档页面。

注入 CityFlow 品牌主题 CSS，替换默认样式。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse

from backend.docs.config import (
    _FAVICON_URL,
    _REDOC_JS_URL,
    _SWAGGER_CSS_URL,
    _SWAGGER_JS_URL,
    get_swagger_css_content,
)

if TYPE_CHECKING:
    from fastapi import FastAPI


def register_docs_endpoints(app: FastAPI) -> None:
    """注册 /docs 和 /redoc 自定义端点（需先禁用默认端点）。

    在 main.py 中调用::

        app = FastAPI(docs_url=None, redoc_url=None)
        register_docs_endpoints(app)
    """

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """带 CityFlow 主题的 Swagger UI 页面。"""
        base_html = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url=_SWAGGER_JS_URL,
            swagger_css_url=_SWAGGER_CSS_URL,
            swagger_favicon_url=_FAVICON_URL,
            init_oauth={
                "clientId": "cityflow-docs",
                "appName": "CityFlow",
                "usePkceWithAuthorizationCodeGrant": True,
            },
        )

        # 注入自定义 CSS 到 <head> 中
        custom_css = get_swagger_css_content()
        if custom_css:
            style_tag = f'<style type="text/css">{custom_css}</style>'
            body = base_html.body.decode("utf-8") if hasattr(base_html, "body") else str(base_html)
            if "</head>" in body:
                body = body.replace("</head>", f"{style_tag}</head>")
            return HTMLResponse(content=body)

        return base_html

    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc_html():
        """带 CityFlow 品牌的 ReDoc 文档页面。"""
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - API 参考文档",
            redoc_js_url=_REDOC_JS_URL,
            redoc_favicon_url=_FAVICON_URL,
        )

    @app.get("/docs/health", include_in_schema=False)
    async def docs_health():
        """文档页面健康检查（可用于监控文档服务是否可用）。"""
        return {"status": "ok", "service": "docs"}
