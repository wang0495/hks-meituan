"""
CityFlow LLM 意图解析模块
将用户自然语言输入解析为结构化出行需求。
基于4个设计文档的要求实现。
"""

import asyncio
import json
import logging
import re

from openai import AsyncOpenAI

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# NOTE: 已移除内置画像 (PROFILES / _match_profile)。
# LLM 的 demand_vector 7 维向量已替代画像匹配，solver 直接消费 demand_vector。


# LLM Prompt 模板
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """你是 CityFlow 城市出行路线规划系统的意图解析器。
用户会用自然语言描述出行需求，你需要解析为严格的 JSON 格式。

输出格式（只输出 JSON，不要任何其他文字）：
{
  "city": "珠海/广州/湛江",
  "time": {"period": "上午/下午/全天", "start": "HH:MM", "end": "HH:MM"},
  "num_days": 1,
  "budget": {"per_person": 金额整数, "type": "硬约束/弹性"},
  "group": {"size": 人数整数, "type": "独居/情侣/亲子/朋友/退休"},
  "preferences": {"culture": 0到1的小数, "food": 0到1的小数, "nature": 0到1的小数, "social": 0到1的小数},
  "pace": "特种兵型/平衡型/闲逛型",
  "hard_constraints": ["约束1", "约束2"],
  "scene_requirements": ["场景元素1", "场景元素2"],
  "preferred_categories": ["类别1", "类别2", "类别3"],
  "demand_vector": {
    "efficiency_seeking": 0~1,
    "excitement_seeking": 0~1,
    "tranquility_seeking": 0~1,
    "budget_sensitivity": 0~1,
    "novelty_seeking": 0~1,
    "social_desire": 0~1,
    "physical_energy": 0~1
  },
  "location": "用户在哪个区域/地标附近，如'拱北''香洲''天河'，不知道则填null"
}

规则：
- city: 根据用户提到的城市判断，无明确城市则默认"珠海"
- budget: 无明确预算则 per_person=500, type="弹性"
- group.type: 根据同行人判断，默认"独居"
- time: 如果用户提到"3小时""半天""2小时搞定"等时长，根据start计算end。如start="14:00"且"3小时"→end="17:00"
- time: 如果用户提到"凌晨""深夜"，start和end应为对应时段（如00:00-06:00）
- num_days: 出行天数。如"两天一夜"/"2天1夜"/"三日游"→对应数字，"一日游"或无明确天数→1。上限5天
- preferences: 根据关键词推断偏好强度（0=完全不感兴趣, 1=非常感兴趣）
  - culture: 文化/历史/艺术/博物馆/展览
  - food: 美食/餐厅/小吃/探店
  - nature: 自然/公园/山/湖/植物
  - social: 社交/聚会/热闹/人多
- pace: "特种兵型"=赶场打卡, "平衡型"=适中, "闲逛型"=慢节奏
- hard_constraints: 提取明确的限制条件，支持以下类型：
  - "不想排队" → "queue_intolerant"
  - "无障碍/轮椅/婴儿车" → "accessible"
  - "带宠物/狗/猫" → "pet_friendly"
  - "室内/空调/下雨天/别中暑" → "indoor_only"
  - "海边/户外/露天" → "outdoor_preferred"
  - "凌晨/深夜/宵夜/通宵" → "late_night"
  - "游乐园/海洋馆/动物园" → "needs_entertainment"
  - "烧烤/火锅/茶馆/咖啡馆/书店" → add specific activity to hard_constraints
- scene_requirements: 【必须填写】从用户输入中提取所有场景关键词和具体需求。
  不要因为某个需求已体现在preferred_categories或preferences中就省略。
  必须把用户提到的每个具体需求都提取出来。
  例如：
  - "珠海美食一日游，想吃海鲜和本地特色" → ["美食", "海鲜", "本地特色", "小吃"]
  - "一天打卡珠海所有著名景点，时间紧" → ["著名景点", "打卡", "地标"]
  - "喝茶听曲" → ["茶馆", "曲艺表演", "传统文化"]
  - "街边小吃" → ["街边小店", "本地小吃", "便宜实惠"]
  - "拍照出片" → ["拍照打卡", "网红景点", "出片"]
  - "游乐园海洋馆" → ["游乐园", "海洋馆", "儿童游乐"]
  - "蹦迪" → ["酒吧", "夜店", "LiveHouse"]
  - "烧烤聚会" → ["烧烤", "聚餐", "户外用餐"]
  - "带6岁孩子去长隆海洋王国" → ["海洋王国", "亲子", "儿童", "游乐园"]
  - "珠海两日游，节奏慢，喜欢公园和海边" → ["公园", "海边", "慢节奏", "休闲"]
  - 即使用户需求看起来很简单，也必须至少提取1-3个关键词，绝不允许填空数组[]
- preferred_categories: 根据用户意图选择3-6个最相关的POI类别，按优先级排序。可选类别：
  餐饮, 景点, 购物, 文化, 运动, 娱乐, 温泉SPA, 海景咖啡馆, 夜市, 夜市小吃,
  书店, 咖啡馆, 密室逃脱, 剧本杀, 恐怖密室, 室内攀岩, 户外攀岩, 水上运动场所,
  游戏, 益智, 科技, 科技体验, 网吧/电竞馆, 自然风光, 文艺, 休闲, 便利店
  示例：
  - "朋友聚会要能玩又能吃" → ["餐饮", "娱乐", "购物"]
  - "下午想蹦迪" → ["娱乐", "餐饮"]
  - "凌晨吃宵夜" → ["餐饮", "夜市", "夜市小吃"]
  - "带孩子玩游乐园" → ["景点", "运动", "娱乐"]
  - "安静画画" → ["文化", "文艺", "咖啡馆"]
  - "拍日出日落夜景" → ["景点", "自然风光"]
  - "情侣约会" → ["餐饮", "文化", "景点", "海景咖啡馆"]
  - "老两口公园喝茶" → ["文化", "景点", "餐饮"]
- 社恐/不想人多 → social 设低值(0.1-0.2)
- demand_vector: 语义需求向量（0~1），与preferences互补但更侧重行为倾向
  - efficiency_seeking: 是否在意效率/赶时间
  - excitement_seeking: 是否想要兴奋刺激
  - tranquility_seeking: 是否想要宁静放松
  - budget_sensitivity: 预算敏感度
  - novelty_seeking: 是否想尝试新东西
  - social_desire: 社交需求
  - physical_energy: 体力意愿
"""

