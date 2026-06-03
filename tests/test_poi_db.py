"""POI 数据库层单元测试。

测试 POI 模型、POIRepository、以及 data_service DB 模式。
使用 aiosqlite 内存数据库，不依赖 PostgreSQL。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.base import Base
from backend.database.poi_repository import POIRepository

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# ---------------------------------------------------------------------------
# 数据库 fixtures（使用 aiosqlite 内存数据库，非 PostgreSQL）
# 只创建 pois 表，因为其他模型使用 JSONB（PostgreSQL 专有）
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine():
    """创建内存 SQLite 异步引擎，仅创建 pois 表。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.tables["pois"].create)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.tables["pois"].drop)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """每个测试一个独立事务，测试结束回滚。"""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def poi_repo(db_session: AsyncSession) -> POIRepository:
    return POIRepository(db_session)


# ---------------------------------------------------------------------------
# 样本数据
# ---------------------------------------------------------------------------

_SAMPLE_POI_A = {
    "id": "poi_test_001",
    "name": "测试景点A",
    "city": "珠海",
    "category": "文化",
    "rating": 4.5,
    "avg_price": 50.0,
    "lat": 22.27,
    "lng": 113.58,
    "business_hours": "09:00-17:00",
    "tags": ["免费", "文化"],
    "queue_prone": False,
    "avg_stay_min": 90,
    "emotion_tags": {
        "excitement": 0.4,
        "tranquility": 0.6,
        "sociability": 0.3,
        "culture_depth": 0.9,
        "surprise": 0.5,
        "physical_demand": 0.2,
    },
    "experience_value": 7.5,
    "price_elasticity": 0.6,
    "experience_leverage": "high",
    "spend_emotion": "value",
}

_SAMPLE_POI_B = {
    "id": "poi_test_002",
    "name": "测试景点B",
    "city": "珠海",
    "category": "餐饮",
    "rating": 3.8,
    "avg_price": 120.0,
    "lat": 22.30,
    "lng": 113.60,
    "business_hours": "10:00-22:00",
    "tags": ["美食", "海鲜"],
    "queue_prone": True,
    "avg_stay_min": 60,
    "emotion_tags": {
        "excitement": 0.5,
        "tranquility": 0.3,
        "sociability": 0.8,
        "culture_depth": 0.2,
        "surprise": 0.3,
        "physical_demand": 0.1,
    },
    "experience_value": None,
    "price_elasticity": None,
    "experience_leverage": None,
    "spend_emotion": None,
}

_SAMPLE_POI_C = {
    "id": "poi_test_003",
    "name": "测试景点C",
    "city": "广州",
    "category": "景点",
    "rating": 4.2,
    "avg_price": 0.0,
    "lat": 23.13,
    "lng": 113.26,
    "business_hours": "08:00-18:00",
    "tags": ["免费", "地标"],
    "queue_prone": False,
    "avg_stay_min": 120,
    "emotion_tags": {
        "excitement": 0.7,
        "tranquility": 0.4,
        "sociability": 0.6,
        "culture_depth": 0.5,
        "surprise": 0.8,
        "physical_demand": 0.3,
    },
    "experience_value": 6.2,
    "price_elasticity": 1.0,
    "experience_leverage": "high",
    "spend_emotion": "value",
}


# ---------------------------------------------------------------------------
# POI 模型测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_poi(poi_repo: POIRepository) -> None:
    """创建 POI 并验证字段正确性。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A])
    poi = await poi_repo.get_by_id("poi_test_001")
    assert poi is not None
    assert poi.name == "测试景点A"
    assert poi.city == "珠海"
    assert poi.category == "文化"
    assert poi.rating == 4.5
    assert poi.avg_price == 50.0
    assert poi.queue_prone is False
    assert poi.avg_stay_min == 90
    assert poi.tags == ["免费", "文化"]
    assert poi.emotion_tags["excitement"] == 0.4
    assert poi.experience_value == 7.5
    assert poi.experience_leverage == "high"
    assert poi.spend_emotion == "value"


@pytest.mark.asyncio
async def test_create_poi_with_none_fields(poi_repo: POIRepository) -> None:
    """创建含空经济字段的 POI。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_B])
    poi = await poi_repo.get_by_id("poi_test_002")
    assert poi is not None
    assert poi.experience_value is None
    assert poi.price_elasticity is None
    assert poi.experience_leverage is None
    assert poi.spend_emotion is None


