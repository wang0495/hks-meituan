"""美团模拟API — 7个数据接口。

模拟美团平台对外暴露的商户/评价/路线数据能力，
供 Agent 通过 tool_use 调用获取原始数据。
"""

from __future__ import annotations

import math
import random
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.meituan_server.data_loader import (
    get_all_pois,
    get_areas,
    get_poi_by_id,
)

router = APIRouter(prefix="/api", tags=["meituan-mock"])


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _generate_address(poi: dict) -> str:
    """根据坐标生成模拟地址。"""
    city = poi.get("city", "珠海")
    name = poi.get("name", "")
    lat = poi.get("lat", 0)
    # 根据经纬度粗略匹配区域
    if lat >= 22.33:
        district = "高新区"
    elif lat >= 22.28:
        district = "香洲区"
    elif lat >= 22.24:
        district = "拱北/吉大"
    else:
        district = "横琴新区"
    return f"广东省{city}市{district}{name}附近"


# ---------------------------------------------------------------------------
# 1. POI 搜索
# ---------------------------------------------------------------------------


def _filter_by_distance(pois: list[dict], lat: float, lng: float, radius_km: float) -> list[dict]:
    """按距离过滤并排序POI。"""
    with_dist = []
    for p in pois:
        if p.get("lat") and p.get("lng"):
            d = _haversine_km(lat, lng, p["lat"], p["lng"])
            p["distance_km"] = round(d, 2)
            if d <= radius_km:
                with_dist.append(p)
    return sorted(with_dist, key=lambda x: x["distance_km"])


def _format_poi_output(poi: dict) -> dict:
    """格式化POI输出，去掉内部字段。"""
    return {
        "id": poi["id"],
        "name": poi["name"],
        "category": poi.get("category"),
        "rating": poi.get("rating"),
        "avg_price": poi.get("avg_price"),
        "lat": poi.get("lat"),
        "lng": poi.get("lng"),
        "address": _generate_address(poi),
        "business_hours": poi.get("business_hours", ""),
        "tags": poi.get("tags", []),
        "avg_stay_min": poi.get("avg_stay_min"),
        "queue_prone": poi.get("queue_prone", False),
        "distance_km": poi.get("distance_km"),
    }


@router.get("/poi/search", summary="商户搜索")
def poi_search(
    keyword: str | None = Query(None, description="搜索关键词"),
    category: str | None = Query(None, description="品类：餐饮/文化/娱乐/景点..."),
    lat: float | None = Query(None, description="用户纬度"),
    lng: float | None = Query(None, description="用户经度"),
    radius_km: float = Query(10.0, description="搜索半径(公里)", ge=0.1, le=100),
    price_min: float | None = Query(None, description="最低人均消费"),
    price_max: float | None = Query(None, description="最高人均消费"),
    rating_min: float | None = Query(None, description="最低评分"),
    limit: int = Query(50, description="最大返回数", ge=1, le=200),
    offset: int = Query(0, description="偏移量", ge=0),
) -> dict[str, Any]:
    """按条件搜索商户，返回POI列表。"""
    results = get_all_pois()

    if keyword:
        kw = keyword.lower()
        results = [
            p
            for p in results
            if kw in p.get("name", "").lower() or any(kw in t for t in p.get("tags", []))
        ]
    if category:
        results = [p for p in results if p.get("category") == category]
    if price_min is not None:
        results = [p for p in results if p.get("avg_price", 0) >= price_min]
    if price_max is not None:
        results = [p for p in results if p.get("avg_price", 0) <= price_max]
    if rating_min is not None:
        results = [p for p in results if p.get("rating", 0) >= rating_min]

    if lat is not None and lng is not None:
        results = _filter_by_distance(results, lat, lng, radius_km)
    else:
        results = sorted(results, key=lambda x: x.get("rating", 0), reverse=True)

    total = len(results)
    items = [_format_poi_output(p) for p in results[offset : offset + limit]]

    return {"total": total, "count": len(items), "items": items}


# ---------------------------------------------------------------------------
# 2. POI 详情
# ---------------------------------------------------------------------------


@router.get("/poi/{poi_id}", summary="商户详情")
def poi_detail(poi_id: str) -> dict[str, Any]:
    """获取单个商户完整信息。"""
    poi = get_poi_by_id(poi_id)
    if not poi:
        raise HTTPException(404, f"POI {poi_id} 不存在")

    constraints = poi.get("constraints", {})
    return {
        "id": poi["id"],
        "name": poi["name"],
        "city": poi.get("city"),
        "category": poi.get("category"),
        "rating": poi.get("rating"),
        "avg_price": poi.get("avg_price"),
        "lat": poi.get("lat"),
        "lng": poi.get("lng"),
        "address": _generate_address(poi),
        "business_hours": poi.get("business_hours", ""),
        "opening_hours": constraints.get("opening_hours", ""),
        "tags": poi.get("tags", []),
        "avg_stay_min": poi.get("avg_stay_min"),
        "queue_prone": poi.get("queue_prone", False),
        "queue_time_min": constraints.get("queue_time_min", 0),
        "accessible": constraints.get("accessible", False),
        "pet_friendly": constraints.get("pet_friendly", False),
        "suitability": poi.get("_suitability", {}),
        "emotion_tags": poi.get("emotion_tags", {}),
        "scene_tags": poi.get("_scene_tags", []),
    }


# ---------------------------------------------------------------------------
# 3. POI 评价（UGC）
# ---------------------------------------------------------------------------


