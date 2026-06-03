"""L3: 长期用户画像。

存储用户的长期偏好数据，包括累计偏好统计、访问次数最多的category、
平均消费水平、历史情绪曲线、完整的 trip_history（附带上下文）。

V2 新增:
- trip_history: 统一行程记录（含上下文），替代分散的 pace/budget 记录
- record_trip(): 一次调用写入完整行程
- get_trip_history(): 按上下文条件过滤查询
- get_contextual_patterns(): 全维度上下文模式分析
- predict_preferences(): 基于当前上下文预测偏好

原则: trip_history 只 append 不覆盖，趋势在查询时实时计算。
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

logger = logging.getLogger(__name__)

LONG_TERM_KEY_PREFIX = "memory:lt:"

# trip_history 最大记录数
_MAX_TRIP_HISTORY = 50


class LongTermMemory:
    """长期用户画像。

    存储用户的长期偏好数据。
    Redis Hash, key = f"memory:lt:{user_id}"
    字段: preferences, category_visits, visit_count, total_spent,
          emotion_history, trip_history, weight_mapper。
    TTL = 无 (长期保留)。
    Redis 不可用时自动回退到内存字典。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._connected = False
        self._fallback = False
        self._memory: dict[str, dict[str, Any]] = {}

    async def _get_redis(self) -> Any:
        """获取 Redis 连接（延迟连接）。"""
        if self._connected and self._redis is not None:
            return self._redis
        if self._fallback or not self._redis_url:
            return None
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await self._redis.ping()
            self._connected = True
            self._fallback = False
            logger.info("[LongTermMemory] Redis 连接成功")
            return self._redis
        except Exception:
            self._connected = False
            self._fallback = True
            logger.warning("[LongTermMemory] Redis 不可达，切换到内存模式")
            return None

    async def _ensure_profile_exists(self, user_id: str) -> None:
        """确保用户画像在 Redis 或内存中存在。"""
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{LONG_TERM_KEY_PREFIX}{user_id}"
                exists = await r.exists(redis_key)
                if not exists:
                    default = self._default_profile()
                    await r.hset(
                        redis_key,
                        mapping={
                            "preferences": json.dumps(default["preferences"], ensure_ascii=False),
                            "category_visits": json.dumps(
                                default["category_visits"], ensure_ascii=False
                            ),
                            "visit_count": json.dumps(default["visit_count"]),
                            "total_spent": json.dumps(default["total_spent"]),
                            "emotion_history": json.dumps(
                                default["emotion_history"], ensure_ascii=False
                            ),
                            "trip_history": json.dumps(default["trip_history"], ensure_ascii=False),
                            "weight_mapper": json.dumps(
                                default["weight_mapper"], ensure_ascii=False
                            ),
                        },
                    )
                return
            except Exception:
                self._fallback = True

        # Fallback
        if user_id not in self._memory:
            self._memory[user_id] = self._default_profile()

    @staticmethod
    def _default_profile() -> dict[str, Any]:
        """返回默认用户画像（V2 含 trip_history + weight_mapper）。"""
        return {
            "preferences": {},
            "category_visits": {},
            "visit_count": 0,
            "total_spent": 0,
            "emotion_history": [],
            "trip_history": [],
            "weight_mapper": None,
        }

    async def get_profile(self, user_id: str) -> dict[str, Any]:
        """获取用户画像（含默认值）。"""
        await self._ensure_profile_exists(user_id)
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{LONG_TERM_KEY_PREFIX}{user_id}"
                data = await r.hgetall(redis_key)
                if data:
                    return {
                        "preferences": json.loads(data.get("preferences", "{}")),
                        "category_visits": json.loads(data.get("category_visits", "{}")),
                        "visit_count": json.loads(data.get("visit_count", "0")),
                        "total_spent": json.loads(data.get("total_spent", "0")),
                        "emotion_history": json.loads(data.get("emotion_history", "[]")),
                        "trip_history": json.loads(data.get("trip_history", "[]")),
                        "weight_mapper": json.loads(data.get("weight_mapper", "null")),
                    }
                return self._default_profile()
            except Exception:
                self._fallback = True

        # Fallback: in-memory
        return dict(self._memory.get(user_id, self._default_profile()))

    async def _save_field(self, user_id: str, field: str, value: Any) -> None:
        """保存单个字段到 Redis 或内存。"""
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{LONG_TERM_KEY_PREFIX}{user_id}"
                await r.hset(
                    redis_key,
                    field,
                    json.dumps(value, ensure_ascii=False),
                )
                return
            except Exception:
                self._fallback = True
        # Fallback
        if user_id in self._memory:
            self._memory[user_id][field] = value
        else:
            profile = self._default_profile()
            profile[field] = value
            self._memory[user_id] = profile

    async def update_preference(self, user_id: str, category: str, value: float) -> None:
        """更新或添加用户偏好。"""
        profile = await self.get_profile(user_id)
        profile["preferences"][category] = value
        await self._save_field(user_id, "preferences", profile["preferences"])

    async def record_visit(
        self, user_id: str, poi_category: str, price: float, emotion: str
    ) -> None:
        """记录一次 POI 访问，更新类别计数和统计数据。"""
        profile = await self.get_profile(user_id)

        profile["category_visits"][poi_category] = (
            profile["category_visits"].get(poi_category, 0) + 1
        )
        profile["visit_count"] += 1
        profile["total_spent"] += price

        profile["emotion_history"].append(
            {"category": poi_category, "emotion": emotion, "price": price}
        )
        if len(profile["emotion_history"]) > 50:
            profile["emotion_history"] = profile["emotion_history"][-50:]

        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{LONG_TERM_KEY_PREFIX}{user_id}"
                await r.hset(
                    redis_key,
                    mapping={
                        "category_visits": json.dumps(
                            profile["category_visits"], ensure_ascii=False
                        ),
                        "visit_count": json.dumps(profile["visit_count"]),
                        "total_spent": json.dumps(profile["total_spent"]),
                        "emotion_history": json.dumps(
                            profile["emotion_history"], ensure_ascii=False
                        ),
                    },
                )
                return
            except Exception:
                self._fallback = True

        # Fallback: in-memory
        self._memory[user_id] = profile

    # ── V2 新增: trip_history ────────────────────────────────────────

    async def record_trip(
        self,
        user_id: str,
        intent: dict[str, Any],
        route_summary: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """统一记录一次行程（替代分散的 record_pace/record_budget 等）。

        参数:
            intent: 用户最终使用的 intent（pace/budget/preferences/constraints/emotion_need）
            route_summary: 路线汇总（poi_count/categories/total_cost/avg_emotion）
            context: 当时的上下文（weather/season/holiday/temperature 等）

        行为:
            - 将一条完整记录 append 到 trip_history
            - 最多保留 _MAX_TRIP_HISTORY 条
            - 同时更新旧的统计字段保持兼容
        """
        profile = await self.get_profile(user_id)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "intent": intent,
            "route_summary": route_summary,
        }

        history: list[dict] = profile.get("trip_history", [])
        history.append(entry)
        if len(history) > _MAX_TRIP_HISTORY:
            history = history[-_MAX_TRIP_HISTORY:]

        profile["trip_history"] = history

        # 同时更新旧的统计字段保持兼容
        profile["visit_count"] += 1
        profile["total_spent"] += route_summary.get("total_cost", 0)
        for cat in route_summary.get("categories", []):
            profile["category_visits"][cat] = profile["category_visits"].get(cat, 0) + 1

        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{LONG_TERM_KEY_PREFIX}{user_id}"
                await r.hset(
                    redis_key,
                    mapping={
                        "trip_history": json.dumps(history, ensure_ascii=False),
                        "visit_count": json.dumps(profile["visit_count"]),
                        "total_spent": json.dumps(profile["total_spent"]),
                        "category_visits": json.dumps(
                            profile["category_visits"], ensure_ascii=False
                        ),
                    },
                )
                return
            except Exception:
                self._fallback = True

        self._memory[user_id] = profile

    async def get_trip_history(
        self,
        user_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """按条件过滤查询历史记录。

        参数 filters 示例:
            {"weather": "rainy"}
            {"season": "summer"}
            {"is_weekend": True}
            {"holiday.is_holiday": True}
            {"pace": "闲逛型"}

        支持点号嵌套路径 (如 "holiday.day_type")。
        """
        profile = await self.get_profile(user_id)
        history: list[dict] = list(profile.get("trip_history", []))

        if filters:
            filtered = []
            for trip in reversed(history):
                match = True
                for key, value in filters.items():
                    parts = key.split(".")
                    val: Any = trip
                    for part in parts:
                        if isinstance(val, dict):
                            val = val.get(part, {})
                        else:
                            val = {}
                    if val != value:
                        match = False
                        break
                if match:
                    filtered.append(trip)
            history = filtered

        return history[:limit]

    def _group_by_context(
        self, history: list[dict], key_func: Callable[[dict], str]
    ) -> dict[str, list[dict]]:
        """按上下文维度分组。"""
        groups: dict[str, list[dict]] = {}
        for trip in history:
            key = key_func(trip)
            groups.setdefault(key, []).append(trip)
        return groups

    @staticmethod
    def _analyze_trip_group(trips: list[dict]) -> dict:
        """分析一组行程的统计信息。"""
        if not trips:
            return {"n": 0}
        paces = []
        budgets = []
        categories = []
        constraints = []
        emotion_needs = []
        for t in trips:
            intent = t.get("intent", {})
            paces.append(intent.get("pace", "unknown"))
            budgets.append(intent.get("budget", {}).get("per_person", 0))
            summary = t.get("route_summary", {})
            categories.extend(summary.get("categories", []))
            constraints.extend(intent.get("constraints", []))
            need = intent.get("emotion_need")
            if need:
                emotion_needs.append(need)

        def _most_common(items: list) -> Any:
            return Counter(items).most_common(1)[0][0] if items else None

        def _distribution(items: list) -> dict:
            if not items:
                return {}
            c = Counter(items)
            total = len(items)
            return {k: round(v / total, 2) for k, v in c.most_common()}

        return {
            "n": len(trips),
            "common_pace": _most_common(paces),
            "avg_budget": (round(sum(budgets) / len(budgets)) if budgets else 0),
            "top_categories": [c for c, _ in Counter(categories).most_common(3)],
            "pace_distribution": _distribution(paces),
            "common_constraints": list(
                dict.fromkeys(c for c, _ in Counter(constraints).most_common(3))
            ),
            "emotion_need_distribution": (_distribution(emotion_needs) if emotion_needs else {}),
        }

    async def get_contextual_patterns(self, user_id: str) -> dict[str, Any]:
        """全面分析用户在不同上下文下的行为模式。"""
        profile = await self.get_profile(user_id)
        history: list[dict] = profile.get("trip_history", [])

        if not history:
            return {}

        analyze = self._analyze_trip_group
        patterns: dict[str, Any] = {}

        dimensions = [
            ("weather_patterns", lambda t: t.get("context", {}).get("weather", "unknown")),
            ("season_patterns", lambda t: t.get("context", {}).get("season", "unknown")),
            (
                "day_type_patterns",
                lambda t: t.get("context", {}).get("holiday", {}).get("day_type", "workday"),
            ),
            (
                "temperature_patterns",
                lambda t: t.get("context", {}).get("temperature_level", "comfortable"),
            ),
            ("period_patterns", lambda t: t.get("context", {}).get("period", "morning")),
        ]

        for pattern_name, key_func in dimensions:
            groups = self._group_by_context(history, key_func)
            patterns[pattern_name] = {k: analyze(v) for k, v in groups.items()}

        holiday_groups: dict[str, list] = {"holiday": [], "non_holiday": []}
        for trip in history:
            key = (
                "holiday"
                if trip.get("context", {}).get("holiday", {}).get("is_holiday")
                else "non_holiday"
            )
            holiday_groups[key].append(trip)
        patterns["holiday_patterns"] = {k: analyze(v) for k, v in holiday_groups.items()}

        weekend_groups: dict[str, list] = {"weekend": [], "workday": []}
        for trip in history:
            key = "weekend" if trip.get("context", {}).get("is_weekend") else "workday"
            weekend_groups[key].append(trip)
        patterns["weekday_patterns"] = {k: analyze(v) for k, v in weekend_groups.items()}

        patterns["overall"] = analyze(history)

        return patterns

    _CATEGORY_TO_DIM: ClassVar[dict[str, str]] = {
        "文化": "culture",
        "景点": "culture",
        "餐饮": "food",
        "运动": "nature",
        "自然": "nature",
        "购物": "social",
    }

    @staticmethod
    def _context_match_score(trip: dict, ctx: dict[str, Any]) -> float:
        """计算trip上下文与目标上下文的匹配分数。"""
        score = 0.0
        tctx = trip.get("context", {})
        if tctx.get("weather") == ctx.get("weather"):
            score += 3.0
        if tctx.get("season") == ctx.get("season"):
            score += 2.0
        if tctx.get("holiday", {}).get("day_type") == ctx.get("holiday", {}).get("day_type"):
            score += 2.0
        if tctx.get("is_weekend") == ctx.get("is_weekend"):
            score += 1.0
        if tctx.get("temperature_level") == ctx.get("temperature_level"):
            score += 1.0
        if tctx.get("period") == ctx.get("period"):
            score += 1.0
        return score

    @staticmethod
    def _calc_dimension_scores(top: list[tuple[float, dict]]) -> dict[str, float]:
        """计算偏好维度分数。"""
        dim_scores: dict[str, float] = {"culture": 0.0, "food": 0.0, "nature": 0.0, "social": 0.0}
        total_weighted = 0.0
        for weight, trip in top:
            for cat in trip.get("route_summary", {}).get("categories", []):
                dim = LongTermMemory._CATEGORY_TO_DIM.get(cat)
                if dim:
                    dim_scores[dim] += weight
            total_weighted += weight
        if total_weighted > 0:
            for dim in dim_scores:
                dim_scores[dim] = round(min(1.0, dim_scores[dim] / total_weighted), 2)
        return dim_scores

    async def predict_preferences(
        self,
        user_id: str,
        current_context: dict[str, Any],
    ) -> dict[str, Any]:
        """基于当前上下文预测用户最可能的偏好。

        策略:
        1. 找出与当前上下文各维度匹配的历史记录子集
        2. 逐条打分（weather+3, season+2, day_type+2, is_weekend+1, temp+1, period+1）
        3. 取 top 3 加权统计

        返回:
        {
            "predicted_pace": "闲逛型",
            "predicted_budget": 200,
            "predicted_categories": ["自然"],
            "predicted_emotion_need": "放松",
            "confidence": 0.75,
            "data_points": 5,
        }
        """
        profile = await self.get_profile(user_id)
        history: list[dict] = profile.get("trip_history", [])

        if not history:
            return {"data_points": 0, "confidence": 0.0}

        scored: list[tuple[float, dict]] = []
        for trip in history:
            score = self._context_match_score(trip, current_context)
            if score > 0:
                scored.append((score, trip))

        if not scored:
            return {"data_points": 0, "confidence": 0.0}

        scored.sort(key=lambda x: -x[0])
        top = scored[:3]
        total_weight = sum(s for s, _ in top)

        paces: list[str] = []
        budgets: list[float] = []
        categories: list[str] = []
        emotion_needs: list[str] = []

        for weight, trip in top:
            intent = trip.get("intent", {})
            paces.extend([intent.get("pace", "unknown")] * int(weight))
            budgets.append(intent.get("budget", {}).get("per_person", 0) * weight)
            categories.extend(trip.get("route_summary", {}).get("categories", []))
            need = intent.get("emotion_need")
            if need:
                emotion_needs.extend([need] * int(weight))

        dim_scores = self._calc_dimension_scores(top)

        return {
            "predicted_pace": (Counter(paces).most_common(1)[0][0] if paces else None),
            "predicted_budget": (round(sum(budgets) / total_weight) if budgets else 0),
            "predicted_categories": [c for c, _ in Counter(categories).most_common(3)],
            "predicted_dimensions": dim_scores,
            "predicted_emotion_need": (
                Counter(emotion_needs).most_common(1)[0][0] if emotion_needs else None
            ),
            "confidence": round(min(1.0, total_weight / 15.0), 2),
            "data_points": len(scored),
        }

    # ── V2 新增: weight_mapper 读写 ──────────────────────────────

    async def save_weight_mapper(self, user_id: str, mapper_data: dict[str, Any]) -> None:
        """保存 WeightMapper 的 delta 参数到 LTM。"""
        await self._save_field(user_id, "weight_mapper", mapper_data)

    async def get_weight_mapper(self, user_id: str) -> dict[str, Any] | None:
        """读取 WeightMapper 的 delta 参数。"""
        profile = await self.get_profile(user_id)
        return profile.get("weight_mapper")

    # ── 已有方法 ──────────────────────────────────────────────────

    async def get_statistics(self, user_id: str) -> dict[str, Any]:
        """获取用户统计信息。"""
        profile = await self.get_profile(user_id)

        category_visits = profile.get("category_visits", {})
        most_visited_category = (
            max(category_visits, key=category_visits.get) if category_visits else None
        )

        visit_count = profile.get("visit_count", 0)
        total_spent = profile.get("total_spent", 0)
        trip_count = len(profile.get("trip_history", []))

        return {
            "visit_count": visit_count,
            "category_visits": category_visits,
            "most_visited_category": most_visited_category,
            "average_spending": (round(total_spent / visit_count, 2) if visit_count > 0 else 0.0),
            "total_spent": total_spent,
            "emotion_history_count": len(profile.get("emotion_history", [])),
            "trip_history_count": trip_count,
        }

    @property
    def is_fallback(self) -> bool:
        return self._fallback