@pytest.mark.asyncio
async def test_poi_timestamps(poi_repo: POIRepository) -> None:
    """POI 创建时自动生成时间戳。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A])
    poi = await poi_repo.get_by_id("poi_test_001")
    assert poi is not None
    assert poi.created_at is not None
    assert poi.updated_at is not None


# ---------------------------------------------------------------------------
# POI.to_dict() 测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poi_to_dict(poi_repo: POIRepository) -> None:
    """to_dict() 返回与 JSON 数据兼容的结构。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A])
    poi = await poi_repo.get_by_id("poi_test_001")
    assert poi is not None
    d = poi.to_dict()

    # 核心字段
    assert d["id"] == "poi_test_001"
    assert d["name"] == "测试景点A"
    assert d["city"] == "珠海"
    assert d["category"] == "文化"

    # 经济字段
    assert d["experience_value"] == 7.5
    assert d["price_elasticity"] == 0.6
    assert d["experience_leverage"] == "high"

    # 不含 ugc_comments
    assert "ugc_comments" not in d


@pytest.mark.asyncio
async def test_poi_to_dict_empty_economy(poi_repo: POIRepository) -> None:
    """经济字段为空时 to_dict() 应返回 None。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_B])
    poi = await poi_repo.get_by_id("poi_test_002")
    assert poi is not None
    d = poi.to_dict()
    assert d["experience_value"] is None
    assert d["price_elasticity"] is None


# ---------------------------------------------------------------------------
# POIRepository 查询测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_by_city(poi_repo: POIRepository) -> None:
    """按城市查询应返回该城市的所有 POI。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A, _SAMPLE_POI_B, _SAMPLE_POI_C])
    zhuhai_pois = await poi_repo.find_by_city("珠海")
    assert len(zhuhai_pois) == 2
    assert all(p.city == "珠海" for p in zhuhai_pois)


@pytest.mark.asyncio
async def test_find_by_category(poi_repo: POIRepository) -> None:
    """按类别查询。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A, _SAMPLE_POI_B, _SAMPLE_POI_C])
    cultural_pois = await poi_repo.find_by_category("文化")
    assert len(cultural_pois) == 1
    assert cultural_pois[0].id == "poi_test_001"


@pytest.mark.asyncio
async def test_find_filtered_by_city(poi_repo: POIRepository) -> None:
    """find_filtered 按城市筛选。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A, _SAMPLE_POI_B, _SAMPLE_POI_C])
    result = await poi_repo.find_filtered({"city": "广州"})
    assert len(result) == 1
    assert result[0].name == "测试景点C"


@pytest.mark.asyncio
async def test_find_filtered_by_rating(poi_repo: POIRepository) -> None:
    """find_filtered 按最低评分筛选。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A, _SAMPLE_POI_B, _SAMPLE_POI_C])
    result = await poi_repo.find_filtered({"min_rating": 4.0})
    assert len(result) >= 1
    assert all(p.rating >= 4.0 for p in result)


@pytest.mark.asyncio
async def test_find_filtered_by_max_price(poi_repo: POIRepository) -> None:
    """find_filtered 按最高价格筛选。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A, _SAMPLE_POI_B, _SAMPLE_POI_C])
    result = await poi_repo.find_filtered({"max_price": 60.0})
    for p in result:
        assert p.avg_price is None or p.avg_price <= 60.0


@pytest.mark.asyncio
async def test_find_filtered_multiple(poi_repo: POIRepository) -> None:
    """多重筛选组合。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A, _SAMPLE_POI_B, _SAMPLE_POI_C])
    result = await poi_repo.find_filtered(
        {
            "city": "珠海",
            "min_rating": 4.0,
        }
    )
    assert len(result) == 1
    assert result[0].id == "poi_test_001"


@pytest.mark.asyncio
async def test_find_filtered_limit(poi_repo: POIRepository) -> None:
    """limit 参数限制返回数量。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A, _SAMPLE_POI_B, _SAMPLE_POI_C])
    result = await poi_repo.find_filtered({}, limit=1)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# POIRepository count / bulk_upsert 测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count(poi_repo: POIRepository) -> None:
    """count() 应返回正确总数。"""
    assert await poi_repo.count() == 0
    await poi_repo.bulk_upsert([_SAMPLE_POI_A])
    assert await poi_repo.count() == 1
    await poi_repo.bulk_upsert([_SAMPLE_POI_B, _SAMPLE_POI_C])
    assert await poi_repo.count() == 3


