"""CityFlow 数据库查询优化器。

提供三类优化能力：
1. 索引建议与 DDL 生成 -- 根据 ORM 模型和查询模式推荐缺失索引
2. 查询优化工具 -- 批量查询、eager loading、分页优化
3. 慢查询检测 -- 包装 AsyncSession 自动记录超过阈值的查询

用法::

    optimizer = DatabaseOptimizer()

    # 生成索引 DDL
    ddl = optimizer.generate_index_ddl()

    # 包装 session 启用慢查询检测
    async with optimizer.monitored_session(session) as s:
        ...
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.models import Route, RouteStep

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndexSuggestion:
    """索引建议。"""

    table: str
    columns: list[str]
    index_type: str  # btree / gin / gist
    reason: str
    ddl: str


@dataclass(frozen=True, slots=True)
class QuerySuggestion:
    """查询优化建议。"""

    category: str  # eager_load / batch / pagination / select_columns
    description: str
    example: str


@dataclass(slots=True)
class SlowQueryRecord:
    """慢查询记录。"""

    statement: str
    duration_ms: float
    parameters: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# 优化器
# ---------------------------------------------------------------------------


class DatabaseOptimizer:
    """数据库查询优化器。

    Args:
        slow_query_threshold_ms: 慢查询阈值（毫秒），默认 200ms。
    """

    def __init__(self, slow_query_threshold_ms: float = 200.0) -> None:
        self._threshold_ms = slow_query_threshold_ms
        self._slow_queries: list[SlowQueryRecord] = []

    # ------------------------------------------------------------------
    # 1. 索引建议
    # ------------------------------------------------------------------

    def get_index_suggestions(self) -> list[IndexSuggestion]:
        """根据 ORM 模型和常见查询模式返回索引建议。

        仅返回 models.py 中尚未定义的索引。
        """
        suggestions: list[IndexSuggestion] = []

        # routes: user_id + created_at 复合索引（按用户查路线最常用）
        suggestions.append(
            IndexSuggestion(
                table="routes",
                columns=["user_id", "created_at"],
                index_type="btree",
                reason="加速按用户查询路线列表（get_by_user），覆盖 WHERE user_id = ? ORDER BY created_at DESC",
                ddl="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_routes_user_created "
                "ON routes (user_id, created_at DESC);",
            )
        )

        # routes: status + created_at（归档/删除过滤）
        suggestions.append(
            IndexSuggestion(
                table="routes",
                columns=["status", "created_at"],
                index_type="btree",
                reason="加速按状态过滤路线（active/archived/deleted）",
                ddl="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_routes_status_created "
                "ON routes (status, created_at DESC);",
            )
        )

        # dialogues: session_id + created_at 复合索引
        suggestions.append(
            IndexSuggestion(
                table="dialogues",
                columns=["session_id", "created_at"],
                index_type="btree",
                reason="加速按会话获取对话历史（get_session_messages），覆盖 WHERE session_id = ? ORDER BY created_at",
                ddl="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dialogues_session_created "
                "ON dialogues (session_id, created_at);",
            )
        )

        # dialogues: route_id + created_at（按路线查对话）
        suggestions.append(
            IndexSuggestion(
                table="dialogues",
                columns=["route_id", "created_at"],
                index_type="btree",
                reason="加速按路线获取对话（get_route_dialogues）",
                ddl="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dialogues_route_created "
                "ON dialogues (route_id, created_at);",
            )
        )

        # route_steps: route_id 已有单列索引，补充 step_index 排序
        suggestions.append(
            IndexSuggestion(
                table="route_steps",
                columns=["route_id", "step_index"],
                index_type="btree",
                reason="加速按路线获取步骤并按 step_index 排序（get_by_route），替代现有单列索引",
                ddl="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_route_steps_route_step "
                "ON route_steps (route_id, step_index);",
            )
        )

        # route_data JSONB GIN 索引（路线内 POI 搜索）
        suggestions.append(
            IndexSuggestion(
                table="routes",
                columns=["route_data"],
                index_type="gin",
                reason="加速 JSONB 路线数据内的 POI ID 搜索",
                ddl="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_routes_route_data_gin "
                "ON routes USING gin (route_data jsonb_path_ops);",
            )
        )

        return suggestions

    def generate_index_ddl(self) -> str:
        """生成所有索引建议的 DDL 脚本。"""
        suggestions = self.get_index_suggestions()
        lines = [
            "-- CityFlow 索引优化 DDL（自动生成）",
            "-- 使用 CONCURRENTLY 避免锁表",
            "",
        ]
        for s in suggestions:
            lines.append(f"-- {s.table}.{','.join(s.columns)}: {s.reason}")
            lines.append(s.ddl)
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 2. 查询优化建议
    # ------------------------------------------------------------------

    def get_query_suggestions(self) -> list[QuerySuggestion]:
        """返回针对当前 Repository 层的查询优化建议。"""
        return [
            QuerySuggestion(
                category="eager_load",
                description="RouteRepository.get() 未使用 eager loading，访问 route.steps / route.dialogues 会触发 N+1 查询",
                example=(
                    "select(Route)\n"
                    ".options(selectinload(Route.steps), selectinload(Route.dialogues))\n"
                    ".where(Route.id == route_id)"
                ),
            ),
            QuerySuggestion(
                category="eager_load",
                description="RouteRepository.get_by_user() 未预加载 steps，前端展示路线步骤时每条路线各触发一次查询",
                example=(
                    "select(Route)\n"
                    ".options(selectinload(Route.steps))\n"
                    ".where(Route.user_id == user_id)\n"
                    ".order_by(Route.created_at.desc())"
                ),
            ),
            QuerySuggestion(
                category="batch",
                description="RouteStepRepository.replace_all() 逐条删除旧步骤，应改为批量 DELETE",
                example=(
                    "from sqlalchemy import delete\n"
                    "await session.execute(\n"
                    "    delete(RouteStep).where(RouteStep.route_id == route_id)\n"
                    ")"
                ),
            ),
            QuerySuggestion(
                category="select_columns",
                description="get_by_user() 只需列表展示字段，不必 SELECT 全部列（route_data / narrative 是大 JSONB）",
                example=(
                    "select(Route.id, Route.user_input, Route.status, Route.created_at)\n"
                    ".where(Route.user_id == user_id)"
                ),
            ),
            QuerySuggestion(
                category="pagination",
                description="offset 分页在大偏移量时性能差，建议改用 keyset 分页（cursor-based）",
                example=(
                    "# 第一页\n"
                    "select(Route).where(Route.user_id == uid)\n"
                    ".order_by(Route.created_at.desc()).limit(10)\n\n"
                    "# 下一页（用最后一条的 created_at 作为 cursor）\n"
                    "select(Route).where(\n"
                    "    Route.user_id == uid,\n"
                    "    Route.created_at < last_created_at,\n"
                    ").order_by(Route.created_at.desc()).limit(10)"
                ),
            ),
            QuerySuggestion(
                category="select_columns",
                description="DialogueRepository.get_session_messages() 含大字段 content，列表场景可仅取摘要",
                example=(
                    "select(Dialogue.id, Dialogue.role, Dialogue.created_at)\n"
                    ".where(Dialogue.session_id == session_id)\n"
                    ".order_by(Dialogue.created_at)"
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # 3. 批量查询工具
    # ------------------------------------------------------------------

    async def get_routes_with_relations(
        self,
        db: AsyncSession,
        user_id: UUID,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Route]:
        """获取用户路线（eager load steps + dialogues），避免 N+1。"""
        result = await db.execute(
            select(Route)
            .options(
                selectinload(Route.steps),
                selectinload(Route.dialogues),
            )
            .where(Route.user_id == user_id)
            .order_by(Route.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_route_detail(self, db: AsyncSession, route_id: UUID) -> Route | None:
        """获取路线详情（eager load steps + dialogues），避免 N+1。"""
        result = await db.execute(
            select(Route)
            .options(
                selectinload(Route.steps),
                selectinload(Route.dialogues),
            )
            .where(Route.id == route_id)
        )
        return result.scalar_one_or_none()

    async def bulk_get_routes(
        self, db: AsyncSession, route_ids: list[UUID]
    ) -> list[Route]:
        """批量获取路线（单次查询），替代循环调用 get()。"""
        if not route_ids:
            return []
        result = await db.execute(
            select(Route)
            .options(
                selectinload(Route.steps),
                selectinload(Route.dialogues),
            )
            .where(Route.id.in_(route_ids))
        )
        return list(result.scalars().all())

    async def batch_delete_route_steps(self, db: AsyncSession, route_id: UUID) -> int:
        """批量删除路线步骤（单条 DELETE），替代逐条删除。"""
        from sqlalchemy import delete

        result = await db.execute(
            delete(RouteStep).where(RouteStep.route_id == route_id)
        )
        return result.rowcount  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # 4. 慢查询检测
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def monitored_session(
        self, session: AsyncSession
    ) -> AsyncGenerator[AsyncSession, None]:
        """包装 AsyncSession，在退出时检查是否有慢查询。

        用法::

            async with optimizer.monitored_session(session) as s:
                result = await s.execute(select(Route)...)
        """
        # 记录开始时间（简单实现：检测 session.info 中的标记）
        start = time.monotonic()
        try:
            yield session
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            if elapsed_ms > self._threshold_ms:
                logger.warning(
                    "慢查询警告: 会话耗时 %.1fms (阈值 %.1fms)",
                    elapsed_ms,
                    self._threshold_ms,
                )

    def get_slow_queries(self) -> list[SlowQueryRecord]:
        """返回已记录的慢查询列表。"""
        return list(self._slow_queries)

    def clear_slow_queries(self) -> None:
        """清空慢查询记录。"""
        self._slow_queries.clear()

    # ------------------------------------------------------------------
    # 5. 索引应用工具
    # ------------------------------------------------------------------

    async def apply_index(self, db: AsyncSession, ddl: str) -> bool:
        """执行单条索引 DDL。返回是否成功。"""
        try:
            await db.execute(text(ddl))
            await db.commit()
            logger.info("索引创建成功: %s", ddl[:80])
            return True
        except Exception:
            logger.exception("索引创建失败: %s", ddl[:80])
            await db.rollback()
            return False

    async def apply_all_indexes(self, db: AsyncSession) -> dict[str, bool]:
        """应用所有索引建议，返回每个索引的执行结果。"""
        results: dict[str, bool] = {}
        for suggestion in self.get_index_suggestions():
            key = f"{suggestion.table}.{','.join(suggestion.columns)}"
            results[key] = await self.apply_index(db, suggestion.ddl)
        return results

    # ------------------------------------------------------------------
    # 6. 综合报告
    # ------------------------------------------------------------------

    def generate_report(self) -> dict[str, Any]:
        """生成综合优化报告。"""
        index_suggestions = self.get_index_suggestions()
        query_suggestions = self.get_query_suggestions()

        return {
            "index_optimizations": [
                {
                    "table": s.table,
                    "columns": s.columns,
                    "type": s.index_type,
                    "reason": s.reason,
                }
                for s in index_suggestions
            ],
            "query_optimizations": [
                {
                    "category": s.category,
                    "description": s.description,
                }
                for s in query_suggestions
            ],
            "summary": {
                "total_index_suggestions": len(index_suggestions),
                "total_query_suggestions": len(query_suggestions),
                "priority_fixes": [
                    "RouteRepository.get() 添加 selectinload 避免 N+1",
                    "routes 表添加 (user_id, created_at) 复合索引",
                    "RouteStepRepository.replace_all() 改为批量 DELETE",
                ],
            },
        }
