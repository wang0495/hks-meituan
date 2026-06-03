"""CityFlow 本地化中间件测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


# 直接加载模块文件，绕过 middleware/__init__.py 的传递导入问题
# （ConfigMiddleware 依赖 backend.config.get_settings，该符号在 config 包中缺失）
def _load_locale_middleware():  # type: ignore[no-untyped-def]
    module_path = Path(__file__).resolve().parent.parent / "middleware" / "locale.py"
    spec = importlib.util.spec_from_file_location("backend.middleware.locale", module_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["backend.middleware.locale"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_mod = _load_locale_middleware()
LocaleMiddleware = _mod.LocaleMiddleware


@pytest.fixture()
def app() -> FastAPI:
    """创建测试用 FastAPI 应用。"""
    _app = FastAPI()
    _app.add_middleware(LocaleMiddleware)

    @_app.get("/test")
    async def test_endpoint(request: Request) -> dict:
        return {"locale": request.state.locale}

    return _app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# _parse_locale 静态方法测试
# ---------------------------------------------------------------------------


class TestParseLocale:
    """Accept-Language 解析测试。"""

    def test_empty_string(self) -> None:
        assert LocaleMiddleware._parse_locale("") == "zh_CN"

    def test_simple_en(self) -> None:
        assert LocaleMiddleware._parse_locale("en") == "en_US"

    def test_simple_zh(self) -> None:
        assert LocaleMiddleware._parse_locale("zh") == "zh_CN"

    def test_en_us_full(self) -> None:
        assert LocaleMiddleware._parse_locale("en-US") == "en_US"

    def test_zh_cn_full(self) -> None:
        assert LocaleMiddleware._parse_locale("zh-CN") == "zh_CN"

    def test_en_gb(self) -> None:
        assert LocaleMiddleware._parse_locale("en-GB") == "en_GB"

    def test_zh_tw(self) -> None:
        assert LocaleMiddleware._parse_locale("zh-TW") == "zh_TW"

    def test_zh_hk(self) -> None:
        assert LocaleMiddleware._parse_locale("zh-HK") == "zh_HK"

    def test_quality_values(self) -> None:
        """q 值高的语言优先。"""
        header = "en-US;q=0.9,zh-CN;q=1.0"
        assert LocaleMiddleware._parse_locale(header) == "zh_CN"

    def test_quality_values_en_first(self) -> None:
        header = "zh-CN;q=0.5,en-US;q=1.0"
        assert LocaleMiddleware._parse_locale(header) == "en_US"

    def test_multiple_with_defaults(self) -> None:
        """未指定 q 值时默认 1.0。"""
        header = "fr;q=0.8,en-US,zh-CN;q=0.5"
        assert LocaleMiddleware._parse_locale(header) == "en_US"

    def test_unknown_locale_fallback(self) -> None:
        assert LocaleMiddleware._parse_locale("fr") == "zh_CN"

    def test_prefix_matching(self) -> None:
        """语言前缀应匹配。"""
        assert LocaleMiddleware._parse_locale("en-GB,en;q=0.9") == "en_GB"


# ---------------------------------------------------------------------------
# 中间件集成测试
# ---------------------------------------------------------------------------


class TestLocaleMiddlewareIntegration:
    """中间件集成测试。"""

    def test_default_locale_is_zh_cn(self, client: TestClient) -> None:
        """无 Accept-Language 时默认 zh_CN。"""
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json()["locale"] == "zh_CN"
        assert resp.headers.get("Content-Language") == "zh_CN"

    def test_accept_language_en(self, client: TestClient) -> None:
        resp = client.get("/test", headers={"Accept-Language": "en-US"})
        assert resp.json()["locale"] == "en_US"
        assert resp.headers.get("Content-Language") == "en_US"

    def test_accept_language_zh(self, client: TestClient) -> None:
        resp = client.get("/test", headers={"Accept-Language": "zh-CN"})
        assert resp.json()["locale"] == "zh_CN"
        assert resp.headers.get("Content-Language") == "zh_CN"

    def test_content_language_header_present(self, client: TestClient) -> None:
        """每个响应都应包含 Content-Language 头。"""
        resp = client.get("/test")
        assert "Content-Language" in resp.headers

    def test_unsupported_locale_falls_back(self, client: TestClient) -> None:
        """不受支持的语言应回退到默认。"""
        resp = client.get("/test", headers={"Accept-Language": "fr-FR"})
        assert resp.json()["locale"] == "zh_CN"

    def test_en_gb_falls_back(self, client: TestClient) -> None:
        """en_GB 不在翻译中时应回退。"""
        resp = client.get("/test", headers={"Accept-Language": "en-GB"})
        # en_GB 无翻译文件，应降级
        assert resp.json()["locale"] in ("en_US", "zh_CN")
