"""美团API Tool 执行器 — 将 LLM tool_call 转为 HTTP 请求。

Agent 发出 tool_call 后，由本模块调用美团模拟服务器获取数据，
再把结果返回给 Agent 继续推理。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 美团模拟服务器地址
BASE_URL = "http://localhost:8001/api"

# tool_name → (HTTP method, path)
_TOOL_ROUTES: dict[str, tuple[str, str]] = {
    "search_poi":         ("GET", "/poi/search"),
    "get_poi_detail":     ("GET", "/poi/{poi_id}"),
    "get_poi_reviews":    ("GET", "/poi/{poi_id}/reviews"),
    "get_poi_location":   ("GET", "/poi/{poi_id}/location"),
    "get_route_distance": ("GET", "/route/distance"),
    "get_hot_trending":   ("GET", "/hot/trending"),
    "get_area_boundaries":("GET", "/area/boundaries"),
}


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    timeout: float = 10.0,
) -> dict[str, Any]:
    """执行单个 tool call，返回美团API响应。

    Args:
        tool_name: 工具名，对应 tools.py 中定义的 function name
        arguments: LLM 传来的参数
        timeout: HTTP 请求超时(秒)

    Returns:
        API 响应的 JSON 数据

    Raises:
        ValueError: 未知工具名
        httpx.HTTPError: 请求失败
    """
    if tool_name not in _TOOL_ROUTES:
        raise ValueError(f"未知工具: {tool_name}，可用: {list(_TOOL_ROUTES.keys())}")

    method, path_template = _TOOL_ROUTES[tool_name]

    # 处理路径参数（如 /poi/{poi_id}）
    path = path_template
    for key in list(arguments.keys()):
        placeholder = "{" + key + "}"
        if placeholder in path:
            path = path.replace(placeholder, str(arguments.pop(key)))

    url = BASE_URL + path

    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            # 过滤掉 None 值的参数
            params = {k: v for k, v in arguments.items() if v is not None}
            resp = await client.get(url, params=params)
        else:
            resp = await client.post(url, json=arguments)

        resp.raise_for_status()
        return resp.json()
