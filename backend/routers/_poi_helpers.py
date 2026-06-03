"""POI 路由共享工具函数。

v1/poi.py、v2/poi.py、poi.py 共用的数据加载、辅助函数和距离矩阵计算。
"""

from __future__ import annotations

import math
from pathlib import Path

from fastapi import HTTPException

from backend.services.cache import distance_cache
from backend.services.vectorized import distance_matrix_vectorized

# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

_pois_data: list[dict] = []
_pois_index: dict[str, dict] = {}


def load_pois() -> None:
    """加载 city_poi_db.json 到模块级缓存。"""
    global _pois_data, _pois_index
    import json

    data_file = Path(__file__).parent.parent / "data" / "city_poi_db.json"
    with open(data_file, encoding="utf-8") as f:
        _pois_data = json.load(f)
    _pois_index = {p["id"]: p for p in _pois_data if "id" in p}


def get_pois_data() -> list[dict]:
    """返回 POI 列表（浅拷贝）。"""
    return list(_pois_data)


def get_pois_index() -> dict[str, dict]:
    """返回 POI 索引字典。"""
    return _pois_index


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
    """根据均价返回价格区间标签。"""
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
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
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
# 距离矩阵计算（V1/V2/主路由共用）
# ---------------------------------------------------------------------------


def compute_distance_matrix(poi_ids: list[str]) -> dict:
    """根据 POI ID 列表计算距离矩阵，带缓存。"""
    cache_key = f"dm:{','.join(sorted(poi_ids))}"
    cached = distance_cache.get(cache_key)
    if cached is not None:
        return cached

    pois: list[dict] = []
    for pid in poi_ids:
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

    result = {"matrix": matrix, "poi_ids": poi_ids}
    distance_cache.set(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# 基础搜索过滤（V1/V2 共用逻辑）
# ---------------------------------------------------------------------------


def apply_basic_filters(
    results: list[dict],
    *,
    region: str | None = None,
    categories: list[str] | None = None,
    tags: list[str] | None = None,
    keyword: str | None = None,
    min_rating: float | None = None,
    max_price: int | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> list[dict]:
    """应用基础过滤条件，返回过滤后的列表。"""
    if region:
        results = [p for p in results if p.get("city") == region]
    if categories:
        cats = set(categories)
        results = [p for p in results if p.get("category") in cats]
    if tags:
        req_tags = set(tags)
        results = [p for p in results if req_tags.issubset(set(p.get("tags", [])))]
    if keyword:
        kw = keyword.lower()
        results = [p for p in results if kw in p.get("name", "").lower()]
    if min_rating is not None:
        results = [p for p in results if p.get("rating", 0) >= min_rating]
    if max_price is not None:
        results = [p for p in results if p.get("avg_price", 0) <= max_price]
    if lat is not None and lng is not None:
        results = [
            p for p in results if haversine(lat, lng, p.get("lat", 0), p.get("lng", 0)) <= 10_000
        ]
    return results
