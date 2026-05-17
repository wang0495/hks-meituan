"""POI (兴趣点) 查询与距离计算接口。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.routers._poi_helpers import (
    apply_basic_filters,
    compute_distance_matrix,
    enrich_poi,
    get_pois_data,
    get_pois_index,
    load_pois,
)
from backend.services.cache import distance_cache
from backend.services.geo import haversine

router = APIRouter(prefix="/api/poi", tags=["POI"])

# 模块级加载
load_pois()

# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """POI搜索请求体。"""

    region: Optional[str] = Field(
        None,
        description='按城市筛选（精确匹配），如 "北京"、"上海"',
        examples=["北京"],
    )
    categories: Optional[list[str]] = Field(
        None,
        description='按类别筛选（OR逻辑），如 ["景点", "餐厅"]',
        examples=[["景点", "公园"]],
    )
    tags: Optional[list[str]] = Field(
        None,
        description="按标签筛选（AND逻辑，POI须包含所有指定标签）",
        examples=[["安静", "文艺"]],
    )
    exclude_ids: Optional[list[str]] = Field(
        None,
        description="排除的POI ID列表",
    )
    keyword: Optional[str] = Field(
        None,
        description="按名称模糊搜索（不区分大小写）",
        examples=["故宫"],
    )
    min_rating: Optional[float] = Field(
        None,
        ge=0,
        le=5,
        description="最低评分过滤（0~5）",
        examples=[4.0],
    )
    max_price: Optional[int] = Field(
        None,
        ge=0,
        description="最高人均消费过滤（元）",
        examples=[200],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "region": "北京",
                    "categories": ["景点"],
                    "tags": ["安静"],
                    "min_rating": 4.0,
                    "max_price": 100,
                }
            ]
        }
    }


class SearchResponse(BaseModel):
    """POI搜索响应。"""

    pois: list[dict] = Field(
        ..., description="匹配的POI列表（已补充情绪标签和价格区间）"
    )
    total: int = Field(..., ge=0, description="匹配总数")


class DistanceMatrixRequest(BaseModel):
    """距离矩阵请求体。"""

    poi_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=50,
        description="POI ID列表（2~50个），将计算这些POI两两之间的距离矩阵",
        examples=[["poi_001", "poi_002", "poi_003"]],
    )


class DistanceItem(BaseModel):
    """距离矩阵元素。"""

    distance_m: int = Field(
        ..., ge=0, description="距离（米），haversine * 1.3 道路系数"
    )
    time_min: int = Field(..., ge=0, description="预估耗时（分钟），按30km/h计算")


class DistanceMatrixResponse(BaseModel):
    """距离矩阵响应。"""

    matrix: list[list[DistanceItem]] = Field(
        ...,
        description="N×N距离矩阵。matrix[i][j] 表示从 poi_ids[i] 到 poi_ids[j] 的距离信息。对角线元素 distance_m=0, time_min=0。",
    )
    poi_ids: list[str] = Field(
        ...,
        description="对应的POI ID列表，顺序与矩阵行列索引一致",
    )


# ---------------------------------------------------------------------------
# API 实现
# ---------------------------------------------------------------------------


@router.post(
    "/search",
    summary="搜索POI",
    description=(
        "多维度筛选搜索兴趣点（POI）。\n\n"
        "## 过滤逻辑（按顺序依次应用）\n\n"
        "1. **城市筛选** - 精确匹配 `region` 字段\n"
        "2. **类别筛选** - POI类别在 `categories` 列表中（OR逻辑）\n"
        "3. **标签匹配** - POI须包含 `tags` 列表中的所有标签（AND逻辑）\n"
        "4. **排除ID** - 排除 `exclude_ids` 中的POI\n"
        "5. **关键词搜索** - 名称模糊匹配（不区分大小写）\n"
        "6. **评分过滤** - 评分 >= `min_rating`\n"
        "7. **价格过滤** - 人均消费 <= `max_price`\n"
        "8. **地理范围** - 若提供 `lat`/`lng`，筛选10km以内的POI\n\n"
        "所有过滤条件为AND关系，同时生效。\n\n"
        "返回的每个POI会自动补充 `emotion_tags`（情绪标签）、`constraints`（约束条件）"
        "和 `price_range`（价格区间）字段。"
    ),
    response_description="匹配的POI列表及总数",
    responses={
        200: {
            "description": "搜索结果",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/SearchResponse"},
                }
            },
        }
    },
    tags=["POI"],
)
async def search_pois(
    request: SearchRequest,
    lat: Optional[float] = Query(
        None,
        ge=-90,
        le=90,
        description="中心点纬度（与lng配合使用，筛选10km范围内的POI）",
    ),
    lng: Optional[float] = Query(
        None,
        ge=-180,
        le=180,
        description="中心点经度（与lat配合使用，筛选10km范围内的POI）",
    ),
) -> dict:
    """
    搜索兴趣点。

    支持按城市、类别、标签、关键词、评分、价格、地理位置等多维度筛选。
    """
    results = apply_basic_filters(
        get_pois_data(),
        region=request.region,
        categories=request.categories,
        tags=request.tags,
        keyword=request.keyword,
        min_rating=request.min_rating,
        max_price=request.max_price,
        lat=lat,
        lng=lng,
    )

    # 排除 ID
    if request.exclude_ids:
        excl = set(request.exclude_ids)
        results = [p for p in results if p.get("id") not in excl]

    results = [enrich_poi(p) for p in results]
    return {"pois": results, "total": len(results)}


@router.get(
    "/detail/{poi_id}",
    summary="获取POI详情",
    description=(
        "获取单个POI的完整信息。\n\n"
        "返回的POI数据包含：\n"
        "- 基本信息（名称、类别、评分、价格等）\n"
        "- 位置信息（经纬度）\n"
        "- 营业时间\n"
        "- 标签列表\n"
        "- **情绪标签**（6维：excitement, tranquility, sociability, culture_depth, surprise, physical_demand）\n"
        "- **约束条件**（无障碍、宠物友好、排队时间等）\n"
        "- **价格区间**（免费/便宜/中等/较贵/高端）"
    ),
    response_description="POI完整详情",
    responses={
        200: {
            "description": "POI详情",
            "content": {
                "application/json": {
                    "example": {
                        "id": "poi_001",
                        "name": "故宫博物院",
                        "category": "景点",
                        "city": "北京",
                        "rating": 4.8,
                        "avg_price": 60,
                        "lat": 39.9163,
                        "lng": 116.3972,
                        "business_hours": "08:30-17:00",
                        "tags": ["历史", "文化", "拍照"],
                        "emotion_tags": {
                            "excitement": 0.6,
                            "tranquility": 0.7,
                            "sociability": 0.3,
                            "culture_depth": 0.95,
                            "surprise": 0.7,
                            "physical_demand": 0.5,
                        },
                        "constraints": {
                            "accessible": True,
                            "pet_friendly": False,
                            "queue_time_min": 15,
                            "opening_hours": "08:30-17:00",
                            "has_restroom": True,
                        },
                        "price_range": "中等",
                    }
                }
            },
        },
        404: {
            "description": "POI不存在",
            "content": {
                "application/json": {
                    "example": {"detail": {"error": "POI not found: xxx", "code": 404}},
                }
            },
        },
    },
    tags=["POI"],
)
async def get_poi_detail(
    poi_id: str,
    lat: Optional[float] = Query(
        None,
        ge=-90,
        le=90,
        description="用户当前纬度（预留，可用于距离计算）",
    ),
    lng: Optional[float] = Query(
        None,
        ge=-180,
        le=180,
        description="用户当前经度（预留，可用于距离计算）",
    ),
) -> dict:
    """
    获取POI详情。

    根据POI ID返回完整的POI信息，包括情绪标签和约束条件。
    """
    poi = get_pois_index().get(poi_id)
    if poi is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"POI not found: {poi_id}", "code": 404},
        )
    return enrich_poi(poi)


@router.post(
    "/distance-matrix",
    summary="计算距离矩阵",
    description=(
        "计算多个POI之间的距离矩阵。\n\n"
        "## 计算方式\n\n"
        "- 使用 **haversine公式** 计算球面直线距离\n"
        "- 乘以 **1.3** 作为实际道路距离估算\n"
        "- 按 **30 km/h** 平均速度估算行车时间\n\n"
        "## 缓存\n\n"
        "结果会缓存，相同POI组合的重复请求直接返回缓存结果。\n\n"
        "## 限制\n\n"
        "- 输入 2~50 个POI ID\n"
        "- 所有ID必须有效，否则返回400错误\n"
        "- 返回 N×N 矩阵，对角线元素为 `{distance_m: 0, time_min: 0}`"
    ),
    response_description="距离矩阵及对应的POI ID列表",
    responses={
        200: {
            "description": "距离矩阵",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/DistanceMatrixResponse"},
                    "example": {
                        "matrix": [
                            [
                                {"distance_m": 0, "time_min": 0},
                                {"distance_m": 3500, "time_min": 7},
                            ],
                            [
                                {"distance_m": 3500, "time_min": 7},
                                {"distance_m": 0, "time_min": 0},
                            ],
                        ],
                        "poi_ids": ["poi_001", "poi_002"],
                    },
                }
            },
        },
        400: {
            "description": "POI ID无效",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {"error": "POI not found: invalid_id", "code": 400}
                    },
                }
            },
        },
    },
    tags=["POI"],
)
async def get_distance_matrix(request: DistanceMatrixRequest) -> dict:
    """
    计算距离矩阵。

    输入POI ID列表，返回N x N的距离矩阵。距离使用haversine公式计算，
    乘以1.3的道路系数，时间按30km/h估算。
    """
    return compute_distance_matrix(request.poi_ids)