# ---------------------------------------------------------------------------
# LLM 调用（带超时降级）
# ---------------------------------------------------------------------------

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        cfg = get_settings().intent_llm
        base_url = cfg.base_url
        api_key = cfg.api_key
        # 不再强制追加 /v1 — 适配讯飞 MaaS 等 base_url 已含路径的 API
        # 例: base_url="https://maas-coding-api.cn-huabei-1.xf-yun.com/v2"
        _client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return _client


def _get_llm_model() -> str:
    """获取 LLM 模型名，通过 pydantic 配置读取（INTENT_LLM_MODEL 优先，LLM_MODEL 兜底）。"""
    return get_settings().intent_llm.model


# Intent parser response cache (same user_input → same intent, 30min TTL)
_intent_cache: dict[str, tuple[dict, float]] = {}
_INTENT_CACHE_TTL = 1800  # 30 minutes
_INTENT_CACHE_MAX = 200  # max entries to prevent unbounded growth

# Generic tool schema for Qwen models — avoids response_format's NotEnoughCvError
_GENERIC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_result",
            "description": "Submit the structured analysis result",
            "parameters": {"type": "object"},
        },
    },
]
_GENERIC_TOOL_CHOICE = {"type": "function", "function": {"name": "submit_result"}}


def _get_cached_intent(cache_key: str) -> dict | None:
    """从缓存获取意图解析结果。"""
    import time as _time

    entry = _intent_cache.get(cache_key)
    if entry is not None:
        result, ts = entry
        if _time.monotonic() - ts < _INTENT_CACHE_TTL:
            logger.debug("intent cache hit")
            return {**result}
        del _intent_cache[cache_key]
    return None


