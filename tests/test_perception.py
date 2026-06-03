"""感知系统测试。

测试场景：
- PerceptionContext 数据类基本属性
- ScenePresets 4 种场景可复现
- 4 种异常检测逻辑
- 4 种调整策略
- Solver 集成
"""

from __future__ import annotations

import pytest

from backend.services.perception import (
    AdjustmentAction,
    Anomaly,
    AnomalyType,
    PerceptionContext,
    PerceptionService,
    ScenePresets,
)

# ---------------------------------------------------------------------------
# Data class 基础测试
# ---------------------------------------------------------------------------


class TestPerceptionContext:
    """T-F005-01: PerceptionContext 基本属性。"""

    def test_default_values(self) -> None:
        ctx = PerceptionContext()
        assert ctx.weather == "sunny"
        assert ctx.temperature == 25.0
        assert ctx.hour_of_day == 9

    def test_custom_values(self) -> None:
        ctx = PerceptionContext(weather="rainy", temperature=18.0, step_count=5000)
        assert ctx.weather == "rainy"
        assert ctx.step_count == 5000


class TestAnomaly:
    """T-F005-01: Anomaly 数据类型。"""

    def test_anomaly_creation(self) -> None:
        a = Anomaly(type=AnomalyType.FATIGUE_WARNING, severity=0.7, message="累了")
        assert a.type == AnomalyType.FATIGUE_WARNING
        assert a.severity == 0.7
        assert a.message == "累了"

    def test_anomaly_to_dict(self) -> None:
        a = Anomaly(type=AnomalyType.TIME_PRESSURE, severity=0.5, message="赶时间")
        d = a.to_dict()
        assert d["type"] == "time_pressure"
        assert d["severity"] == 0.5


# ---------------------------------------------------------------------------
# 场景预设
# ---------------------------------------------------------------------------


class TestScenePresets:
    """T-F005-02: 4 种演示场景预设。"""

    def test_sunny_scene(self) -> None:
        ctx = ScenePresets.get("sunny")
        assert ctx is not None
        assert ctx.weather == "sunny"
        assert ctx.temperature == 25.0
        assert ctx.fatigue_level == 0.2

    def test_rainy_scene(self) -> None:
        ctx = ScenePresets.get("rainy")
        assert ctx is not None
        assert ctx.weather == "rainy"
        assert ctx.temperature == 18.0

    def test_fatigue_scene(self) -> None:
        ctx = ScenePresets.get("fatigue")
        assert ctx is not None
        assert ctx.step_count == 18000
        assert ctx.fatigue_level == 0.8

    def test_time_pressure_scene(self) -> None:
        ctx = ScenePresets.get("time_pressure")
        assert ctx is not None
        assert ctx.hour_of_day == 16

    def test_unknown_scene(self) -> None:
        assert ScenePresets.get("nonexistent") is None


# ---------------------------------------------------------------------------
# 异常检测
# ---------------------------------------------------------------------------


class TestAnomalyDetection:
    """T-F005-03: 异常检测逻辑。"""

    @pytest.mark.asyncio
    async def test_fatigue_warning_high(self) -> None:
        """体力预警：步数 > 15000，疲劳度 > 0.7 → severity=0.7。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext(step_count=18000, fatigue_level=0.8)

        anomalies = await service.detect_anomaly(ctx)
        fatigue = [a for a in anomalies if a.type == AnomalyType.FATIGUE_WARNING]
        assert len(fatigue) == 1
        assert fatigue[0].severity == 0.7

    @pytest.mark.asyncio
    async def test_fatigue_warning_medium(self) -> None:
        """体力预警：步数 > 10000，疲劳度 > 0.5 → severity=0.4。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext(step_count=12000, fatigue_level=0.6)

        anomalies = await service.detect_anomaly(ctx)
        fatigue = [a for a in anomalies if a.type == AnomalyType.FATIGUE_WARNING]
        assert len(fatigue) == 1
        assert fatigue[0].severity == 0.4

    @pytest.mark.asyncio
    async def test_no_fatigue_warning(self) -> None:
        """步数 < 10000 时无体力预警。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext(step_count=5000, fatigue_level=0.2)

        anomalies = await service.detect_anomaly(ctx)
        fatigue = [a for a in anomalies if a.type == AnomalyType.FATIGUE_WARNING]
        assert len(fatigue) == 0

    @pytest.mark.asyncio
    async def test_emotion_dip(self) -> None:
        """连续 3 站情绪 < 0.4 时触发情绪低谷。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext()
        emotion_curve = [
            {"emotion_intensity": 0.3},
            {"emotion_intensity": 0.2},
            {"emotion_intensity": 0.35},
        ]

        anomalies = await service.detect_anomaly(ctx, emotion_curve=emotion_curve)
        dip = [a for a in anomalies if a.type == AnomalyType.EMOTION_DIP]
        assert len(dip) == 1

    @pytest.mark.asyncio
    async def test_no_emotion_dip_short_curve(self) -> None:
        """不足 3 站时不触发情绪低谷。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext()
        emotion_curve = [{"emotion_intensity": 0.3}, {"emotion_intensity": 0.2}]

        anomalies = await service.detect_anomaly(ctx, emotion_curve=emotion_curve)
        dip = [a for a in anomalies if a.type == AnomalyType.EMOTION_DIP]
        assert len(dip) == 0

    @pytest.mark.asyncio
    async def test_time_pressure_after_16(self) -> None:
        """下午 4 点后触发时间压力。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext(hour_of_day=17)

        anomalies = await service.detect_anomaly(ctx)
        tp = [a for a in anomalies if a.type == AnomalyType.TIME_PRESSURE]
        assert len(tp) == 1

    @pytest.mark.asyncio
    async def test_no_time_pressure_before_16(self) -> None:
        """下午 4 点前无时间压力。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext(hour_of_day=10)

        anomalies = await service.detect_anomaly(ctx)
        tp = [a for a in anomalies if a.type == AnomalyType.TIME_PRESSURE]
        assert len(tp) == 0

    @pytest.mark.asyncio
    async def test_no_anomalies_by_default(self) -> None:
        """正常状态下应无异常（步数少、时间早、无情绪数据）。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext(
            weather="sunny",
            step_count=2000,
            fatigue_level=0.1,
            hour_of_day=10,
        )

        anomalies = await service.detect_anomaly(ctx)
        assert len(anomalies) == 0


