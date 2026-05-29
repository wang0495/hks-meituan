"""CityFlow 路线文案引擎。

将求解器输出的路线数据转换为用户友好的文案描述。
模板驱动 + LLM 局部润色。

参考文档1表格10的格式：
时间 | 体验 | 情绪设计 | 消费 | 杠杆 | 设计意图
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from backend.services.economy import enrich_poi_economics
from backend.services.emotion import get_dominant_emotion

# 内容引擎（可选引入，无则降级）
try:
    from backend.services.city_personality import (
        get_city_based_opening,
        get_vibe_style_adjectives,
    )
except ImportError:
    get_city_based_opening = None  # type: ignore
    get_vibe_style_adjectives = None  # type: ignore

# ---------------------------------------------------------------------------
# 情绪设计模板（参考文档1表格10）
# ---------------------------------------------------------------------------

EMOTION_DESIGN_TEMPLATES: dict[str, str] = {
    "excitement": "兴奋",
    "tranquility": "宁静",
    "culture_depth": "文化",
    "surprise": "惊喜",
    "physical_demand": "体力",
    "sociability": "社交",
}

# 设计意图模板（按情绪阶段）
DESIGN_INTENT_TEMPLATES: dict[str, list[str]] = {
    "opening": [
        "情绪铺垫：融入本地生活",
        "开场预热：放松心情，进入状态",
        "温和开场：不急不躁，慢慢进入",
    ],
    "rising": [
        "情绪上升：逐步提升期待感",
        "渐入佳境：从轻松过渡到探索",
        "好奇心驱动：发现城市的另一面",
    ],
    "climax": [
        "情绪高点：体验密度最高的时刻",
        "兴奋高潮：今天的重头戏",
        "感官盛宴：让所有感官都活跃起来",
    ],
    "breathing": [
        "呼吸空间：消化前一段体验",
        "沉淀时刻：让身体和心灵都喘口气",
        "留白设计：不填满，给体验留空间",
    ],
    "culture": [
        "文化输入：为收尾做铺垫",
        "深度体验：投入认知资源",
        "精神滋养：让旅程有厚度",
    ],
    "closing": [
        "高潮收尾：值得回忆的告别",
        "温暖收束：带着满足感结束",
        "仪式感：给今天画上完美句号",
    ],
}

# 体验杠杆率判断
def _get_leverage(avg_price: float, rating: float, category: str) -> str:
    """判断POI的体验杠杆率。"""
    if avg_price == 0:
        return "高"  # 免费体验
    if avg_price <= 30 and rating >= 4.0:
        return "高"  # 花小钱获大体验
    if avg_price <= 100 and rating >= 4.0:
        return "中"  # 花钱与体验成正比
    if avg_price > 200 and rating < 4.0:
        return "低"  # 花大钱体验增量小
    return "中"


# ---------------------------------------------------------------------------
# 模板库
# ---------------------------------------------------------------------------

OPENING_TEMPLATES: dict[str, list[str]] = {
    "独居": [
        "周末给自己一个安静的角落，让心灵慢下来。",
        "一个人也能过得很丰富，这趟行程是为你量身定制的。",
        "独处时光，是最好的自我充电。",
    ],
    "情侣": [
        "这趟行程是为你们设计的，每个转角都有氛围感。",
        "两个人的周末，不需要太多计划，跟着感觉走就好。",
        "浪漫不需要远行，城市的角落藏着惊喜。",
    ],
    "亲子": [
        "孩子们会喜欢的，大人也能松口气。",
        "带娃出行，轻松最重要。这条路线兼顾了趣味和休息。",
        "让孩子们放电，让大人放松，一举两得。",
    ],
    "朋友": [
        "周末就该和朋友们一起，不用赶路，开心就好。",
        "朋友聚会，重在氛围。这条路线保证你们玩得尽兴。",
        "人多热闹，但也不用太累，节奏刚刚好。",
    ],
    "退休": [
        "慢节奏的行程，适合慢慢享受。",
        "退休生活，就该这样悠闲自在。",
        "不赶时间，不赶景点，享受当下。",
    ],
}

CATEGORY_STEP_TEMPLATES: dict[str, list[str]] = {
    "餐饮": [
        "在{poi_name}，犒劳一下自己的胃。",
        "走累了，{poi_name}是个歇脚吃饭的好地方。",
        "来{poi_name}，尝尝本地的味道。",
    ],
    "文化": [
        "在{poi_name}，感受这座城市的文化底蕴。",
        "走进{poi_name}，每一步都是历史。",
        "{poi_name}，值得慢慢逛、细细看。",
    ],
    "运动": [
        "在{poi_name}，动起来，出出汗。",
        "{poi_name}，让身体跟着心情一起舒展。",
        "来{poi_name}，释放一下积累的能量。",
    ],
    "景点": [
        "在{poi_name}，拍照打卡不能少。",
        "{poi_name}，每一帧都是风景。",
        "来{poi_name}，感受城市的另一面。",
    ],
    "购物": [
        "在{poi_name}，逛逛看看，说不定有惊喜。",
        "{poi_name}，适合随意走走停停。",
    ],
    "休息": [
        "休息一下，给身体和心灵都充个电。",
        "找个地方坐下来，回味刚才的体验。",
        "片刻休息，为下一站积蓄能量。",
    ],
}

CLOSING_TEMPLATES: dict[str, list[str]] = {
    "观景": [
        "用这一刻，给今天画上句号。",
        "站在这里，回望今天的旅程，一切都是最好的安排。",
    ],
    "美食": [
        "美食是最好的告别方式。",
        "用一顿美味，为今天画上圆满的句号。",
    ],
    "文化": [
        "文化的熏陶，是今天最好的收获。",
        "带着满满的收获，结束今天的旅程。",
    ],
    "default": [
        "今天的行程就到这里，希望你喜欢。",
        "行程结束，但美好的回忆会一直留着。",
    ],
}

_VIEW_CATEGORIES = {"观景", "自然"}


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _get_step_phase(index: int, total: int) -> str:
    """根据步骤在路线中的位置判断情绪阶段。"""
    ratio = index / max(total - 1, 1)
    if ratio < 0.15:
        return "opening"
    elif ratio < 0.35:
        return "rising"
    elif ratio < 0.55:
        return "climax"
    elif ratio < 0.75:
        return "breathing"
    elif ratio < 0.9:
        return "culture"
    else:
        return "closing"


def _get_emotion_design(poi: dict[str, Any]) -> str:
    """生成情绪设计说明。"""
    et = poi.get("emotion_tags", {})
    dominant = get_dominant_emotion(et)
    label = EMOTION_DESIGN_TEMPLATES.get(dominant, "体验")

    # 找第二高的情绪维度
    sorted_emotions = sorted(et.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_emotions) >= 2:
        second_key = sorted_emotions[1][0]
        second_label = EMOTION_DESIGN_TEMPLATES.get(second_key, "")
        if second_label and sorted_emotions[1][1] > 0.4:
            return f"{label} + {second_label}"
    return label


def _generate_opening(user_intent: dict[str, Any], city: str = "") -> str:
    """生成个性化开场语。"""
    # 城市性格开场优先（内容引擎 D4）
    if city and get_city_based_opening:
        city_opening = get_city_based_opening(city)
        return city_opening

    group_type = user_intent.get("group", {}).get("type", "独居")
    templates = OPENING_TEMPLATES.get(group_type, OPENING_TEMPLATES["独居"])
    return random.choice(templates)


def _generate_step(step: dict[str, Any], index: int, total: int, city: str = "") -> dict[str, Any]:
    """生成单步路线描述，包含情绪设计和设计意图。

    Args:
        step: 路线步骤
        index: 步骤索引
        total: 总步数
        city: 城市名（用于内容引擎风格调整）

    Returns:
        包含 description, emotion_design, design_intent, leverage 的字典。
    """
    poi = step["poi"]
    poi_name = poi["name"]
    category = poi.get("category", "")
    emotion_tags = poi.get("emotion_tags", {})
    avg_price = poi.get("avg_price", 0)
    rating = poi.get("rating", 0)

    # 描述文案
    if category in CATEGORY_STEP_TEMPLATES:
        templates = CATEGORY_STEP_TEMPLATES[category]
    else:
        dominant = get_dominant_emotion(emotion_tags)
        templates = [
            f"在{{poi_name}}，感受不一样的体验。",
            f"{{poi_name}}，值得停留的地方。",
        ]
    template = random.choice(templates)
    description = template.format(poi_name=poi_name)

    # 城市性格风格词注入（内容引擎 D4）
    if city and get_vibe_style_adjectives:
        from backend.services.city_personality import get_city_personality

        personality = get_city_personality(city)
        if personality:
            vibe = personality.get("vibe", "")
            adj = get_vibe_style_adjectives(vibe)
            if adj and random.random() < 0.5:
                inject = random.choice(adj)
                description = description.replace("。", f"，{inject}。")

    arrival = step.get("arrival_time", "")
    if arrival:
        description = f"{arrival} {description}"

    # 情绪设计
    emotion_design = _get_emotion_design(poi)

    # 设计意图
    phase = _get_step_phase(index, total)
    intent_templates = DESIGN_INTENT_TEMPLATES.get(phase, DESIGN_INTENT_TEMPLATES["opening"])
    design_intent = random.choice(intent_templates)

    # 体验杠杆率
    leverage = _get_leverage(avg_price, rating, category)

    # 经济引擎数据
    enriched = enrich_poi_economics(poi)
    experience_leverage = enriched.get("experience_leverage", "medium")
    spend_emotion = enriched.get("spend_emotion", "fair")

    return {
        "description": description,
        "emotion_design": emotion_design,
        "design_intent": design_intent,
        "leverage": leverage,
        "experience_leverage": experience_leverage,
        "spend_emotion": spend_emotion,
        "cost": avg_price,
    }


def _generate_closing(route_result: dict[str, Any]) -> str:
    """生成收尾语。"""
    route = route_result.get("route", [])
    if not route:
        return random.choice(CLOSING_TEMPLATES["default"])

    last_poi = route[-1]["poi"]
    category = last_poi.get("category", "")

    if category in _VIEW_CATEGORIES:
        templates = CLOSING_TEMPLATES["观景"]
    elif category in ("餐饮", "美食"):
        templates = CLOSING_TEMPLATES["美食"]
    elif category == "文化":
        templates = CLOSING_TEMPLATES["文化"]
    else:
        templates = CLOSING_TEMPLATES["default"]

    return random.choice(templates)


def _extract_emotion_highlights(route_result: dict[str, Any]) -> list[dict[str, str]]:
    """提取路线中的情绪亮点。"""
    highlights: list[dict[str, str]] = []

    for step in route_result.get("route", []):
        emotion = step["poi"].get("emotion_tags", {})
        poi_name = step["poi"]["name"]

        if emotion.get("excitement", 0) > 0.8:
            highlights.append({
                "type": "excitement",
                "poi": poi_name,
                "description": "心跳加速的时刻",
            })
        if emotion.get("tranquility", 0) > 0.8:
            highlights.append({
                "type": "tranquility",
                "poi": poi_name,
                "description": "宁静致远的角落",
            })
        if emotion.get("culture_depth", 0) > 0.8:
            highlights.append({
                "type": "culture",
                "poi": poi_name,
                "description": "文化底蕴深厚",
            })

    return highlights


async def _llm_generate_description(step: dict, user_intent: dict, city: str = "") -> str:
    """调用 LLM 为路线步骤生成生动的描述文案。

    超时或异常时退回模板文案。
    """
    from backend.services.llm_service import chat

    poi = step["poi"]
    poi_name = poi.get("name", "")
    category = poi.get("category", "")
    rating = poi.get("rating", 0)
    tags = poi.get("tags", [])
    et = poi.get("emotion_tags", {})
    dominant_emotions = sorted(et.items(), key=lambda x: -x[1])[:2]
    emotion_str = "、".join(f"{k}({v})" for k, v in dominant_emotions if v > 0.3)

    group_type = user_intent.get("group", {}).get("type", "独居")
    pace = user_intent.get("pace", "平衡型")

    prompt = (
        f'你是CityFlow的旅行文案写手。为以下路线站点写1-2句中文描述，'
        f'要生动、有画面感，不要评价"不错/很好"：\n'
        f'地点：{poi_name}\n'
        f'类别：{category}\n'
        f'评分：{rating}\n'
        f'标签：{", ".join(tags[:4])}\n'
        f'情绪氛围：{emotion_str}\n'
        f'用户类型：{group_type}，节奏：{pace}\n'
        f'城市：{city or "珠海"}\n'
        f'要求：写一段让人身临其境的短描述，包含具体感官体验。'
    )

    try:
        result = await asyncio.wait_for(chat(prompt), timeout=15.0)
        if result and len(result) > 10:
            arrival = step.get("arrival_time", "")
            return f"{arrival} {result.strip()}" if arrival else result.strip()
    except (asyncio.TimeoutError, Exception):
        pass

    # 退回模板
    return _template_step_description(step, user_intent, city)


def _template_step_description(step: dict, user_intent: dict, city: str = "") -> str:
    """模板生成步骤描述（LLM不可用时的降级方案）。"""
    poi = step["poi"]
    poi_name = poi["name"]
    category = poi.get("category", "")

    templates = CATEGORY_STEP_TEMPLATES.get(category, [
        f"在{{poi_name}}，感受不一样的体验。",
        f"{{poi_name}}，值得停留的地方。",
    ])
    import random
    template = random.choice(templates)
    description = template.format(poi_name=poi_name)

    if city:
        try:
            from backend.services.city_personality import get_vibe_style_adjectives, get_city_personality
            personality = get_city_personality(city)
            if personality:
                vibe = personality.get("vibe", "")
                adj = get_vibe_style_adjectives(vibe)
                if adj and random.random() < 0.5:
                    inject = random.choice(adj)
                    description = description.replace("。", f"，{inject}。")
        except ImportError:
            pass

    arrival = step.get("arrival_time", "")
    if arrival:
        description = f"{arrival} {description}"
    return description


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------


async def generate_narrative(
    route_result: dict[str, Any],
    user_intent: dict[str, Any],
    *,
    enable_llm_polish: bool = True,
    city: str = "",
) -> dict[str, Any]:
    """生成路线文案。

    Args:
        route_result: solver.solve_route() 的返回值，包含 route 列表。
        user_intent: 用户意图字典，包含 group、preferences 等。
        enable_llm_polish: 是否启用 LLM 生成描述（默认开启）。
        city: 城市名（用于内容引擎城市性格文案风格）。

    Returns:
        包含 opening, steps, closing, emotion_highlights, budget_breakdown 的文案字典。
        每个step包含: description, emotion_design, design_intent, leverage, cost
    """
    route = route_result.get("route", [])

    opening = _generate_opening(user_intent, city=city)

    # 生成每步描述（包含情绪设计和设计意图）
    steps: list[dict[str, Any]] = []
    total_cost = 0
    for i, step in enumerate(route):
        step_data = _generate_step(step, i, len(route), city=city)
        steps.append(step_data)
        total_cost += step_data["cost"]

    # LLM润色：并行调用所有step的description
    if enable_llm_polish and steps:
        import asyncio
        llm_tasks = [
            _llm_generate_description(route[i], user_intent, city)
            for i in range(min(len(steps), len(route)))
        ]
        llm_results = await asyncio.gather(*llm_tasks, return_exceptions=True)
        for i, result in enumerate(llm_results):
            if isinstance(result, str):
                steps[i]["description"] = result

    closing = _generate_closing(route_result)
    highlights = _extract_emotion_highlights(route_result)

    # 预算汇总
    budget_per_person = user_intent.get("budget", {}).get("per_person", 500)
    budget_breakdown = {
        "total": total_cost,
        "budget_limit": budget_per_person,
        "remaining": max(0, budget_per_person - total_cost),
        "leverage_summary": {
            "高": sum(1 for s in steps if s["leverage"] == "高"),
            "中": sum(1 for s in steps if s["leverage"] == "中"),
            "低": sum(1 for s in steps if s["leverage"] == "低"),
        },
    }

    return {
        "opening": opening,
        "steps": steps,
        "closing": closing,
        "emotion_highlights": highlights,
        "budget_breakdown": budget_breakdown,
    }
