"""CityFlow 感知系统。

Mock 层采集天气/时间/体力/行为等感知信号，检测异常后触发路线调整。
比赛环境说明：所有外部数据使用 Mock 模拟，无需真实 API。

用法:
    service = PerceptionService()
    ctx = await service.get_context(scene="rainy")
    anomalies = await service.detect_anomaly(ctx, emotion_curve=[])
    adj = await service.adjust_suggestions(ctx, plan={"route": [...]}, anomalies=anomalies)
"""

from __future__ import annotations

import enum
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class PerceptionContext:
    """聚合所有感知信号的上下文数据类。"""

    weather: str = "sunny"  # sunny/rainy/cloudy/hot/cold
    temperature: float = 25.0  # 15.0 ~ 35.0
    hour_of_day: int = 9  # 6 ~ 22
    day_of_week: int = 0  # 0=周一
    season: str = "spring"  # spring/summer/autumn/winter
    step_count: int = 0  # 0 ~ 30000
    fatigue_level: float = 0.0  # 0.0 ~ 1.0
    avg_stay_duration: int = 60  # 30 ~ 180 (min)
    photo_frequency: float = 0.0  # 0 ~ 5 (次/小时)
    # 城市特色（by 王启龙 2026-05-09: 感知应该反映城市特质，而非纯气象数据）
    city: str = "珠海"
    city_vibe: str = "relaxed"  # relaxed/lively/rustic/energetic
    city_specialties: list[str] = field(default_factory=list)
    is_holiday: bool = False  # 当天是否是节假日


class AnomalyType(str, enum.Enum):
    """异常类型枚举。"""

    WEATHER_CHANGE = "weather_change"
    FATIGUE_WARNING = "fatigue_warning"
    EMOTION_DIP = "emotion_dip"
    TIME_PRESSURE = "time_pressure"


@dataclass
class Anomaly:
    """检测到的异常事件。"""

    type: AnomalyType
    severity: float  # 0.0 ~ 1.0
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp,
        }


class AdjustmentAction(str, enum.Enum):
    """调整策略动作类型。"""

    INDOOR_REPLACEMENT = "indoor_replacement"
    REST_INSERTION = "rest_insertion"
    STYLE_SWITCH = "style_switch"
    SKIP_LOW_VALUE = "skip_low_value"


@dataclass
class AdjustmentResult:
    """调整建议结果。"""

    action_type: AdjustmentAction | None
    target_poi_ids: list[str]  # 受影响的 POI ID 列表
    reasoning: str
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value if self.action_type else None,
            "target_poi_ids": self.target_poi_ids,
            "reasoning": self.reasoning,
            "suggestions": self.suggestions,
        }


# ---------------------------------------------------------------------------
# 演示场景预设
# ---------------------------------------------------------------------------


class ScenePresets:
    """4 种预设演示场景。"""

    # 场景A: 晴天悠闲
    SUNNY_LEISURE = PerceptionContext(
        weather="sunny",
        temperature=25.0,
        hour_of_day=10,
        day_of_week=6,
        season="spring",
        step_count=3000,
        fatigue_level=0.2,
        avg_stay_duration=90,
        photo_frequency=2.0,
    )

    # 场景B: 雨天室内
    RAINY_INDOOR = PerceptionContext(
        weather="rainy",
        temperature=18.0,
        hour_of_day=14,
        day_of_week=6,
        season="spring",
        step_count=5000,
        fatigue_level=0.5,
        avg_stay_duration=120,
        photo_frequency=0.5,
    )

    # 场景C: 体力预警（高温 + 久走）
    FATIGUE_WARNING = PerceptionContext(
        weather="sunny",
        temperature=32.0,
        hour_of_day=14,
        day_of_week=0,
        season="summer",
        step_count=18000,
        fatigue_level=0.8,
        avg_stay_duration=45,
        photo_frequency=0.3,
    )

    # 场景D: 时间压力
    TIME_PRESSURE = PerceptionContext(
        weather="cloudy",
        temperature=22.0,
        hour_of_day=16,
        day_of_week=0,
        season="autumn",
        step_count=12000,
        fatigue_level=0.6,
        avg_stay_duration=60,
        photo_frequency=1.0,
    )

    _ALL = {
        "sunny": SUNNY_LEISURE,
        "rainy": RAINY_INDOOR,
        "fatigue": FATIGUE_WARNING,
        "time_pressure": TIME_PRESSURE,
    }

    @classmethod
    def get(cls, name: str) -> PerceptionContext | None:
        return cls._ALL.get(name)

    @classmethod
    def names(cls) -> list[str]:
        return list(cls._ALL.keys())


