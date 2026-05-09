"""向量化距离计算模块测试。"""

from __future__ import annotations

import numpy as np
import pytest

from backend.services.vectorized import (distance_from_point_vectorized,
                                         distance_matrix_vectorized,
                                         emotion_score_vectorized,
                                         haversine_scalar,
                                         haversine_vectorized,
                                         travel_time_matrix_vectorized)

# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------

# 北京天安门附近几个 POI
SAMPLE_POIS = [
    {"id": "A", "lat": 39.9087, "lng": 116.3975, "name": "天安门广场"},
    {"id": "B", "lat": 39.9163, "lng": 116.3972, "name": "故宫"},
    {"id": "C", "lat": 39.9063, "lng": 116.3912, "name": "前门大街"},
]


# ---------------------------------------------------------------------------
# haversine_vectorized 测试
# ---------------------------------------------------------------------------


class TestHaversineVectorized:
    """向量化 haversine 测试。"""

    def test_same_point_distance_is_zero(self) -> None:
        lat = np.array([39.9087])
        lon = np.array([116.3975])
        dist = haversine_vectorized(lat, lon, lat, lon)
        assert float(dist[0]) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance(self) -> None:
        # 天安门到故宫约 850 米
        lat1 = np.array([39.9087])
        lon1 = np.array([116.3975])
        lat2 = np.array([39.9163])
        lon2 = np.array([116.3972])
        dist = haversine_vectorized(lat1, lon1, lat2, lon2)
        assert 700 < float(dist[0]) < 1000

    def test_symmetry(self) -> None:
        lat1 = np.array([39.9087])
        lon1 = np.array([116.3975])
        lat2 = np.array([39.9163])
        lon2 = np.array([116.3972])
        d1 = haversine_vectorized(lat1, lon1, lat2, lon2)
        d2 = haversine_vectorized(lat2, lon2, lat1, lon1)
        assert float(d1[0]) == pytest.approx(float(d2[0]), rel=1e-10)

    def test_batch_calculation(self) -> None:
        lat1 = np.array([39.9087, 39.9163])
        lon1 = np.array([116.3975, 116.3972])
        lat2 = np.array([39.9163, 39.9063])
        lon2 = np.array([116.3972, 116.3912])
        dists = haversine_vectorized(lat1, lon1, lat2, lon2)
        assert len(dists) == 2
        assert all(d > 0 for d in dists)


# ---------------------------------------------------------------------------
# distance_matrix_vectorized 测试
# ---------------------------------------------------------------------------


class TestDistanceMatrix:
    """距离矩阵测试。"""

    def test_shape(self) -> None:
        matrix = distance_matrix_vectorized(SAMPLE_POIS)
        assert matrix.shape == (3, 3)

    def test_diagonal_is_zero(self) -> None:
        matrix = distance_matrix_vectorized(SAMPLE_POIS)
        for i in range(3):
            assert float(matrix[i, i]) == pytest.approx(0.0, abs=1e-6)

    def test_symmetry(self) -> None:
        matrix = distance_matrix_vectorized(SAMPLE_POIS)
        for i in range(3):
            for j in range(3):
                assert float(matrix[i, j]) == pytest.approx(
                    float(matrix[j, i]), rel=1e-10
                )

    def test_road_factor_applied(self) -> None:
        matrix_default = distance_matrix_vectorized(SAMPLE_POIS)
        matrix_no_factor = distance_matrix_vectorized(SAMPLE_POIS, road_factor=1.0)
        # 默认有 road_factor=1.3，应该比无系数的大
        assert float(matrix_default[0, 1]) > float(matrix_no_factor[0, 1])

    def test_empty_pois(self) -> None:
        matrix = distance_matrix_vectorized([])
        assert matrix.shape == (0, 0)


# ---------------------------------------------------------------------------
# travel_time_matrix_vectorized 测试
# ---------------------------------------------------------------------------


class TestTravelTimeMatrix:
    """旅行时间矩阵测试。"""

    def test_shape(self) -> None:
        matrix = travel_time_matrix_vectorized(SAMPLE_POIS)
        assert matrix.shape == (3, 3)

    def test_diagonal_is_zero(self) -> None:
        matrix = travel_time_matrix_vectorized(SAMPLE_POIS)
        for i in range(3):
            assert float(matrix[i, i]) == pytest.approx(0.0, abs=1e-6)

    def test_positive_values(self) -> None:
        matrix = travel_time_matrix_vectorized(SAMPLE_POIS)
        for i in range(3):
            for j in range(3):
                if i != j:
                    assert float(matrix[i, j]) > 0


# ---------------------------------------------------------------------------
# distance_from_point_vectorized 测试
# ---------------------------------------------------------------------------


class TestDistanceFromPoint:
    """单点到多 POI 距离测试。"""

    def test_shape(self) -> None:
        dists = distance_from_point_vectorized(39.9087, 116.3975, SAMPLE_POIS)
        assert len(dists) == 3

    def test_first_poi_is_closest(self) -> None:
        # 从天安门出发，天安门本身距离应该最近（约0）
        dists = distance_from_point_vectorized(39.9087, 116.3975, SAMPLE_POIS)
        assert float(dists[0]) < float(dists[1])

    def test_empty_pois(self) -> None:
        dists = distance_from_point_vectorized(39.9, 116.4, [])
        assert len(dists) == 0


# ---------------------------------------------------------------------------
# emotion_score_vectorized 测试
# ---------------------------------------------------------------------------


class TestEmotionScore:
    """情绪评分向量化测试。"""

    def test_basic_scoring(self) -> None:
        pois = [
            {
                "emotion_tags": {
                    "excitement": 0.8,
                    "tranquility": 0.2,
                    "culture_depth": 0.5,
                }
            },
            {
                "emotion_tags": {
                    "excitement": 0.3,
                    "tranquility": 0.9,
                    "culture_depth": 0.7,
                }
            },
        ]
        preferences = {"excitement": 1.0, "tranquility": 0.5, "culture_depth": 0.3}
        score = emotion_score_vectorized(pois, preferences)
        # 手动验证：POI1: 0.8*1.0 + 0.2*0.5 + 0.5*0.3 = 1.05
        # POI2: 0.3*1.0 + 0.9*0.5 + 0.7*0.3 = 0.96
        # 总分: 2.01
        assert score == pytest.approx(2.01, rel=1e-6)

    def test_empty_pois(self) -> None:
        score = emotion_score_vectorized([], {"excitement": 1.0})
        assert score == 0.0

    def test_missing_tags_default_zero(self) -> None:
        pois = [{"emotion_tags": {}}]
        score = emotion_score_vectorized(pois, {"excitement": 1.0})
        assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# haversine_scalar 一致性测试
# ---------------------------------------------------------------------------


class TestHaversineScalar:
    """标量 haversine 一致性测试。"""

    def test_consistency_with_vectorized(self) -> None:
        lat1, lon1 = 39.9087, 116.3975
        lat2, lon2 = 39.9163, 116.3972
        scalar_dist = haversine_scalar(lat1, lon1, lat2, lon2)
        vec_dist = float(
            haversine_vectorized(
                np.array([lat1]),
                np.array([lon1]),
                np.array([lat2]),
                np.array([lon2]),
            )[0]
        )
        assert scalar_dist == pytest.approx(vec_dist, rel=1e-10)