def _cache_intent_result(cache_key: str, result: dict) -> None:
    """缓存意图解析结果。"""
    import time as _time

    if len(_intent_cache) >= _INTENT_CACHE_MAX:
        now_mono = _time.monotonic()
        expired = [k for k, (_, ts) in _intent_cache.items() if now_mono - ts > _INTENT_CACHE_TTL]
        for k in expired:
            del _intent_cache[k]
        if len(_intent_cache) >= _INTENT_CACHE_MAX:
            oldest_key = min(_intent_cache, key=lambda k: _intent_cache[k][1])
            del _intent_cache[oldest_key]
    _intent_cache[cache_key] = (result.copy(), _time.monotonic())


async def _call_llm(user_input: str) -> dict | None:
    """调用 LLM 解析意图，返回解析结果或 None（失败时）。带缓存+重试。"""
    import hashlib

    cache_key = hashlib.md5(user_input.encode()).hexdigest()
    cached = _get_cached_intent(cache_key)
    if cached is not None:
        return cached

    client = _get_client()
    cfg = get_settings().intent_llm
    is_ds = "deepseek" in _get_llm_model().lower() or "deepseek" in cfg.base_url
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    kwargs: dict = dict(
        model=_get_llm_model(),
        messages=messages,
        temperature=0.1,
        max_tokens=1500,
    )
    use_tools = False
    if is_ds:
        kwargs["response_format"] = {"type": "json_object"}
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    elif "qwen" in _get_llm_model().lower():
        use_tools = True
        kwargs["tools"] = _GENERIC_TOOLS
        kwargs["tool_choice"] = _GENERIC_TOOL_CHOICE

    for attempt in range(5):
        try:
            resp = await client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            raw = (
                msg.tool_calls[0].function.arguments
                if use_tools and msg.tool_calls
                else msg.content
            ) or ""
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if json_match:
                result = json.loads(json_match.group())
                result["_llm_raw_response"] = raw[:200]
                result["_llm_model"] = _get_llm_model()
                _cache_intent_result(cache_key, result)
                return result
        except Exception as e:
            if attempt < 4:
                await asyncio.sleep(2)
            else:
                logger.warning("LLM 调用失败(5次): %s", e)
    return None


# ---------------------------------------------------------------------------
# 情感信号检测
# ---------------------------------------------------------------------------


def detect_emotion_need(text: str) -> str | None:
    """检测用户输入中的情感信号，返回情感需求或 None。

    规则:
        "烦"/"压抑"/"透口气" → "放松"
        "无聊"/"没意思" → "新鲜感"
        "累"/"疲惫"/"没劲" → "恢复"
        "开心"/"兴奋" → "愉悦"
    """
    t = text.lower()
    if any(w in t for w in ["烦", "压抑", "透口气", "喘口气", "郁闷"]):
        return "放松"
    if any(w in t for w in ["无聊", "没意思", "单调", "腻了"]):
        return "新鲜感"
    if any(w in t for w in ["累", "疲惫", "没劲", "透支", "虚脱"]):
        return "恢复"
    if any(w in t for w in ["开心", "兴奋", "高兴", "嗨"]):
        return "愉悦"
    return None


# ---------------------------------------------------------------------------
# 偏好合并
# ---------------------------------------------------------------------------


