"""CityFlow 统一错误处理机制测试。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.errors import (CityFlowException, DialogueError, ErrorCode,
                            IntentParseError, LLMServiceError,
                            NarrativeGenerationError, NoPOIsFoundError,
                            RateLimitError, RouteSolvingError)
from backend.middleware.error_handler import setup_error_handlers

# ---------------------------------------------------------------------------
# ErrorCode 测试
# ---------------------------------------------------------------------------


class TestErrorCode:
    """错误码枚举测试。"""

    def test_error_code_values_unique(self):
        """错误码值必须唯一。"""
        values = [code.value for code in ErrorCode]
        assert len(values) == len(set(values))

    def test_error_code_ranges(self):
        """错误码按段分类。"""
        assert ErrorCode.UNKNOWN_ERROR.value == 1000
        assert ErrorCode.UNAUTHORIZED.value == 2001
        assert ErrorCode.INTENT_PARSE_FAILED.value == 3001
        assert ErrorCode.INVALID_POI_DATA.value == 4001
        assert ErrorCode.LLM_SERVICE_ERROR.value == 5001


# ---------------------------------------------------------------------------
# CityFlowException 测试
# ---------------------------------------------------------------------------


class TestCityFlowException:
    """基础异常测试。"""

    def test_basic_creation(self):
        """创建基础异常。"""
        exc = CityFlowException(
            code=ErrorCode.INTERNAL_ERROR,
            message="测试错误",
        )
        assert exc.code == ErrorCode.INTERNAL_ERROR
        assert exc.message == "测试错误"
        assert exc.details == {}
        assert exc.status_code == 500

    def test_with_details(self):
        """带详情的异常。"""
        details = {"key": "value", "count": 42}
        exc = CityFlowException(
            code=ErrorCode.INVALID_REQUEST,
            message="参数错误",
            details=details,
        )
        assert exc.details == details

    def test_custom_status_code(self):
        """自定义 HTTP 状态码。"""
        exc = CityFlowException(
            code=ErrorCode.UNKNOWN_ERROR,
            message="自定义状态码",
            status_code=502,
        )
        assert exc.status_code == 502

    def test_to_dict_basic(self):
        """转换为基础字典。"""
        exc = CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="未找到",
        )
        d = exc.to_dict()
        assert d == {
            "error": {
                "code": 1002,
                "message": "未找到",
            }
        }

    def test_to_dict_with_details(self):
        """带详情的字典。"""
        exc = CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="未找到",
            details={"id": "abc123"},
        )
        d = exc.to_dict()
        assert d["error"]["details"] == {"id": "abc123"}

    def test_is_exception(self):
        """CityFlowException 是 Exception 子类。"""
        assert issubclass(CityFlowException, Exception)

    def test_str_representation(self):
        """字符串表示包含消息。"""
        exc = CityFlowException(
            code=ErrorCode.INTERNAL_ERROR,
            message="测试消息",
        )
        assert "测试消息" in str(exc)


# ---------------------------------------------------------------------------
# 异常子类测试
# ---------------------------------------------------------------------------


class TestExceptionSubclasses:
    """异常子类默认值测试。"""

    def test_intent_parse_error(self):
        exc = IntentParseError()
        assert exc.code == ErrorCode.INTENT_PARSE_FAILED
        assert exc.status_code == 400
        assert "意图解析" in exc.message

    def test_no_pois_found_error(self):
        exc = NoPOIsFoundError()
        assert exc.code == ErrorCode.NO_POIS_FOUND
        assert exc.status_code == 404

    def test_route_solving_error(self):
        exc = RouteSolvingError()
        assert exc.code == ErrorCode.ROUTE_SOLVING_FAILED
        assert exc.status_code == 500

    def test_narrative_generation_error(self):
        exc = NarrativeGenerationError()
        assert exc.code == ErrorCode.NARRATIVE_GENERATION_FAILED
        assert exc.status_code == 500

    def test_dialogue_error(self):
        exc = DialogueError()
        assert exc.code == ErrorCode.DIALOGUE_FAILED
        assert exc.status_code == 500

    def test_llm_service_error(self):
        exc = LLMServiceError()
        assert exc.code == ErrorCode.LLM_SERVICE_ERROR
        assert exc.status_code == 503

    def test_rate_limit_error(self):
        exc = RateLimitError()
        assert exc.code == ErrorCode.RATE_LIMITED
        assert exc.status_code == 429

    def test_custom_message(self):
        """子类支持自定义消息。"""
        exc = IntentParseError(message="自定义消息")
        assert exc.message == "自定义消息"

    def test_custom_details(self):
        """子类支持自定义详情。"""
        exc = LLMServiceError(details={"model": "gpt-4o"})
        assert exc.details == {"model": "gpt-4o"}


# ---------------------------------------------------------------------------
# 全局异常处理器测试
# ---------------------------------------------------------------------------


class TestGlobalErrorHandlers:
    """FastAPI 全局异常处理器测试。"""

    @pytest.fixture
    def app(self):
        app = FastAPI()
        setup_error_handlers(app)

        @app.get("/cityflow-error")
        async def cityflow_error():
            raise CityFlowException(
                code=ErrorCode.NOT_FOUND,
                message="资源不存在",
                details={"resource": "route"},
            )

        @app.get("/intent-error")
        async def intent_error():
            raise IntentParseError(message="无法解析")

        @app.get("/llm-error")
        async def llm_error():
            raise LLMServiceError()

        @app.get("/dialogue-error")
        async def dialogue_error():
            raise DialogueError(message="会话已过期")

        @app.get("/no-pois-error")
        async def no_pois_error():
            raise NoPOIsFoundError()

        @app.get("/rate-limit-error")
        async def rate_limit_error():
            raise RateLimitError()

        @app.get("/generic-error")
        async def generic_error():
            raise ValueError("未预期的错误")

        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app, raise_server_exceptions=False)

    def test_cityflow_exception_returns_json(self, client):
        """CityFlowException 返回标准化 JSON。"""
        resp = client.get("/cityflow-error")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == 1002
        assert body["error"]["message"] == "资源不存在"
        assert body["error"]["details"] == {"resource": "route"}

    def test_intent_parse_error_status(self, client):
        """IntentParseError 返回 400。"""
        resp = client.get("/intent-error")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == 3001

    def test_llm_service_error_status(self, client):
        """LLMServiceError 返回 503。"""
        resp = client.get("/llm-error")
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"]["code"] == 5001

    def test_dialogue_error_status(self, client):
        """DialogueError 返回 500。"""
        resp = client.get("/dialogue-error")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == 3005

    def test_no_pois_error_status(self, client):
        """NoPOIsFoundError 返回 404。"""
        resp = client.get("/no-pois-error")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == 3002

    def test_rate_limit_error_status(self, client):
        """RateLimitError 返回 429。"""
        resp = client.get("/rate-limit-error")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == 1005

    def test_generic_error_returns_500(self, client):
        """未预期异常返回 500 且不暴露内部细节。"""
        resp = client.get("/generic-error")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == 1003
        assert body["error"]["message"] == "服务器内部错误"
        # 不应包含 "ValueError" 等内部信息
        assert "ValueError" not in str(body)

    def test_error_response_format_consistency(self, client):
        """所有错误响应格式一致：{error: {code, message, [details]}}。"""
        for path in [
            "/cityflow-error",
            "/intent-error",
            "/llm-error",
            "/dialogue-error",
            "/no-pois-error",
            "/rate-limit-error",
            "/generic-error",
        ]:
            resp = client.get(path)
            body = resp.json()
            assert "error" in body, f"{path} 缺少 error 字段"
            assert "code" in body["error"], f"{path} 缺少 error.code"
            assert "message" in body["error"], f"{path} 缺少 error.message"
            assert isinstance(body["error"]["code"], int), f"{path} error.code 应为整数"


# ---------------------------------------------------------------------------
# 装饰器测试
# ---------------------------------------------------------------------------


class TestHandleErrorsDecorator:
    """handle_errors 装饰器测试。"""

    @pytest.mark.asyncio
    async def test_passes_through_cityflow_exception(self):
        """CityFlowException 原样抛出。"""
        from backend.utils.error_handler import handle_errors

        @handle_errors("测试失败")
        async def failing_func():
            raise IntentParseError(message="自定义意图错误")

        with pytest.raises(IntentParseError) as exc_info:
            await failing_func()
        assert exc_info.value.message == "自定义意图错误"

    @pytest.mark.asyncio
    async def test_wraps_generic_exception(self):
        """其他异常包装为 CityFlowException。"""
        from backend.utils.error_handler import handle_errors

        @handle_errors("操作失败")
        async def failing_func():
            raise RuntimeError("底层错误")

        with pytest.raises(CityFlowException) as exc_info:
            await failing_func()
        assert exc_info.value.code == ErrorCode.INTERNAL_ERROR
        assert exc_info.value.message == "操作失败"
        assert "底层错误" in exc_info.value.details["original_error"]

    @pytest.mark.asyncio
    async def test_success_passes_through(self):
        """正常执行不受影响。"""
        from backend.utils.error_handler import handle_errors

        @handle_errors("测试失败")
        async def success_func():
            return {"result": "ok"}

        result = await success_func()
        assert result == {"result": "ok"}


class TestHandleLLMErrorsDecorator:
    """handle_llm_errors 装饰器测试。"""

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """TimeoutError 转换为 LLMServiceError。"""
        from backend.utils.error_handler import handle_llm_errors

        @handle_llm_errors
        async def timeout_func():
            raise TimeoutError()

        with pytest.raises(LLMServiceError) as exc_info:
            await timeout_func()
        assert exc_info.value.details.get("timeout") is True

    @pytest.mark.asyncio
    async def test_generic_error(self):
        """其他异常转换为 LLMServiceError。"""
        from backend.utils.error_handler import handle_llm_errors

        @handle_llm_errors
        async def error_func():
            raise ConnectionError("连接失败")

        with pytest.raises(LLMServiceError) as exc_info:
            await error_func()
        assert "连接失败" in exc_info.value.details["original_error"]

    @pytest.mark.asyncio
    async def test_passes_through_cityflow_exception(self):
        """CityFlowException 原样抛出。"""
        from backend.utils.error_handler import handle_llm_errors

        @handle_llm_errors
        async def cityflow_func():
            raise LLMServiceError(message="已有错误")

        with pytest.raises(LLMServiceError) as exc_info:
            await cityflow_func()
        assert exc_info.value.message == "已有错误"

    @pytest.mark.asyncio
    async def test_success_passes_through(self):
        """正常执行不受影响。"""
        from backend.utils.error_handler import handle_llm_errors

        @handle_llm_errors
        async def success_func():
            return "LLM回复"

        result = await success_func()
        assert result == "LLM回复"
