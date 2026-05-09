"""OpenAPI 元数据定义。"""

from __future__ import annotations

from typing import Any


def get_openapi_metadata() -> dict[str, Any]:
    """返回 OpenAPI 规范的顶层元数据。"""
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "CityFlow API",
            "description": "智能城市出行规划系统 API",
            "version": "1.0.0",
            "contact": {
                "name": "CityFlow Team",
                "email": "team@cityflow.com",
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
        },
        "servers": [
            {
                "url": "http://localhost:8000",
                "description": "本地开发环境",
            },
            {
                "url": "https://api.cityflow.com",
                "description": "生产环境",
            },
        ],
        "tags": [
            {
                "name": "路线规划",
                "description": "核心路线规划接口：意图解析、POI筛选、TSPTW求解、文案生成。",
            },
            {
                "name": "路线管理",
                "description": "路线的查询、缓存与调整接口。",
            },
            {
                "name": "对话",
                "description": "对话式路线调整接口，支持替换景点、调整节奏/预算/时间等。",
            },
            {
                "name": "POI",
                "description": "兴趣点查询与距离计算接口。",
            },
            {
                "name": "数据",
                "description": "底层数据集查询接口（POI、订单、道路流量等）。",
            },
            {
                "name": "LLM",
                "description": "大语言模型对话接口，支持普通与流式响应。",
            },
            {
                "name": "系统",
                "description": "健康检查等运维接口。",
            },
        ],
    }
