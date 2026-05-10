"""
CityFlow 数据模型
Pydantic v2 定义所有生成数据的结构 + 校验规则
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ──────────────────────────────────────────────
# 枚举 & 常量
# ──────────────────────────────────────────────

class HighlightType(str, Enum):
    """highlight 体验类型"""
    view = "view"          # 观景
    photo = "photo"        # 拍照打卡
    walk = "walk"          # 散步/漫游
    eat = "eat"            # 餐饮体验
    shop = "shop"          # 购物
    play = "play"          # 互动娱乐
    rest = "rest"          # 休息
    learn = "learn"        # 文化学习
    sport = "sport"        # 运动


class NoiseLevel(str, Enum):
    quiet = "quiet"
    moderate = "moderate"
    loud = "loud"


class Season(str, Enum):
    spring = "spring"
    summer = "summer"
    autumn = "autumn"
    winter = "winter"


class PoiCategory(str, Enum):
    culture = "文化"
    dining = "餐饮"
    attraction = "景点"
    sport = "运动"
    shopping = "购物"
    hotel = "酒店"
    other = "其他"


# 六维情绪标签键
EMOTION_DIMS = [
    "excitement",
    "tranquility",
    "sociability",
    "culture_depth",
    "surprise",
    "physical_demand",
]


# ──────────────────────────────────────────────
# 基础类型
# ──────────────────────────────────────────────

class EmotionTags(BaseModel):
    """6 维情绪标签，各维度 0.0 ~ 1.0"""
    excitement: float = Field(default=0.0, ge=0.0, le=1.0)
    tranquility: float = Field(default=0.0, ge=0.0, le=1.0)
    sociability: float = Field(default=0.0, ge=0.0, le=1.0)
    culture_depth: float = Field(default=0.0, ge=0.0, le=1.0)
    surprise: float = Field(default=0.0, ge=0.0, le=1.0)
    physical_demand: float = Field(default=0.0, ge=0.0, le=1.0)


class EmotionBoost(BaseModel):
    """emotion_boost：高亮体验的情绪增量"""
    excitement: float = Field(default=0.0, ge=0.0, le=0.5)
    tranquility: float = Field(default=0.0, ge=0.0, le=0.5)
    sociability: float = Field(default=0.0, ge=0.0, le=0.5)
    culture_depth: float = Field(default=0.0, ge=0.0, le=0.5)
    surprise: float = Field(default=0.0, ge=0.0, le=0.5)
    physical_demand: float = Field(default=0.0, ge=0.0, le=0.5)

    @model_validator(mode="after")
    def check_total_boost(self):
        """所有维度的增量之和不超过 0.8"""
        total = (
            self.excitement + self.tranquility + self.sociability
            + self.culture_depth + self.surprise + self.physical_demand
        )
        if total > 0.8:
            raise ValueError(
                f"emotion_boost 总和 {total:.1f} 超过上限 0.8"
            )
        # 至少有一个维度 > 0
        if total == 0:
            raise ValueError("emotion_boost 至少需要一个维度 > 0")
        return self


# ──────────────────────────────────────────────
# 数据 1：POI highlights
# ──────────────────────────────────────────────

class HighlightItem(BaseModel):
    """单个高亮体验"""
    id: str = Field(pattern=r"^hl_\w+$")
    name: str = Field(min_length=2, max_length=10)
    type: HighlightType
    description: str = Field(min_length=10, max_length=40)
    duration_min: int = Field(ge=5, le=120)
    emotion_boost: EmotionBoost


class PoiHighlights(BaseModel):
    """POI + 它的 highlights 列表"""
    poi_id: str = Field(pattern=r"^poi_\d+$")
    poi_name: str
    city: str
    category: str
    highlights: list[HighlightItem] = Field(min_length=3, max_length=6)

    @field_validator("highlights")
    @classmethod
    def check_highlight_ids_unique(cls, v: list[HighlightItem]):
        ids = [h.id for h in v]
        if len(ids) != len(set(ids)):
            raise ValueError("highlights 中存在重复 id")
        return v


# ──────────────────────────────────────────────
# 数据 2：POI constraints
# ──────────────────────────────────────────────

class PoiConstraints(BaseModel):
    """POI 约束数据"""
    poi_id: str = Field(pattern=r"^poi_\d+$")
    poi_name: str
    accessible: bool
    pet_friendly: bool
    queue_prone: bool
    queue_time_min: int = Field(ge=0, le=120)
    has_restroom: bool
    has_parking: bool
    indoor: bool
    noise_level: NoiseLevel
    best_weather: list[str] = Field(min_length=1, max_length=5)
    age_groups: list[str] = Field(min_length=1, max_length=4)

    @field_validator("best_weather")
    @classmethod
    def check_weather(cls, v: list[str]):
        valid = {"sunny", "cloudy", "rainy", "hot", "cold"}
        for w in v:
            if w not in valid:
                raise ValueError(f"无效天气值: {w}，可选 {valid}")
        return v

    @field_validator("age_groups")
    @classmethod
    def check_age_groups(cls, v: list[str]):
        valid = {"all", "children", "adult", "elderly"}
        for a in v:
            if a not in valid:
                raise ValueError(f"无效年龄段: {a}，可选 {valid}")
        return v


# ──────────────────────────────────────────────
# 数据 3：Nonstandard Experience（新格式）
# ──────────────────────────────────────────────

class NonstandardExperience(BaseModel):
    """非标体验数据（单个）"""
    id: str = Field(pattern=r"^nse_\w+_\d{3}$")
    name: str = Field(min_length=6, max_length=15)
    city: str
    category: str
    description: str = Field(min_length=15, max_length=50)
    best_time: str = Field(pattern=r"^\d{2}:\d{2}-\d{2}:\d{2}$")
    best_time_label: Optional[str] = Field(default=None, pattern=r"^(清晨|上午|午后|傍晚|夜晚)$")
    season: list[Season] = Field(min_length=1, max_length=4)
    emotion_tags: EmotionTags
    poi_id: Optional[str] = Field(default=None, pattern=r"^(poi_\d+|null)$")
    tags: list[str] = Field(default_factory=list)
    duration_min: int = Field(ge=5, le=300)
    price: int = Field(ge=0)

    @field_validator("poi_id")
    @classmethod
    def normalize_null(cls, v: str | None):
        """poi_id 允许 null 值，统一存为 None"""
        if v == "null":
            return None
        return v


# ──────────────────────────────────────────────
# 数据 4：POI 补充（文化/运动）
# ──────────────────────────────────────────────

class PoiSupplement(BaseModel):
    """补充 POI（完全复用 city_poi_db.json 格式）"""
    id: str = Field(pattern=r"^poi_\w+$")
    name: str = Field(min_length=2, max_length=30)
    city: str
    category: str  # 文化 / 运动
    rating: float = Field(ge=1.0, le=5.0)
    avg_price: int = Field(ge=0)
    lat: float = Field(ge=20.0, le=26.0)
    lng: float = Field(ge=110.0, le=116.0)
    business_hours: str
    tags: list[str]
    queue_prone: bool = False
    avg_stay_min: int = Field(ge=15, le=300)
    emotion_tags: EmotionTags

    @field_validator("category")
    @classmethod
    def check_category(cls, v: str):
        if v not in ("文化", "运动"):
            raise ValueError(f"补充 POI category 仅允许 文化/运动，收到: {v}")
        return v


# ──────────────────────────────────────────────
# 生成管线输入/输出包装
# ──────────────────────────────────────────────

class GenerationResult(BaseModel):
    """一次生成任务的结果"""
    task_name: str
    success_count: int
    fail_count: int
    errors: list[str] = Field(default_factory=list)
    output_path: str = ""
