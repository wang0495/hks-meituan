"""三层记忆系统 + 心理学规则。

协调 L1 工作记忆、L2 短期行程记忆、L3 长期用户画像，
以及心理学评分规则。
"""

from __future__ import annotations

import logging
from typing import Any

from backend.services.memory.long_term import LongTermMemory
from backend.services.memory.psychology import PsychologyRules
from backend.services.memory.short_term import ShortTermMemory
from backend.services.memory.working_memory import WorkingMemory

logger = logging.getLogger(__name__)


class MemoryOrchestrator:
    """统一协调 3 层记忆 + 心理学规则。

    Args:
        redis_url: Redis 连接 URL。为 None 时所有层使用内存回退。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._working: WorkingMemory | None = None
        self._short_term: ShortTermMemory | None = None
        self._long_term: LongTermMemory | None = None

    async def get_working(self, session_id: str) -> WorkingMemory:
        """获取工作记忆实例（所有 session 共享同一实例，由 key 隔离）。"""
        if self._working is None:
            self._working = WorkingMemory(redis_url=self._redis_url)
        return self._working

    async def get_short_term(self, user_id: str) -> ShortTermMemory:
        """获取短期记忆实例。"""
        if self._short_term is None:
            self._short_term = ShortTermMemory(redis_url=self._redis_url)
        return self._short_term

    async def get_long_term(self, user_id: str) -> LongTermMemory:
        """获取长期画像实例。"""
        if self._long_term is None:
            self._long_term = LongTermMemory(redis_url=self._redis_url)
        return self._long_term

    async def on_trip_completed(
        self,
        user_id: str,
        session_id: str,
        trip_summary: dict[str, Any],
    ) -> None:
        """行程完成时: 保存到 short-term + 更新 long-term。"""
        # L2: 保存行程摘要
        st = await self.get_short_term(user_id)
        await st.add_trip(user_id, trip_summary)

        # L3: 记录访问统计
        lt = await self.get_long_term(user_id)
        for step in trip_summary.get("route", []):
            poi = step.get("poi", {})
            category = poi.get("category", "unknown")
            price = poi.get("avg_price", 0)
            emotion_tags = poi.get("emotion_tags", {})
            emotion = max(emotion_tags, key=emotion_tags.get) if emotion_tags else "default"
            await lt.record_visit(user_id, category, price, emotion)

    async def apply_psychology(
        self,
        route: list[dict[str, Any]],
        scores: list[float],
    ) -> list[float]:
        """对路线评分应用所有心理学规则。

        Args:
            route: 路线步骤列表
            scores: 评分列表

        Returns:
            调整后的评分列表
        """
        scores = PsychologyRules.apply_peak_end(route, scores)
        scores = PsychologyRules.apply_hedonic_adaptation(route, scores)
        scores = PsychologyRules.apply_loss_aversion(route, scores)
        return scores


__all__ = [
    "LongTermMemory",
    "MemoryOrchestrator",
    "PsychologyRules",
    "ShortTermMemory",
    "WorkingMemory",
]
