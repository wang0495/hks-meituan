"""测试配置：确保 backend 包可导入，并提供通用 fixtures。

包含 Mock 服务 fixtures、测试客户端、以及性能优化配置。
"""

from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

# 导入 conftest_db 中的 fixtures，使其对所有测试可用
from tests.conftest_db import *  # noqa: F403

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# 将项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 测试客户端（复用连接）
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """异步测试客户端，使用 ASGITransport 直连 app。"""
    from backend.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def client_no_startup() -> AsyncIterator[AsyncClient]:
    """不触发 startup 事件的测试客户端（适用于纯 Mock 场景）。"""
    from backend.main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Mock LLM 服务
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM 服务，返回通用意图 JSON 字符串。"""
    mock = AsyncMock()
    mock.chat.return_value = '{"time": {"period": "全天"}, "group": {"type": "独居"}}'
    return mock


@pytest.fixture
def mock_intent_llm() -> AsyncMock:
    """Mock 意图解析 LLM，返回完整的结构化意图。"""
    mock = AsyncMock()
    mock.return_value = {
        "time": {"period": "全天", "start": "09:00", "end": "18:00"},
        "budget": {"per_person": 500, "type": "弹性"},
        "group": {"size": 1, "type": "独居"},
        "preferences": {
            "culture": 0.5,
            "food": 0.4,
            "nature": 0.7,
            "social": 0.1,
        },
        "pace": "闲逛型",
        "hard_constraints": [],
    }
    return mock


# ---------------------------------------------------------------------------
# Mock POI 数据
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_poi_data() -> list[dict]:
    """Mock POI 数据集。"""
    return [
        {
            "id": "mock_001",
            "name": "测试文化馆",
            "category": "文化",
            "city": "珠海",
            "rating": 4.5,
            "avg_price": 50,
            "lat": 22.27,
            "lng": 113.58,
            "business_hours": "09:00-17:00",
            "tags": ["免费", "文化"],
            "queue_prone": False,
            "emotion_tags": {
                "excitement": 0.3,
                "tranquility": 0.8,
                "sociability": 0.2,
                "culture_depth": 0.9,
                "surprise": 0.1,
                "physical_demand": 0.2,
            },
        },
        {
            "id": "mock_002",
            "name": "测试美食街",
            "category": "美食",
            "city": "珠海",
            "rating": 4.2,
            "avg_price": 80,
            "lat": 22.28,
            "lng": 113.59,
            "business_hours": "10:00-22:00",
            "tags": ["美食", "热闹"],
            "queue_prone": True,
            "emotion_tags": {
                "excitement": 0.6,
                "tranquility": 0.2,
                "sociability": 0.8,
                "culture_depth": 0.3,
                "surprise": 0.5,
                "physical_demand": 0.3,
            },
        },
        {
            "id": "mock_003",
            "name": "测试公园",
            "category": "自然",
            "city": "珠海",
            "rating": 4.7,
            "avg_price": 0,
            "lat": 22.26,
            "lng": 113.57,
            "business_hours": "06:00-22:00",
            "tags": ["免费", "公园", "安静"],
            "queue_prone": False,
            "emotion_tags": {
                "excitement": 0.2,
                "tranquility": 0.95,
                "sociability": 0.1,
                "culture_depth": 0.1,
                "surprise": 0.2,
                "physical_demand": 0.4,
            },
        },
    ]


# ---------------------------------------------------------------------------
# 文件 Fixtures（保留原有功能）
# ---------------------------------------------------------------------------


@pytest.fixture
def test_pois() -> list[dict]:
    """加载测试POI数据。"""
    with open(FIXTURES_DIR / "test_pois.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def test_intents() -> list[dict]:
    """加载测试意图数据。"""
    with open(FIXTURES_DIR / "test_intents.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def test_scenarios() -> list[dict]:
    """加载测试场景数据。"""
    with open(FIXTURES_DIR / "test_scenarios.json", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 示例数据 Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_intent() -> dict:
    """返回一个示例意图。"""
    return {
        "time": {"period": "全天", "start": "09:00", "end": "18:00"},
        "budget": {"per_person": 100, "type": "弹性"},
        "group": {"size": 1, "type": "独居"},
        "preferences": {
            "culture": 0.6,
            "food": 0.4,
            "nature": 0.7,
            "social": 0.1,
        },
        "pace": "闲逛型",
        "hard_constraints": ["排队容忍度<5min"],
    }


@pytest.fixture
def sample_poi() -> dict:
    """返回一个示例POI。"""
    return {
        "id": "test_001",
        "name": "安静图书馆",
        "category": "文化",
        "rating": 4.5,
        "avg_price": 0,
        "lat": 22.27,
        "lng": 113.58,
        "business_hours": "09:00-21:00",
        "tags": ["免费", "安静", "学习"],
        "queue_prone": False,
        "avg_stay_min": 120,
        "emotion_tags": {
            "excitement": 0.1,
            "tranquility": 0.95,
            "sociability": 0.1,
            "culture_depth": 0.9,
            "surprise": 0.05,
            "physical_demand": 0.1,
        },
        "constraints": {
            "accessible": True,
            "pet_friendly": False,
            "queue_time_min": 0,
            "opening_hours": "09:00-21:00",
            "has_restroom": True,
        },
    }