def merge_user_preference(
    base_intent: dict,
    user_stated_prefs: dict | None = None,
    ltm_prediction: dict | None = None,
) -> dict:
    """将用户对话中表达的偏好 + LTM 历史预测合并到解析结果。

    合并策略（优先级递减）:
    1. user_stated_prefs: 对话中用户明确表达的
    2. ltm_prediction: LTM 基于上下文的预测
    3. base_intent: intent_parser 的结果

    每个维度的来源被标记在 preferences_source 中。
    """
    intent = dict(base_intent)
    source: dict[str, str] = {}

    # 偏好维度
    prefs = dict(intent.get("preferences", {}))
    ltm_dims = (ltm_prediction or {}).get("predicted_dimensions", {})
    for dim in ["culture", "food", "nature", "social"]:
        src = "profile_default"
        if user_stated_prefs and dim in user_stated_prefs:
            prefs[dim] = user_stated_prefs[dim]
            src = "user_stated"
        elif dim in ltm_dims:
            prefs[dim] = ltm_dims[dim]
            src = "ltm_contextual"
        source[f"preferences.{dim}"] = src
    intent["preferences"] = prefs

    # 节奏
    src = "profile_default"
    if user_stated_prefs and "pace" in user_stated_prefs:
        intent["pace"] = user_stated_prefs["pace"]
        src = "user_stated"
    elif ltm_prediction and ltm_prediction.get("predicted_pace"):
        intent["pace"] = ltm_prediction["predicted_pace"]
        src = "ltm_contextual"
    source["pace"] = src

    # 预算
    if user_stated_prefs and "budget" in user_stated_prefs:
        intent["budget"] = user_stated_prefs["budget"]
        source["budget"] = "user_stated"
    elif ltm_prediction and ltm_prediction.get("predicted_budget", 0) > 0:
        budget_val = ltm_prediction["predicted_budget"]
        intent["budget"] = {"per_person": budget_val, "type": "弹性"}
        source["budget"] = "ltm_contextual"
    else:
        source["budget"] = "profile_default"

    # 情感需求
    emotion_need = (
        intent.get("emotion_need")
        or (user_stated_prefs.get("emotion_need") if user_stated_prefs else None)
        or (ltm_prediction.get("predicted_emotion_need") if ltm_prediction else None)
    )
    if emotion_need:
        intent["emotion_need"] = emotion_need
        source["emotion_need"] = (
            "user_stated"
            if (user_stated_prefs and user_stated_prefs.get("emotion_need"))
            else "ltm_contextual"
        )

    intent["preferences_source"] = source
    return intent


# ---------------------------------------------------------------------------
# 关键词规则匹配（降级方案）
# ---------------------------------------------------------------------------

# 区域关键词 → 区域名称（用于 synthesizer 位置感知）
_LOCATION_KW_MAP: list[tuple[list[str], str]] = [
    (["横琴"], "横琴"),
    (["金湾机场", "机场"], "金湾机场"),
    (["金湾", "三灶", "红旗"], "金湾"),
    (["斗门", "井岸", "乾务", "莲洲"], "斗门"),
    (["唐家湾", "唐家", "淇澳"], "唐家湾"),
    (["拱北", "口岸", "关口"], "拱北"),
    (["香洲"], "香洲"),
    (["吉大", "免税"], "吉大"),
    (["湾仔", "南屏"], "湾仔"),
    (["华发", "商都"], "华发"),
    (["前山"], "前山"),
]


def _extract_location(text: str) -> str | None:
    """从用户输入中提取区域位置关键词。"""
    for kws, loc_name in _LOCATION_KW_MAP:
        for kw in kws:
            if kw in text:
                return loc_name
    return None


def _parse_city(text: str) -> str:
    """从文本提取城市。"""
    for city in ["珠海", "广州", "湛江"]:
        if city in text:
            return city
    return "珠海"


def _parse_time(text: str) -> tuple[str, str, str]:
    """从文本提取时间段。返回 (period, start, end)。"""
    period, start, end = "全天", "08:00", "22:00"
    if any(w in text for w in ["上午", "早上", "早晨"]):
        period, start, end = "上午", "08:00", "12:00"
    elif any(w in text for w in ["下午", "午后"]):
        period, start, end = "下午", "13:00", "18:00"
    elif any(w in text for w in ["晚上", "夜间", "夜"]):
        period, start, end = "晚上", "18:00", "22:00"
    if any(w in text for w in ["凌晨", "深夜", "半夜"]):
        period, start, end = "深夜", "00:00", "06:00"

    # 时长约束
    duration_match = re.search(r"(\d+)\s*[个]?\s*小时", text)
    hours = int(duration_match.group(1)) if duration_match else (4 if "半天" in text else 0)
    if hours > 0:
        sh, sm = start.split(":")
        end_min = int(sh) * 60 + int(sm) + hours * 60
        end = f"{(end_min // 60) % 24:02d}:{end_min % 60:02d}"

    return period, start, end


