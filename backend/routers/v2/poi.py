"""V2 POI 查询接口（增强版）。"""

from __future__ import annotations

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

router = APIRouter(tags=["v2-poi"])

# 模块级加载
load_pois()


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class SearchRequestV2(BaseModel):
    """V2 POI 搜索请求（增强版，支持约束过滤）。"""

    region: str | None = Field(None, description="按城市筛选", examples=["北京"])
    categories: list[str] | None = Field(None, description="按类别筛选", examples=[["景点"]])
    tags: list[str] | None = Field(None, description="按标签筛选（AND逻辑）")
    keyword: str | None = Field(None, description="按名称模糊搜索")
    min_rating: float | None = Field(None, ge=0, le=5, description="最低评分")
    max_price: int | None = Field(None, ge=0, description="最高人均消费")
    # V2 新增
    exclude_ids: list[str] | None = Field(None, description="排除的POI ID列表")
    accessible: bool | None = Field(None, description="仅返回无障碍通行的POI")
    pet_friendly: bool | None = Field(None, description="仅返回允许携带宠物的POI")
    max_queue_time: int | None = Field(None, ge=0, description="最大排队时间（分钟）")
    emotion_filter: dict | None = Field(
        None,
        description="情绪标签过滤，如 {'excitement_min': 0.7, 'tranquility_min': 0.5}",
    )


class DistanceMatrixRequestV2(BaseModel):
    """V2 距离矩阵请求。"""

    poi_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=50,
        description="POI ID列表（2~50个）",
    )


# ---------------------------------------------------------------------------
# API 实现
# ---------------------------------------------------------------------------


@router.post(
    "/poi/search",
    summary="[V2] 搜索POI（增强版）",
    description=(
        "V2版本的POI搜索接口，新增约束过滤和情绪标签过滤。\n\n"
        "相比V1新增功能：\n"
        "- **exclude_ids** - 排除指定POI\n"
        "- **accessible** - 无障碍通行过滤\n"
        "- **pet_friendly** - 宠物友好过滤\n"
        "- **max_queue_time** - 排队时间过滤\n"
        "- **emotion_filter** - 情绪标签过滤"
    ),
    tags=["v2-poi"],
)
async def search_pois_v2(
    request: SearchRequestV2,
    lat: float | None = Query(None, ge=-90, le=90, description="中心点纬度"),
    lng: float | None = Query(None, ge=-180, le=180, description="中心点经度"),
) -> dict:
    """V2 版本的 POI 搜索（增强版）。"""
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

    # V2 新增过滤
    if request.exclude_ids:
        excl = set(request.exclude_ids)
        results = [p for p in results if p.get("id") not in excl]

    # 先补充字段再做约束过滤
    results = [enrich_poi(p) for p in results]

    if request.accessible is not None:
        results = [
            p
            for p in results
            if p.get("constraints", {}).get("accessible", True) == request.accessible
        ]
    if request.pet_friendly is not None:
        results = [
            p
            for p in results
            if p.get("constraints", {}).get("pet_friendly", False) == request.pet_friendly
        ]
    if request.max_queue_time is not None:
        results = [
            p
            for p in results
            if p.get("constraints", {}).get("queue_time_min", 0) <= request.max_queue_time
        ]

    # 情绪标签过滤
    if request.emotion_filter:
        ef = request.emotion_filter
        for key in [
            "excitement",
            "tranquility",
            "sociability",
            "culture_depth",
            "surprise",
        ]:
            min_key = f"{key}_min"
            max_key = f"{key}_max"
            if min_key in ef:
                results = [
                    p for p in results if p.get("emotion_tags", {}).get(key, 0) >= ef[min_key]
                ]
            if max_key in ef:
                results = [
                    p for p in results if p.get("emotion_tags", {}).get(key, 1) <= ef[max_key]
                ]

    return {"pois": results, "total": len(results)}


@router.get(
    "/poi/detail/{poi_id}",
    summary="[V2] 获取POI详情（增强版）",
    description="V2版本的POI详情接口，返回完整的约束和情绪数据。",
    tags=["v2-poi"],
)
async def get_poi_detail_v2(poi_id: str) -> dict:
    """V2 版本的 POI 详情（增强版）。"""
    poi = get_pois_index().get(poi_id)
    if poi is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"POI not found: {poi_id}", "code": 404},
        )
    enriched = enrich_poi(poi)
    # V2: 确保返回完整的情绪标签和约束数据
    enriched.setdefault("emotion_tags", {})
    enriched.setdefault("constraints", {})
    return enriched


@router.post(
    "/poi/distance-matrix",
    summary="[V2] 计算距离矩阵",
    description="V2版本的距离矩阵计算接口。",
    tags=["v2-poi"],
)
async def get_distance_matrix_v2(request: DistanceMatrixRequestV2) -> dict:
    """V2 版本的距离矩阵计算。"""
    return compute_distance_matrix(request.poi_ids)
