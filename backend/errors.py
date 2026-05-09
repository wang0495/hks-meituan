"""CityFlow 统一错误码与异常体系。

错误码分段：
    1xxx - 通用错误
    2xxx - 认证/授权错误
    3xxx - 业务逻辑错误
    4xxx - 数据/输入错误
    5xxx - 外部服务错误
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(Enum):
    """错误码枚举。"""

    # 通用错误 (1xxx)
    UNKNOWN_ERROR = 1000
    INVALID_REQUEST = 1001
    NOT_FOUND = 1002
    INTERNAL_ERROR = 1003
    TIMEOUT = 1004
    RATE_LIMITED = 1005

    # 认证错误 (2xxx)
    UNAUTHORIZED = 2001
    FORBIDDEN = 2002
    TOKEN_EXPIRED = 2003

    # 业务错误 (3xxx)
    INTENT_PARSE_FAILED = 3001
    NO_POIS_FOUND = 3002
    ROUTE_SOLVING_FAILED = 3003
    NARRATIVE_GENERATION_FAILED = 3004
    DIALOGUE_FAILED = 3005

    # 数据错误 (4xxx)
    INVALID_POI_DATA = 4001
    INVALID_USER_INPUT = 4002
    INVALID_ROUTE_DATA = 4003

    # 外部服务错误 (5xxx)
    LLM_SERVICE_ERROR = 5001
    EXTERNAL_API_ERROR = 5002


# 错误码 -> HTTP 状态码默认映射
_STATUS_MAP: dict[ErrorCode, int] = {
    ErrorCode.UNKNOWN_ERROR: 500,
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.TIMEOUT: 504,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.INTENT_PARSE_FAILED: 400,
    ErrorCode.NO_POIS_FOUND: 404,
    ErrorCode.ROUTE_SOLVING_FAILED: 500,
    ErrorCode.NARRATIVE_GENERATION_FAILED: 500,
    ErrorCode.DIALOGUE_FAILED: 500,
    ErrorCode.INVALID_POI_DATA: 400,
    ErrorCode.INVALID_USER_INPUT: 400,
    ErrorCode.INVALID_ROUTE_DATA: 400,
    ErrorCode.LLM_SERVICE_ERROR: 503,
    ErrorCode.EXTERNAL_API_ERROR: 502,
}


class CityFlowException(Exception):
    """CityFlow 基础异常。

    所有业务异常的基类，携带错误码、消息、可选详情和 HTTP 状态码。
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details: dict[str, Any] = details or {}
        self.status_code = status_code or _STATUS_MAP.get(code, 500)
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """转换为 API 响应字典。"""
        result: dict[str, Any] = {
            "error": {
                "code": self.code.value,
                "message": self.message,
            }
        }
        if self.details:
            result["error"]["details"] = self.details
        return result


# ---------------------------------------------------------------------------
# 业务异常子类（直接使用，不用记 status_code）
# ---------------------------------------------------------------------------


class IntentParseError(CityFlowException):
    """意图解析失败。"""

    def __init__(
        self, message: str = "意图解析失败", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code=ErrorCode.INTENT_PARSE_FAILED,
            message=message,
            details=details,
        )


class NoPOIsFoundError(CityFlowException):
    """未找到符合条件的 POI。"""

    def __init__(
        self,
        message: str = "未找到符合条件的POI",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.NO_POIS_FOUND,
            message=message,
            details=details,
        )


class RouteSolvingError(CityFlowException):
    """路线求解失败。"""

    def __init__(
        self, message: str = "路线求解失败", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code=ErrorCode.ROUTE_SOLVING_FAILED,
            message=message,
            details=details,
        )


class NarrativeGenerationError(CityFlowException):
    """文案生成失败。"""

    def __init__(
        self, message: str = "文案生成失败", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code=ErrorCode.NARRATIVE_GENERATION_FAILED,
            message=message,
            details=details,
        )


class DialogueError(CityFlowException):
    """对话处理失败。"""

    def __init__(
        self, message: str = "对话处理失败", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code=ErrorCode.DIALOGUE_FAILED,
            message=message,
            details=details,
        )


class LLMServiceError(CityFlowException):
    """LLM 服务异常。"""

    def __init__(
        self, message: str = "LLM服务异常", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code=ErrorCode.LLM_SERVICE_ERROR,
            message=message,
            details=details,
        )


class RateLimitError(CityFlowException):
    """请求频率超限。"""

    def __init__(
        self, message: str = "请求过于频繁", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            message=message,
            details=details,
        )
