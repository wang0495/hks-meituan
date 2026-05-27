import json
import logging
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).parent.parent / "data"

_cache: dict[str, Any] = {}

# DB 模式相关
_poi_repo_instance: Any = None  # POIRepository 实例或 None（未初始化）
_DB_FALLBACK_SENTINEL: Any = object()  # 标记：DB 不可用，使用 JSON 回退

logger = logging.getLogger(__name__)


def load_data() -> None:
    for json_file in DATA_DIR.glob("*.json"):
        _cache[json_file.stem] = json.loads(json_file.read_text(encoding="utf-8"))


def get_data(dataset: Optional[str] = None, filters: Optional[dict] = None, city: Optional[str] = None) -> Any:
    if not _cache:
        load_data()

    if dataset and dataset in _cache:
        data = _cache[dataset]
    else:
        data = []
        for v in _cache.values():
            if isinstance(v, list):
                data.extend(v)

    # 按城市过滤
    if city and isinstance(data, list):
        data = [d for d in data if isinstance(d, dict) and d.get("city") == city]

    if filters and isinstance(data, list):
        for key, val in filters.items():
            data = [d for d in data if isinstance(d, dict) and d.get(key) == val]

    return data


def get_datasets() -> list[str]:
    if not _cache:
        load_data()
    return list(_cache.keys())


# ---------------------------------------------------------------------------
# DB 模式：异步 POI 查询
# ---------------------------------------------------------------------------


async def get_poi_data_async(
    filters: Optional[dict[str, Any]] = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """从 PostgreSQL 查询 POI 数据（DB 模式）。

    行为：
        - 当 ``settings.use_db`` 为 ``False``（默认）时，直接回退 JSON 模式。
        - 当 ``settings.use_db`` 为 ``True`` 时，首次调用会惰性建立数据库连接，
          后续复用。如果连接失败，永久回退 JSON。
        - ``filters`` 支持 ``city``、``category``、``min_rating``、``max_price`` 等键。

    Args:
        filters: 可选的筛选条件。
        limit: 最大返回条数，默认 1000。

    Returns:
        POI 字典列表，结构与 JSON 模式一致（不含 ``ugc_comments``）。
    """
    from backend.config import settings

    # DB 模式未开启 → JSON 回退
    if not settings.use_db:
        return get_data("city_poi_db", filters)

    global _poi_repo_instance

    # 首次调用 → 惰性连接
    if _poi_repo_instance is None:
        try:
            from sqlalchemy import text

            from backend.database.base import async_session_factory
            from backend.database.poi_repository import POIRepository

            session = async_session_factory()
            try:
                _poi_repo_instance = POIRepository(session)
                await session.execute(text("SELECT 1"))
                logger.info("DB 模式已激活，连接成功")
            except Exception:
                await session.close()
                logger.warning("DB 模式不可用，回退 JSON（检查 PostgreSQL 是否运行）")
                _poi_repo_instance = _DB_FALLBACK_SENTINEL
                return get_data("city_poi_db", filters)
        except Exception:
            logger.warning("DB 模式不可用，回退 JSON（检查 PostgreSQL 是否运行）")
            _poi_repo_instance = _DB_FALLBACK_SENTINEL
            return get_data("city_poi_db", filters)

    # DB 之前已标记为不可用 → JSON 回退
    if _poi_repo_instance is _DB_FALLBACK_SENTINEL:
        return get_data("city_poi_db", filters)

    # 正常 DB 查询
    try:
        pois = await _poi_repo_instance.find_filtered(filters or {}, limit=limit)
        return [p.to_dict() for p in pois]
    except Exception:
        logger.exception("DB 查询失败，回退 JSON")
        return get_data("city_poi_db", filters)