# ---------------------------------------------------------------------------
# 动态调整策略
# ---------------------------------------------------------------------------


class TestAdjustmentStrategies:
    """T-F005-04: 动态调整策略。"""

    def _make_route(self) -> dict:
        return {
            "route": [
                {
                    "poi": {
                        "id": "p1",
                        "name": "海滨公园",
                        "category": "自然",
                        "rating": 4.5,
                        "avg_stay_min": 60,
                        "emotion_tags": {"excitement": 0.8, "tranquility": 0.5},
                    },
                },
                {
                    "poi": {
                        "id": "p2",
                        "name": "低评分景点",
                        "category": "其他",
                        "rating": 3.5,
                        "avg_stay_min": 90,
                        "emotion_tags": {"excitement": 0.2, "tranquility": 0.3},
                    },
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_indoor_replacement(self) -> None:
        """天气突变 → indoor_replacement。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext(weather="rainy")
        anomalies = [Anomaly(type=AnomalyType.WEATHER_CHANGE, severity=0.6, message="下雨")]

        adj = await service.adjust_suggestions(ctx, self._make_route(), anomalies=anomalies)
        assert adj.action_type == AdjustmentAction.INDOOR_REPLACEMENT
        assert len(adj.target_poi_ids) > 0
        assert "室内" in adj.reasoning

    @pytest.mark.asyncio
    async def test_rest_insertion(self) -> None:
        """体力预警 → rest_insertion。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext(step_count=18000, fatigue_level=0.8)
        anomalies = [Anomaly(type=AnomalyType.FATIGUE_WARNING, severity=0.7, message="累了")]

        adj = await service.adjust_suggestions(ctx, self._make_route(), anomalies=anomalies)
        assert adj.action_type == AdjustmentAction.REST_INSERTION
        assert "休息" in adj.suggestions[0]

    @pytest.mark.asyncio
    async def test_style_switch(self) -> None:
        """情绪低谷 → style_switch。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext()
        anomalies = [Anomaly(type=AnomalyType.EMOTION_DIP, severity=0.5, message="平淡")]

        adj = await service.adjust_suggestions(ctx, self._make_route(), anomalies=anomalies)
        assert adj.action_type == AdjustmentAction.STYLE_SWITCH

    @pytest.mark.asyncio
    async def test_skip_low_value(self) -> None:
        """时间压力 → skip_low_value。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext(hour_of_day=17)
        anomalies = [Anomaly(type=AnomalyType.TIME_PRESSURE, severity=0.5, message="赶时间")]

        adj = await service.adjust_suggestions(ctx, self._make_route(), anomalies=anomalies)
        assert adj.action_type == AdjustmentAction.SKIP_LOW_VALUE
        # p2 是 avg_stay_min=90 评分 3.5 的低价值 POI
        assert "p2" in adj.target_poi_ids

    @pytest.mark.asyncio
    async def test_no_anomalies_no_adjustment(self) -> None:
        """无异常时返回无动作。"""
        service = PerceptionService(seed=42)
        ctx = PerceptionContext()

        adj = await service.adjust_suggestions(ctx, self._make_route(), anomalies=[])
        assert adj.action_type is None


# ---------------------------------------------------------------------------
# Solver 集成
# ---------------------------------------------------------------------------


class TestSolverIntegration:
    """T-F005-05: 与 solver 集成。"""

    @pytest.mark.asyncio
    async def test_scene_presets_reproducible(self) -> None:
        """4 种预设场景通过 get_context(scene=...) 可复现。"""
        service = PerceptionService(seed=42)

        for scene_name in ["sunny", "rainy", "fatigue", "time_pressure"]:
            # 调用两次，结果应相同
            ctx1 = await service.get_context(scene=scene_name)
            ctx2 = await service.get_context(scene=scene_name)
            assert ctx1.weather == ctx2.weather
            assert ctx1.temperature == ctx2.temperature
            assert ctx1.fatigue_level == ctx2.fatigue_level

    @pytest.mark.asyncio
    async def test_random_context_generation(self) -> None:
        """随机上下文应包含有效数据。"""
        service = PerceptionService(seed=42)
        ctx = await service.get_context()
        assert ctx.weather in ("sunny", "rainy", "cloudy", "hot", "cold")
        assert 10 <= ctx.temperature <= 35
        assert 0 <= ctx.hour_of_day <= 23
