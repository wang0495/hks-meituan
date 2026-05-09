"""CityFlow 数据校验框架。

提供请求/响应数据的校验基类和业务校验器。
基于 Pydantic v2，与项目已有的错误体系 (CityFlowException) 对接。
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.errors import CityFlowException, ErrorCode

# ---------------------------------------------------------------------------
# 基础校验器
# ---------------------------------------------------------------------------


class BaseValidator(BaseModel):
    """基础校验器 — 所有业务校验器的基类。"""

    model_config = {
        "extra": "forbid",
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


# ---------------------------------------------------------------------------
# 通用字符串清理
# ---------------------------------------------------------------------------

# 匹配 HTML 标签
_HTML_TAG_RE = re.compile(r"<[^>]*>")
# 匹配常见 SQL 注入片段
_SQL_INJECTION_RE = re.compile(
    r"(union\s+all\s+select|;\s*drop\s+table|;\s*delete\s+from)",
    re.IGNORECASE,
)


def sanitize_string(value: str) -> str:
    """清理字符串：去除 HTML 标签、首尾空白。"""
    value = _HTML_TAG_RE.sub("", value)
    return value.strip()


def check_injection(value: str) -> None:
    """检测 SQL 注入模式，匹配则抛出 CityFlowException。"""
    if _SQL_INJECTION_RE.search(value):
        raise CityFlowException(
            code=ErrorCode.INVALID_USER_INPUT,
            message="输入包含非法内容",
        )


# ---------------------------------------------------------------------------
# 请求校验基类
# ---------------------------------------------------------------------------


class RequestValidator(BaseValidator):
    """请求校验基类 — 自动清理所有字符串字段。"""

    @model_validator(mode="before")
    @classmethod
    def sanitize_all_strings(cls, data: Any) -> Any:
        """在字段校验之前，清理所有字符串值。"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    data[key] = sanitize_string(value)
        return data


# ---------------------------------------------------------------------------
# POI 校验器
# ---------------------------------------------------------------------------


class EmotionTagsValidator(BaseValidator):
    """POI 情绪标签校验（6 维，取值 0~1）。"""

    excitement: float = Field(0.5, ge=0, le=1)
    tranquility: float = Field(0.5, ge=0, le=1)
    sociability: float = Field(0.5, ge=0, le=1)
    culture_depth: float = Field(0.5, ge=0, le=1)
    surprise: float = Field(0.5, ge=0, le=1)
    physical_demand: float = Field(0.5, ge=0, le=1)


class ConstraintsValidator(BaseValidator):
    """POI 约束条件校验。"""

    accessible: bool = True
    pet_friendly: bool = False
    queue_time_min: int = Field(0, ge=0)
    opening_hours: str = "09:00-17:00"
    has_restroom: bool = True


class POIValidator(RequestValidator):
    """POI 数据校验器 — 匹配 city_poi_db.json 的实际字段。"""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    rating: float = Field(..., ge=0, le=5)
    avg_price: float = Field(0, ge=0)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    business_hours: str = "09:00-17:00"
    tags: list[str] = Field(default_factory=list)
    emotion_tags: EmotionTagsValidator | None = None
    constraints: ConstraintsValidator | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("POI ID 只允许字母、数字、下划线和连字符")
        return v

    @field_validator("business_hours")
    @classmethod
    def validate_business_hours(cls, v: str) -> str:
        if v and not re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", v):
            raise ValueError("营业时间格式应为 HH:MM-HH:MM")
        return v


class POISearchValidator(RequestValidator):
    """POI 搜索请求校验器 — 匹配 SearchRequest 模型。"""

    region: str | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None
    exclude_ids: list[str] | None = None
    keyword: str | None = Field(None, max_length=100)
    min_rating: float | None = Field(None, ge=0, le=5)
    max_price: int | None = Field(None, ge=0)


# ---------------------------------------------------------------------------
# 路线校验器
# ---------------------------------------------------------------------------


class RouteStepValidator(BaseValidator):
    """路线步骤校验器。"""

    poi: dict = Field(..., description="POI 信息")
    arrival_time: str | None = None
    departure_time: str | None = None
    travel_from_prev: dict | None = None

    @field_validator("arrival_time", "departure_time")
    @classmethod
    def validate_time_format(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("时间格式应为 HH:MM")
        return v


class RouteValidator(RequestValidator):
    """路线校验器 — 用于校验完整的路线数据。"""

    route: list[dict] = Field(..., min_length=1)
    narrative: dict | None = None
    user_intent: dict | None = None

    @field_validator("route")
    @classmethod
    def validate_route_not_empty(cls, v: list[dict]) -> list[dict]:
        if len(v) == 0:
            raise ValueError("路线不能为空")
        return v


class PlanRequestValidator(RequestValidator):
    """V1 路线规划请求校验器 — 匹配 PlanRequestV1。"""

    user_input: str = Field(..., min_length=1, max_length=500)

    @field_validator("user_input")
    @classmethod
    def validate_user_input(cls, v: str) -> str:
        check_injection(v)
        return v


# ---------------------------------------------------------------------------
# 对话校验器
# ---------------------------------------------------------------------------


class DialogueRequestValidator(RequestValidator):
    """对话调整请求校验器 — 匹配 AdjustRequestV1。"""

    instruction: str = Field(..., min_length=1, max_length=200)

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, v: str) -> str:
        check_injection(v)
        return v


# ---------------------------------------------------------------------------
# 距离矩阵校验器
# ---------------------------------------------------------------------------


class DistanceMatrixValidator(RequestValidator):
    """距离矩阵请求校验器 — 匹配 DistanceMatrixRequest。"""

    poi_ids: list[str] = Field(..., min_length=2, max_length=50)

    @field_validator("poi_ids")
    @classmethod
    def validate_poi_ids(cls, v: list[str]) -> list[str]:
        for pid in v:
            if not pid.strip():
                raise ValueError("POI ID 不能为空字符串")
        if len(v) != len(set(v)):
            raise ValueError("POI ID 列表中存在重复")
        return v


# ---------------------------------------------------------------------------
# LLM 对话校验器
# ---------------------------------------------------------------------------


class ChatRequestValidator(RequestValidator):
    """LLM 对话请求校验器 — 匹配 ChatRequest。"""

    message: str = Field(..., min_length=1, max_length=4000)
    model: str = "openai"

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        check_injection(v)
        return v
