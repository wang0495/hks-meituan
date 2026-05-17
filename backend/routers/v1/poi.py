"""V1 POI 查询接口。"""

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

router = APIRouter(tags=["v1-poi"])

# 模块级加载
load_pois()


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class SearchRequestV1(BaseModel):
    """V1 POI 搜索请求。"""

    region: Optional[str] = Field(None, description="按城市筛选", examples=["北京"])
    categories: Optional[list[str]] = Field(
        None, description="按类别筛选", examples=[["景点"]]
    )
    tags: Optional[list[str]] = Field(None, description="按标签筛选（AND逻辑）")
    keyword: Optional[str] = Field(None, description="按名称模糊搜索")
    min_rating: Optional[float] = Field(None, ge=0, le=5, description="最低评分")
    max_price: Optional[int] = Field(None, ge=0, description="最高人均消费")


class DistanceMatrixRequestV1(BaseModel):
    """V1 距离矩阵请求。"""

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
    summary="[V1] 搜索POI",
    description="V1版本的POI搜索接口。",
    tags=["v1-poi"],
)
async def search_pois_v1(
    request: SearchRequestV1,
    lat: Optional[float] = Query(None, ge=-90, le=90, description="中心点纬度"),
    lng: Optional[float] = Query(None, ge=-180, le=180, description="中心点经度"),
) -> dict:
    """V1 版本的 POI 搜索。"""
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
    results = [enrich_poi(p) for p in results]
    return {"pois": results, "total": len(results)}


@router.get(
    "/poi/detail/{poi_id}",
    summary="[V1] 获取POI详情",
    description="V1版本的POI详情接口。",
    tags=["v1-poi"],
)
async def get_poi_detail_v1(poi_id: str) -> dict:
    """V1 版本的 POI 详情。"""
    poi = get_pois_index().get(poi_id)
    if poi is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"POI not found: {poi_id}", "code": 404},
        )
    return enrich_poi(poi)


@router.post(
    "/poi/distance-matrix",
    summary="[V1] 计算距离矩阵",
    description="V1版本的距离矩阵计算接口。",
    tags=["v1-poi"],
)
async def get_distance_matrix_v1(request: DistanceMatrixRequestV1) -> dict:
    """V1 版本的距离矩阵计算。"""
    return compute_distance_matrix(request.poi_ids)