def _parse_budget(text: str) -> tuple[int, str]:
    """从文本提取预算。返回 (per_person, type)。"""
    budget_match = re.search(r"(\d+)\s*[元块]", text)
    if budget_match:
        return int(budget_match.group(1)), "硬约束"
    return 500, "弹性"


def _parse_group(text: str) -> tuple[int, str]:
    """从文本提取群体信息。返回 (size, type)。"""
    if any(w in text for w in ["情侣", "女朋友", "男朋友", "对象", "约会", "老伴"]):
        return 2, "情侣"
    if any(w in text for w in ["亲子", "带娃", "孩子", "小孩", "宝宝", "娃", "孙子"]):
        return 3, "亲子"
    if any(w in text for w in ["朋友", "一起", "聚会", "团建", "室友", "同学", "兄弟"]):
        return 4, "朋友"
    if any(w in text for w in ["退休", "老年", "爸妈", "父母"]):
        return 2, "退休"
    return 1, "独居"


def _parse_preferences(text: str) -> dict[str, float]:
    """从文本提取偏好分数。"""
    culture = (
        0.8 if any(w in text for w in ["文化", "历史", "博物馆", "艺术", "展览", "看展"]) else 0.3
    )
    food = (
        0.8
        if any(w in text for w in ["美食", "吃", "餐厅", "小吃", "探店", "好吃", "咖啡"])
        else 0.4
    )
    nature = (
        0.8 if any(w in text for w in ["自然", "公园", "爬山", "户外", "山", "湖", "散步"]) else 0.3
    )

    neg_crowd = re.search(r"(不想|不要|不去|不愿|害怕|怕).{0,4}(人多|热闹|拥挤|排队)", text)
    if neg_crowd or any(w in text for w in ["社恐", "安静", "独处", "一个人"]):
        social = 0.1
    elif any(w in text for w in ["热闹", "人多", "聚会", "嗨"]):
        social = 0.9
    else:
        social = 0.5

    return {"culture": culture, "food": food, "nature": nature, "social": social}


def _parse_pace(text: str) -> str:
    """从文本提取节奏偏好。"""
    if any(w in text for w in ["特种兵", "打卡", "赶场", "效率"]):
        return "特种兵型"
    if any(w in text for w in ["闲逛", "慢慢", "放松", "不想赶", "悠闲", "松口气"]):
        return "闲逛型"
    return "平衡型"


_ACTIVITY_CONSTRAINT_MAP: dict[str, str] = {
    "游乐园": "needs_entertainment",
    "乐园": "needs_entertainment",
    "游乐场": "needs_entertainment",
    "海洋馆": "needs_entertainment",
    "海洋王国": "needs_entertainment",
    "水族馆": "needs_entertainment",
    "动物园": "needs_entertainment",
    "烧烤": "needs_bbq",
    "火锅": "needs_dining",
    "茶馆": "needs_teahouse",
    "茶室": "needs_teahouse",
    "品茶": "needs_teahouse",
    "书店": "needs_bookstore",
    "书吧": "needs_bookstore",
    "游泳": "needs_swimming",
    "泳池": "needs_swimming",
    "踢球": "needs_sports",
    "打球": "needs_sports",
    "爬山": "needs_hiking",
    "画画": "needs_art",
    "写生": "needs_art",
    "书法": "needs_calligraphy",
}

