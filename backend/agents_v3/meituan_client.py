"""美团API客户端 — agent通过此模块获取数据，替代直接读JSON。

启动前确保 meituan_server 已运行在 localhost:8001。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE = "http://localhost:8001/api"

# 模块级缓存（单次测试run内有效）
_cache: dict[str, Any] | None = None
_cache_key: str = ""


def _normalize(poi: dict) -> dict:
    """把API返回的字段名映射为agent期望的格式。"""
    # constraints 重建
    constraints = {
        "opening_hours": poi.get("opening_hours", poi.get("business_hours", "")),
        "queue_time_min": poi.get("queue_time_min", 0),
        "accessible": poi.get("accessible", False),
        "pet_friendly": poi.get("pet_friendly", False),
    }

    # UGC评价摘要（取前2条有实质内容的）
    ugc_summary = ""
    for c in poi.get("ugc_comments", [])[:4]:
        content = c.get("content", c.get("text", ""))
        if content and len(content.strip()) > 5:
            ugc_summary += f"「{content.strip()[:60]}」"

    return {
        "id": poi.get("id", ""),
        "name": poi.get("name", ""),
        "city": poi.get("city", "珠海"),
        "category": poi.get("category", ""),
        "rating": poi.get("rating"),
        "avg_price": poi.get("avg_price", 0),
        "lat": poi.get("lat"),
        "lng": poi.get("lng"),
        "business_hours": poi.get("business_hours", ""),
        "tags": poi.get("tags", []),
        "avg_stay_min": poi.get("avg_stay_min", 60),
        "queue_prone": poi.get("queue_prone", False),
        # agent期望的字段名
        "_scene_tags": poi.get("scene_tags", []),
        "_suitability": poi.get("suitability", {}),
        "emotion_tags": poi.get("emotion_tags", {}),
        "constraints": constraints,
        "_llm_quality": {"is_tourist": poi.get("rating", 0) >= 4.0, "score": int(poi.get("rating", 0)), "issues": []},
        # UGC评价摘要
        "_ugc_summary": ugc_summary,
    }


async def fetch_pois(
    category: str | None = None,
    price_max: float | None = None,
    rating_min: float | None = None,
) -> list[dict[str, Any]]:
    """从美团API获取POI列表，高评分的自动enrich详情。

    Args:
        category: 品类过滤
        price_max: 最高人均价
        rating_min: 最低评分

    Returns:
        规范化后的POI列表
    """
    global _cache, _cache_key

    # 简单缓存：同参数只请求一次
    key = f"{category}-{price_max}-{rating_min}"
    if _cache is not None and _cache_key == key:
        return _cache  # type: ignore

    async with httpx.AsyncClient(base_url=BASE, timeout=2.0) as client:
        # 1. 分页获取全部POI（API限制limit最大200）
        items: list[dict] = []
        page_size = 200
        offset = 0
        while True:
            params: dict[str, Any] = {"limit": page_size, "offset": offset}
            if category:
                params["category"] = category
            if price_max is not None:
                params["price_max"] = price_max
            if rating_min is not None:
                params["rating_min"] = rating_min

            resp = await client.get("/poi/search", params=params)
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("items", [])
            items.extend(batch)
            total = data.get("total", 0)
            offset += page_size
            if offset >= total or not batch:
                break

        if not items:
            _cache = []
            _cache_key = key
            return []

        # 2. 按rating排序，top 200 enrich详情（获取scene_tags/suitability等）
        items.sort(key=lambda x: x.get("rating", 0), reverse=True)
        top_ids = [it["id"] for it in items[:200]]

        detail_map: dict[str, dict] = {}
        sem = asyncio.Semaphore(50)

        async def _fetch_detail(poi_id: str) -> None:
            async with sem:
                try:
                    r = await client.get(f"/poi/{poi_id}")
                    if r.status_code == 200:
                        detail_map[poi_id] = r.json()
                except Exception:
                    logger.debug("individual POI detail fetch failed for %s", poi_id, exc_info=True)

        await asyncio.gather(*[_fetch_detail(pid) for pid in top_ids])

        # 3. 合并：有详情用详情，没有用搜索结果
        result = []
        for it in items:
            raw = detail_map.get(it["id"], it)
            result.append(_normalize(raw))

        logger.info("从美团API获取 %d 条POI（%d 条enriched）", len(result), len(detail_map))
        _cache = result
        _cache_key = key
        return result


def clear_cache() -> None:
    """清缓存（测试场景切换时用）。"""
    global _cache, _cache_key
    _cache = None
    _cache_key = ""
