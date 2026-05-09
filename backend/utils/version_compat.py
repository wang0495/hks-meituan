"""API 版本兼容性处理工具。"""

from __future__ import annotations

from typing import Any


def convert_v1_to_v2_request(v1_request: dict[str, Any]) -> dict[str, Any]:
    """将 V1 请求转换为 V2 格式。

    V1 请求格式:
        {"user_input": "..."}

    V2 请求格式:
        {"user_input": "...", "preferences": null, "constraints": [], "pace": "平衡型"}

    Args:
        v1_request: V1 格式的请求数据

    Returns:
        V2 格式的请求数据
    """
    v2_request = v1_request.copy()

    # V1 没有 preferences/constraints/pace 字段，设置默认值
    v2_request.setdefault("preferences", None)
    v2_request.setdefault("constraints", [])
    v2_request.setdefault("pace", "平衡型")

    return v2_request


def convert_v2_to_v1_response(v2_response: dict[str, Any]) -> dict[str, Any]:
    """将 V2 响应转换为 V1 格式。

    V2 响应包含 emotion_curve 和 metadata，V1 不需要这些字段。

    Args:
        v2_response: V2 格式的响应数据

    Returns:
        V1 格式的响应数据（移除了 emotion_curve 和 metadata）
    """
    v1_response = v2_response.copy()

    # V2 新增的字段在 V1 中不返回
    v1_response.pop("emotion_curve", None)
    v1_response.pop("metadata", None)

    return v1_response


def convert_v2_to_v1_poi(poi: dict[str, Any]) -> dict[str, Any]:
    """将 V2 POI 数据转换为 V1 格式。

    V2 POI 包含完整的 constraints 和 emotion_tags，V1 只返回基本字段。

    Args:
        poi: V2 格式的 POI 数据

    Returns:
        V1 格式的 POI 数据
    """
    v1_poi = poi.copy()

    # V1 不需要完整的约束条件
    if "constraints" in v1_poi:
        constraints = v1_poi["constraints"]
        # V1 只保留无障碍和营业时间
        v1_poi["constraints"] = {
            "accessible": constraints.get("accessible", True),
            "opening_hours": constraints.get("opening_hours", "09:00-17:00"),
        }

    return v1_poi


def get_version_from_request(request: Any) -> str:
    """从请求中获取 API 版本。

    优先级：请求状态 > URL路径 > 请求头 > 默认版本

    Args:
        request: FastAPI Request 对象

    Returns:
        版本号（如 "v1"）
    """
    # 优先从请求状态获取（由中间件设置）
    if hasattr(request.state, "api_version"):
        return request.state.api_version

    # 从 URL 路径提取
    path = request.url.path
    for version in ["v1", "v2"]:
        if f"/{version}/" in path:
            return version

    # 从请求头获取
    return request.headers.get("X-API-Version", "v1")


def is_v1_request(request: Any) -> bool:
    """判断是否为 V1 请求。"""
    return get_version_from_request(request) == "v1"


def is_v2_request(request: Any) -> bool:
    """判断是否为 V2 请求。"""
    return get_version_from_request(request) == "v2"
