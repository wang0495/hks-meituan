"""CityFlow OpenAPI 文档配置。

提供文档页面的元数据、标签定义和示例数据，
供 custom_swagger.py 和 __init__.py 使用。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 静态资源路径
# ---------------------------------------------------------------------------

_STATIC_DIR = Path(__file__).parent.parent / "static"
_CSS_FILE = _STATIC_DIR / "css" / "swagger-custom.css"

_SWAGGER_JS_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
_SWAGGER_CSS_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
_REDOC_JS_URL = "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"
_FAVICON_URL = "https://fastapi.tiangolo.com/img/favicon.png"


# ---------------------------------------------------------------------------
# OpenAPI 信息（info 块）
# ---------------------------------------------------------------------------

_OPENAPI_INFO: dict[str, Any] = {
    "title": "CityFlow API",
    "description": (
        "# CityFlow - 智能城市出行规划系统\n\n"
        "基于情绪感知的个性化城市路线规划API。\n\n"
        "---\n\n"
        "## 核心功能\n\n"
        "- **意图解析** - 理解用户自然语言需求，自动匹配用户画像\n"
        "- **路线规划** - TSPTW（带时间窗约束的旅行商问题）算法优化路线\n"
        "- **对话调整** - 支持多轮对话实时调整已规划路线\n"
        "- **文案生成** - 自动生成路线描述与情绪曲线\n\n"
        "## 快速开始\n\n"
        "```python\n"
        "import httpx\n\n"
        "response = httpx.post(\n"
        '    "http://localhost:8000/api/plan",\n'
        '    json={"user_input": "周末想一个人安静走走"}\n'
        ")\n"
        "```\n\n"
        "## 情绪标签\n\n"
        "每个POI携带6维情绪标签（取值 0~1）：\n\n"
        "| 维度 | 字段 | 说明 |\n"
        "|------|------|------|\n"
        "| 兴奋度 | `excitement` | 该地点带来的兴奋刺激感 |\n"
        "| 宁静度 | `tranquility` | 该地点的安静平和程度 |\n"
        "| 社交性 | `sociability` | 该地点适合社交互动的程度 |\n"
        "| 文化深度 | `culture_depth` | 该地点的文化内涵丰富度 |\n"
        "| 惊喜度 | `surprise` | 该地点带来意外惊喜的可能性 |\n"
        "| 体力消耗 | `physical_demand` | 该地点对体力的要求 |\n\n"
        "## 用户画像\n\n"
        "系统内置20种典型用户画像，自动从自然语言中推断匹配：\n\n"
        "| ID | 名称 | 群体 | 节奏 |\n"
        "|----|------|------|------|\n"
        "| P1 | 社恐独居 | 独居 | 闲逛型 |\n"
        "| P2 | 浪漫情侣 | 情侣 | 平衡型 |\n"
        "| P3 | 活力亲子 | 亲子 | 平衡型 |\n"
        "| P4 | 朋友聚会 | 朋友 | 特种兵型 |\n"
        "| P5 | 退休休闲 | 退休 | 闲逛型 |\n"
        "| P6-P20 | ... | ... | ... |\n\n"
        "## 节奏模式\n\n"
        "| 模式 | 说明 |\n"
        "|------|------|\n"
        "| 闲逛型 | 悠闲步行，每个景点停留较久，穿插休息 |\n"
        "| 平衡型 | 适度紧凑，兼顾体验与效率 |\n"
        "| 特种兵型 | 高密度打卡，时间利用率最高 |\n\n"
        "## 价格区间\n\n"
        "| 区间 | 条件 |\n"
        "|------|------|\n"
        "| 免费 | avg_price = 0 |\n"
        "| 便宜 | avg_price <= 50 |\n"
        "| 中等 | avg_price <= 150 |\n"
        "| 较贵 | avg_price <= 500 |\n"
        "| 高端 | avg_price > 500 |\n"
    ),
    "version": "1.0.0",
    "contact": {
        "name": "CityFlow Team",
        "email": "team@cityflow.com",
    },
    "license": {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    "x-logo": {
        "url": "/static/logo.png",
        "altText": "CityFlow Logo",
    },
}


# ---------------------------------------------------------------------------
# OpenAPI Tags 元数据
# ---------------------------------------------------------------------------

_TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "路线规划",
        "description": (
            "核心路线规划接口。根据用户自然语言描述，通过意图解析、POI筛选、"
            "TSPTW算法求解、文案生成四个阶段，以SSE流式返回个性化路线。"
        ),
    },
    {
        "name": "路线管理",
        "description": "路线的查询、缓存与调整接口。",
    },
    {
        "name": "对话",
        "description": (
            "对话式路线调整接口。支持替换景点、调整节奏、调整预算、"
            "调整时间、重新规划等指令类型。"
        ),
    },
    {
        "name": "POI",
        "description": (
            "兴趣点（Point of Interest）查询与距离计算接口。"
            "支持多维度筛选、详情查询、距离矩阵计算。"
        ),
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
        "name": "审计日志",
        "description": (
            "审计日志查询与导出接口。记录系统中所有关键操作（路线规划、"
            "对话调整、POI搜索等），支持按用户、动作类型、时间范围过滤，"
            "以及 JSON/CSV 格式导出。"
        ),
    },
    {
        "name": "系统",
        "description": "健康检查等运维接口。",
    },
    {
        "name": "任务",
        "description": (
            "异步后台任务管理接口。支持提交后台任务、查询任务状态、"
            "取消任务、列出所有任务。"
        ),
    },
    {
        "name": "WebSocket",
        "description": (
            "WebSocket 实时通信接口。支持路线更新订阅、心跳检测、" "实时消息推送。"
        ),
    },
    {
        "name": "GraphQL",
        "description": (
            "GraphQL 查询与变更接口。支持按条件查询 POI、路线，"
            "以及通过自然语言规划路线和对话式调整路线。"
        ),
    },
    {
        "name": "消息队列",
        "description": (
            "Redis 消息队列接口。支持消息发布（单条/批量）、"
            "消费者启动、队列状态查询与清空。"
        ),
    },
]


# ---------------------------------------------------------------------------
# OpenAPI Examples（组件级示例）
# ---------------------------------------------------------------------------

_OPENAPI_EXAMPLES: dict[str, dict[str, Any]] = {
    "PlanRequest": {
        "summary": "路线规划请求",
        "value": {"user_input": "周末想一个人安静走走"},
    },
    "PlanRequestRomantic": {
        "summary": "浪漫约会请求",
        "value": {"user_input": "和女朋友约会，要有氛围感"},
    },
    "PlanRequestFamily": {
        "summary": "亲子出行请求",
        "value": {"user_input": "带孩子出去玩，不要太累"},
    },
    "PlanRequestFriends": {
        "summary": "朋友聚会请求",
        "value": {"user_input": "和朋友一起吃喝玩乐，预算500以内"},
    },
    "POISearchRequest": {
        "summary": "POI 搜索请求",
        "value": {"region": "珠海", "categories": ["文化", "美食"]},
    },
}


# ---------------------------------------------------------------------------
# 服务器配置
# ---------------------------------------------------------------------------

_SERVERS: list[dict[str, str]] = [
    {
        "url": "http://localhost:8000",
        "description": "本地开发环境",
    },
    {
        "url": "https://api.cityflow.com",
        "description": "生产环境",
    },
]


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def get_openapi_info() -> dict[str, Any]:
    """返回 OpenAPI info 块。"""
    return _OPENAPI_INFO.copy()


def get_tags_metadata() -> list[dict[str, Any]]:
    """返回 tags 元数据。"""
    return [t.copy() for t in _TAGS_METADATA]


def get_openapi_examples() -> dict[str, dict[str, Any]]:
    """返回 components/examples 内容。"""
    return {k: v.copy() for k, v in _OPENAPI_EXAMPLES.items()}


def get_servers() -> list[dict[str, str]]:
    """返回 servers 配置。"""
    return [s.copy() for s in _SERVERS]


def get_swagger_css_content() -> str:
    """读取自定义 CSS 文件内容，用于内联注入。"""
    if _CSS_FILE.exists():
        return _CSS_FILE.read_text(encoding="utf-8")
    return ""