@router.get("/poi/{poi_id}/reviews", summary="用户评价")
def poi_reviews(
    poi_id: str,
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """获取商户的UGC用户评价。"""
    poi = get_poi_by_id(poi_id)
    if not poi:
        raise HTTPException(404, f"POI {poi_id} 不存在")

    comments = poi.get("ugc_comments", [])
    items = comments[:limit]

    # 计算评价摘要
    avg_rating = sum(c["rating"] for c in comments) / len(comments) if comments else 0
    # 高频词提取（简单从tags里取）
    keywords = list({w for c in items for w in c.get("content", c.get("text", "")) if len(w) >= 2})[
        :8
    ]

    return {
        "poi_id": poi_id,
        "poi_name": poi["name"],
        "total_reviews": len(comments),
        "avg_rating": round(avg_rating, 1),
        "keywords": keywords,
        "reviews": [
            {
                "user": c.get("user", "匿名"),
                "text": c.get("content", c.get("text", "")),
                "rating": c.get("rating"),
            }
            for c in items
        ],
    }


# ---------------------------------------------------------------------------
# 4. 商户位置
# ---------------------------------------------------------------------------


@router.get("/poi/{poi_id}/location", summary="商户位置")
def poi_location(poi_id: str) -> dict[str, Any]:
    """获取商户精确位置信息。"""
    poi = get_poi_by_id(poi_id)
    if not poi:
        raise HTTPException(404, f"POI {poi_id} 不存在")

    lat = poi.get("lat")
    lng = poi.get("lng")

    # 找附近地标（距离最近的3个不同品类POI）
    all_pois = get_all_pois()
    nearby = []
    for other in all_pois:
        if other["id"] == poi_id or not other.get("lat"):
            continue
        d = _haversine_km(lat, lng, other["lat"], other["lng"])
        if d <= 2.0:
            nearby.append(
                {"name": other["name"], "category": other["category"], "distance_km": round(d, 2)}
            )
    nearby.sort(key=lambda x: x["distance_km"])
    nearby = nearby[:5]

    return {
        "poi_id": poi_id,
        "poi_name": poi["name"],
        "lat": lat,
        "lng": lng,
        "address": _generate_address(poi),
        "district": (
            _generate_address(poi).split("区")[-1].replace(poi["name"], "").replace("附近", "")
            if "区" in _generate_address(poi)
            else ""
        ),
        "nearby_landmarks": nearby,
    }


# ---------------------------------------------------------------------------
# 5. 路线距离
# ---------------------------------------------------------------------------


@router.get("/route/distance", summary="路线距离")
def route_distance(
    origin_lat: float = Query(..., description="起点纬度"),
    origin_lng: float = Query(..., description="起点经度"),
    dest_lat: float = Query(..., description="终点纬度"),
    dest_lng: float = Query(..., description="终点经度"),
    mode: str = Query("driving", description="出行方式: driving/walking/cycling"),
) -> dict[str, Any]:
    """计算两点间距离和预估耗时。"""
    distance_km = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)

    # 不同交通方式的速度假设
    speed_map = {"driving": 30, "walking": 5, "cycling": 15, "transit": 25}
    speed = speed_map.get(mode, 30)
    time_min = (distance_km / speed) * 60

    # 加点随机拥堵因子
    traffic_factor = random.uniform(0.9, 1.4) if mode == "driving" else 1.0
    time_min *= traffic_factor

    return {
        "origin": {"lat": origin_lat, "lng": origin_lng},
        "destination": {"lat": dest_lat, "lng": dest_lng},
        "mode": mode,
        "distance_km": round(distance_km, 2),
        "time_min": round(time_min, 1),
        "traffic_factor": round(traffic_factor, 2),
    }


# ---------------------------------------------------------------------------
# 6. 热门推荐
# ---------------------------------------------------------------------------


@router.get("/hot/trending", summary="热门推荐")
def hot_trending(
    city: str = Query("珠海", description="城市"),
    category: str | None = Query(None, description="品类筛选"),
    time_slot: str | None = Query(None, description="时段: morning/afternoon/evening/late_night"),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """获取当前热门商户排行。"""
    results = get_all_pois()

    if category:
        results = [p for p in results if p.get("category") == category]

    # 按评分 + 随机热度因子排序
    for p in results:
        base_rating = p.get("rating", 3)
        hotness = random.uniform(0.8, 1.2)
        p["_hot_score"] = base_rating * hotness

    results.sort(key=lambda x: x["_hot_score"], reverse=True)
    results = results[:limit]

    items = []
    for i, p in enumerate(results):
        items.append(
            {
                "rank": i + 1,
                "id": p["id"],
                "name": p["name"],
                "category": p.get("category"),
                "rating": p.get("rating"),
                "avg_price": p.get("avg_price"),
                "hot_score": round(p["_hot_score"], 1),
                "tags": p.get("tags", []),
            }
        )

    return {
        "city": city,
        "time_slot": time_slot,
        "count": len(items),
        "items": items,
    }


# ---------------------------------------------------------------------------
# 7. 商圈范围
# ---------------------------------------------------------------------------


@router.get("/area/boundaries", summary="商圈范围")
def area_boundaries(
    city: str = Query("珠海", description="城市"),
) -> dict[str, Any]:
    """获取城市主要商圈信息。"""
    areas = get_areas()
    return {
        "city": city,
        "count": len(areas),
        "areas": [
            {
                "name": a["name"],
                "center": {"lat": a["center_lat"], "lng": a["center_lng"]},
                "boundary": a["boundary"],
                "poi_count": a["poi_count"],
                "main_categories": a["poi_categories"][:10],
            }
            for a in areas
        ],
    }
