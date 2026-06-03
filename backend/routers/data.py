from datetime import date, timedelta

from fastapi import APIRouter, Query

from backend.models.schemas import DataResponse
from backend.services import data_service

router = APIRouter(prefix="/api", tags=["数据"])


@router.get(
    "/data/",
    response_model=DataResponse,
    summary="查询数据集",
    description=("通用数据集查询接口。\n\n" "根据数据集名称和可选的类别过滤器返回数据。"),
    response_description="数据列表及总数",
    tags=["数据"],
)
async def get_data(
    dataset: str | None = Query(None, description="数据集名称"),
    category: str | None = Query(None, description="按类别过滤"),
) -> DataResponse:
    """通用数据集查询。"""
    filters = {"category": category} if category else None
    data = data_service.get_data(dataset=dataset, filters=filters)
    return DataResponse(data=data, total=len(data))


@router.get(
    "/poi/",
    summary="查询城市POI数据",
    description=(
        "返回城市POI数据，支持按城市和品类筛选。\n\n"
        "这是底层数据查询接口，返回原始POI数据（不含情绪标签补充）。\n"
        "如需带情绪标签的POI数据，请使用 `/api/poi/search` 接口。"
    ),
    response_description="POI数据列表及总数",
    tags=["数据"],
)
async def get_poi(
    city: str | None = Query(None, description="按城市筛选"),
    category: str | None = Query(None, description="按品类筛选"),
) -> dict:
    """返回城市 POI 数据，支持城市和品类筛选。"""
    all_data = data_service.get_data(dataset="city_poi_db")
    if city:
        all_data = [d for d in all_data if d.get("city") == city]
    if category:
        all_data = [d for d in all_data if d.get("category") == category]
    return {"data": all_data, "total": len(all_data)}


@router.get(
    "/datasets",
    summary="列出所有数据集",
    description="返回系统中已加载的所有数据集名称列表。",
    response_description="数据集名称列表",
    tags=["数据"],
)
async def get_datasets() -> dict:
    """列出所有可用数据集。"""
    return {"datasets": data_service.get_datasets()}


@router.get(
    "/order/",
    summary="查询POI交通流量",
    description=(
        "返回POI交通流量快照数据。\n\n"
        "## 数据说明\n\n"
        "- 基于 `order_data` 数据集\n"
        "- 支持按城市、品类筛选\n"
        "- 支持按年中第几天（day_of_year）和小时（hour）定位\n"
        "- 返回每个POI的日订单量和小时订单量\n\n"
        "## 时间参数\n\n"
        "- `day_of_year`: 1~365，默认1（即1月1日）\n"
        "- `hour`: 0~23，不传则返回日订单量"
    ),
    response_description="流量数据列表",
    tags=["数据"],
)
async def get_order(
    city: str | None = Query(None, description="按城市筛选"),
    category: str | None = Query(None, description="按品类筛选"),
    day_of_year: int | None = Query(None, ge=1, le=365, description="年中第几天（1~365），默认1"),
    hour: int | None = Query(None, ge=0, le=23, description="小时（0~23），不传则返回日订单量"),
) -> dict:
    """返回 POI 交通流量快照，支持按城市/品类筛选。"""
    # order_data.json 根是 dict，直接取；city_poi_db.json 根是 list
    order_root = data_service.get_data(dataset="order_data")
    poi_data = data_service.get_data(dataset="city_poi_db")

    if not order_root:
        return {"data": [], "total": 0, "error": "order_data not loaded"}

    # order_root 可能是 dict 或 [dict]，统一处理
    if isinstance(order_root, list):
        order_root = order_root[0]
    elif not isinstance(order_root, dict):
        return {"data": [], "total": 0, "error": "order_data format error"}

    hourly_profiles = order_root.get("hourly_profiles", {})
    poi_daily = order_root.get("poi_daily", {})

    # 构建 POI 元信息映射
    poi_meta = {p["id"]: p for p in poi_data}

    # day_of_year 从 1 开始，转为 0-based
    idx = (day_of_year - 1) if day_of_year else 0

    results = []
    for poi_id, daily_list in poi_daily.items():
        if poi_id not in poi_meta:
            continue
        meta_poi = poi_meta[poi_id]

        # 城市/品类过滤
        if city and meta_poi.get("city") != city:
            continue
        if category and meta_poi.get("category") != category:
            continue

        daily_orders = daily_list[idx] if idx < len(daily_list) else 0

        # 小时分布
        cat = meta_poi.get("category", "其他")
        profile = hourly_profiles.get(cat, [1 / 24] * 24)
        hourly_orders = (
            int(daily_orders * profile[hour])
            if hour is not None and 0 <= hour < 24
            else daily_orders
        )

        results.append(
            {
                "poi_id": poi_id,
                "name": meta_poi.get("name", ""),
                "city": meta_poi.get("city", ""),
                "category": meta_poi.get("category", ""),
                "lat": meta_poi.get("lat", 0),
                "lng": meta_poi.get("lng", 0),
                "daily_orders": daily_orders,
                "hourly_orders": hourly_orders,
                "rating": meta_poi.get("rating", 0),
            }
        )

    day_idx = day_of_year - 1 if day_of_year else 0
    day_date = date(2026, 1, 1) + timedelta(days=day_idx)
    return {
        "date": day_date.isoformat(),
        "hour": hour if hour is not None else -1,
        "city": city or "全部",
        "data": results,
        "total": len(results),
    }


