"""V1 POI 查询接口。"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.cache import distance_cache
from backend.services.vectorized import distance_matrix_vectorized

router = APIRouter(tags=["v1-poi"])


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

_pois_data: list[dict] = []
_pois_index: dict[str, dict] = {}


def load_pois() -> None:
    global _pois_data, _pois_index
    data_file = Path(__file__).parent.parent.parent / "data" / "city_poi_db.json"
    with open(data_file, encoding="utf-8") as f:
        import json

        _pois_data = json.load(f)
    _pois_index = {p["id"]: p for p in _pois_data if "id" in p}


load_pois()


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

_PRICE_THRESHOLDS = [
    (0, "免费"),
    (50, "便宜"),
    (150, "中等"),
    (500, "较贵"),
    (float("inf"), "高端"),
]


def get_price_range(avg_price: float) -> str:
    for threshold, label in _PRICE_THRESHOLDS:
        if avg_price <= threshold:
            return label
    return "高端"


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """返回两点间的球面直线距离（米）。"""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def enrich_poi(poi: dict) -> dict:
    """为 POI 补充 emotion_tags、constraints、price_range 字段。"""
    if "emotion_tags" not in poi:
        poi["emotion_tags"] = {
            "excitement": 0.5,
            "tranquility": 0.5,
            "sociability": 0.5,
            "culture_depth": 0.5,
            "surprise": 0.5,
            "physical_demand": 0.5,
        }
    if "constraints" not in poi:
        poi["constraints"] = {
            "accessible": True,
            "pet_friendly": False,
            "queue_time_min": 15 if poi.get("queue_prone") else 0,
            "opening_hours": poi.get("business_hours", "09:00-17:00"),
            "has_restroom": True,
        }
    poi["price_range"] = get_price_range(poi.get("avg_price", 0))
    return poi


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
):
    """V1 版本的 POI 搜索。"""
    results = list(_pois_data)

    if request.region:
        results = [p for p in results if p.get("city") == request.region]
    if request.categories:
        cats = set(request.categories)
        results = [p for p in results if p.get("category") in cats]
    if request.tags:
        req_tags = set(request.tags)
        results = [p for p in results if req_tags.issubset(set(p.get("tags", [])))]
    if request.keyword:
        kw = request.keyword.lower()
        results = [p for p in results if kw in p.get("name", "").lower()]
    if request.min_rating is not None:
        results = [p for p in results if p.get("rating", 0) >= request.min_rating]
    if request.max_price is not None:
        results = [p for p in results if p.get("avg_price", 0) <= request.max_price]
    if lat is not None and lng is not None:
        results = [
            p
            for p in results
            if haversine(lat, lng, p.get("lat", 0), p.get("lng", 0)) <= 10_000
        ]

    results = [enrich_poi(p) for p in results]
    return {"pois": results, "total": len(results)}


@router.get(
    "/poi/detail/{poi_id}",
    summary="[V1] 获取POI详情",
    description="V1版本的POI详情接口。",
    tags=["v1-poi"],
)
async def get_poi_detail_v1(poi_id: str):
    """V1 版本的 POI 详情。"""
    poi = _pois_index.get(poi_id)
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
async def get_distance_matrix_v1(request: DistanceMatrixRequestV1):
    """V1 版本的距离矩阵计算。"""
    cache_key = f"dm:{','.join(sorted(request.poi_ids))}"
    cached_result = distance_cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    pois: list[dict] = []
    for pid in request.poi_ids:
        poi = _pois_index.get(pid)
        if poi is None:
            raise HTTPException(
                status_code=400,
                detail={"error": f"POI not found: {pid}", "code": 400},
            )
        pois.append(poi)

    dist_matrix = distance_matrix_vectorized(pois)
    time_matrix = dist_matrix / 1000.0 / 30.0 * 60.0

    n = len(pois)
    matrix: list[list[dict]] = []
    for i in range(n):
        row: list[dict] = []
        for j in range(n):
            if i == j:
                row.append({"distance_m": 0, "time_min": 0})
            else:
                row.append(
                    {
                        "distance_m": round(float(dist_matrix[i, j])),
                        "time_min": round(float(time_matrix[i, j])),
                    }
                )
        matrix.append(row)

    result = {"matrix": matrix, "poi_ids": request.poi_ids}
    distance_cache.set(cache_key, result)
    return result