_SCENE_MAP: dict[str, list[str]] = {
    "喝茶": ["茶馆", "品茶"],
    "听曲": ["曲艺表演", "传统文化"],
    "茶馆": ["茶馆"],
    "街边小吃": ["街边小店", "本地小吃"],
    "小吃街": ["小吃街", "夜市"],
    "拍照": ["拍照打卡", "网红景点"],
    "出片": ["出片", "拍照打卡"],
    "游乐园": ["游乐园", "儿童游乐"],
    "海洋馆": ["海洋馆", "水族馆"],
    "喝酒": ["酒吧", "清吧"],
    "烧烤": ["烧烤", "聚餐"],
    "火锅": ["火锅"],
    "书店": ["书店", "阅读空间"],
    "咖啡馆": ["咖啡馆"],
    "书法": ["书法", "传统文化"],
    "画画": ["安静画画", "艺术", "写生"],
    "日出": ["日出观景", "海边观景"],
    "日落": ["日落观景"],
    "夜景": ["夜景观景", "城市夜景"],
    "游泳": ["游泳", "水上运动"],
    "攀岩": ["攀岩"],
    "密室": ["密室逃脱", "剧本杀"],
    "长隆": ["长隆", "海洋王国", "游乐园"],
    "安静画画": ["安静画画", "艺术"],
    "蹦迪": ["蹦迪", "酒吧", "夜店"],
}

_CATEGORY_MAP: dict[str, list[str]] = {
    "游乐园": ["景点", "娱乐"],
    "乐园": ["景点", "娱乐"],
    "游乐场": ["景点", "娱乐"],
    "海洋馆": ["景点", "娱乐"],
    "水族馆": ["景点", "娱乐"],
    "蹦迪": ["娱乐", "餐饮"],
    "酒吧": ["娱乐", "餐饮"],
    "夜店": ["娱乐"],
    "KTV": ["娱乐"],
    "密室": ["娱乐", "密室逃脱"],
    "剧本杀": ["娱乐", "剧本杀"],
    "烧烤": ["餐饮"],
    "火锅": ["餐饮"],
    "美食": ["餐饮"],
    "小吃": ["餐饮", "夜市小吃"],
    "宵夜": ["餐饮", "夜市", "夜市小吃"],
    "博物馆": ["文化"],
    "美术馆": ["文化"],
    "展览": ["文化"],
    "书法": ["文化"],
    "画画": ["文化", "文艺", "咖啡馆"],
    "安静画画": ["文化", "文艺", "咖啡馆"],
    "书店": ["书店", "文化"],
    "咖啡馆": ["咖啡馆", "海景咖啡馆"],
    "公园": ["景点", "运动"],
    "爬山": ["运动", "自然风光"],
    "运动": ["运动"],
    "海边": ["景点", "自然风光"],
    "沙滩": ["景点", "自然风光"],
    "购物": ["购物"],
    "逛街": ["购物"],
    "拍照": ["景点", "文化"],
    "打卡": ["景点", "文化"],
    "温泉": ["温泉SPA"],
    "游泳": ["水上运动场所"],
    "聚会": ["餐饮", "娱乐", "购物"],
    "朋友": ["餐饮", "娱乐", "购物"],
    "情侣": ["餐饮", "文化", "景点", "海景咖啡馆"],
    "亲子": ["景点", "运动", "娱乐"],
    "孩子": ["景点", "运动", "娱乐"],
    "退休": ["文化", "景点", "餐饮"],
}


_KEYWORD_CONSTRAINT_MAP: list[tuple[list[str], str]] = [
    (["宠物", "狗", "猫", "狗子", "毛孩子"], "pet_friendly"),
    (["婴儿车", "轮椅", "无障碍"], "accessible"),
    (["排队", "不要排队"], "排队容忍度<10min"),
    (["孩子", "小孩", "儿童", "娃", "宝宝"], "儿童友好"),
    (["室内", "空调", "下雨", "雨天", "别中暑", "别淋", "别晒"], "indoor_only"),
    (["海边", "户外", "露天", "草地", "沙滩"], "outdoor_preferred"),
    (["凌晨", "深夜", "宵夜", "夜宵", "通宵", "半夜"], "late_night"),
]


def _parse_hard_constraints(text: str) -> list[str]:
    """从文本提取硬约束。"""
    constraints: list[str] = []
    neg_crowd = re.search(r"(不想|不要|不去|不愿|害怕|怕).{0,4}(人多|热闹|拥挤|排队)", text)

    if neg_crowd or any(w in text for w in ["社恐", "不想人多", "不要人多", "不想去人多"]):
        constraints.append("低人流")

    for keywords, constraint in _KEYWORD_CONSTRAINT_MAP:
        if any(w in text for w in keywords):
            constraints.append(constraint)

    for kw, constraint in _ACTIVITY_CONSTRAINT_MAP.items():
        if kw in text and constraint not in constraints:
            constraints.append(constraint)

    return constraints


