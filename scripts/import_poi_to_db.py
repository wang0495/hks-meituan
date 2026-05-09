#!/usr/bin/env python
"""
导入 POI 数据到 PostgreSQL。

从 JSON 文件读取 POI 数据，经过经济引擎富化后，批量写入 PostgreSQL。

用法:
    python scripts/import_poi_to_db.py
    python scripts/import_poi_to_db.py --json backend/data/city_poi_db.json
    python scripts/import_poi_to_db.py --batch-size 200
    python scripts/import_poi_to_db.py --dry-run

依赖:
    - 项目依赖已安装（见 requirements.txt）
    - PostgreSQL 数据库已启动且配置正确（.env / 环境变量）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# 将项目根目录加入 sys.path，确保可以 import backend
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("import_poi")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 POI 数据从 JSON 导入 PostgreSQL，含经济引擎富化。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/import_poi_to_db.py\n"
            "  python scripts/import_poi_to_db.py --dry-run --json backend/data/city_poi_db.json\n"
            "  python scripts/import_poi_to_db.py --batch-size 500\n"
        ),
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        type=str,
        default=str(_PROJECT_ROOT / "frontend" / "data" / "city_poi_db.json"),
        help="POI JSON 文件路径 (默认: frontend/data/city_poi_db.json)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="每批写入的 POI 数量 (默认: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅展示统计信息，不写入数据库",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="数据库连接 URL (默认: 从 backend.config.settings 读取)",
    )
    return parser.parse_args()


def load_json(path: str) -> list[dict]:
    """加载 POI JSON 文件。"""
    p = Path(path)
    if not p.exists():
        logger.error("文件不存在: %s", p.resolve())
        sys.exit(1)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        logger.error("JSON 根元素应为数组，实际为 %s", type(data).__name__)
        sys.exit(1)
    logger.info("加载 %d 条 POI: %s", len(data), p.resolve())
    return data


def enrich_pois(pois: list[dict]) -> list[dict]:
    """使用经济引擎富化 POI 数据（幂等，原地修改）。"""
    from backend.services.economy import enrich_poi_economics

    enriched_count = 0
    already_have = 0
    for poi in pois:
        if "experience_value" in poi:
            already_have += 1
            continue
        enrich_poi_economics(poi)
        enriched_count += 1
    logger.info("经济引擎富化: %d 条新增, %d 条已有", enriched_count, already_have)
    return pois


def prepare_db_rows(pois: list[dict]) -> list[dict]:
    """将 POI 字典转换为数据库行数据（过滤 ugc_comments 等非模型字段）。"""
    allowed_keys = {
        "id", "name", "city", "category", "rating", "avg_price",
        "lat", "lng", "business_hours", "tags", "queue_prone",
        "avg_stay_min", "emotion_tags",
        "experience_value", "price_elasticity",
        "experience_leverage", "spend_emotion",
    }
    rows = []
    skipped = 0
    for poi in pois:
        row = {k: poi[k] for k in allowed_keys if k in poi}
        # 确保必填字段存在
        if "id" not in row or "name" not in row:
            skipped += 1
            continue
        rows.append(row)
    if skipped:
        logger.warning("跳过 %d 条缺少必填字段的 POI", skipped)
    return rows


async def import_to_db(
    rows: list[dict],
    batch_size: int,
    dry_run: bool,
    db_url: str | None = None,
) -> dict:
    """批量导入 POI 到 PostgreSQL。"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    if db_url:
        engine = create_async_engine(db_url, echo=False, pool_size=2, max_overflow=5)
    else:
        from backend.database.base import engine

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from backend.database.poi_repository import POIRepository

    total = len(rows)
    processed = 0
    errors = 0

    if dry_run:
        return {
            "total": total,
            "dry_run": True,
            "message": "Dry-run 模式，未写入数据库",
        }

    start = time.perf_counter()

    async with factory() as session:
        repo = POIRepository(session)
        for i in range(0, total, batch_size):
            batch = rows[i : i + batch_size]
            try:
                count = await repo.bulk_upsert(batch)
                processed += count
                await session.commit()
                pct = (i + len(batch)) / total * 100
                logger.info(
                    "进度: %6d / %d (%5.1f%%) | 批次: %3d 条",
                    min(i + batch_size, total),
                    total,
                    pct,
                    count,
                )
            except Exception:
                logger.exception("批次写入失败 (offset=%d)", i)
                await session.rollback()
                errors += len(batch)

        # 统计
        total_in_db = await repo.count()

    await engine.dispose()

    elapsed = time.perf_counter() - start
    return {
        "total": total,
        "processed": processed,
        "errors": errors,
        "total_in_db": total_in_db,
        "elapsed_seconds": round(elapsed, 2),
    }


async def main() -> None:
    args = parse_args()

    # 1. 加载 JSON
    pois = load_json(args.json_path)

    # 2. 经济引擎富化
    pois = enrich_pois(pois)

    # 3. 准备数据库行
    rows = prepare_db_rows(pois)
    logger.info("准备写入 %d 条 POI (共 %d 条)", len(rows), len(pois))

    if args.dry_run:
        logger.info("DRY-RUN 模式 — 统计信息:")
    else:
        logger.info("开始导入 PostgreSQL (batch_size=%d)...", args.batch_size)

    stats = await import_to_db(rows, args.batch_size, args.dry_run, args.db_url)

    # 4. 输出统计
    logger.info("=" * 50)
    logger.info("导入完成统计:")
    for k, v in stats.items():
        logger.info("  %s: %s", k, v)
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
