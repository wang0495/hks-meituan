"""CityFlow 偏好管理器。

核心协调层：整合 用户身份 + LTM 长期记忆 + 上下文感知 + WeightMapper + 推荐生成。

数据流:
  用户输入 → 识别身份 → 调取LTM → 分析上下文模式 → 预测偏好
      → 生成推荐 → 用户确认 → WeightMapper算权重 → 求解器 → 写入LTM

原则:
  - trip_history 只 append 不覆盖
  - 趋势在查询时实时计算
  - 权重通过 WeightMapper 渐进学习，不突变
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from backend.services.holiday_utils import (
    build_context,
    format_context_summary,
)
from backend.services.memory.long_term import LongTermMemory
from backend.services.weight_mapper import WeightMapper

logger = logging.getLogger(__name__)

# 本地用户身份文件
_USER_CONFIG_DIR = Path.home() / ".cityflow"
_USER_CONFIG_PATH = _USER_CONFIG_DIR / "user.json"

_DEFAULT_USER_ID = "default_user"


# ---------------------------------------------------------------------------
# 用户身份管理
# ---------------------------------------------------------------------------


def _ensure_user_config() -> dict:
    """读取本地用户身份配置。"""
    try:
        _USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if _USER_CONFIG_PATH.exists():
            return json.loads(_USER_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"last_user_id": _DEFAULT_USER_ID, "known_users": []}


def _save_user_config(cfg: dict) -> None:
    """保存本地用户身份配置。"""
    try:
        _USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _USER_CONFIG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"保存用户配置失败: {e}")


def get_known_users() -> list[str]:
    """返回已知用户列表。"""
    cfg = _ensure_user_config()
    return cfg.get("known_users", [])


def get_last_user() -> str | None:
    """返回上次使用的用户 ID。"""
    cfg = _ensure_user_config()
    uid = cfg.get("last_user_id")
    return uid if uid and uid != _DEFAULT_USER_ID else None


def register_user(nickname: str) -> str:
    """注册新用户（或确认已有用户），返回 user_id。"""
    user_id = nickname.strip()
    if not user_id:
        user_id = _DEFAULT_USER_ID
    cfg = _ensure_user_config()
    cfg["last_user_id"] = user_id
    known: list = cfg.setdefault("known_users", [])
    if user_id not in known:
        known.append(user_id)
    _save_user_config(cfg)
    return user_id


# ── 路线摘要辅助 ─────────────────────────────────────────────────


def _build_route_summary(route_result: dict, user_intent: dict) -> dict:
    """从路线结果 + intent 构建 route_summary。"""
    route = route_result.get("route", [])
    categories = []
    total_cost = 0
    emotion_values: list[float] = []
    emotion_keys = ["excitement", "tranquility", "culture_depth", "sociability", "surprise"]

    for step in route or []:
        poi = step.get("poi", {})
        cat = poi.get("category", "")
        if cat:
            categories.append(cat)
        total_cost += poi.get("avg_price", 0) or 0
        et = poi.get("emotion_tags", {})
        for k in emotion_keys:
            v = et.get(k)
            if v is not None:
                emotion_values.append(v)

    avg_emotion: dict[str, float] = {}
    if emotion_values:
        for k in emotion_keys:
            vals = [
                step.get("poi", {}).get("emotion_tags", {}).get(k, 0)
                for step in route or []
            ]
            vals = [v for v in vals if v is not None]
            if vals:
                avg_emotion[k] = round(sum(vals) / len(vals), 2)

    return {
        "poi_count": len(route or []),
        "categories": list(dict.fromkeys(categories)),  # dedup, keep order
        "total_cost": total_cost,
        "avg_emotion": avg_emotion,
    }


# ---------------------------------------------------------------------------
# PreferenceManager
# ---------------------------------------------------------------------------


class PreferenceManager:
    """偏好管理的统一入口。

    职责:
    1. 用户身份识别与管理
    2. LTM 数据读写 + 上下文模式分析
    3. WeightMapper 权重映射
    4. 主动推荐生成
    5. 行程完成后的记忆写入
    """

    def __init__(self, user_id: str | None = None) -> None:
        self.user_id = user_id or get_last_user() or _DEFAULT_USER_ID
        self.ltm: LongTermMemory | None = None
        self.mapper: WeightMapper | None = None
        self._initialized = False

    @classmethod
    def from_user_id(cls, user_id: str) -> "PreferenceManager":
        """用指定 user_id 创建。"""
        return cls(user_id)

    async def _ensure_init(self) -> None:
        if self._initialized:
            return
        # 从配置获取 Redis URL，无配置时使用内存模式
        redis_url = await self._build_redis_url()
        self.ltm = LongTermMemory(redis_url=redis_url)
        # 从 LTM 恢复 WeightMapper
        mapper_data = await self.ltm.get_weight_mapper(self.user_id)
        self.mapper = WeightMapper(self.user_id)
        self.mapper.from_dict(mapper_data)
        self._initialized = True

    @staticmethod
    async def _build_redis_url() -> str | None:
        """从配置构建 Redis 连接 URL。"""
        try:
            from backend.config import settings
            rs = settings.redis
            if rs.password:
                return f"redis://:{rs.password}@{rs.host}:{rs.port}/{rs.db}"
            return f"redis://{rs.host}:{rs.port}/{rs.db}"
        except (ImportError, AttributeError):
            return None

    # ── 用户状态 ────────────────────────────────────────────────

    async def get_user_status(self, current_context: dict | None = None) -> dict:
        """返回用户状态，用于 TUI 展示。

        返回:
        {
            "is_new": True/False,
            "user_id": "小王",
            "interaction_count": 5,
            "greeting": "又见面啦小王！",
            "context_info": "☀️ 晴 25°C · 周六 · 春季",
            "context_hints": ["今天天气不错，你之前出太阳时都去户外走走的"],
        }
        """
        await self._ensure_init()
        assert self.ltm is not None

        profile = await self.ltm.get_profile(self.user_id)
        history: list = profile.get("trip_history", [])
        is_new = len(history) == 0

        # 提取信息
        interaction_count = profile.get("visit_count", 0)

        # 生成打招呼
        if is_new:
            greeting = "你好呀！第一次使用 CityFlow 吧？"
        else:
            greeting = f"又见面啦{self.user_id}！"

        # 上下文提示
        context_hints: list[str] = []
        if current_context and not is_new:
            patterns = await self.ltm.get_contextual_patterns(self.user_id)
            ctx = current_context

            # 天气提示
            weather_key = ctx.get("weather", "")
            wp = patterns.get("weather_patterns", {})
            if weather_key in wp and wp[weather_key]["n"] >= 2:
                wp_data = wp[weather_key]
                top_cat = wp_data.get("top_categories", [])
                if top_cat:
                    context_hints.append(
                        f"今天{weather_key}，你之前{wp_data['n']}次"
                        f"都选了{''.join(top_cat[:2])}类的路线"
                    )

            # 节假日提示
            holiday_info = ctx.get("holiday", {})
            if holiday_info.get("is_holiday"):
                hp = patterns.get("holiday_patterns", {}).get("holiday", {})
                if hp.get("n", 0) >= 1:
                    avg_budget = hp.get("avg_budget", 0)
                    context_hints.append(
                        f"{holiday_info['name']}你一般预算在¥{avg_budget}左右"
                    )

        context_info = ""
        if current_context:
            context_info = format_context_summary(current_context)

        return {
            "is_new": is_new,
            "user_id": self.user_id,
            "interaction_count": interaction_count,
            "greeting": greeting,
            "context_info": context_info,
            "context_hints": context_hints,
        }

    # ── 推荐生成 ──────────────────────────────────────────────

    async def generate_recommendations(
        self,
        user_input: str,
        current_context: dict,
    ) -> dict:
        """基于 LTM + 上下文生成主动推荐选项。

        返回:
        {
            "has_recommendations": True/False,
            "recommendations": [
                {"id": "a", "label": "...", "description": "...", "intent_hint": {...}},
                {"id": "b", "label": "...", "description": "...", "intent_hint": {...}},
                {"id": "c", "label": "我自己来", "description": "自由描述偏好"},
            ],
            "context_info": "...",
            "prediction": {...}  # predict_preferences 的结果
        }
        """
        await self._ensure_init()
        assert self.ltm is not None

        # 预测偏好
        prediction = await self.ltm.predict_preferences(
            self.user_id, current_context
        )
        has_prediction = prediction.get("data_points", 0) > 0

        recommendations = []

        if has_prediction and prediction.get("confidence", 0) > 0.3:
            # 选项 A: 按预测推荐
            pace = prediction.get("predicted_pace", "")
            budget = prediction.get("predicted_budget", 0)
            cats = prediction.get("predicted_categories", [])
            need = prediction.get("predicted_emotion_need", "")

            label_parts = []
            if pace:
                label_parts.append(pace)
            if cats:
                label_parts.append("".join(cats[:2]))
            label = " ".join(label_parts) if label_parts else "经典路线"
            if need:
                desc = f"你之前{prediction['data_points']}次在类似条件下都选了{label}"
            else:
                desc = f"根据你{prediction['data_points']}次历史记录推荐"

            ah_intent: dict[str, Any] = {}
            if pace:
                ah_intent["pace"] = pace
            if budget > 0:
                ah_intent.setdefault("budget", {})["per_person"] = budget

            recommendations.append({
                "id": "a",
                "label": label,
                "description": desc,
                "intent_hint": ah_intent,
            })

            # 选项 B: 换一个方向（如果预测明确，推荐相反方向）
            b_intent: dict[str, Any] = {}
            if pace == "闲逛型":
                b_intent["pace"] = "平衡型"
                b_label = "今天想紧凑一点"
            elif pace == "特种兵型":
                b_intent["pace"] = "闲逛型"
                b_label = "今天想悠闲一点"
            else:
                b_intent["pace"] = "闲逛型"
                b_label = "换个节奏试试"

            recommendations.append({
                "id": "b",
                "label": b_label,
                "description": "尝试不同的节奏和风格",
                "intent_hint": b_intent,
            })

        # 选项 C: 自定义
        recommendations.append({
            "id": "c",
            "label": "我自己来",
            "description": "自由描述出行偏好",
            "intent_hint": {},
        })

        # 选项 D: 一键规划（直接用 parse_intent 默认）
        recommendations.append({
            "id": "d",
            "label": "直接规划",
            "description": "用默认配置快速出方案",
            "intent_hint": {},
        })

        return {
            "has_recommendations": has_prediction,
            "recommendations": recommendations,
            "prediction": prediction,
        }

    # ── 权重计算 ──────────────────────────────────────────────

    def compute_solver_weights(self, demand_vector: dict) -> dict[str, float]:
        """计算求解器权重（委托给 WeightMapper）。"""
        if self.mapper is None:
            self.mapper = WeightMapper(self.user_id)
        return self.mapper.compute_weights(demand_vector)

    # ── 反馈学习 ──────────────────────────────────────────────

    async def record_feedback(
        self,
        demand_vector: dict,
        applied_weights: dict,
        feedback: str,
        modification_hint: str | None = None,
    ) -> dict[str, float]:
        """记录用户反馈，更新 WeightMapper，持久化到 LTM。

        返回: 更新后的权重。
        """
        await self._ensure_init()
        assert self.ltm is not None
        assert self.mapper is not None

        new_weights = self.mapper.update_from_feedback(
            demand_vector, applied_weights, feedback, modification_hint
        )

        # 持久化到 LTM
        await self.ltm.save_weight_mapper(
            self.user_id, self.mapper.to_dict()
        )

        logger.info(
            f"[PreferenceManager] 反馈 {feedback} 已学习. "
            f"Mapper: {self.mapper.summary()}"
        )
        return new_weights

    # ── 行程记录 ──────────────────────────────────────────────

    async def save_trip_to_memory(
        self,
        route_result: dict,
        user_intent: dict,
        context: dict,
    ) -> None:
        """行程完成后写入 LTM。

        构建 trip_history 记录并调用 LTM.record_trip()，
        同时更新 WeightMapper 并持久化。
        """
        await self._ensure_init()
        assert self.ltm is not None

        route_summary = _build_route_summary(route_result, user_intent)

        await self.ltm.record_trip(
            self.user_id,
            intent=user_intent,
            route_summary=route_summary,
            context=context,
        )

        # 持久化 mapper 参数
        if self.mapper is not None:
            await self.ltm.save_weight_mapper(
                self.user_id, self.mapper.to_dict()
            )

        logger.info(
            f"[PreferenceManager] 行程已记录到 LTM user={self.user_id} "
            f"pois={route_summary['poi_count']} cats={route_summary['categories']}"
        )

    # ── 注入 LTM（用于共享 Redis 连接） ─────────────────────

    def inject_ltm(self, ltm: LongTermMemory) -> None:
        """注入外部 LTM 实例（共享 Redis 连接）。"""
        self.ltm = ltm
        self._initialized = True
