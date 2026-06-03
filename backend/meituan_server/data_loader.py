"""美团模拟数据加载器。

启动时一次性加载 JSON 数据到内存，后续查询纯内存操作。
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

_pois: list[dict[str, Any]] = []
_poi_by_id: dict[str, dict[str, Any]] = {}
_areas: list[dict[str, Any]] = []


def load_all() -> None:
    """加载所有数据文件。"""
    global _pois, _poi_by_id

    poi_file = DATA_DIR / "city_poi_db.json"
    if poi_file.exists():
        _pois = json.loads(poi_file.read_text(encoding="utf-8"))
        _poi_by_id = {p["id"]: p for p in _pois}
        logger.info("加载 %d 条POI数据", len(_pois))

    # 构建商圈数据（按category + 坐标聚类）
    _build_areas()


def _build_areas() -> None:
    """从POI数据推断商圈。"""
    global _areas

    # 简单按坐标方格聚类，每个 0.02° ≈ 2km 的方格为一个商圈
    grid: dict[str, list[dict]] = {}
    for p in _pois:
        lat_key = round(p.get("lat", 0) * 50) / 50  # ≈2km网格
        lng_key = round(p.get("lng", 0) * 50) / 50
        key = f"{lat_key}_{lng_key}"
        grid.setdefault(key, []).append(p)

    # 珠海主要区域名称映射（按坐标范围）
    _district_map = [
        (22.20, 22.27, 113.48, 113.55, "拱北商圈"),
        (22.27, 22.33, 113.50, 113.58, "吉大商圈"),
        (22.25, 22.31, 113.55, 113.62, "香洲商圈"),
        (22.28, 22.35, 113.55, 113.63, "老香洲商圈"),
        (22.33, 22.40, 113.50, 113.60, "唐家湾商圈"),
        (22.10, 22.22, 113.48, 113.60, "横琴商圈"),
        (22.22, 22.30, 113.40, 113.52, "斗门商圈"),
        (22.38, 22.45, 113.47, 113.55, "金湾商圈"),
    ]

    for s_lat, n_lat, w_lng, e_lng, name in _district_map:
        pois_in = [
            p
            for p in _pois
            if s_lat <= p.get("lat", 0) <= n_lat and w_lng <= p.get("lng", 0) <= e_lng
        ]
        if pois_in:
            center_lat = sum(p["lat"] for p in pois_in) / len(pois_in)
            center_lng = sum(p["lng"] for p in pois_in) / len(pois_in)
            _areas.append(
                {
                    "name": name,
                    "city": "珠海",
                    "center_lat": round(center_lat, 4),
                    "center_lng": round(center_lng, 4),
                    "boundary": {
                        "south": s_lat,
                        "north": n_lat,
                        "west": w_lng,
                        "east": e_lng,
                    },
                    "poi_count": len(pois_in),
                    "poi_categories": list({p["category"] for p in pois_in}),
                }
            )

    logger.info("构建 %d 个商圈", len(_areas))


# ---------------------------------------------------------------------------
# 查询函数
# ---------------------------------------------------------------------------


def get_all_pois() -> list[dict[str, Any]]:
    return _pois


def get_poi_by_id(poi_id: str) -> dict[str, Any] | None:
    return _poi_by_id.get(poi_id)


def get_areas() -> list[dict[str, Any]]:
    return _areas
