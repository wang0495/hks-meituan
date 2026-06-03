"""CityFlow POI Repository — PostgreSQL 数据访问层。

提供 POI 数据的增删改查操作。
使用 AsyncSession，与 FastAPI 依赖注入模式一致。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import POI

logger = logging.getLogger(__name__)


class POIRepository:
    """POI 数据访问。

    Args:
        db: SQLAlchemy 异步会话实例。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 批量导入
    # ------------------------------------------------------------------

    async def bulk_upsert(self, pois: list[dict[str, Any]]) -> int:
        """批量插入或更新 POI。

        对 PostgreSQL 使用原生 ``ON CONFLICT DO UPDATE`` upsert 语义；
        对非 PostgreSQL 数据库（如 aiosqlite 测试环境）回退为逐条 merge。

        Args:
            pois: POI 字典列表，每个字典的键必须与 POI 模型列名一致。

        Returns:
            实际处理的行数。
        """
        if not pois:
            return 0

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        try:
            stmt = pg_insert(POI).values(pois)
            # 排除主键，其余列全部更新
            update_cols = {k: stmt.excluded[k] for k in pois[0] if k != "id"}
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_=update_cols,
            )
            await self.db.execute(stmt)
            await self.db.flush()
            return len(pois)
        except Exception:
            # 非 PostgreSQL 回退：逐条 merge
            logger.info("bulk_upsert 回退为逐条 merge（非 PostgreSQL 数据库）")
            count = 0
            for pdata in pois:
                obj = POI(**pdata)
                await self.db.merge(obj)
                count += 1
            await self.db.flush()
            return count

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    async def find_by_city(self, city: str) -> list[POI]:
        """按城市查询 POI。"""
        result = await self.db.execute(
            select(POI).where(POI.city == city).order_by(POI.rating.desc())
        )
        return list(result.scalars().all())

    async def find_by_category(self, category: str) -> list[POI]:
        """按类别查询 POI。"""
        result = await self.db.execute(
            select(POI).where(POI.category == category).order_by(POI.rating.desc())
        )
        return list(result.scalars().all())

    async def find_filtered(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[POI]:
        """按条件筛选 POI。

        支持的筛选键（均为可选）:
            - city: str             城市精确匹配
            - category: str         类别精确匹配
            - min_rating: float     最低评分
            - max_price: float      最高人均消费
            - tags: list[str]       tags 数组包含任一标签（OR）
            - queue_prone: bool     是否容易排队

        Args:
            filters: 筛选条件字典。
            limit: 最大返回条数，默认 50。

        Returns:
            匹配条件的 POI 列表，按评分降序排列。
        """
        filters = filters or {}
        query = select(POI)

        if filters.get("city"):
            query = query.where(POI.city == filters["city"])
        if filters.get("category"):
            query = query.where(POI.category == filters["category"])
        if "min_rating" in filters:
            query = query.where(POI.rating >= filters["min_rating"])
        if "max_price" in filters:
            query = query.where((POI.avg_price <= filters["max_price"]) | (POI.avg_price.is_(None)))
        if "queue_prone" in filters:
            query = query.where(POI.queue_prone == filters["queue_prone"])
        if filters.get("tags"):
            # tags 是 JSONB 数组，使用 PostgreSQL @> 或 ? 操作符
            # 这里用简单方式：对每个 tag 做 contains 过滤
            for tag in filters["tags"]:
                query = query.where(POI.tags.contains(tag))

        query = query.order_by(POI.rating.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(self) -> int:
        """返回 POI 总数。"""
        result = await self.db.execute(select(func.count(POI.id)))
        return result.scalar_one()

    async def get_by_id(self, poi_id: str) -> POI | None:
        """按 ID 获取单个 POI。"""
        result = await self.db.execute(select(POI).where(POI.id == poi_id))
        return result.scalar_one_or_none()