def _parse_scene_requirements(text: str) -> list[str]:
    """从文本提取场景需求。"""
    requirements: list[str] = []
    for kw, scenes in _SCENE_MAP.items():
        if kw in text:
            for s in scenes:
                if s not in requirements:
                    requirements.append(s)
    return requirements


def _parse_preferred_categories(text: str) -> list[str]:
    """从文本推断偏好分类。"""
    categories: list[str] = []
    for kw, cats in _CATEGORY_MAP.items():
        if kw in text:
            for c in cats:
                if c not in categories:
                    categories.append(c)
    if not categories:
        categories = ["文化", "餐饮", "运动", "景点", "购物"]
    if "景点" not in categories:
        categories.append("景点")
    return categories


def _rule_based_parse(user_input: str) -> dict:
    """基于关键词的降级解析。"""
    text = user_input.lower()
    period, start, end = _parse_time(text)

    return {
        "city": _parse_city(text),
        "time": {"period": period, "start": start, "end": end},
        "budget": {"per_person": _parse_budget(text)[0], "type": _parse_budget(text)[1]},
        "group": {"size": _parse_group(text)[0], "type": _parse_group(text)[1]},
        "preferences": _parse_preferences(text),
        "pace": _parse_pace(text),
        "hard_constraints": _parse_hard_constraints(text),
        "scene_requirements": _parse_scene_requirements(text),
        "preferred_categories": _parse_preferred_categories(text),
        "emotion_need": detect_emotion_need(text),
        "location": _extract_location(text),
        "num_days": _extract_num_days(text),
    }


# ---------------------------------------------------------------------------
# 天数提取
# ---------------------------------------------------------------------------


def _extract_num_days(text: str) -> int:
    """从用户输入提取出行天数。默认1天，上限5天。"""
    text_lower = text.lower()
    # 数字+天/日
    m = re.search(r"(\d+)\s*[天日]", text_lower)
    if m:
        return min(5, max(1, int(m.group(1))))
    # 中文表达
    if any(w in text_lower for w in ("三天两晚", "三日", "3天")):
        return 3
    if any(w in text_lower for w in ("两天一夜", "两日", "二日", "2天", "周末")):
        return 2
    if any(w in text_lower for w in ("四天三晚", "四日", "4天")):
        return 4
    if any(w in text_lower for w in ("五天", "五日", "5天")):
        return 5
    if "一夜" in text_lower or "一晚" in text_lower:
        return 2
    return 1


# ---------------------------------------------------------------------------
# 时间工具
# ---------------------------------------------------------------------------


def _is_late_night_time(time_str: str) -> bool:
    """判断时间字符串是否在深夜时段（22:00-06:00）。"""
    try:
        h, _m = time_str.split(":")
        hour = int(h)
        return hour >= 22 or hour < 6
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


_VALID_CONSTRAINTS = {
    "queue_intolerant",
    "accessible",
    "pet_friendly",
    "indoor_only",
    "outdoor_preferred",
    "late_night",
    "needs_entertainment",
    "free",
    "低人流",
    "儿童友好",
    "排队容忍度<10min",
}

_DEFAULT_DEMAND_VECTOR = {
    "efficiency_seeking": 0.5,
    "excitement_seeking": 0.5,
    "tranquility_seeking": 0.5,
    "budget_sensitivity": 0.5,
    "novelty_seeking": 0.5,
    "social_desire": 0.5,
    "physical_energy": 0.5,
}


def _validate_budget(intent: dict) -> None:
    """预算边界校验。"""
    pp = intent.get("budget", {}).get("per_person", 500)
    if isinstance(pp, (int, float)):
        if pp < 50:
            logger.warning("预算异常低(%s), 修正为50", pp)
            intent["budget"]["per_person"] = 50
        if pp > 10000:
            logger.warning("预算异常高(%s), 修正为5000", pp)
            intent["budget"]["per_person"] = 5000


