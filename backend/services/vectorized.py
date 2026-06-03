"""CityFlow 向量化距离计算模块。

用 numpy 批量计算 haversine 距离矩阵，比逐对循环快 10-100 倍。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from backend.services.geo import _AVG_SPEED_KMH, _EARTH_RADIUS_M, _ROAD_FACTOR

if TYPE_CHECKING:
    from numpy.typing import NDArray

# 实际道路系数


# ---------------------------------------------------------------------------
# 向量化 haversine
# ---------------------------------------------------------------------------


def haversine_vectorized(
    lat1: NDArray[np.floating[Any]],
    lon1: NDArray[np.floating[Any]],
    lat2: NDArray[np.floating[Any]],
    lon2: NDArray[np.floating[Any]],
) -> NDArray[np.floating[Any]]:
    """向量化 haversine 距离计算（米）。

    所有输入应为同 shape 的 numpy 数组，支持广播。
    """
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return _EARTH_RADIUS_M * c


# ---------------------------------------------------------------------------
# 距离矩阵
# ---------------------------------------------------------------------------


def distance_matrix_vectorized(
    pois: list[dict[str, Any]],
    road_factor: float = _ROAD_FACTOR,
) -> NDArray[np.floating[Any]]:
    """向量化计算 POI 间距离矩阵（米，含道路系数）。

    Args:
        pois: POI 列表，每个需含 lat, lng 字段
        road_factor: 道路弯曲系数

    Returns:
        shape (n, n) 的距离矩阵
    """
    n = len(pois)
    if n == 0:
        return np.array([], dtype=np.float64).reshape(0, 0)

    lats = np.array([p["lat"] for p in pois], dtype=np.float64)
    lngs = np.array([p["lng"] for p in pois], dtype=np.float64)

    # 广播计算 n*n 矩阵
    lat1, lat2 = np.meshgrid(lats, lats)
    lon1, lon2 = np.meshgrid(lngs, lngs)

    matrix = haversine_vectorized(lat1, lon1, lat2, lon2) * road_factor
    return matrix


def travel_time_matrix_vectorized(
    pois: list[dict[str, Any]],
    speed_kmh: float = _AVG_SPEED_KMH,
    road_factor: float = _ROAD_FACTOR,
) -> NDArray[np.floating[Any]]:
    """向量化计算 POI 间旅行时间矩阵（分钟）。

    Args:
        pois: POI 列表
        speed_kmh: 平均速度 km/h
        road_factor: 道路弯曲系数

    Returns:
        shape (n, n) 的时间矩阵（分钟）
    """
    dist_matrix = distance_matrix_vectorized(pois, road_factor)
    # 距离(米) -> 时间(分钟)
    return dist_matrix / 1000.0 / speed_kmh * 60.0


# ---------------------------------------------------------------------------
# 单点到批量距离
# ---------------------------------------------------------------------------


def distance_from_point_vectorized(
    lat: float,
    lng: float,
    pois: list[dict[str, Any]],
    road_factor: float = _ROAD_FACTOR,
) -> NDArray[np.floating[Any]]:
    """计算一个点到多个 POI 的距离数组（米）。

    Args:
        lat: 起点纬度
        lng: 起点经度
        pois: 目标 POI 列表
        road_factor: 道路系数

    Returns:
        shape (n,) 的距离数组
    """
    if not pois:
        return np.array([], dtype=np.float64)

    lats = np.array([p["lat"] for p in pois], dtype=np.float64)
    lngs = np.array([p["lng"] for p in pois], dtype=np.float64)

    return (
        haversine_vectorized(
            np.full_like(lats, lat),
            np.full_like(lngs, lng),
            lats,
            lngs,
        )
        * road_factor
    )


# ---------------------------------------------------------------------------
# 向量化路线评分辅助
# ---------------------------------------------------------------------------


def emotion_score_vectorized(
    pois: list[dict[str, Any]],
    preferences: dict[str, float],
) -> float:
    """批量计算 POI 列表的情绪偏好总分。

    Args:
        pois: POI 列表
        preferences: 用户偏好权重 {key: weight}

    Returns:
        总分
    """
    if not pois:
        return 0.0

    keys = list(preferences.keys())
    weights = np.array([preferences[k] for k in keys], dtype=np.float64)

    # 构建 (n_pois, n_prefs) 矩阵
    matrix = np.zeros((len(pois), len(keys)), dtype=np.float64)
    for i, poi in enumerate(pois):
        emo = poi.get("emotion_tags", {})
        for j, k in enumerate(keys):
            matrix[i, j] = emo.get(k, 0.0)

    # 每行点乘权重后求和
    return float(np.sum(matrix @ weights))


# ---------------------------------------------------------------------------
# 兼容性辅助：标量版 haversine（供旧代码使用）
# ---------------------------------------------------------------------------


def haversine_scalar(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """标量 haversine（米），用于少量点对的场景。"""
    from backend.services.geo import haversine

    return haversine(lat1, lon1, lat2, lon2)