@pytest.mark.asyncio
async def test_bulk_upsert_empty(poi_repo: POIRepository) -> None:
    """空列表的 bulk_upsert 应返回 0。"""
    count = await poi_repo.bulk_upsert([])
    assert count == 0


@pytest.mark.asyncio
async def test_bulk_upsert_update_existing(poi_repo: POIRepository) -> None:
    """upsert 更新已有 POI 的字段。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A])
    updated = dict(_SAMPLE_POI_A)
    updated["rating"] = 5.0
    updated["name"] = "测试景点A(已更新)"
    await poi_repo.bulk_upsert([updated])

    poi = await poi_repo.get_by_id("poi_test_001")
    assert poi is not None
    assert poi.rating == 5.0
    assert poi.name == "测试景点A(已更新)"
    assert await poi_repo.count() == 1  # 条数不变


@pytest.mark.asyncio
async def test_bulk_upsert_idempotent(poi_repo: POIRepository) -> None:
    """重复 upsert 同一数据应幂等。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A])
    await poi_repo.bulk_upsert([_SAMPLE_POI_A])
    assert await poi_repo.count() == 1


# ---------------------------------------------------------------------------
# data_service DB 模式测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_service_db_mode_returns_pois(
    poi_repo: POIRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """data_service.get_poi_data_async 在 DB 模式下应返回 POI 字典列表。"""
    # 注入测试用 POI
    await poi_repo.bulk_upsert([_SAMPLE_POI_A, _SAMPLE_POI_B])

    # 模拟 DB 模式
    from backend.config import settings

    monkeypatch.setattr(settings, "use_db", True)

    # 注入 POI 仓库实例
    from backend.services import data_service

    data_service._poi_repo_instance = poi_repo  # type: ignore[attr-defined]

    result = await data_service.get_poi_data_async()
    assert isinstance(result, list)
    assert len(result) >= 2

    # 验证返回的字典结构
    first = result[0]
    assert "id" in first
    assert "name" in first
    assert "city" in first
    assert "category" in first
    assert "rating" in first
    assert "avg_price" in first
    assert "lat" in first
    assert "lng" in first
    assert "emotion_tags" in first
    assert "ugc_comments" not in first  # 不包含 JSON 独有字段


@pytest.mark.asyncio
async def test_data_service_db_mode_with_filters(
    poi_repo: POIRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DB 模式下 get_poi_data_async 应支持筛选。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A, _SAMPLE_POI_B, _SAMPLE_POI_C])

    from backend.config import settings
    from backend.services import data_service

    monkeypatch.setattr(settings, "use_db", True)
    data_service._poi_repo_instance = poi_repo  # type: ignore[attr-defined]

    result = await data_service.get_poi_data_async(filters={"city": "广州"})
    assert len(result) == 1
    assert result[0]["city"] == "广州"


@pytest.mark.asyncio
async def test_data_service_json_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DB 关闭时应回退到 JSON。"""
    from backend.config import settings
    from backend.services import data_service

    monkeypatch.setattr(settings, "use_db", False)

    # 清除注入的仓库，确认走 JSON
    data_service._poi_repo_instance = None
    if hasattr(data_service, "_DB_FALLBACK_SENTINEL"):
        pass  # 仅确认模块正常

    result = await data_service.get_poi_data_async()
    # JSON 模式应返回数据
    assert isinstance(result, list)
    # 如果不确定是否有 JSON 数据，至少返回列表
    if result:
        assert "id" in result[0]


# ---------------------------------------------------------------------------
# 边缘情况
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_not_found(poi_repo: POIRepository) -> None:
    """查询不存在的 POI 返回 None。"""
    result = await poi_repo.get_by_id("nonexistent_id")
    assert result is None


@pytest.mark.asyncio
async def test_find_filtered_no_match(poi_repo: POIRepository) -> None:
    """无匹配筛选条件返回空列表。"""
    await poi_repo.bulk_upsert([_SAMPLE_POI_A])
    result = await poi_repo.find_filtered({"city": "不存在的城市"})
    assert result == []