@router.get(
    "/road-traffic/",
    summary="查询道路拥堵指数",
    description=(
        "返回道路拥堵指数（TTI）快照数据。\n\n"
        "## 数据说明\n\n"
        "- 基于 `road_traffic_data` 数据集\n"
        "- 支持按城市、路段类型筛选\n"
        "- 支持按日期和小时定位\n\n"
        "## 拥堵等级\n\n"
        "| TTI 范围 | 等级 |\n"
        "|----------|------|\n"
        "| < 1.2 | 畅通 |\n"
        "| 1.2 ~ 1.5 | 缓行 |\n"
        "| 1.5 ~ 2.0 | 拥堵 |\n"
        "| >= 2.0 | 严重拥堵 |"
    ),
    response_description="道路拥堵数据列表",
    tags=["数据"],
)
def _get_congestion_level(tti: float | None) -> str | None:
    """根据TTI计算拥堵等级。"""
    if tti is None:
        return None
    if tti < 1.2:
        return "畅通"
    if tti < 1.5:
        return "缓行"
    if tti < 2.0:
        return "拥堵"
    return "严重拥堵"


async def get_road_traffic(
    city: str | None = Query(None, description="按城市筛选"),
    road_type: str | None = Query(None, description="按路段类型筛选"),
    day_of_year: int | None = Query(None, ge=1, le=365, description="年中第几天（1~365）"),
    hour: int | None = Query(None, ge=0, le=23, description="小时（0~23）"),
) -> dict:
    """返回道路拥堵指数快照，支持按城市/路段类型筛选。"""
    road_root = data_service.get_data(dataset="road_traffic_data")

    _day_idx = (day_of_year - 1) if day_of_year else 0
    _date = date(2026, 1, 1) + timedelta(days=_day_idx)

    if not road_root:
        return {"data": [], "total": 0, "error": "road_traffic_data not loaded"}

    if isinstance(road_root, list):
        road_root = road_root[0]
    elif not isinstance(road_root, dict):
        return {"data": [], "total": 0, "error": "road_traffic_data format error"}

    roads = road_root.get("roads", [])
    hourly_congestion = road_root.get("hourly_congestion", {})

    results = []
    for road in roads:
        if city and road.get("city") != city:
            continue
        if road_type and road.get("road_type") != road_type:
            continue

        road_tti_list = hourly_congestion.get(road["road_id"], [])
        if _day_idx >= len(road_tti_list):
            continue

        h_idx = hour if hour is not None and 0 <= hour < 24 else -1
        tti = road_tti_list[_day_idx][h_idx] if h_idx >= 0 else None

        results.append({
            "road_id": road["road_id"],
            "name": road["name"],
            "city": road["city"],
            "road_type": road["road_type"],
            "lng": road["lng"],
            "lat": road["lat"],
            "tti": tti,
            "congestion_level": _get_congestion_level(tti),
        })

    return {
        "date": _date.isoformat(),
        "hour": hour if hour is not None else -1,
        "city": city or "全部",
        "data": results,
        "total": len(results),
    }