def _apply_post_processing(intent: dict, user_input: str) -> None:
    """对解析结果进行后处理。"""
    dv = intent.pop("demand_vector", None) if isinstance(intent, dict) else None
    if dv and all(
        k in dv for k in ("efficiency_seeking", "excitement_seeking", "tranquility_seeking")
    ):
        intent["_demand_vector"] = dv
    else:
        intent["_demand_vector"] = dict(_DEFAULT_DEMAND_VECTOR)

    if not intent.get("emotion_need"):
        need = detect_emotion_need(user_input)
        if need:
            intent["emotion_need"] = need

    _validate_budget(intent)
    intent["hard_constraints"] = list(
        set(c for c in intent.get("hard_constraints", []) if c in _VALID_CONSTRAINTS)
    )

    cats = intent.get("preferred_categories", [])
    if len(cats) > 8:
        intent["preferred_categories"] = cats[:8]

    time_info = intent.get("time", {})
    for key in ("start", "end"):
        t = time_info.get(key, "")
        if t and not isinstance(t, str):
            time_info[key] = "09:00" if key == "start" else "21:00"

    if not intent.get("scene_requirements"):
        intent["scene_requirements"] = []

    nd = intent.get("num_days", 1)
    intent["num_days"] = max(1, min(5, int(nd) if isinstance(nd, (int, float)) else 1))


def _apply_late_night_fix(intent: dict, user_input: str) -> None:
    """深夜场景时间修正。"""
    _late_night_keywords = {"凌晨", "深夜", "通宵", "宵夜", "夜宵", "半夜"}
    has_explicit_late = any(kw in user_input for kw in _late_night_keywords)

    if has_explicit_late and "late_night" not in intent.get("hard_constraints", []):
        intent.setdefault("hard_constraints", []).append("late_night")
        logger.debug("补充late_night约束（检测到深夜关键词）")

    if "late_night" not in intent.get("hard_constraints", []):
        return

    if has_explicit_late:
        start = intent.get("time", {}).get("start", "")
        if not start or not _is_late_night_time(start):
            intent["time"] = {"period": "深夜", "start": "22:00", "end": "06:00"}
            logger.debug("深夜时间修正: %s → 22:00-06:00", start)
    else:
        intent["hard_constraints"] = [
            c for c in intent.get("hard_constraints", []) if c != "late_night"
        ]
        logger.debug("移除late_night约束（无明确深夜关键词）")


async def parse_intent(user_input: str) -> dict:
    """将用户自然语言输入解析为结构化出行需求。"""
    logger.info("收到用户输入: %s", user_input)

    intent, llm_used, llm_error = await _try_llm_parse(user_input)
    if intent is None:
        intent = _rule_based_parse(user_input)
        logger.info("使用规则匹配结果")

    _apply_post_processing(intent, user_input)
    _apply_late_night_fix(intent, user_input)

    intent["_llm_used"] = llm_used
    intent["_llm_error"] = llm_error

    logger.info("解析结果: %s", json.dumps(intent, ensure_ascii=False))
    return intent


async def _try_llm_parse(user_input: str) -> tuple[dict | None, bool, str]:
    """尝试LLM解析，返回 (intent, llm_used, llm_error)。"""
    llm_error = ""

    for attempt in range(3):
        try:
            intent = await asyncio.wait_for(_call_llm(user_input), timeout=30.0)
            if intent:
                logger.info("LLM 解析成功")
                return intent, True, ""
            llm_error = "LLM 返回空结果"
        except TimeoutError:
            llm_error = f"LLM 超时（30s）第{attempt + 1}次"
            logger.warning("%s", llm_error)
        except Exception as e:
            llm_error = f"LLM 异常: {e}"
            logger.warning("%s", llm_error)
        if attempt < 2:
            await asyncio.sleep(1)

    return None, False, llm_error


# ---------------------------------------------------------------------------
# CLI 测试入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    test_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "周末想出去走走，不想去人多的地方"
    result = asyncio.run(parse_intent(test_input))
    print("\n=== 最终结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