# ---------------------------------------------------------------------------
# 感知服务
# ---------------------------------------------------------------------------

_WEATHER_WEIGHTS: dict[str, float] = {
    "sunny": 0.55,
    "cloudy": 0.20,
    "hot": 0.10,
    "rainy": 0.10,
    "cold": 0.05,
}

_SEASONS = ["spring", "summer", "autumn", "winter"]


class PerceptionService:
    """感知服务：采集、检测、调整。

    全部 Mock 数据，无需外部 API。
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._last_weather: str = "sunny"

    # ---- 数据采集 ----------------------------------------------------------

    async def get_context(
        self, scene: str | None = None, route: list[dict] | None = None,
        city: str = "珠海",
    ) -> PerceptionContext:
        """获取感知上下文。

        不再随机生成天气，使用基于当前时间和季节的确定性默认值。

        Args:
            scene: 预设场景名（sunny/rainy/fatigue/time_pressure），用于测试
            route: 当前路线步骤（用于估算步数）
            city: 用户所在城市，用于加载城市特色数据
        """
        if scene and ScenePresets.get(scene):
            return ScenePresets.get(scene)  # type: ignore[return-value]

        return self._deterministic_context(city)

    def _deterministic_context(self, city: str = "珠海") -> PerceptionContext:
        """生成确定的感知上下文（非随机）。"""
        now = datetime.now()

        # 季节决定基础天气（夏季偏晴热，冬季不出现hot）
        season_idx = (now.month % 12) // 3
        season = _SEASONS[season_idx]
        weather, temp = {
            "spring": ("cloudy", 22),
            "summer": ("sunny", 30),
            "autumn": ("sunny", 25),
            "winter": ("cloudy", 16),
        }[season]

        # 加载城市特色
        vibe = "relaxed"
        specialties: list[str] = []
        try:
            import json
            from pathlib import Path
            _cp_path = Path(__file__).parent.parent / "data" / "city_personality.json"
            if _cp_path.exists():
                cp = json.loads(_cp_path.read_text(encoding="utf-8"))
                personality = cp.get(city, {})
                if personality:
                    vibe = personality.get("vibe", "relaxed")
                    specialties = personality.get("specialties", [])
        except Exception:
            pass

        return PerceptionContext(
            weather=weather,
            temperature=temp,
            hour_of_day=now.hour,
            day_of_week=now.weekday(),
            season=season,
            step_count=0,
            fatigue_level=0.0,
            avg_stay_duration=60,
            photo_frequency=1.0,
            city=city,
            city_vibe=vibe,
            city_specialties=specialties,
            is_holiday=now.weekday() >= 5,
        )

    # ---- 异常检测 ----------------------------------------------------------

    async def detect_anomaly(
        self,
        ctx: PerceptionContext,
        emotion_curve: list[dict[str, Any]] | None = None,
    ) -> list[Anomaly]:
        """检测感知异常，返回异常列表。

        Args:
            ctx: 当前感知上下文
            emotion_curve: 当前路线情绪曲线（用于情绪低谷检测）

        Returns:
            异常列表，无异常时返回空列表
        """
        anomalies: list[Anomaly] = []

        # 1) 天气突变（5% 概率）
        if self._detect_weather_change(ctx):
            anomalies.append(
                Anomaly(
                    type=AnomalyType.WEATHER_CHANGE,
                    severity=0.6,
                    message=f"天气突变：{self._last_weather}→{ctx.weather}，建议寻找室内替代方案",
                )
            )
        self._last_weather = ctx.weather

        # 2) 体力预警
        if ctx.step_count > 15000 and ctx.fatigue_level > 0.7:
            anomalies.append(
                Anomaly(
                    type=AnomalyType.FATIGUE_WARNING,
                    severity=0.7,
                    message="走了不少路了，建议插入休息节点或打车前往下一站",
                )
            )
        elif ctx.step_count > 10000 and ctx.fatigue_level > 0.5:
            anomalies.append(
                Anomaly(
                    type=AnomalyType.FATIGUE_WARNING,
                    severity=0.4,
                    message="体力消耗较大，建议适当放慢节奏",
                )
            )

        # 3) 情绪低谷（需要 emotion_curve 数据）
        if emotion_curve and len(emotion_curve) >= 3:
            recent_emotions = [
                s.get("emotion_intensity", 0) for s in emotion_curve[-3:]
            ]
            if all(e < 0.4 for e in recent_emotions):
                anomalies.append(
                    Anomaly(
                        type=AnomalyType.EMOTION_DIP,
                        severity=0.5,
                        message="近期体验偏平淡，建议切换到高刺激/惊喜类型的景点",
                    )
                )

        # 4) 时间压力（基于当前时间和步数综合判断）
        #    基础阈值16:00，闲逛型放宽到17:00，体力好时延后
        base_threshold = 16
        if getattr(ctx, "city_vibe", "") == "relaxed":
            base_threshold = 17  # 休闲城市节奏慢，时间压力来得晚
        step_count = len(emotion_curve) if emotion_curve else 4
        if ctx.hour_of_day >= base_threshold and step_count >= 4:
            anomalies.append(
                Anomaly(
                    type=AnomalyType.TIME_PRESSURE,
                    severity=0.5,
                    message="时间有限，建议跳过低价值耗时的景点",
                )
            )

        return anomalies

    def _detect_weather_change(self, ctx: PerceptionContext) -> bool:
        """检测天气突变（5% 概率触发）。"""
        if self._last_weather == ctx.weather:
            return False
        # 从晴天变雨天才是"突变"
        if self._last_weather == "sunny" and ctx.weather in ("rainy", "cold"):
            return True
        return False

    # ---- 动态调整 ----------------------------------------------------------

    async def adjust_suggestions(
        self,
        ctx: PerceptionContext,
        plan: dict[str, Any],
        anomalies: list[Anomaly] | None = None,
    ) -> AdjustmentResult:
        """根据异常生成调整建议。

        Args:
            ctx: 感知上下文
            plan: 当前路线计划
            anomalies: 已检测到的异常列表

        Returns:
            调整建议
        """
        if not anomalies:
            return AdjustmentResult(
                action_type=None,
                target_poi_ids=[],
                reasoning="无异常，不需要调整",
            )

        # 按严重度排序，处理最严重的异常
        anomaly = max(anomalies, key=lambda a: a.severity)

        route_steps = plan.get("route", [])

        if anomaly.type == AnomalyType.WEATHER_CHANGE:
            # 找出室外 POI 建议替换
            indoor_cats = {"文化", "购物", "餐饮"}
            target_ids = [
                step["poi"]["id"]
                for step in route_steps
                if step.get("poi", {}).get("category") not in indoor_cats
            ]
            return AdjustmentResult(
                action_type=AdjustmentAction.INDOOR_REPLACEMENT,
                target_poi_ids=target_ids,
                reasoning="天气突变，建议替换为室内 POI",
                suggestions=["考虑博物馆、商场、咖啡厅等室内场所"],
            )

        elif anomaly.type == AnomalyType.FATIGUE_WARNING:
            # 找到路线中间位置插入休息
            mid = len(route_steps) // 2
            target_ids = (
                [route_steps[mid]["poi"]["id"]] if route_steps else []
            )
            return AdjustmentResult(
                action_type=AdjustmentAction.REST_INSERTION,
                target_poi_ids=target_ids,
                reasoning="体力消耗较大，建议插入休息节点",
                suggestions=["在公园或咖啡馆休息 15-20 分钟", "打车前往下一站"],
            )

        elif anomaly.type == AnomalyType.EMOTION_DIP:
            # 建议切换高兴奋度 POI
            target_ids = []
            for step in route_steps[-3:]:
                et = step.get("poi", {}).get("emotion_tags", {})
                if et.get("excitement", 0) < 0.4:
                    target_ids.append(step["poi"]["id"])
            return AdjustmentResult(
                action_type=AdjustmentAction.STYLE_SWITCH,
                target_poi_ids=target_ids,
                reasoning="近期体验偏平淡，需要更高强度的情绪刺激",
                suggestions=["考虑娱乐类或互动类景点", "增加惊喜感强的体验项目"],
            )

        elif anomaly.type == AnomalyType.TIME_PRESSURE:
            # 跳过耗时 > 45min 且评分 < 4.0 的 POI
            target_ids = [
                step["poi"]["id"]
                for step in route_steps
                if step.get("poi", {}).get("avg_stay_min", 0) > 45
                and step.get("poi", {}).get("rating", 5.0) < 4.0
            ]
            return AdjustmentResult(
                action_type=AdjustmentAction.SKIP_LOW_VALUE,
                target_poi_ids=target_ids,
                reasoning="时间有限，建议跳过低价值体验",
                suggestions=["跳过耗时较长评分偏低的景点", "集中时间在高质量体验上"],
            )

        return AdjustmentResult(
            action_type=None,
            target_poi_ids=[],
            reasoning="无需调整",
        )


# ---------------------------------------------------------------------------
# 全局实例
# ---------------------------------------------------------------------------

perception_service = PerceptionService()
