"""CityFlow TSPTW 情绪混合求解器。

5阶段求解：
1. 候选筛选（按意图category偏好 + 情绪匹配）
2. TW-Nearest Neighbor 贪心初始化（含时间窗可行性剪枝）
3. 2-opt 局部搜索改进
4. 呼吸空间插入（高兴奋POI之间插入休息节点）
5. 高潮收尾检查 + 输出组装
"""

from __future__ import annotations

import logging
import threading
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from backend.services.cache import distance_cache

logger = logging.getLogger(__name__)

from backend.services.economy import enrich_poi_economics  # noqa: E402
from backend.services.emotion import (  # noqa: E402
    calculate_emotion_curve,
    chemical_reaction,
    emotion_compatibility,
    fatigue_penalty,
    sensory_alternation,
)
from backend.services.filters import filter_candidates  # noqa: E402
from backend.services.geo import (  # noqa: E402
    cache_key_distance,
    cache_key_travel_time,
    poi_distance,
    poi_travel_time,
)
from backend.services.memory.psychology import PsychologyRules  # noqa: E402
from backend.services.poi_scenes import audit_route, tag_poi  # noqa: E402
from backend.services.time_utils import (  # noqa: E402
    format_time,
    get_poi_opening_hours,
    parse_hours_to_minutes,
    parse_time,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# 非标体验加载（by 王启龙 2026-05-09: 集成城市特色体验到求解流程）
# ---------------------------------------------------------------------------

_NSE_CACHE: list[dict] | None = None


def _load_nonstandard_experiences() -> list[dict]:
    """加载非标体验数据。数据由用户生成，放入 data/nonstandard_experiences.json。"""
    global _NSE_CACHE
    if _NSE_CACHE is not None:
        return _NSE_CACHE
    try:
        import json
        from pathlib import Path

        path = Path(__file__).parent.parent / "data" / "nonstandard_experiences.json"
        if path.exists():
            _NSE_CACHE = json.loads(path.read_text(encoding="utf-8"))
            return _NSE_CACHE
    except Exception:
        logger.debug("NSE缓存加载失败", exc_info=True)
    _NSE_CACHE = []
    return _NSE_CACHE


def _get_nse_for_city(city: str, hour: int) -> list[dict]:
    """获取某城市当前时段适合的非标体验。"""
    all_nse = _load_nonstandard_experiences()
    if not all_nse:
        return []

    matched = []
    for nse in all_nse:
        if nse.get("city", "").strip() != city:
            continue
        best_time = nse.get("best_time", "")
        if not best_time:
            continue
        try:
            open_s, close_s = best_time.split("-")
            open_m = parse_hours_to_minutes(open_s.strip())
            close_m = parse_hours_to_minutes(close_s.strip())
            current_m = hour * 60
            if open_m <= current_m <= close_m:
                matched.append(nse)
        except Exception:
            continue
    return matched


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_ALPHA = 1.0  # 旅行时间权重
_BETA = 0.5  # 情绪评分权重（提高）
_GAMMA = 0.2  # 疲劳惩罚权重（可通过 solve_route 的 perception_ctx 动态调整）
_DELTA = 2.0  # 同类惩罚权重（强制多样性，避免连续同类POI）
_EPSILON = 0.5  # category多样性权重
_REACTION_WEIGHT = 0.3  # 化学反应评分权重

# 区域转移惩罚
_AREA_REVISIT_PENALTY = 4.0  # 回跳已去过区域
_AREA_CROSS_PENALTY = 1.0  # 跨区域

# 距离惩罚系数
_CIRCUIT_DIST_DIVISOR = 10000.0  # 环路距离归一化（10km）
_START_DIST_PENALTY = 0.1  # 起点距离惩罚系数

# category比例阈值
_CAT_RATIO_HIGH = 0.4  # 高比例阈值
_CAT_RATIO_LOW = 0.3  # 低比例阈值
_SENSORY_WEIGHT = 0.2  # 感官交替评分权重

# 场景同义词映射（统一模块常量，避免重复创建）
_SCENE_SYNONYMS: dict[str, list[str]] = {
    "茶馆": ["茶室", "茶楼", "品茶", "茶舍", "茶座", "茶"],
    "街边小店": ["夜市", "小吃街", "小吃", "大排档", "美食街"],
    "街边小吃": [
        "夜市",
        "小吃街",
        "小吃",
        "大排档",
        "美食街",
        "路边摊",
        "小吃街",
        "小吃",
        "大排档",
        "路边摊",
        "美食街",
    ],
    "本地小吃": ["夜市", "小吃", "本地美食", "老字号", "传统美食", "地道"],
    "烧烤": ["BBQ", "烤肉", "烧烤", "烤"],
    "蹦迪": ["酒吧", "夜店", "LiveHouse", "音乐现场", "夜生活", "清吧", "居酒屋"],
    "游乐园": ["乐园", "游乐", "主题公园", "长隆"],
    "海洋馆": ["海洋", "水族", "海洋王国", "长隆"],
    "曲艺表演": ["曲艺", "粤曲", "戏曲", "表演", "传统文化"],
    "室内": ["室内", "空调", "封闭"],
    "宵夜": ["夜市", "深夜", "宵夜", "大排档", "小吃", "排档", "夜排档"],
    "便宜实惠": ["便宜", "实惠", "经济", "平价"],
    "安静画画": ["画室", "美术馆", "艺术", "写生", "手作", "陶艺"],
}

# V2: 线程局部状态（替代模块级全局变量，防止并发竞态）
_thread_state = threading.local()


def _get_thread_state() -> threading.local:
    """获取当前线程的局部状态。"""
    if not hasattr(_thread_state, "current_weights"):
        _thread_state.current_weights = None
        _thread_state.gamma_multiplier = 1.0
        _thread_state.progress_callback = None
    return _thread_state


_REST_MINUTES = 30  # 休息停留时间（分钟）
_EXCITEMENT_THRESHOLD = 0.6  # 高兴奋度阈值
_TRANQUILITY_THRESHOLD = 0.7  # 高宁静度阈值
_REST_CATEGORIES = {"公园", "咖啡馆", "广场", "休息"}
_REST_CANDIDATE_TAGS = {"公园", "咖啡", "休息", "安静"}

# 地理聚类：网格大小（度，约 5km，防止微观波动）
_GEO_GRID_SIZE = 0.05

# ── 旅游相关性评分 ──────────────────────────────────────────

# 非旅游关键词：这些名称特征的 POI 大概率不是旅游目的地
_NON_TOURIST_KEYWORDS: list[str] = [
    "汽配",
    "修车",
    "维修",
    "五金",
    "建材",
    "装修",
    "小卖部",
    "便利店",
    "超市",
    "菜市场",
    "菜市",
    "瑜伽",
    "普拉提",  # 健身工作室，非旅游目的地
    "Fitness",
    "fitness",
    "Gym",
    "gym",  # 健身房（英文名）
    "Cyber",
    "cyber",  # 网吧/电竞
    "宿舍",
    "厂房",
    "仓库",
    "工业",
    "物流",
    "保安",
    "消防",
    "宣传",
    "居委会",
    "社区",
    "物业",
    "学校",
    "幼儿园",
    "小学",
    "中学",
    "大学",
    "学院",
    "医院",
    "诊所",
    "药房",
    "药店",
    "公司",
    "集团",
    "办公",
    "写字楼",
    "加油站",
    "洗车",
    "轮胎",
    "配电",
    "变电站",
    "环卫",
    "计算机",
    "网吧",
    "网咖",
    "教育中心",
    "Centro",  # 非旅游设施
    "麦当劳",
    "麥當勞",
    "McDonald",
    "McDonald's",
    "KFC",
    "肯德基",  # 连锁快餐
    "永旺",
    "超级市場",
    "Supermercado",
    "7-Eleven",
    "便利店",  # 超市/便利店
    "UGYM",  # 健身房
    # 澳门地名（坐标在珠海但实际位于澳门）
    "澳門",
    "Macau",
    "沙梨頭",
    "望德",
    "氹仔",
    "路環",
    "大三巴",
    "议事亭",
    "喷水池",
    "葡文",
    "Plataforma",
    "Posto do",
    "Edifício",
    "Edif",
    "Mong Há",
    "Patane",  # 葡语/澳门地名
]

# 旅游相关关键词：加分
_TOURIST_KEYWORDS: list[str] = [
    "公园",
    "海滩",
    "沙滩",
    "海湾",
    "山",
    "峰",
    "博物馆",
    "美术馆",
    "展览馆",
    "纪念馆",
    "故居",
    "寺",
    "庙",
    "祠",
    "教堂",
    "广场",
    "步行街",
    "老街",
    "历史",
    "景区",
    "景点",
    "度假",
    "温泉",
    "乐园",
    "游乐场",
    "剧场",
    "影院",
    "夜市",
    "美食街",
    "酒吧街",
    "塔",
    "桥",
    "岛",
    "灯塔",
    "艺术区",
    "创意园",
    "文化园",
]

# ── 用户输入 → 场景标签直接映射（不走 preference 间接匹配）──
_INPUT_TO_SCENE_TAGS: dict[str, set[str]] = {
    "夜景": {"夜景"},
    "晚上": {"夜景"},
    "夜晚": {"夜景"},
    "夜间": {"夜景"},
    "浪漫": {"情侣", "夜景", "拍照出片"},
    "情侣": {"情侣"},
    "约会": {"情侣"},
    "二人": {"情侣"},
    "亲子": {"亲子"},
    "小孩": {"亲子"},
    "孩子": {"亲子"},
    "儿童": {"亲子"},
    "带娃": {"亲子"},
    "海边": {"海滨"},
    "海滩": {"海滨"},
    "沙滩": {"海滨"},
    "海景": {"海滨"},
    "海": {"海滨"},
    "安静": {"休闲放松", "安静"},
    "放松": {"休闲放松"},
    "爬山": {"运动健身", "山景"},
    "运动": {"运动健身"},
    "徒步": {"运动健身"},
    "拍照": {"拍照出片", "出片"},
    "摄影": {"拍照出片", "出片"},
    "出片": {"拍照出片", "出片"},
    "打卡": {"打卡热点", "出片"},
    "文化": {"文化历史"},
    "历史": {"文化历史"},
    "博物馆": {"文化历史"},
    "美食": {"美食"},
    "小吃": {"美食"},
    "吃": {"美食"},
    "餐厅": {"美食"},
    "购物": {"购物"},
    "逛街": {"购物"},
    "买东西": {"购物"},
    "自然": {"自然风光"},
    "风景": {"自然风光"},
    "公园": {"公园"},
    "免费": {"经济实惠"},
    "省钱": {"经济实惠"},
}
_PREF_TO_SCENE_TAGS: dict[str, set[str]] = {
    "nature": {"自然风光", "海滨", "山景", "公园"},
    "culture": {"文化历史", "经典"},
    "food": {"美食", "适合聚餐", "老字号", "味道正宗"},
    "social": {"朋友聚会", "情侣", "朋友友好"},
    "excitement": {"拍照出片", "打卡热点", "夜景", "网红店"},
    "tranquility": {"休闲放松", "安静"},
    "budget": {"经济实惠", "免费"},
}


_MEANINGFUL_TAGS = {
    "海滨", "山景", "公园", "夜景", "文化历史", "自然风光",
    "拍照出片", "打卡热点", "品质体验", "运动健身", "休闲放松",
    "亲子", "情侣", "网红店", "老字号",
}

_WEAK_TAGS = {
    "餐饮", "购物", "美食", "住宿", "运动", "文化", "市区", "经济", "经典",
    "出片", "休闲", "其他", "经济实惠", "适合聚餐", "交通便利", "环境好",
    "性价比高", "品牌齐全", "打折", "味道正宗", "停车方便", "服务好",
    "排队", "免费", "分量足",
}


def _calc_tourist_relevance(poi: dict) -> float:
    """计算 POI 作为旅游目的地的相关性评分 (0~1)。

    核心逻辑：
    1. 只有类别派生标签(餐饮/购物/住宿)的POI → 低分（generic）
    2. 有有意义场景标签(海滨/山景/文化等)的POI → 高分
    3. 名称含非旅游关键词(汽配/社区/消防等) → 直接过滤
    4. 酒店 → 排除（住宿不是游玩目的地）
    """
    name = poi.get("name", "")
    category = poi.get("category", "")
    tags = poi.get("tags", [])
    rating = poi.get("rating", 0)
    scene_tags = poi.get("_scene_tags", [])

    if category == "酒店":
        return 0.0

    has_meaningful_tag = any(t in scene_tags for t in _MEANINGFUL_TAGS)
    only_weak_tags = scene_tags and all(t in _WEAK_TAGS for t in scene_tags)

    score = 0.5
    if has_meaningful_tag:
        score += 0.3
    elif only_weak_tags:
        score -= 0.3

    if any(kw in name for kw in _NON_TOURIST_KEYWORDS):
        return 0.3

    if any(kw in name for kw in _TOURIST_KEYWORDS):
        score += 0.2

    if rating >= 4.5:
        score += 0.15
    elif rating >= 4.0:
        score += 0.1

    if len(tags) >= 3:
        score += 0.1

    return max(0.0, min(1.0, score))


def _assign_area_ids(pois: list[dict]) -> None:
    """给 POI 分配地理区域 ID。

    基于经纬度网格聚类，同一网格内的 POI 共享 area_id。
    防止路线在不同区域间来回跳跃。
    """
    for poi in pois:
        lat = poi.get("lat", 0)
        lng = poi.get("lng", 0)
        if lat == 0 and lng == 0:
            poi["_area_id"] = "unknown"
            continue
        # 网格坐标
        gx = round(lat / _GEO_GRID_SIZE) * _GEO_GRID_SIZE
        gy = round(lng / _GEO_GRID_SIZE) * _GEO_GRID_SIZE
        poi["_area_id"] = f"{gx:.3f},{gy:.3f}"


def _area_transition_penalty(route: list[dict], current: dict, next_poi: dict) -> float:
    """区域切换惩罚（正值 = 不好，越低分越好）。

    同一区域 0 惩罚，跨区域加分（不好）。
    严重惩罚回到已去过区域（回头路）。
    """
    if not route:
        return 0.0

    current_area = current.get("_area_id", "unknown")
    next_area = next_poi.get("_area_id", "unknown")

    if current_area == next_area:
        return 0.0  # 同一区域，好

    # 统计当前路线中已经到过的区域
    visited_areas = set()
    for step in route:
        area = step.get("poi", {}).get("_area_id", "unknown")
        visited_areas.add(area)

    if next_area in visited_areas:
        return _AREA_REVISIT_PENALTY
    return _AREA_CROSS_PENALTY


# ---------------------------------------------------------------------------
# V2: 动态权重与进度回调辅助
# ---------------------------------------------------------------------------


def _get_weight(name: str, default: float) -> float:
    """获取动态权重值（如有设置），否则返回默认值。"""
    tl = _get_thread_state()
    if tl.current_weights is not None and name in tl.current_weights:
        return tl.current_weights[name]
    return default


def _report_progress(stage: str, data: dict) -> None:
    """触发进度回调（如有设置）。"""
    tl = _get_thread_state()
    if tl.progress_callback is not None:
        tl.progress_callback(stage, data)


# 用户偏好维度 → 情绪标签映射
_PREF_TO_EMOTION: dict[str, str] = {
    "culture": "culture_depth",
    "nature": "tranquility",
    "social": "sociability",
    "food": "excitement",
}

_MAX_POIS_BY_PACE: dict[str, int] = {
    "闲逛型": 4,
    "平衡型": 6,
    "特种兵型": 8,
}

# 经济引擎权重
_ECONOMY_LEVERAGE_BONUS = 0.3  # high leverage 奖励（分数越低越好）
_ECONOMY_LEVERAGE_PENALTY = 0.2  # low leverage 惩罚
_BUDGET_RHYTHM_OPENING_BONUS = 0.3  # 开场阶段低价奖励
_BUDGET_RHYTHM_CLOSING_FACTOR = 0.05  # 收尾阶段体验价值系数
_BUDGET_TIGHT_LEVERAGE_BONUS = 0.3  # 预算紧张时高杠杆额外奖励
_BUDGET_TIGHT_THRESHOLD = 100  # 预算紧张阈值（元/人）

# _select_diverse_candidates 常量
_TOURIST_QUALITY_THRESHOLD = 0.4  # 旅游相关性最低阈值
_MIXED_SCORE_TOURIST_WEIGHT = 0.6  # 混合评分中旅游相关性权重
_MIXED_SCORE_RATING_WEIGHT = 0.4  # 混合评分中评分权重
_INPUT_SCENE_MATCH_BONUS = 1.0  # 输入场景标签匹配加分
_ACTIVITY_MATCH_BONUS = 2.0  # 活动需求匹配加分
_SCENE_MATCH_BONUS = 2.0  # 场景需求匹配加分（单次）
_LLM_PREFERRED_BONUS = 3.0  # LLM Planner推荐加分
_MAX_CAT_RATIO_DEFAULT = 0.3  # 默认单category上限比例
_MAX_CAT_RATIO_WITH_SCENE = 0.8  # 有场景需求时放宽上限比例
_MIN_SCENE_MATCH_FOR_LOCK = 4  # 两阶段锁定的最少匹配POI数

# _phase1_initialize 常量
_INTENT_SCORE_STRONG = -6.0  # 强意图匹配（输入/hard_constraints）
_INTENT_SCORE_MEDIUM = -3.0  # 中意图匹配（偏好）
_INTENT_SCORE_WEAK = -1.5  # 弱意图匹配（类别推荐）
_LLM_PLAN_PHASE1_BONUS = 5.0  # LLM Planner推荐加分（Phase1）
_SCENE_MATCHED_PHASE1_BONUS = 8.0  # scene_requirements匹配加分（Phase1）
_SCENE_SEMANTIC_PHASE1_BONUS = 3.0  # 场景语义匹配加分（Phase1）
_BUDGET_END_MARGIN_MINUTES = 15  # 预算结束时间弹性（分钟）
_OUTDOOR_CATS = {"运动", "景点"}  # 户外类POI类别

# _phase1 场景过滤常量
_VAGUE_LATE_NIGHT_SCENE_REQS = {"安静", "安全", "街头漫步", "街头", "夜景", "散步"}
_FOOD_SCENE_REQS = {
    "宵夜",
    "美食",
    "小吃",
    "烧烤",
    "火锅",
    "街边小店",
    "本地小吃",
    "街边小吃",
    "便宜实惠",
    "夜市",
}
_CONVENIENCE_KEYWORDS = ["美宜佳", "7-Eleven", "全家", "便利店", "Circle K", "OK便利店"]
_DAY_ONLY_KEYWORDS = ["海洋剧场", "海豚剧场", "儿童科技馆", "探险家中心", "动物园"]
_ACTIVITY_KEYWORDS: dict[str, list[str]] = {
    "needs_entertainment": ["游乐园", "乐园", "海洋", "水族", "动物园", "游乐", "主题公园", "长隆"],
    "needs_bbq": ["烧烤", "BBQ", "烤肉"],
    "needs_dining": ["火锅", "餐厅", "酒家"],
    "needs_teahouse": ["茶馆", "茶室", "茶楼", "品茶", "茶舍"],
    "needs_bookstore": ["书店", "书屋", "书吧", "图书馆", "阅读"],
    "needs_swimming": ["游泳", "泳池", "水上乐园", "水世界"],
    "needs_sports": ["球场", "足球", "篮球", "网球", "运动场"],
    "needs_hiking": ["山", "步道", "绿道", "登山"],
    "needs_art": ["画室", "美术馆", "艺术", "手工", "工坊", "陶艺"],
    "needs_calligraphy": ["书法", "博物馆", "文化馆", "展览"],
}

# 连锁快餐/非旅游品牌黑名单
_CHAIN_BLACKLIST: set[str] = {
    "麦当劳",
    "麥當勞",
    "mcdonald",
    "肯德基",
    "kfc",
    "星巴克",
    "starbucks",
    "瑞幸",
    "luckin",
    "必胜客",
    "必勝客",
    "pizza hut",
    "subway",
    "大家樂",
    "大家乐",
    "café de coral",
    "7-eleven",
    "全家",
    "罗森",
    "lawson",
    "蜜雪冰城",
    "茶百道",
    "古茗",
    "沪上阿姨",
}

# 情绪曲线7阶段（参考产品设计文档表格10成都示例）
_EMOTION_PHASES: list[dict] = [
    {
        "name": "宁静铺垫",
        "ratio": 0.15,
        "target": {"tranquility": (0.5, 1.0)},
        "cats": ["文化", "运动", "景点"],
    },
    {
        "name": "温暖上升",
        "ratio": 0.15,
        "target": {"excitement": (0.3, 0.6)},
        "cats": ["景点", "餐饮"],
    },
    {
        "name": "好奇探索",
        "ratio": 0.15,
        "target": {"surprise": (0.4, 1.0), "culture_depth": (0.3, 0.7)},
        "cats": ["文化", "景点", "其他"],
    },
    {
        "name": "兴奋高潮",
        "ratio": 0.15,
        "target": {"excitement": (0.6, 1.0)},
        "cats": ["运动", "购物", "景点"],
    },
    {
        "name": "沉淀呼吸",
        "ratio": 0.10,
        "target": {"tranquility": (0.5, 1.0)},
        "cats": ["文化", "景点"],
    },
    {
        "name": "文化输入",
        "ratio": 0.15,
        "target": {"culture_depth": (0.6, 1.0)},
        "cats": ["文化", "景点"],
    },
    {
        "name": "社交收尾",
        "ratio": 0.15,
        "target": {"excitement": (0.3, 0.7), "sociability": (0.4, 1.0)},
        "cats": ["餐饮", "购物", "景点"],
    },
]


def _get_dynamic_phases(user_intent: dict[str, Any]) -> list[dict]:
    """根据用户意图生成动态情绪阶段（替代硬编码7阶段）。

    核心思路：不同意图类型有不同的情绪曲线，
    比如朋友聚会全程高excitement，文艺独处全程高tranquility。
    """
    raw = user_intent.get("_raw_input", "")
    pref_cats = user_intent.get("preferred_categories", [])
    group = user_intent.get("group", {}).get("type", "")

    def _ensure_cats(cats: list[str]) -> list[str]:
        result = list(cats)
        for c in pref_cats:
            if c not in result:
                result.append(c)
        return result

    # 场景类型 → (匹配条件, 阶段模板)
    _phase_templates = [
        (
            lambda g, r: g == "朋友" or any(kw in r for kw in ["朋友", "聚会", "轰趴", "聚餐", "party"]),
            [
                {"name": "社交热身", "ratio": 0.3, "target": {"sociability": (0.5, 1.0), "excitement": (0.3, 0.7)}, "cats": ["餐饮", "购物"]},
                {"name": "兴奋高潮", "ratio": 0.4, "target": {"excitement": (0.6, 1.0), "sociability": (0.4, 1.0)}, "cats": ["娱乐", "运动", "购物"]},
                {"name": "美食收尾", "ratio": 0.3, "target": {"excitement": (0.3, 0.6), "sociability": (0.4, 1.0)}, "cats": ["餐饮", "购物"]},
            ],
        ),
        (
            lambda g, r: g == "情侣" or any(kw in r for kw in ["浪漫", "约会", "情侣", "二人"]),
            [
                {"name": "浪漫铺垫", "ratio": 0.3, "target": {"tranquility": (0.5, 0.8), "excitement": (0.2, 0.5)}, "cats": ["景点", "海景咖啡馆", "文化"]},
                {"name": "探索升温", "ratio": 0.4, "target": {"surprise": (0.3, 0.8), "excitement": (0.4, 0.7)}, "cats": ["景点", "餐饮", "购物"]},
                {"name": "甜蜜收尾", "ratio": 0.3, "target": {"excitement": (0.3, 0.6), "sociability": (0.3, 0.7)}, "cats": ["餐饮", "景点", "海景咖啡馆"]},
            ],
        ),
        (
            lambda g, r: any(kw in r for kw in ["安静", "独处", "看书", "一个人", "小众", "文艺"]),
            [
                {"name": "宁静铺垫", "ratio": 0.25, "target": {"tranquility": (0.6, 1.0)}, "cats": ["文化", "咖啡馆", "书店"]},
                {"name": "文化探索", "ratio": 0.25, "target": {"culture_depth": (0.5, 1.0), "tranquility": (0.3, 0.7)}, "cats": ["文化", "书店", "景点"]},
                {"name": "文艺体验", "ratio": 0.25, "target": {"surprise": (0.3, 0.7), "culture_depth": (0.3, 0.7)}, "cats": ["咖啡馆", "购物", "景点"]},
                {"name": "安静收尾", "ratio": 0.25, "target": {"tranquility": (0.5, 0.9), "culture_depth": (0.4, 0.8)}, "cats": ["文化", "咖啡馆", "餐饮"]},
            ],
        ),
        (
            lambda g, r: g == "亲子" or any(kw in r for kw in ["带娃", "孩子", "儿童", "亲子", "小孩"]),
            [
                {"name": "兴奋开场", "ratio": 0.3, "target": {"excitement": (0.6, 1.0), "surprise": (0.3, 0.7)}, "cats": ["运动", "娱乐", "景点"]},
                {"name": "探索中段", "ratio": 0.4, "target": {"surprise": (0.4, 0.8), "excitement": (0.3, 0.6)}, "cats": ["景点", "文化", "运动"]},
                {"name": "轻松收尾", "ratio": 0.3, "target": {"tranquility": (0.4, 0.7), "excitement": (0.2, 0.5)}, "cats": ["餐饮", "景点"]},
            ],
        ),
        (
            lambda g, r: any(kw in r for kw in ["凌晨", "深夜", "宵夜", "夜宵", "通宵", "半夜"]),
            [
                {"name": "觅食探索", "ratio": 0.5, "target": {"excitement": (0.4, 0.8), "surprise": (0.3, 0.7)}, "cats": ["餐饮", "夜市", "夜市小吃", "景点"]},
                {"name": "深夜延续", "ratio": 0.5, "target": {"excitement": (0.3, 0.6), "sociability": (0.3, 0.7)}, "cats": ["餐饮", "夜市", "景点"]},
            ],
        ),
        (
            lambda g, r: any(kw in r for kw in ["极速", "快速", "赶时间", "打卡", "2小时"]),
            [
                {"name": "高效打卡", "ratio": 0.4, "target": {"excitement": (0.5, 0.8), "surprise": (0.3, 0.7)}, "cats": ["景点", "文化", "购物"]},
                {"name": "核心体验", "ratio": 0.3, "target": {"excitement": (0.4, 0.7)}, "cats": ["景点", "餐饮"]},
                {"name": "收尾打卡", "ratio": 0.3, "target": {"excitement": (0.3, 0.6)}, "cats": ["餐饮", "购物"]},
            ],
        ),
        (
            lambda g, r: g == "退休" or any(kw in r for kw in ["退休", "老两口", "慢慢逛", "喝茶"]),
            [
                {"name": "悠闲漫步", "ratio": 0.4, "target": {"tranquility": (0.6, 1.0)}, "cats": ["景点", "文化", "运动"]},
                {"name": "品茗休憩", "ratio": 0.3, "target": {"tranquility": (0.5, 0.8), "culture_depth": (0.3, 0.6)}, "cats": ["餐饮", "文化"]},
                {"name": "文化收尾", "ratio": 0.3, "target": {"culture_depth": (0.5, 0.8)}, "cats": ["文化", "景点"]},
            ],
        ),
    ]

    for matcher, phases in _phase_templates:
        if matcher(group, raw):
            return [{**p, "cats": _ensure_cats(p["cats"])} for p in phases]

    # 默认：使用原始7阶段
    return [{**p, "cats": _ensure_cats(p["cats"])} for p in _EMOTION_PHASES]


def _score_poi_for_phase(poi: dict, phase: dict) -> float:
    """计算POI对某情绪阶段的匹配分数。"""
    et = poi.get("emotion_tags", {})
    score = 0.0
    for dim, (lo, hi) in phase["target"].items():
        val = et.get(dim, 0.5)
        if lo <= val <= hi:
            score += 1.0
        else:
            score -= abs(val - (lo + hi) / 2)
    # category匹配加分
    if poi.get("category") in phase["cats"]:
        score += 0.5
    return score


# category偏好映射：用户偏好 → 优先选择的category
_PREF_TO_CATEGORIES: dict[str, list[str]] = {
    "culture": ["文化", "景点"],
    "food": ["餐饮"],
    "nature": ["运动", "景点"],
    "social": ["餐饮", "购物"],
}

# 意图关键词 → preferred categories
_KEYWORD_CATEGORIES: dict[str, list[str]] = {
    "安静": ["文化", "景点", "餐饮"],
    "文化": ["文化"],
    "博物馆": ["文化"],
    "艺术": ["文化"],
    "展览": ["文化"],
    "咖啡": ["餐饮"],
    "美食": ["餐饮"],
    "吃": ["餐饮"],
    "公园": ["运动", "景点"],
    "散步": ["运动", "景点"],
    "自然": ["运动", "景点"],
    "爬山": ["运动"],
    "运动": ["运动"],
    "健身": ["运动"],
    "网红": ["文化", "购物", "餐饮"],
    "打卡": ["文化", "购物", "餐饮"],
    "拍照": ["文化", "景点"],
    "购物": ["购物"],
    "带娃": ["运动", "文化", "景点"],
    "孩子": ["运动", "文化", "景点"],
    "宠物": ["运动", "景点"],
    "退休": ["文化", "运动", "景点"],
    "情侣": ["文化", "餐饮", "景点"],
    "约会": ["文化", "餐饮", "景点"],
    "朋友": ["餐饮", "购物", "运动"],
}


# ---------------------------------------------------------------------------
# 距离/时间（带缓存的封装）
# ---------------------------------------------------------------------------


def estimate_distance(poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None) -> float:
    """估算两点间实际道路距离（米）。None 安全。带缓存。"""
    if not poi_a or not poi_b:
        return 0.0
    cache_key = cache_key_distance(poi_a, poi_b)
    cached_val = distance_cache.get(cache_key)
    if cached_val is not None:
        return cached_val
    dist = poi_distance(poi_a, poi_b)
    distance_cache.set(cache_key, dist)
    return dist


def estimate_travel_time(poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None) -> float:
    """估算两点间旅行时间（分钟）。None 安全。带缓存。"""
    if not poi_a or not poi_b:
        return 0.0
    cache_key = cache_key_travel_time(poi_a, poi_b)
    cached_val = distance_cache.get(cache_key)
    if cached_val is not None:
        return cached_val
    ttime = poi_travel_time(poi_a, poi_b)
    distance_cache.set(cache_key, ttime)
    return ttime


def estimate_steps(poi: dict[str, Any]) -> int:
    """根据停留时间和体力需求估算步数。"""
    stay_min = poi.get("avg_stay_min", 60)
    physical = poi.get("emotion_tags", {}).get("physical_demand", 0.5)
    return int(stay_min * 100 * physical)


# ---------------------------------------------------------------------------
# Phase 0: 候选筛选（按意图category偏好 + 情绪匹配）
# ---------------------------------------------------------------------------


_MACRO_CATS = ["文化", "餐饮", "运动", "景点", "购物"]

_GROUP_TYPE_CATEGORIES: dict[str, list[str]] = {
    "情侣": ["文化", "餐饮", "景点"],
    "亲子": ["运动", "文化", "景点"],
    "朋友": ["餐饮", "购物", "运动"],
    "退休": ["文化", "运动", "景点"],
}


def _get_preferred_categories(user_intent: dict[str, Any]) -> list[str]:
    """根据用户意图获取优先category列表。优先使用LLM推荐的类别。"""
    llm_cats = user_intent.get("preferred_categories", [])
    if llm_cats:
        result = list(llm_cats)
        for cat in _MACRO_CATS:
            if cat not in result:
                result.append(cat)
        return result

    seen: set[str] = set()
    preferred: list[str] = []

    def _add(cats: list[str]) -> None:
        for c in cats:
            if c not in seen:
                seen.add(c)
                preferred.append(c)

    prefs = user_intent.get("preferences", {})
    high_prefs = [k for k, v in prefs.items() if v > 0.5]
    for pref_key in high_prefs:
        _add(_PREF_TO_CATEGORIES.get(pref_key, []))

    for c in user_intent.get("hard_constraints", []):
        _add(_KEYWORD_CATEGORIES.get(c, []))

    group_type = user_intent.get("group", {}).get("type", "")
    _add(_GROUP_TYPE_CATEGORIES.get(group_type, []))

    if not preferred:
        return list(_MACRO_CATS)

    # 确保"景点"始终在偏好列表中
    _add(["景点"])
    return preferred


# ---------------------------------------------------------------------------
# _select_diverse_candidates 子函数
# ---------------------------------------------------------------------------


def _select_diverse_filter_by_city(
    all_pois: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按POI数量最多的城市筛选，浅拷贝避免修改全局缓存。"""
    city_counts: dict[str, int] = {}
    for poi in all_pois:
        city = poi.get("city", "未知")
        city_counts[city] = city_counts.get(city, 0) + 1
    if city_counts:
        main_city = max(city_counts, key=city_counts.get)
        all_pois = [p for p in all_pois if p.get("city") == main_city or not p.get("city")]
    # 浅拷贝避免修改全局缓存的POI对象
    return [{**p} for p in all_pois]


def _select_diverse_filter_tourist_quality(
    all_pois: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """预计算旅游相关性，过滤低质量POI。"""
    for poi in all_pois:
        poi["_tourist_relevance"] = _calc_tourist_relevance(poi)
    quality_pois = [
        p for p in all_pois if p.get("_tourist_relevance", 0.5) >= _TOURIST_QUALITY_THRESHOLD
    ]
    if not quality_pois:
        quality_pois = all_pois  # 兜底：如果全过滤掉了就恢复
    return quality_pois


def _select_diverse_filter_hard_constraints(
    quality_pois: list[dict[str, Any]],
    hard_constraints: list[str],
) -> list[dict[str, Any]]:
    """硬约束过滤：indoor_only、pet_friendly。"""
    # indoor_only: 只保留室内POI
    if "indoor_only" in hard_constraints:
        indoor_pois = [p for p in quality_pois if p.get("constraints", {}).get("is_indoor") is True]
        if indoor_pois:
            quality_pois = indoor_pois

    # pet_friendly: 只保留宠物友好POI
    if "pet_friendly" in hard_constraints:
        pet_pois = [
            p
            for p in quality_pois
            if p.get("constraints", {}).get("pet_friendly") or p.get("pet_friendly")
        ]
        if pet_pois:
            quality_pois = pet_pois

    return quality_pois


def _matches_scene_requirement(poi: dict, scene_reqs: list[str]) -> bool:
    """检查POI是否匹配任意一个scene_requirement (ANY-match)。"""
    text = (
        poi.get("name", "")
        + " "
        + " ".join(poi.get("tags", []))
        + " "
        + " ".join(poi.get("_scene_tags", []))
    )
    for sr in scene_reqs:
        if sr in text:
            return True
        for syn in _SCENE_SYNONYMS.get(sr, []):
            if syn in text:
                return True
    return False


def _is_poi_open_in_window(poi: dict, start_min: int, end_min: int) -> bool:
    """检查POI在用户时间窗口内是否可用。"""
    cat = poi.get("category", "")
    hours = poi.get("business_hours", "")

    if cat in _OUTDOOR_CATS:
        if not hours or hours == "00:00-23:59" or "24小时" in str(poi.get("tags", [])):
            return True
    if "00:00" in hours and ("23:59" in hours or hours.endswith("00:00")):
        return True

    try:
        parts = hours.split("-")
        oh, om = parts[0].strip().split(":")
        ch, cm = parts[1].strip().split(":")
        open_min_val = int(oh) * 60 + int(om)
        close_min_val = int(ch) * 60 + int(cm)
    except (ValueError, AttributeError, IndexError):
        tags = " ".join(poi.get("tags", []) + poi.get("_scene_tags", []))
        return bool(any(kw in tags for kw in ["24小时", "通宵", "深夜", "夜市"]))

    if open_min_val <= close_min_val:
        return open_min_val < end_min and close_min_val > start_min
    return open_min_val < end_min or start_min < close_min_val


def _select_diverse_filter_scene_requirements(
    quality_pois: list[dict[str, Any]],
    user_intent: dict[str, Any],
    hard_constraints: list[str],
) -> list[dict[str, Any]]:
    """scene_requirements预过滤（ANY-match）+ 场景感知过滤（美食/深夜/late_night）。"""
    _scene_reqs = user_intent.get("scene_requirements", [])
    _is_late_night_active = "late_night" in hard_constraints
    if (
        _is_late_night_active
        and _scene_reqs
        and all(sr in _VAGUE_LATE_NIGHT_SCENE_REQS for sr in _scene_reqs)
    ):
        _scene_reqs = []

    if _scene_reqs:
        sr_matched = [p for p in quality_pois if _matches_scene_requirement(p, _scene_reqs)]
        if len(sr_matched) >= 3:
            quality_pois = sr_matched
            logger.debug("scene_requirements Phase0预过滤(ANY-match): %d 个匹配", len(sr_matched))

    # 美食场景过滤便利店
    if bool(set(user_intent.get("scene_requirements", [])) & _FOOD_SCENE_REQS):
        before = len(quality_pois)
        quality_pois = [
            p for p in quality_pois
            if not any(kw in p.get("name", "") for kw in _CONVENIENCE_KEYWORDS)
        ]
        if len(quality_pois) < before:
            logger.debug("美食场景过滤: 移除便利店%d个, 剩余%d", before - len(quality_pois), len(quality_pois))

    # 深夜场景过滤白天专属景点
    _night_scene = any(
        kw in str(user_intent.get("scene_requirements", [])) + str(user_intent.get("_raw_input", ""))
        for kw in ["深夜", "凌晨", "宵夜", "夜景", "夜晚"]
    )
    if _night_scene:
        before = len(quality_pois)
        quality_pois = [p for p in quality_pois if not any(kw in p.get("name", "") for kw in _DAY_ONLY_KEYWORDS)]
        if len(quality_pois) < before:
            logger.debug("深夜场景过滤: 移除白天专属景点%d个", before - len(quality_pois))

    # late_night营业时间过滤
    if "late_night" in hard_constraints:
        quality_pois = _filter_late_night_pois(quality_pois, user_intent)

    return quality_pois


def _filter_late_night_pois(
    quality_pois: list[dict[str, Any]], user_intent: dict[str, Any]
) -> list[dict[str, Any]]:
    """过滤late_night场景下不可用的POI。"""
    time_info = user_intent.get("time", {})
    start_str = time_info.get("start", "22:00")
    end_str = time_info.get("end", "06:00")

    try:
        sh, sm = start_str.split(":")
        start_min = int(sh) * 60 + int(sm)
    except (ValueError, AttributeError):
        start_min = 22 * 60
    try:
        eh, em = end_str.split(":")
        end_min = int(eh) * 60 + int(em)
    except (ValueError, AttributeError):
        end_min = 6 * 60

    _crosses_midnight = end_min < start_min or start_min >= 22 * 60 or start_min <= 6 * 60

    if _crosses_midnight:
        late_pois = [p for p in quality_pois if _is_poi_open_in_window(p, start_min, end_min)]
    else:
        late_pois = quality_pois

    logger.debug(
        "late_night filter: %d → %d POIs (window=%s-%s, crosses_midnight=%s)",
        len(quality_pois), len(late_pois), start_str, end_str, _crosses_midnight,
    )
    return late_pois if late_pois else quality_pois


def _select_diverse_build_mixed_scorer(
    user_intent: dict[str, Any],
    hard_constraints: list[str],
    excluded_cats: set[str],
) -> Callable[[dict], float]:
    """构建混合排序评分函数（旅游相关性*0.6 + 评分*0.4 + 意图匹配 + 随机抖动）。"""
    import random as _randmod

    _raw_input_text = user_intent.get("_raw_input", "")
    _input_scene_tags: set[str] = set()
    for kw, tags in _INPUT_TO_SCENE_TAGS.items():
        if kw in _raw_input_text:
            _input_scene_tags.update(tags)

    # LLM Planner推荐的POI ID集合
    _llm_plan = user_intent.get("_llm_plan", {})
    _preferred_ids = set(_llm_plan.get("recommended_pois", []))

    # 场景需求关键词
    _scene_requirements = user_intent.get("scene_requirements", [])

    def _mixed_score(p: dict) -> float:
        score = (
            p.get("_tourist_relevance", 0.5) * _MIXED_SCORE_TOURIST_WEIGHT
            + (p.get("rating", 0) / 5.0) * _MIXED_SCORE_RATING_WEIGHT
            + _randmod.uniform(-0.01, 0.01)
        )
        # 输入意图匹配加分
        if _input_scene_tags:
            poi_tags = set(p.get("_scene_tags", []))
            if poi_tags & _input_scene_tags:
                score += _INPUT_SCENE_MATCH_BONUS
        # 特定活动需求加分
        poi_text = (
            p.get("name", "")
            + " "
            + " ".join(p.get("tags", []))
            + " "
            + " ".join(p.get("_scene_tags", []))
        )
        for constraint, keywords in _ACTIVITY_KEYWORDS.items():
            if constraint in hard_constraints:  # noqa: SIM102
                if any(kw in poi_text for kw in keywords):
                    score += _ACTIVITY_MATCH_BONUS
                    break
        # 场景需求语义匹配（scene_requirements，含同义词扩展）
        if _scene_requirements:
            matched_scenes = 0
            for sr in _scene_requirements:
                if sr in poi_text:
                    matched_scenes += 1
                else:
                    synonyms = _SCENE_SYNONYMS.get(sr, [])
                    if any(syn in poi_text for syn in synonyms):
                        matched_scenes += 1
            if matched_scenes > 0:
                score += matched_scenes * _SCENE_MATCH_BONUS
        # LLM Planner推荐加分
        if _preferred_ids and p.get("id") in _preferred_ids:
            score += _LLM_PREFERRED_BONUS
        return score

    return _mixed_score


def _select_diverse_select_by_category(
    quality_pois: list[dict[str, Any]],
    preferred_cats: list[str],
    excluded_cats: set[str],
    max_candidates: int,
    mixed_score: Callable[[dict], float],
    user_intent: dict[str, Any],
) -> list[dict[str, Any]]:
    """按category分组，从preferred cats和other cats中选择高评分POI。

    确保至少包含餐饮类POI（提升类别多样性）。
    """
    # 按category分组
    by_category: dict[str, list[dict]] = {}
    for poi in quality_pois:
        cat = poi.get("category", "其他")
        if cat in excluded_cats:
            continue
        by_category.setdefault(cat, []).append(poi)

    # 每个category上限
    _scene_reqs_for_diversity = user_intent.get("scene_requirements", [])
    if _scene_reqs_for_diversity:
        max_cat_ratio = _MAX_CAT_RATIO_WITH_SCENE
    else:
        max_cat_ratio = _MAX_CAT_RATIO_DEFAULT
    per_cat_max = max(2, int(max_candidates * max_cat_ratio))

    selected: list[dict] = []
    used_ids: set[str] = set()

    # 先从最匹配的category中选
    for cat in preferred_cats:
        if cat in excluded_cats or cat not in by_category:
            continue
        pois_in_cat = by_category[cat]
        pois_in_cat.sort(key=mixed_score, reverse=True)
        for p in pois_in_cat[:per_cat_max]:
            if p["id"] not in used_ids:
                selected.append(p)
                used_ids.add(p["id"])

    # 如果不够，从其他category补充
    if len(selected) < max_candidates:
        for cat, pois_in_cat in by_category.items():
            if cat in excluded_cats or cat in preferred_cats:
                continue
            already = sum(1 for s in selected if s.get("category", "") == cat)
            remaining_quota = max(0, per_cat_max - already)
            pois_in_cat.sort(key=mixed_score, reverse=True)
            for p in pois_in_cat[: min(2, remaining_quota)]:
                if p["id"] not in used_ids and len(selected) < max_candidates:
                    selected.append(p)
                    used_ids.add(p["id"])

    # 确保包含餐饮类POI（提升类别多样性）
    has_food = any(s.get("category") == "餐饮" for s in selected)
    if not has_food and "餐饮" in by_category:
        food_pois = by_category["餐饮"]
        food_pois.sort(key=mixed_score, reverse=True)
        # 添加1-2个餐饮POI
        for p in food_pois[:2]:
            if p["id"] not in used_ids and len(selected) < max_candidates:
                selected.append(p)
                used_ids.add(p["id"])

    return selected


def _select_diverse_dedup(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """连锁快餐黑名单过滤 + 名称去重。"""
    # 连锁快餐/非旅游品牌黑名单
    selected = [
        p for p in selected if not any(bw in p.get("name", "").lower() for bw in _CHAIN_BLACKLIST)
    ]

    # 名称去重：归一化后去重
    import re

    def _normalize_name(name: str) -> str:
        n = name.strip()
        n = re.sub(r"\s+[A-Za-z][A-Za-z\s\'\.&]+$", "", n)
        n = re.sub(r"[（(][^）)]*[）)]", "", n)
        return n.strip().lower()

    seen_names: dict[str, dict] = {}
    for p in selected:
        norm = _normalize_name(p.get("name", ""))
        if norm in seen_names:
            existing = seen_names[norm]
            if p.get("rating", 0) > existing.get("rating", 0):
                seen_names[norm] = p
        else:
            seen_names[norm] = p
    if len(seen_names) < len(selected):
        selected = list(seen_names.values())

    return selected


def _select_diverse_candidates(
    all_pois: list[dict[str, Any]],
    user_intent: dict[str, Any],
    max_candidates: int = 30,
) -> list[dict[str, Any]]:
    """按意图筛选候选POI，确保category多样性。

    策略：
    1. 先按城市筛选（同城市内规划）
    2. 从preferred categories中各选一些高评分POI
    3. 确保至少覆盖2种category
    4. 酒店类默认排除（不是出行目的地）
    """
    preferred_cats = _get_preferred_categories(user_intent)
    excluded_cats = {"酒店"}
    hard_constraints = user_intent.get("hard_constraints", [])

    # 1. 按城市筛选 + 浅拷贝
    all_pois = _select_diverse_filter_by_city(all_pois)

    # 2. 旅游相关性过滤
    quality_pois = _select_diverse_filter_tourist_quality(all_pois)

    # 3. 硬约束过滤
    quality_pois = _select_diverse_filter_hard_constraints(quality_pois, hard_constraints)

    # 4. 场景需求 + 场景感知过滤
    quality_pois = _select_diverse_filter_scene_requirements(
        quality_pois, user_intent, hard_constraints
    )

    # 5. 混合评分 + 按category选择
    mixed_score = _select_diverse_build_mixed_scorer(user_intent, hard_constraints, excluded_cats)
    selected = _select_diverse_select_by_category(
        quality_pois, preferred_cats, excluded_cats, max_candidates, mixed_score, user_intent
    )

    # 6. 去重
    selected = _select_diverse_dedup(selected)

    return selected


# ---------------------------------------------------------------------------
# 时间窗检查
# ---------------------------------------------------------------------------


def _check_time_windows(route: list[dict[str, Any]]) -> bool:
    """检查路线中每一步的到达时间是否在 POI 营业时间内。"""
    for step in route:
        open_t, close_t = get_poi_opening_hours(step["poi"])
        arrival = parse_time(step["arrival_time"])
        if arrival < open_t or arrival > close_t:
            return False
    return True


def _recalculate_times(
    route: list[dict[str, Any]], start_time: str, is_late_night: bool = False
) -> list[dict[str, Any]]:
    """按空间顺序重新计算路线中每一步的到达/出发时间。"""
    if not route:
        return route

    current_time = parse_time(start_time)
    prev_poi: dict[str, Any] | None = None
    new_route: list[dict[str, Any]] = []
    _OUTDOOR_CATS_TW = {"运动", "景点"}

    for step in route:
        poi = step["poi"]
        travel = estimate_travel_time(prev_poi, poi)
        arrival = current_time + timedelta(minutes=travel)

        # 深夜+户外类POI不等待开门
        if not (is_late_night and poi.get("category", "") in _OUTDOOR_CATS_TW):
            open_t, _ = get_poi_opening_hours(poi)
            arrival_dt = parse_time(format_time(arrival))
            if arrival_dt < open_t:
                arrival = parse_time(format_time(open_t))

        stay = poi.get("avg_stay_min", 60)
        departure = arrival + timedelta(minutes=stay)

        new_route.append(
            {
                "poi": poi,
                "arrival_time": format_time(arrival),
                "departure_time": format_time(departure),
                "travel_from_prev": {
                    "distance_m": round(estimate_distance(prev_poi, poi)),
                    "time_min": round(travel),
                },
            }
        )

        current_time = departure
        prev_poi = poi

    return new_route


# ---------------------------------------------------------------------------
# 路线评分
# ---------------------------------------------------------------------------


def _evaluate_route(route: list[dict[str, Any]], user_intent: dict[str, Any]) -> float:
    """评估路线综合评分（越高越好）。"""
    score = 0.0
    preferences = user_intent.get("preferences", {})

    # 情绪匹配度（偏好维度映射到情绪标签）
    for step in route:
        emotion = step["poi"].get("emotion_tags", {})
        for pref_key, pref_val in preferences.items():
            emotion_key = _PREF_TO_EMOTION.get(pref_key, pref_key)
            score += emotion.get(emotion_key, 0) * pref_val

    # 情绪兼容性（相邻POI对）
    for i in range(len(route) - 1):
        score += emotion_compatibility(route[i]["poi"], route[i + 1]["poi"])

    # 疲劳惩罚
    if route:
        total_steps = sum(estimate_steps(s["poi"]) for s in route)
        score += fatigue_penalty(total_steps, len(route))

    # category多样性奖励（使用动态权重）
    categories = [s["poi"].get("category", "") for s in route]
    unique_cats = len(set(categories))
    score += unique_cats * _get_weight("beta", _BETA)

    # 连续同类惩罚（使用动态权重）
    for i in range(len(route) - 1):
        if route[i]["poi"].get("category") == route[i + 1]["poi"].get("category"):
            score -= _get_weight("delta", _DELTA)

    # 回路惩罚：末站到首站距离越远越差（形成回路更好）
    if len(route) >= 2:
        first_poi = route[0]["poi"]
        last_poi = route[-1]["poi"]
        circuit_dist = estimate_distance(first_poi, last_poi)
        # 每10km扣1分
        score -= circuit_dist / _CIRCUIT_DIST_DIVISOR * _get_weight("alpha", _ALPHA)

    # 起终点奖励/惩罚
    start_point = user_intent.get("start_point")
    end_point = user_intent.get("end_point")
    if route and start_point:
        # 起点距离奖励：路线第一个POI离起点近更好
        first_poi = route[0]["poi"]
        start_dist = _calc_distance_to_point(first_poi, start_point)
        # 距离越近奖励越高（每公里-0.1分）
        score -= start_dist * _START_DIST_PENALTY
    if route and end_point:
        # 终点距离奖励：路线最后一个POI离终点近更好
        last_poi = route[-1]["poi"]
        end_dist = _calc_distance_to_point(last_poi, end_point)
        # 距离越近奖励越高（每公里-0.1分）
        score -= end_dist * _START_DIST_PENALTY

    return score


def _calc_distance_to_point(poi: dict[str, Any], point: dict[str, Any]) -> float:
    """计算POI到指定点的距离（公里）。"""
    poi_lat = poi.get("lat", 0)
    poi_lng = poi.get("lng", 0)

    # 支持坐标和地名两种格式
    if isinstance(point, dict):
        point_lat = point.get("lat", 0)
        point_lng = point.get("lng", 0)
    else:
        # 地名格式，从 filters 中获取坐标
        from backend.services.filters import _extract_user_location

        point_lat, point_lng = _extract_user_location({"location": point})

    if poi_lat == 0 or poi_lng == 0 or point_lat is None or point_lng is None:
        return 0.0

    # 使用 Haversine 公式计算距离
    from backend.services.filters import _haversine_km

    return _haversine_km(poi_lat, poi_lng, point_lat, point_lng)


# ---------------------------------------------------------------------------
# Phase 1: TW-Nearest Neighbor 贪心初始化
# ---------------------------------------------------------------------------


def _phase1_prepare_context(
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
) -> tuple[
    set[str],  # _preferred_ids
    list[str],  # _scene_requirements
    set[str],  # _scene_matched_ids
    int,  # max_pois
    float,  # budget_limit
    list[dict],  # phases
]:
    """准备Phase1所需上下文：LLM推荐ID、场景匹配、预算、情绪阶段。"""
    # LLM Planner推荐的POI ID集合
    _llm_plan = user_intent.get("_llm_plan", {})
    _preferred_ids = set(_llm_plan.get("recommended_pois", []))

    # 场景需求关键词
    _scene_requirements: list[str] = user_intent.get("scene_requirements", [])
    logger.debug(
        "Phase1 scene_requirements: %s, candidates: %d", _scene_requirements, len(candidates)
    )

    # 构建scene_requirements匹配集合（ANY-match）
    _scene_matched_ids: set[str] = set()
    if _scene_requirements:
        for p in candidates:
            text = (
                p.get("name", "")
                + " "
                + " ".join(p.get("tags", []))
                + " "
                + " ".join(p.get("_scene_tags", []))
            )
            for sr in _scene_requirements:
                if sr in text or any(syn in text for syn in _SCENE_SYNONYMS.get(sr, [])):
                    _scene_matched_ids.add(p.get("id"))
                    break  # ANY-match: 匹配一个就够了

    pace = user_intent.get("pace", "平衡型")
    max_pois = _MAX_POIS_BY_PACE.get(pace, 6)

    # 预算硬约束
    budget_limit = user_intent.get("budget", {}).get("per_person", 0)

    # 按情绪阶段选POI
    phases = _get_dynamic_phases(user_intent)
    # 最低阶段保护：动态阶段至少3个
    if len(phases) < 3:
        default_phases = []
        for phase in _EMOTION_PHASES:
            p = dict(phase)
            pref_cats = user_intent.get("preferred_categories", [])
            for c in pref_cats:
                if c not in p["cats"]:
                    p["cats"].append(c)
            default_phases.append(p)
        phases = default_phases

    # 两阶段锁定：food类scene_requirements额外要求餐饮类
    _food_scene_reqs = {"宵夜", "街边小店", "本地小吃", "烧烤", "美食"}
    _is_food_req = bool(set(_scene_requirements) & _food_scene_reqs)
    if _is_food_req and _scene_matched_ids:
        _scene_matched_ids = {
            pid
            for pid in _scene_matched_ids
            if any(p.get("id") == pid and p.get("category") == "餐饮" for p in candidates)
        }

    return _preferred_ids, _scene_requirements, _scene_matched_ids, max_pois, budget_limit, phases


def _phase1_check_time_window(
    poi: dict[str, Any],
    current_poi: dict[str, Any] | None,
    current_time: Any,
    end_time: Any,
    budget_limit: float,
    running_budget: float,
    is_late_night: bool,
) -> tuple[bool, float, Any] | None:
    """检查POI的时间窗口和预算可行性。

    返回:
        None 表示不可行（剪枝）
        (True, wait, arrival_as_time) 表示可行
    """
    travel = estimate_travel_time(current_poi, poi)
    arrival = current_time + timedelta(minutes=travel)

    open_t, close_t = get_poi_opening_hours(poi)
    arrival_as_time = parse_time(format_time(arrival))
    wait = 0.0

    # 深夜场景营业时间检查（考虑跨午夜）
    if is_late_night:
        if poi.get("category", "") in _OUTDOOR_CATS:
            hours = poi.get("business_hours", "")
            if not hours or hours == "00:00-23:59" or "24小时" in str(poi.get("tags", [])):
                pass  # 不检查
            else:
                pass
        else:
            open_min = open_t.hour * 60 + open_t.minute
            close_min = close_t.hour * 60 + close_t.minute
            arrival_min = arrival_as_time.hour * 60 + arrival_as_time.minute

            if close_min < open_min:
                if arrival_min >= open_min or arrival_min <= close_min:
                    pass  # 在营业时段内
                else:
                    return None  # 不在营业时段，剪枝
            else:
                if arrival_as_time < open_t:
                    wait = (open_t - arrival_as_time).total_seconds() / 60
                    arrival_as_time = open_t
                if arrival_as_time > close_t:
                    return None  # 已关门，剪枝
    else:
        # 正常时段营业时间检查
        if arrival_as_time < open_t:
            wait = (open_t - arrival_as_time).total_seconds() / 60
            arrival_as_time = open_t
        if arrival_as_time > close_t:
            return None

    # 剪枝：离开时间不超过用户结束时间
    if end_time:
        stay_min = poi.get("avg_stay_min", 60)
        departure_minutes = arrival_as_time.hour * 60 + arrival_as_time.minute + stay_min
        end_minutes = end_time.hour * 60 + end_time.minute
        if departure_minutes - end_minutes > _BUDGET_END_MARGIN_MINUTES:
            return None

    # 预算硬约束
    if budget_limit > 0 and running_budget + poi.get("avg_price", 0) > budget_limit:
        return None

    return (True, wait, arrival_as_time)


def _phase1_score_scene_bonus(
    poi: dict[str, Any],
    user_intent: dict[str, Any],
) -> float:
    """计算场景标签匹配加分（输入匹配 + hard_constraints + 偏好 + category）。"""
    scene_bonus = 0.0
    preferences = user_intent.get("preferences", {})
    poi_scene_tags = set(poi.get("_scene_tags", []))
    raw_input = user_intent.get("_raw_input", "")

    # 1. 用户输入文本 → 场景标签直接匹配
    input_matched = False
    for keyword, target_tags in _INPUT_TO_SCENE_TAGS.items():
        if keyword in raw_input and (poi_scene_tags & target_tags):
            scene_bonus += _INTENT_SCORE_STRONG
            input_matched = True
            break

    # 1b. hard_constraints → 场景标签匹配
    if not input_matched:
        hard_constraints = user_intent.get("hard_constraints", [])
        for constraint in hard_constraints:
            for keyword, target_tags in _INPUT_TO_SCENE_TAGS.items():
                if keyword in constraint and (poi_scene_tags & target_tags):
                    scene_bonus += _INTENT_SCORE_STRONG
                    input_matched = True
                    break
            if input_matched:
                break

    # 2. 偏好 → 场景标签间接匹配
    pref_matched = False
    if not input_matched:
        for pref_key, pref_val in preferences.items():
            if pref_val > 0.3:
                matched_tags = _PREF_TO_SCENE_TAGS.get(pref_key, set())
                if poi_scene_tags & matched_tags:
                    scene_bonus += _INTENT_SCORE_MEDIUM
                    pref_matched = True
        has_active_prefs = any(v > 0.3 for v in preferences.values())
        if has_active_prefs and not pref_matched and not input_matched:
            scene_bonus += 0.5

    # 3. preferred_categories匹配
    _pref_cats = user_intent.get("preferred_categories", [])
    _cat_bonus = 0.0
    if _pref_cats and poi.get("category", "") in _pref_cats:
        _cat_idx = _pref_cats.index(poi.get("category", ""))
        _cat_bonus += _INTENT_SCORE_WEAK + _cat_idx * 1.0

    return scene_bonus + _cat_bonus


def _calc_same_type_penalty(poi: dict, route: list[dict[str, Any]]) -> float:
    """计算同类POI连续访问惩罚。"""
    if not route:
        return 0.0

    curr_cat = poi.get("category", "")
    consecutive = 0
    for prev_step in reversed(route):
        if prev_step["poi"].get("category", "") == curr_cat:
            consecutive += 1
        else:
            break

    penalty = 0.5 + consecutive * 1.0 if consecutive > 0 else 0.0

    cat_count = sum(1 for s in route if s["poi"].get("category", "") == curr_cat)
    cat_ratio = cat_count / len(route)
    if cat_ratio >= _CAT_RATIO_HIGH:
        penalty += 3.0
    elif cat_ratio >= _CAT_RATIO_LOW:
        penalty += 1.5

    return penalty


def _calc_scene_semantic_bonus(
    poi: dict[str, Any], scene_requirements: list[str]
) -> float:
    """计算场景需求语义匹配加分。"""
    if not scene_requirements:
        return 0.0

    poi_text = (
        poi.get("name", "")
        + " "
        + " ".join(poi.get("tags", []))
        + " "
        + " ".join(poi.get("_scene_tags", []))
    )
    matched = 0
    for sr in scene_requirements:
        if sr in poi_text:
            matched += 1
        elif any(syn in poi_text for syn in _SCENE_SYNONYMS.get(sr, [])):
            matched += 1

    return matched * _SCENE_SEMANTIC_PHASE1_BONUS if matched > 0 else 0.0


def _calc_economy_score(
    poi: dict[str, Any],
    route: list[dict[str, Any]],
    max_pois: int,
    user_intent: dict[str, Any],
) -> float:
    """计算经济引擎评分（杠杆率+预算节奏）。"""
    enriched = enrich_poi_economics(poi)
    leverage = enriched.get("experience_leverage", "medium")

    score = 0.0
    route_pos = len(route) / max_pois if max_pois > 0 else 0
    if route_pos < 0.25 and poi.get("avg_price", 0) < 50:
        score -= _BUDGET_RHYTHM_OPENING_BONUS
    if route_pos > 0.75:
        ev = enriched.get("experience_value", 5.0)
        score -= ev * _BUDGET_RHYTHM_CLOSING_FACTOR

    if leverage == "high":
        score -= _ECONOMY_LEVERAGE_BONUS
    elif leverage == "low":
        score += _ECONOMY_LEVERAGE_PENALTY

    budget_per_person = user_intent.get("budget", {}).get("per_person", 500)
    budget_strictness = _get_weight("budget_strictness", 1.0)
    if budget_per_person < _BUDGET_TIGHT_THRESHOLD * budget_strictness and leverage == "high":
        score -= _BUDGET_TIGHT_LEVERAGE_BONUS

    return score


def _phase1_score_candidate(
    poi: dict[str, Any],
    travel: float,
    wait: float,
    route: list[dict[str, Any]],
    current_poi: dict[str, Any] | None,
    step_count: int,
    max_pois: int,
    phase: dict,
    user_intent: dict[str, Any],
    _preferred_ids: set[str],
    _scene_matched_ids: set[str],
    _scene_requirements: list[str],
    budget_limit: float,
) -> float:
    """为候选POI计算综合评分（越低越好）。"""
    phase_score = -_score_poi_for_phase(poi, phase)
    fatigue = fatigue_penalty(step_count, len(route))
    same_type = _calc_same_type_penalty(poi, route)
    reaction_score = chemical_reaction(route[-1]["poi"], poi) if route else 0.0
    sensory_score = sensory_alternation([*route, {"poi": poi}])
    area_penalty = _area_transition_penalty(route, current_poi, poi)
    scene_bonus = _phase1_score_scene_bonus(poi, user_intent)

    score = (
        _get_weight("alpha", _ALPHA) * (travel + wait)
        + _get_weight("beta", _BETA) * phase_score
        + _get_weight("gamma", _GAMMA) * fatigue * _get_thread_state().gamma_multiplier
        + _get_weight("delta", _DELTA) * same_type
        + _get_weight("reaction", _REACTION_WEIGHT) * reaction_score
        + _get_weight("sensory", _SENSORY_WEIGHT) * sensory_score
        + _get_weight("area", 1.0) * area_penalty
        + scene_bonus
    )

    if _preferred_ids and poi.get("id") in _preferred_ids:
        score -= _LLM_PLAN_PHASE1_BONUS
    if _scene_matched_ids and poi.get("id") in _scene_matched_ids:
        score -= _SCENE_MATCHED_PHASE1_BONUS

    score -= _calc_scene_semantic_bonus(poi, _scene_requirements)
    score += _calc_economy_score(poi, route, max_pois, user_intent)

    return score


def _phase1_finalize_step(
    best: dict[str, Any],
    current_poi: dict[str, Any] | None,
    current_time: Any,
    is_late_night: bool,
) -> tuple[Any, dict[str, Any]]:
    """计算最终到达/出发时间，返回 (new_current_time, route_step)。"""
    travel = estimate_travel_time(current_poi, best)
    arrival = current_time + timedelta(minutes=travel)
    # 深夜+户外类POI不等待开门
    if not (is_late_night and best.get("category", "") in _OUTDOOR_CATS):
        open_t, _ = get_poi_opening_hours(best)
        arrival_as_time = parse_time(format_time(arrival))
        if arrival_as_time < open_t:
            arrival = parse_time(format_time(open_t))

    stay = best.get("avg_stay_min", 60)
    departure = arrival + timedelta(minutes=stay)

    step: dict[str, Any] = {
        "poi": best,
        "arrival_time": format_time(arrival),
        "departure_time": format_time(departure),
        "travel_from_prev": {
            "distance_m": round(estimate_distance(current_poi, best)),
            "time_min": round(travel),
        },
    }
    return departure, step


def _phase1_initialize(
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str,
) -> list[dict[str, Any]]:
    """按情绪曲线阶段选POI（先苦后甜编排）。

    按_EMOTION_PHASES定义的7个阶段依次选POI，
    每个阶段从候选池中选最匹配该阶段情绪目标的POI。
    """
    route: list[dict[str, Any]] = []
    remaining = list(candidates)
    current_time = parse_time(start_time)
    current_poi: dict[str, Any] | None = None
    step_count = 0
    running_budget = 0

    # 准备上下文
    _preferred_ids, _scene_requirements, _scene_matched_ids, max_pois, budget_limit, phases = (
        _phase1_prepare_context(candidates, user_intent)
    )

    # 用户结束时间
    end_time_str = user_intent.get("time", {}).get("end")
    end_time = parse_time(end_time_str) if end_time_str else None

    phase_idx = 0

    # 两阶段锁定
    _is_food_req = bool(set(_scene_requirements) & {"宵夜", "街边小店", "本地小吃", "烧烤", "美食"})
    logger.debug(
        "Phase1 _scene_matched_ids: %d, remaining: %d, is_food_req: %s",
        len(_scene_matched_ids),
        len(remaining),
        _is_food_req,
    )
    if _scene_matched_ids and len(_scene_matched_ids) >= _MIN_SCENE_MATCH_FOR_LOCK:
        scene_remaining = [p for p in remaining if p.get("id") in _scene_matched_ids]
        if len(scene_remaining) >= _MIN_SCENE_MATCH_FOR_LOCK:
            remaining = scene_remaining
            logger.debug("Phase1 两阶段锁定: 只从%d个scene_matched POI中选", len(remaining))

    # 深夜场景
    _is_late_night = user_intent.get("_is_late_night", False)

    while remaining and len(route) < max_pois and phase_idx < len(phases):
        phase = phases[phase_idx]
        best: dict[str, Any] | None = None
        best_score = float("inf")

        for poi in remaining:
            # 时间窗口和预算可行性检查
            tw_result = _phase1_check_time_window(
                poi,
                current_poi,
                current_time,
                end_time,
                budget_limit,
                running_budget,
                _is_late_night,
            )
            if tw_result is None:
                continue
            _, wait, _ = tw_result

            travel = estimate_travel_time(current_poi, poi)

            # 综合评分
            score = _phase1_score_candidate(
                poi,
                travel,
                wait,
                route,
                current_poi,
                step_count,
                max_pois,
                phase,
                user_intent,
                _preferred_ids,
                _scene_matched_ids,
                _scene_requirements,
                budget_limit,
            )

            if score < best_score:
                best_score = score
                best = poi

        if best is None:
            phase_idx += 1
            continue

        # 计算最终时间并添加到路线
        current_time, step_dict = _phase1_finalize_step(
            best, current_poi, current_time, _is_late_night
        )
        route.append(step_dict)

        current_poi = best
        running_budget += best.get("avg_price", 0)
        step_count += estimate_steps(best)
        remaining.remove(best)

        # 类别多样性推进
        prev_cat = route[-2]["poi"].get("category", "") if len(route) >= 2 else ""
        curr_cat = best.get("category", "")
        can_add_more = (
            len(route) < max_pois and phase_idx < len(phases) - 1 and curr_cat != prev_cat
        )
        if can_add_more:
            other_cats = [p for p in remaining if p.get("category", "") != curr_cat]
            if other_cats:
                phase_idx += 1
            else:
                phase_idx += 1
        else:
            phase_idx += 1

    return route


# ---------------------------------------------------------------------------
# Phase 1.5: 强制category多样性
# ---------------------------------------------------------------------------


def _enforce_category_diversity(
    route: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str = "09:00",
) -> list[dict[str, Any]]:
    """强制路线中至少有2种不同category。

    策略：
    1. 如果路线中连续2个同category，用候选池中不同category的高评分POI替换
    2. 如果路线中没有餐饮类POI，在替换时优先选择餐饮类
    """
    if len(route) < 3:
        return route

    used_ids = {s["poi"]["id"] for s in route}
    _get_preferred_categories(user_intent)

    # 检查路线中是否包含餐饮类
    has_food = any(s["poi"].get("category") == "餐饮" for s in route)

    # 检查连续同类
    i = 0
    while i <= len(route) - 2:
        cat_i = route[i]["poi"].get("category", "")
        cat_next = route[i + 1]["poi"].get("category", "")

        if cat_i == cat_next and cat_i != "休息":
            # 找一个不同category的候选POI
            replacement = None

            # 如果没有餐饮类，优先选择餐饮类POI
            if not has_food:
                for c in candidates:
                    if c["id"] not in used_ids and c.get("category") == "餐饮":
                        replacement = c
                        has_food = True
                        break

            # 如果没有找到餐饮类或已有餐饮类，选择其他category
            if replacement is None:
                for c in candidates:
                    if (
                        c["id"] not in used_ids
                        and c.get("category") != cat_i
                        and c.get("category") not in {"酒店", "休息"}
                    ):
                        replacement = c
                        break

            if replacement:
                # 检查替换POI的营业时间
                _, close_t = get_poi_opening_hours(replacement)
                travel = estimate_travel_time(route[i]["poi"], replacement)
                arrival = parse_time(route[i]["departure_time"]) + timedelta(minutes=travel)
                open_t, _ = get_poi_opening_hours(replacement)
                arrival_dt = parse_time(format_time(arrival))
                if arrival_dt < open_t:
                    arrival_dt = open_t
                if arrival_dt > close_t:
                    continue  # 替换POI已关门，尝试下一个

                # 替换route[i+1]
                used_ids.discard(route[i + 1]["poi"]["id"])
                if arrival_dt < open_t:
                    arrival = parse_time(format_time(open_t))
                stay = replacement.get("avg_stay_min", 60)
                departure = arrival + timedelta(minutes=stay)

                route[i + 1] = {
                    "poi": replacement,
                    "arrival_time": format_time(arrival),
                    "departure_time": format_time(departure),
                    "travel_from_prev": {
                        "distance_m": round(estimate_distance(route[i]["poi"], replacement)),
                        "time_min": round(travel),
                    },
                }
                used_ids.add(replacement["id"])
        i += 1

    # 重新计算时间
    _is_ln = user_intent.get("_is_late_night", False)
    route = _recalculate_times(route, start_time, is_late_night=_is_ln)
    return route


# ---------------------------------------------------------------------------
# Phase 2: 2-opt 局部搜索改进
# ---------------------------------------------------------------------------


def _phase2_improve(
    route: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str = "09:00",
    max_iterations: int = 50,
) -> list[dict[str, Any]]:
    """2-opt 局部搜索改进。"""
    improved = True
    iteration = 0
    _is_ln = user_intent.get("_is_late_night", False)

    while improved and iteration < max_iterations:
        improved = False
        iteration += 1

        for i in range(len(route) - 1):
            for j in range(i + 2, len(route)):
                new_route = route[: i + 1] + route[i + 1 : j + 1][::-1] + route[j + 1 :]
                new_route = _recalculate_times(new_route, start_time, is_late_night=_is_ln)

                if _check_time_windows(new_route):
                    old_score = _evaluate_route(route, user_intent)
                    new_score = _evaluate_route(new_route, user_intent)
                    if new_score > old_score:
                        route = new_route
                        improved = True
                        break
            if improved:
                break

    return route


# ---------------------------------------------------------------------------
# Phase 3: 呼吸空间插入
# ---------------------------------------------------------------------------


def _find_rest_poi(
    candidates: list[dict[str, Any]], used_ids: set[str], ref_poi: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """从候选池中找一个休息型 POI（高宁静度）。"""

    def _is_rest(p: dict[str, Any]) -> bool:
        return (
            p.get("category") in _REST_CATEGORIES
            or any(t in _REST_CANDIDATE_TAGS for t in p.get("tags", []))
        ) and p.get("emotion_tags", {}).get("tranquility", 0) > _TRANQUILITY_THRESHOLD

    unused = [p for p in candidates if _is_rest(p) and p["id"] not in used_ids]
    if unused:
        return max(unused, key=lambda p: p.get("emotion_tags", {}).get("tranquility", 0))

    # 兜底：生成合成休息节点（继承参考POI的坐标，避免距离计算错误）
    ref_lat = ref_poi.get("lat", 22.26) if ref_poi else 22.26
    ref_lng = ref_poi.get("lng", 113.58) if ref_poi else 113.58
    return {
        "id": f"_synth_rest_{len(used_ids)}",
        "name": "休息片刻",
        "category": "休息",
        "rating": 0,
        "avg_price": 0,
        "lat": ref_lat,
        "lng": ref_lng,
        "business_hours": "00:00-23:59",
        "tags": ["休息"],
        "queue_prone": False,
        "avg_stay_min": _REST_MINUTES,
        "emotion_tags": {
            "excitement": 0.0,
            "tranquility": 0.9,
            "sociability": 0.0,
            "culture_depth": 0.0,
            "surprise": 0.0,
            "physical_demand": 0.0,
        },
        "constraints": {
            "accessible": True,
            "pet_friendly": True,
            "queue_time_min": 0,
            "opening_hours": "00:00-23:59",
            "has_restroom": True,
        },
    }


def _insert_rest_at(
    route: list[dict[str, Any]],
    insert_pos: int,
    rest_poi: dict[str, Any],
) -> None:
    """在指定位置插入休息节点，更新时间。"""
    prev = route[insert_pos - 1]
    prev_departure = parse_time(prev["departure_time"])
    travel = estimate_travel_time(prev["poi"], rest_poi)
    arrival = prev_departure + timedelta(minutes=travel)
    departure = arrival + timedelta(minutes=_REST_MINUTES)

    new_step: dict[str, Any] = {
        "poi": rest_poi,
        "arrival_time": format_time(arrival),
        "departure_time": format_time(departure),
        "travel_from_prev": {
            "distance_m": round(estimate_distance(prev["poi"], rest_poi)),
            "time_min": round(travel),
        },
    }
    route.insert(insert_pos, new_step)


def _phase3_breathing(
    route: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str = "09:00",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """在连续高兴奋 POI 之间插入休息节点。"""
    breathing_spots: list[dict[str, Any]] = []
    used_ids = {s["poi"]["id"] for s in route}
    _is_ln = user_intent.get("_is_late_night", False)

    # 检测连续 3 个高兴奋 POI
    i = 0
    while i <= len(route) - 3:
        consecutive = all(
            route[i + j]["poi"].get("emotion_tags", {}).get("excitement", 0) > _EXCITEMENT_THRESHOLD
            for j in range(3)
        )

        if consecutive:
            rest = _find_rest_poi(candidates, used_ids, route[i]["poi"])
            if rest:
                insert_pos = i + 1
                _insert_rest_at(route, insert_pos, rest)
                breathing_spots.append(rest)
                used_ids.add(rest["id"])
                # 插入后立即重新计算后续时间
                route = _recalculate_times(route, start_time, is_late_night=_is_ln)
                i += 4
                continue
        i += 1

    # 闲逛型节奏：每 2 个原始 POI 插入一个休息
    if user_intent.get("pace") == "闲逛型" and len(route) >= 3:
        rest_ids = {s["poi"]["id"] for s in breathing_spots}
        original_indices = [i for i, s in enumerate(route) if s["poi"]["id"] not in rest_ids]

        insert_after = [
            original_indices[i]
            for i in range(2, len(original_indices), 2)
            if i < len(original_indices)
        ]

        for idx in reversed(insert_after):
            if idx >= len(route):
                continue
            ref_poi = route[idx]["poi"] if idx < len(route) else None
            rest = _find_rest_poi(candidates, used_ids, ref_poi)
            if rest:
                insert_pos = idx + 1
                _insert_rest_at(route, insert_pos, rest)
                breathing_spots.append(rest)
                used_ids.add(rest["id"])
                # 插入后立即重新计算后续时间
                route = _recalculate_times(route, start_time, is_late_night=_is_ln)

    return route, breathing_spots


# ---------------------------------------------------------------------------
# Phase 4: 高潮收尾检查
# ---------------------------------------------------------------------------


def _phase4_finale(
    route: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    end_point: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """确保最后一个 POI 有足够的情绪高潮。"""
    if len(route) < 2:
        return route

    last_exc = route[-1]["poi"].get("emotion_tags", {}).get("excitement", 0)
    second_last_exc = route[-2]["poi"].get("emotion_tags", {}).get("excitement", 0)

    used_ids = {s["poi"]["id"] for s in route}

    if last_exc < second_last_exc * 0.8:
        better = [
            p
            for p in candidates
            if p.get("emotion_tags", {}).get("excitement", 0) > second_last_exc * 0.8
            and p.get("id") not in used_ids
        ]
        if better:
            # 按时间窗过滤：只保留到达时仍在营业的POI
            prev_departure = parse_time(route[-2]["departure_time"])
            time_ok = []
            for p in better:
                travel = estimate_travel_time(route[-2]["poi"], p)
                arrival = prev_departure + timedelta(minutes=travel)
                open_t, close_t = get_poi_opening_hours(p)
                arrival_dt = parse_time(format_time(arrival))
                if arrival_dt < open_t:
                    arrival_dt = open_t
                if arrival_dt <= close_t:
                    time_ok.append(p)

            if not time_ok:
                return route  # 无可用替换，保持原路线

            best = max(
                time_ok,
                key=lambda p: p.get("emotion_tags", {}).get("excitement", 0),
            )

            travel = estimate_travel_time(route[-2]["poi"], best)
            arrival = prev_departure + timedelta(minutes=travel)
            open_t, _ = get_poi_opening_hours(best)
            arrival_dt = parse_time(format_time(arrival))
            if arrival_dt < open_t:
                arrival = parse_time(format_time(open_t))
            departure = arrival + timedelta(minutes=best.get("avg_stay_min", 60))

            route[-1] = {
                "poi": best,
                "arrival_time": format_time(arrival),
                "departure_time": format_time(departure),
                "travel_from_prev": {
                    "distance_m": round(estimate_distance(route[-2]["poi"], best)),
                    "time_min": round(travel),
                },
            }

    return route


# ---------------------------------------------------------------------------
# Phase 4.5: 起终点插入
# ---------------------------------------------------------------------------


def _insert_start_point(
    route: list[dict[str, Any]], start_point: dict[str, Any], start_time: str
) -> list[dict[str, Any]]:
    """插入起点到路线首位。

    Args:
        route: 当前路线
        start_point: 起点位置，坐标 {lat, lng} 或地名字符串
        start_time: 出发时间

    Returns:
        插入起点后的路线
    """
    if not route:
        return route

    # 构建起点POI对象
    start_poi = _build_point_poi(start_point, "起点")

    # 计算从起点到第一个POI的行程
    first_poi = route[0]["poi"]
    travel = estimate_travel_time(start_poi, first_poi)

    # 计算出发时间
    start_dt = parse_time(start_time)
    arrival_first = start_dt + timedelta(minutes=travel)

    # 更新第一个POI的到达时间
    route[0] = {
        "poi": route[0]["poi"],
        "arrival_time": format_time(arrival_first),
        "departure_time": route[0]["departure_time"],
        "travel_from_prev": {
            "distance_m": round(estimate_distance(start_poi, first_poi)),
            "time_min": round(travel),
        },
    }

    # 在路线首位插入起点
    start_step = {
        "poi": start_poi,
        "arrival_time": start_time,
        "departure_time": start_time,
        "travel_from_prev": {
            "distance_m": 0,
            "time_min": 0,
        },
    }
    route.insert(0, start_step)

    return route


def _insert_end_point(
    route: list[dict[str, Any]], end_point: dict[str, Any]
) -> list[dict[str, Any]]:
    """插入终点到路线末位。

    Args:
        route: 当前路线
        end_point: 终点位置，坐标 {lat, lng} 或地名字符串

    Returns:
        插入终点后的路线
    """
    if not route:
        return route

    # 构建终点POI对象
    end_poi = _build_point_poi(end_point, "终点")

    # 计算从最后一个POI到终点的行程
    last_poi = route[-1]["poi"]
    travel = estimate_travel_time(last_poi, end_poi)

    # 计算到达终点的时间
    last_departure = parse_time(route[-1]["departure_time"])
    arrival_end = last_departure + timedelta(minutes=travel)

    # 在路线末位插入终点
    end_step = {
        "poi": end_poi,
        "arrival_time": format_time(arrival_end),
        "departure_time": format_time(arrival_end),
        "travel_from_prev": {
            "distance_m": round(estimate_distance(last_poi, end_poi)),
            "time_min": round(travel),
        },
    }
    route.append(end_step)

    return route


def _build_point_poi(point: dict[str, Any] | str, name: str = "位置") -> dict[str, Any]:
    """构建起终点POI对象。

    Args:
        point: 位置信息，坐标 {lat, lng} 或地名字符串
        name: 显示名称

    Returns:
        POI对象
    """
    if isinstance(point, str):
        # 地名格式，从 filters 中获取坐标
        from backend.services.filters import _extract_user_location

        lat, lng = _extract_user_location({"location": point})
        if lat is None or lng is None:
            lat, lng = 0, 0
    else:
        lat = point.get("lat", 0)
        lng = point.get("lng", 0)

    return {
        "id": f"point_{name}_{lat}_{lng}",
        "name": name,
        "city": "",
        "category": "位置",
        "rating": 0,
        "avg_price": 0,
        "lat": lat,
        "lng": lng,
        "business_hours": "00:00-23:59",
        "tags": [name],
        "queue_prone": False,
        "avg_stay_min": 0,
        "emotion_tags": {
            "excitement": 0,
            "tranquility": 0,
            "sociability": 0,
            "culture_depth": 0,
            "surprise": 0,
            "physical_demand": 0,
        },
        "_is_point": True,
    }


# ---------------------------------------------------------------------------
# Phase 5: 输出组装
# ---------------------------------------------------------------------------


def _phase5_assemble(
    route: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    breathing_spots: list[dict[str, Any]],
    user_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """组装最终输出，应用心理学规则调整评分。"""
    emotion_curve = calculate_emotion_curve(route)

    # ── 应用心理学规则 ─────────────────────────────────────
    # 1. 计算每个 POI 的基础评分
    base_scores = []
    for step in route:
        poi = step.get("poi", {})
        emo = poi.get("emotion_tags", {})
        # 综合情绪评分
        avg_emo = sum(emo.values()) / len(emo) if emo else 0.5
        # 评分 = 情绪评分 + 评分因子
        rating = poi.get("rating", 4.0) / 5.0
        base_scores.append(avg_emo * 0.6 + rating * 0.4)

    # 2. 应用峰终定律：最后一段 +20%，最高体验 +15%
    scores = PsychologyRules.apply_peak_end(route, base_scores)

    # 3. 应用享乐适应：连续高刺激折扣
    scores = PsychologyRules.apply_hedonic_adaptation(route, scores)

    # 4. 应用损失厌恶：价格波动惩罚
    scores = PsychologyRules.apply_loss_aversion(route, scores)

    # 5. 将调整后的评分写入每个步骤（用于后续排序/展示）
    for i, step in enumerate(route):
        step["psychology_score"] = round(scores[i], 3)
        # 标记峰终定律影响的 POI
        if i == len(route) - 1:
            step["psychology_note"] = "峰终定律：收尾加成"
        elif scores[i] > base_scores[i] * 1.1:
            step["psychology_note"] = "峰终定律：高峰加成"
        elif scores[i] < base_scores[i] * 0.8:
            step["psychology_note"] = "享乐适应：刺激折扣"

    # ── 统计数据 ─────────────────────────────────────
    total_stay = 0.0
    total_travel = 0.0
    total_budget = 0
    total_steps = 0

    for step in route:
        arr = parse_time(step["arrival_time"])
        dep = parse_time(step["departure_time"])
        delta = (dep - arr).total_seconds() / 60
        total_stay += max(delta, 0)
        total_travel += step["travel_from_prev"]["time_min"]
        total_budget += step["poi"].get("avg_price", 0)
        total_steps += estimate_steps(step["poi"])

    used_ids = {s["poi"]["id"] for s in route}
    unused = [p for p in candidates if p["id"] not in used_ids]

    # 应用选择过载：返回给用户的候选不超过 5 个
    unused_top5 = PsychologyRules.apply_choice_overload(unused)

    # 路线合理性审核
    start_loc = user_intent.get("start_location", "") if user_intent else ""
    audit_issues = audit_route(
        {"route": route, "start_location": start_loc},
        user_intent or {},
    )

    return {
        "route": route,
        "emotion_curve": emotion_curve,
        "total_cost": {
            "time_min": round(total_stay + total_travel),
            "budget_used": total_budget,
            "step_estimate": total_steps,
        },
        "unused_candidates": unused_top5,  # 应用选择过载
        "all_unused": unused,  # 保留完整列表供调试
        "breathing_spots": breathing_spots,
        "psychology_applied": True,  # 标记心理学规则已应用
        "audit_issues": audit_issues,  # 路线审核问题列表
        "start_location": user_intent.get("start_location", ""),  # 出发位置
    }


# ---------------------------------------------------------------------------
# 主求解函数
# ---------------------------------------------------------------------------


def solve_route(
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str = "09:00",
    perception_ctx: Any = None,
    dynamic_weights: dict[str, float] | None = None,
    progress_callback: Callable | None = None,
    start_point: dict[str, Any] | None = None,
    end_point: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """求解最优路线。

    Args:
        candidates: 候选 POI 列表
        user_intent: 用户意图字典
        start_time: 出发时间，格式 "HH:MM"
        perception_ctx: 感知上下文（PerceptionContext），用于影响疲劳惩罚权重
        dynamic_weights: 动态权重（来自 WeightMapper），覆盖默认常量
        progress_callback: 进度回调函数，签名为 callback(stage: str, data: dict)
        start_point: 起点位置，坐标 {lat, lng} 或地名字符串
        end_point: 终点位置，坐标 {lat, lng} 或地名字符串

    Returns:
        包含 route, emotion_curve, total_cost, unused_candidates, breathing_spots 的字典
    """
    # 从 user_intent 获取起终点（如果参数未提供）
    if start_point is None:
        start_point = user_intent.get("start_point")
    if end_point is None:
        end_point = user_intent.get("end_point")
    # 设置线程局部状态（替代全局变量，防止并发竞态）
    tl = _get_thread_state()
    tl.current_weights = dynamic_weights
    tl.progress_callback = progress_callback

    # 预计算深夜标志（跨午夜或start在22:00-06:00之间）
    _is_late_night = False
    if "late_night" in user_intent.get("hard_constraints", []):
        try:
            _sh, _sm = start_time.split(":")
            _start_m = int(_sh) * 60 + int(_sm)
            _end_str = user_intent.get("time", {}).get("end", "22:00")
            _eh, _em = _end_str.split(":")
            _end_m = int(_eh) * 60 + int(_em)
            _is_late_night = _end_m < _start_m or _start_m >= 22 * 60 or _start_m <= 6 * 60
        except (ValueError, AttributeError):
            pass
    user_intent["_is_late_night"] = _is_late_night

    # 感知上下文 → 动态调整疲劳惩罚权重
    if perception_ctx is not None:
        fatigue = getattr(perception_ctx, "fatigue_level", 0.0)
        if fatigue > 0.7:
            tl.gamma_multiplier = 3.0
        elif fatigue > 0.5:
            tl.gamma_multiplier = 2.0
        else:
            tl.gamma_multiplier = 1.0
    else:
        tl.gamma_multiplier = 1.0
    empty_result: dict[str, Any] = {
        "route": [],
        "emotion_curve": [],
        "total_cost": {"time_min": 0, "budget_used": 0, "step_estimate": 0},
        "unused_candidates": list(candidates),
        "breathing_spots": [],
    }

    if not candidates:
        return empty_result

    # Phase 0: 按意图筛选候选（确保category多样性）
    selected = _select_diverse_candidates(candidates, user_intent, max_candidates=30)

    # 约束过滤
    filtered = filter_candidates(selected, user_intent)

    # 场景标签：给所有候选 POI 打场景标签
    for poi in filtered:
        tag_poi(poi)

    # 地理聚类：给 POI 分配区域 ID，确保路线不走回头路
    _assign_area_ids(filtered)

    # 集成非标体验（城市特色活动，按时间窗口匹配）
    city = user_intent.get("city", "珠海")
    try:
        start_h = int(start_time.split(":")[0])
    except Exception:
        start_h = 9
    nse_list = _get_nse_for_city(city, start_h)
    if nse_list:
        added = 0
        for nse in nse_list:
            if len(filtered) >= 30 + len(nse_list):
                break
            # 转成类似POI的格式供求解器处理
            nse_poi = {
                "id": nse.get("id", f"nse_{len(filtered)}"),
                "name": nse.get("name", ""),
                "city": city,
                "category": nse.get("category", "其他"),
                "rating": 4.5,
                "avg_price": nse.get("price", 0),
                "lat": 0,
                "lng": 0,  # 无坐标，跟随上一个POI
                "business_hours": nse.get("best_time", "00:00-23:59"),
                "tags": nse.get("tags", []),
                "queue_prone": False,
                "avg_stay_min": nse.get("duration_min", 60),
                "emotion_tags": nse.get(
                    "emotion_tags",
                    {
                        "excitement": 0.5,
                        "tranquility": 0.5,
                        "sociability": 0.5,
                        "culture_depth": 0.5,
                        "surprise": 0.5,
                        "physical_demand": 0.3,
                    },
                ),
                "_is_nse": True,
            }
            if not any(p.get("id") == nse_poi["id"] for p in filtered):
                filtered.append(nse_poi)
                added += 1
        if added:
            _report_progress("nse_injected", {"phase": "非标体验", "count": added})

    # late_night场景：如果过滤后没有候选，不要fallback放宽约束（会导致白天POI被选中）
    if not filtered:
        if "late_night" in user_intent.get("hard_constraints", []):
            # 深夜场景无候选，返回空路线并提示用户
            empty_result["_impossible_hints"] = ["凌晨时段营业的POI较少，建议尝试白天时段"]
            _report_progress("filtered", {"phase": "筛选", "remaining": 0})
            return empty_result
        # 其他场景：放宽约束再试
        filtered = filter_candidates(candidates[:100], user_intent)
        if not filtered:
            return empty_result

    # ── 不可解场景检测 ──
    _impossible_hints = []
    budget_pp = user_intent.get("budget", {}).get("per_person", 500)
    affordable = [p for p in filtered if p.get("avg_price", 0) <= budget_pp]
    if not affordable and budget_pp < 100:
        _impossible_hints.append(f"预算{budget_pp}元/人偏低，当前候选中没有此价位的POI")
    if _impossible_hints:
        empty_result["_impossible_hints"] = _impossible_hints

    _report_progress("filtered", {"phase": "筛选", "remaining": len(filtered)})

    # Phase 1: 贪心初始化
    route = _phase1_initialize(filtered, user_intent, start_time)
    _report_progress("initial_route", {"phase": "初排", "length": len(route)})

    # 最低路线长度保护：如果Phase 1选出的POI太少，从候选中补充
    if 0 < len(route) < 3:
        used_ids = {s["poi"].get("id") for s in route}
        for poi in filtered:
            if len(route) >= 3:
                break
            if poi.get("id") not in used_ids:
                # 简单添加到最后
                last = route[-1]["poi"]
                travel = estimate_travel_time(last, poi)
                last_departure = parse_time(route[-1]["departure_time"])
                arrival = last_departure + timedelta(minutes=travel)
                stay = poi.get("avg_stay_min", 60)
                departure = arrival + timedelta(minutes=stay)
                route.append(
                    {
                        "poi": poi,
                        "arrival_time": format_time(arrival),
                        "departure_time": format_time(departure),
                        "travel_from_prev": {
                            "distance_m": round(estimate_distance(last, poi)),
                            "time_min": round(travel),
                        },
                    }
                )
                used_ids.add(poi.get("id"))
        logger.debug("最低长度保护: 补充到%d站", len(route))

    if not route:
        return empty_result

    # Phase 1.5: 强制category多样性（替换连续同类POI）
    route = _enforce_category_diversity(route, filtered, user_intent, start_time)

    # Phase 2: 2-opt 局部改进
    route = _phase2_improve(route, user_intent, start_time)
    _report_progress("optimizing", {"phase": "优化", "iterations": 50, "length": len(route)})

    # Phase 3: 呼吸空间插入
    route, breathing_spots = _phase3_breathing(route, filtered, user_intent, start_time)
    for spot in breathing_spots:
        _report_progress(
            "breathing",
            {"phase": "休息", "spot": spot.get("name", "?"), "found": len(breathing_spots)},
        )

    # Phase 4: 高潮收尾检查（考虑终点距离）
    route = _phase4_finale(route, filtered, end_point)
    last_name = route[-1]["poi"]["name"] if route else "?"
    _report_progress("finale", {"phase": "收尾", "last_poi": last_name})

    # Phase 4.5: 起终点插入
    if start_point and route:
        # 插入起点到路线首位
        route = _insert_start_point(route, start_point, start_time)
        _report_progress("start_point", {"phase": "起点", "point": start_point})
    if end_point and route:
        # 插入终点到路线末位
        route = _insert_end_point(route, end_point)
        _report_progress("end_point", {"phase": "终点", "point": end_point})

    # Phase 5: 输出组装
    return _phase5_assemble(route, filtered, breathing_spots, user_intent)
