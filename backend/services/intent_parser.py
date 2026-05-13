"""
CityFlow LLM 意图解析模块
将用户自然语言输入解析为结构化出行需求，并匹配用户画像。
基于4个设计文档的要求实现。
"""

import asyncio
import json
import logging
import os
import re

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 20 组用户画像（来自 本地周末出行_用户画像与测试场景_V2_20组.docx）
# ---------------------------------------------------------------------------

PROFILES: dict[str, dict] = {
    "P1": {
        "name": "社恐独居青年",
        "group_type": "独居",
        "age": "25-30",
        "social": 0.1,
        "pace": "闲逛型",
        "budget": 100,
        "queue_tolerance": "极低",
        "culture": 0.8,
        "food": 0.4,
        "keywords": ["社恐", "一个人", "安静", "独处", "不想人多", "不想去人多"],
        "constraints": ["低人流", "安静环境", "室内备选"],
    },
    "P2": {
        "name": "新戏情侣",
        "group_type": "情侣",
        "age": "25-32",
        "social": 0.5,
        "pace": "平衡型",
        "budget": 300,
        "queue_tolerance": "中等",
        "culture": 0.5,
        "food": 0.7,
        "keywords": ["约会", "浪漫", "情侣", "女朋友", "男朋友", "对象", "氛围感", "拍照"],
        "constraints": ["出片", "互动体验"],
    },
    "P3": {
        "name": "带娃小家庭",
        "group_type": "亲子",
        "age": "30-38",
        "social": 0.6,
        "pace": "平衡型",
        "budget": 400,
        "queue_tolerance": "低",
        "culture": 0.3,
        "food": 0.6,
        "keywords": ["亲子", "带娃", "孩子", "小孩", "消耗体力", "宝宝", "娃"],
        "constraints": ["儿童友好", "卫生间", "安全", "休息区"],
    },
    "P4": {
        "name": "退休独行女士",
        "group_type": "独居",
        "age": "62-70",
        "social": 0.3,
        "pace": "闲逛型",
        "budget": 80,
        "queue_tolerance": "中等",
        "culture": 0.7,
        "food": 0.5,
        "keywords": ["退休", "老年", "散步", "转转", "买菜", "一个人在家"],
        "constraints": ["无障碍", "休息座椅", "公交直达"],
    },
    "P5": {
        "name": "室友打卡组",
        "group_type": "朋友",
        "age": "22-26",
        "social": 0.9,
        "pace": "特种兵型",
        "budget": 150,
        "queue_tolerance": "高",
        "culture": 0.2,
        "food": 0.8,
        "keywords": ["网红", "打卡", "拍照", "小红书", "快快快"],
        "constraints": ["打卡场景", "户外走拍"],
    },
    "P6": {
        "name": "中产情侣",
        "group_type": "情侣",
        "age": "35-45",
        "social": 0.4,
        "pace": "闲逛型",
        "budget": 800,
        "queue_tolerance": "低",
        "culture": 0.6,
        "food": 0.8,
        "keywords": ["质感", "调性", "不挤", "聊天", "品质"],
        "constraints": ["有调性", "停车便利", "非年轻人玩法"],
    },
    "P7": {
        "name": "带婴儿家庭",
        "group_type": "亲子",
        "age": "28-35",
        "social": 0.3,
        "pace": "闲逛型",
        "budget": 300,
        "queue_tolerance": "极低",
        "culture": 0.2,
        "food": 0.5,
        "keywords": ["婴儿", "宝宝", "婴儿车", "推车"],
        "constraints": ["婴儿车通道", "哺乳室", "无障碍"],
    },
    "P8": {
        "name": "退休奶奶团",
        "group_type": "朋友",
        "age": "60-70",
        "social": 0.6,
        "pace": "闲逛型",
        "budget": 150,
        "queue_tolerance": "高",
        "culture": 0.7,
        "food": 0.5,
        "keywords": ["退休", "大家", "走走", "拍花", "发朋友圈"],
        "constraints": ["无障碍", "公交直达", "休息座椅"],
    },
    "P9": {
        "name": "大学生情侣",
        "group_type": "情侣",
        "age": "19-22",
        "social": 0.7,
        "pace": "特种兵型",
        "budget": 150,
        "queue_tolerance": "高",
        "culture": 0.4,
        "food": 0.6,
        "keywords": ["小红书", "火了", "拍照", "预算不多", "开心"],
        "constraints": ["性价比", "拍照场景"],
    },
    "P10": {
        "name": "单亲妈妈",
        "group_type": "亲子",
        "age": "30-38",
        "social": 0.3,
        "pace": "平衡型",
        "budget": 250,
        "queue_tolerance": "低",
        "culture": 0.4,
        "food": 0.5,
        "keywords": ["一个人带", "两个孩子", "松口气"],
        "constraints": ["儿童安全", "封闭式环境", "工作人员"],
    },
    "P11": {
        "name": "银发情侣",
        "group_type": "情侣",
        "age": "65-75",
        "social": 0.3,
        "pace": "闲逛型",
        "budget": 200,
        "queue_tolerance": "高",
        "culture": 0.7,
        "food": 0.5,
        "keywords": ["老伴", "天气好", "走走", "看看花", "拍拍照"],
        "constraints": ["无障碍", "休息座椅", "卫生间"],
    },
    "P12": {
        "name": "宠物独居青年",
        "group_type": "独居",
        "age": "26-32",
        "social": 0.3,
        "pace": "闲逛型",
        "budget": 250,
        "queue_tolerance": "低",
        "culture": 0.4,
        "food": 0.5,
        "keywords": ["宠物", "狗", "猫", "毛孩子", "狗子", "带出去转转"],
        "constraints": ["pet_friendly", "宠物饮水点", "户外空间"],
    },
    "P13": {
        "name": "异地恋情侣",
        "group_type": "情侣",
        "age": "25-30",
        "social": 0.5,
        "pace": "平衡型",
        "budget": 600,
        "queue_tolerance": "低",
        "culture": 0.5,
        "food": 0.7,
        "keywords": ["专程", "特别", "值得", "异地"],
        "constraints": ["值得专程", "拍照记录"],
    },
    "P14": {
        "name": "三代同堂",
        "group_type": "亲子",
        "age": "混合30-70",
        "social": 0.5,
        "pace": "闲逛型",
        "budget": 400,
        "queue_tolerance": "低",
        "culture": 0.5,
        "food": 0.6,
        "keywords": ["一家人", "老人", "孩子", "三代", "大家都能玩"],
        "constraints": ["无障碍", "儿童设施", "多人停车"],
    },
    "P15": {
        "name": "室友合租团",
        "group_type": "朋友",
        "age": "23-27",
        "social": 0.8,
        "pace": "平衡型",
        "budget": 120,
        "queue_tolerance": "中等",
        "culture": 0.3,
        "food": 0.7,
        "keywords": ["室友们", "一起出去玩", "聊天", "吃东西", "人多热闹"],
        "constraints": ["适合3-4人", "轻松随意"],
    },
    "P16": {
        "name": "独居职业女性",
        "group_type": "独居",
        "age": "28-35",
        "social": 0.3,
        "pace": "闲逛型",
        "budget": 500,
        "queue_tolerance": "低",
        "culture": 0.8,
        "food": 0.7,
        "keywords": ["一个人好好休息", "有调性", "咖啡", "看展", "品质"],
        "constraints": ["有品质感", "单独出行友好"],
    },
    "P17": {
        "name": "带孩子的爷爷奶奶",
        "group_type": "亲子",
        "age": "58-68",
        "social": 0.4,
        "pace": "闲逛型",
        "budget": 100,
        "queue_tolerance": "高",
        "culture": 0.6,
        "food": 0.4,
        "keywords": ["带孙子", "不花钱", "儿子加班"],
        "constraints": ["安全封闭", "免费低价停车"],
    },
    "P18": {
        "name": "初中生好友",
        "group_type": "朋友",
        "age": "13-15",
        "social": 0.7,
        "pace": "特种兵型",
        "budget": 80,
        "queue_tolerance": "低",
        "culture": 0.3,
        "food": 0.6,
        "keywords": ["同学", "一起出去玩", "家长同意", "注意安全"],
        "constraints": ["安全保障", "家长放心"],
    },
    "P19": {
        "name": "男生室友团",
        "group_type": "朋友",
        "age": "24-28",
        "social": 0.8,
        "pace": "平衡型",
        "budget": 200,
        "queue_tolerance": "中等",
        "culture": 0.3,
        "food": 0.7,
        "keywords": ["兄弟们", "能吃能玩", "新鲜感", "一起出去玩"],
        "constraints": ["互动性", "轻松随意", "能大声聊天"],
    },
    "P20": {
        "name": "社恐女孩",
        "group_type": "独居",
        "age": "22-26",
        "social": 0.1,
        "pace": "闲逛型",
        "budget": 80,
        "queue_tolerance": "极低",
        "culture": 0.7,
        "food": 0.4,
        "keywords": ["散散心", "不想人多", "安静", "好看", "独处"],
        "constraints": ["低人流", "安静环境", "独处空间"],
    },
}

# ---------------------------------------------------------------------------
# LLM Prompt 模板
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """你是 CityFlow 城市出行路线规划系统的意图解析器。
用户会用自然语言描述出行需求，你需要解析为严格的 JSON 格式。

输出格式（只输出 JSON，不要任何其他文字）：
{
  "city": "珠海/广州/湛江",
  "time": {"period": "上午/下午/全天", "start": "HH:MM", "end": "HH:MM"},
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
        # 手动加载 .env（pydantic-settings 嵌套模型有时不传递 LLM_ 前缀）
        _ensure_env_loaded()
        base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        api_key = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        if not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        _client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return _client


def _ensure_env_loaded():
    """确保 .env 中的 LLM_ 变量已加载到 os.environ。"""
    if os.environ.get("_LLM_ENV_LOADED"):
        return
    from pathlib import Path
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip().strip("\"'").strip()
            if key.startswith("LLM_") and key not in os.environ:
                os.environ[key] = val
    os.environ["_LLM_ENV_LOADED"] = "1"


def _get_llm_model() -> str:
    """获取 LLM 模型名，优先 settings 再 os.getenv 兜底。"""
    _ensure_env_loaded()
    return os.getenv("LLM_MODEL", "deepseek-chat")


async def _call_llm(user_input: str) -> dict | None:
    """调用 LLM 解析意图，返回解析结果或 None（失败时）。"""
    client = _get_client()
    try:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]
        resp = await client.chat.completions.create(
            model=_get_llm_model(),
            messages=messages,
            temperature=0.1,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        # 提取 JSON（兼容 markdown 代码块）
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            result = json.loads(json_match.group())
            result["_llm_prompt"] = _SYSTEM_PROMPT
            result["_llm_raw_response"] = raw[:500]
            result["_llm_model"] = _get_llm_model()
            return result
    except Exception as e:
        logger.warning(f"LLM 调用失败: {e}")
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
    3. base_intent: intent_parser 的结果（含画像默认）

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
    emotion_need = intent.get("emotion_need") or (
        user_stated_prefs.get("emotion_need") if user_stated_prefs else None
    ) or (
        ltm_prediction.get("predicted_emotion_need") if ltm_prediction else None
    )
    if emotion_need:
        intent["emotion_need"] = emotion_need
        source["emotion_need"] = "user_stated" if (
            user_stated_prefs and user_stated_prefs.get("emotion_need")
        ) else "ltm_contextual"

    intent["preferences_source"] = source
    return intent


# ---------------------------------------------------------------------------
# 关键词规则匹配（降级方案）
# ---------------------------------------------------------------------------


def _rule_based_parse(user_input: str) -> dict:
    """基于关键词的降级解析。"""
    text = user_input.lower()

    # 城市
    city = "珠海"
    for c in ["珠海", "广州", "湛江"]:
        if c in text:
            city = c
            break

    # 时间
    period, start, end = "全天", "08:00", "22:00"
    if any(w in text for w in ["上午", "早上", "早晨"]):
        period, start, end = "上午", "08:00", "12:00"
    elif any(w in text for w in ["下午", "午后"]):
        period, start, end = "下午", "13:00", "18:00"
    elif any(w in text for w in ["晚上", "夜间", "夜"]):
        period, start, end = "晚上", "18:00", "22:00"
    # 凌晨/深夜
    if any(w in text for w in ["凌晨", "深夜", "半夜"]):
        period, start, end = "深夜", "00:00", "06:00"

    # 时长约束："3小时"、"半天"、"2小时搞定"
    duration_match = re.search(r"(\d+)\s*[个]?\s*小时", text)
    if duration_match:
        hours = int(duration_match.group(1))
        # 计算 end = start + hours
        sh, sm = start.split(":")
        end_min = int(sh) * 60 + int(sm) + hours * 60
        end_h = (end_min // 60) % 24
        end_m = end_min % 60
        end = f"{end_h:02d}:{end_m:02d}"
    elif "半天" in text:
        # 半天 = 4小时
        sh, sm = start.split(":")
        end_min = int(sh) * 60 + int(sm) + 4 * 60
        end_h = (end_min // 60) % 24
        end_m = end_min % 60
        end = f"{end_h:02d}:{end_m:02d}"

    # 预算
    budget_per_person, budget_type = 500, "弹性"
    budget_match = re.search(r"(\d+)\s*[元块]", text)
    if budget_match:
        budget_per_person = int(budget_match.group(1))
        budget_type = "硬约束"

    # 群体
    group_size, group_type = 1, "独居"
    if any(w in text for w in ["情侣", "女朋友", "男朋友", "对象", "约会", "老伴"]):
        group_size, group_type = 2, "情侣"
    elif any(w in text for w in ["亲子", "带娃", "孩子", "小孩", "宝宝", "娃", "孙子"]):
        group_size, group_type = 3, "亲子"
    elif any(w in text for w in ["朋友", "一起", "聚会", "团建", "室友", "同学", "兄弟"]):
        group_size, group_type = 4, "朋友"
    elif any(w in text for w in ["退休", "老年", "爸妈", "父母"]):
        group_size, group_type = 2, "退休"

    # 偏好
    culture = 0.3
    if any(w in text for w in ["文化", "历史", "博物馆", "艺术", "展览", "看展"]):
        culture = 0.8

    food = 0.4
    if any(w in text for w in ["美食", "吃", "餐厅", "小吃", "探店", "好吃", "咖啡"]):
        food = 0.8

    nature = 0.3
    if any(w in text for w in ["自然", "公园", "爬山", "户外", "山", "湖", "散步"]):
        nature = 0.8

    social = 0.5
    # 否定模式优先：不想/不要/不去 + 人多/热闹 → 低社交
    _neg_crowd = re.search(
        r"(不想|不要|不去|不愿|害怕|怕).{0,4}(人多|热闹|拥挤|排队)", text
    )
    if _neg_crowd or any(w in text for w in ["社恐", "安静", "独处", "一个人"]):
        social = 0.1
    elif any(w in text for w in ["热闹", "人多", "聚会", "嗨"]):
        social = 0.9

    # 节奏
    pace = "平衡型"
    if any(w in text for w in ["特种兵", "打卡", "赶场", "效率"]):
        pace = "特种兵型"
    elif any(w in text for w in ["闲逛", "慢慢", "放松", "不想赶", "悠闲", "松口气"]):
        pace = "闲逛型"

    # 硬约束
    hard_constraints: list[str] = []
    if _neg_crowd or any(w in text for w in ["社恐", "不想人多", "不要人多"]):
        hard_constraints.append("低人流")
    if any(w in text for w in ["宠物", "狗", "猫", "狗子", "毛孩子"]):
        hard_constraints.append("pet_friendly")
    if any(w in text for w in ["婴儿车", "轮椅", "无障碍"]):
        hard_constraints.append("accessible")
    if any(w in text for w in ["排队", "不要排队"]):
        hard_constraints.append("排队容忍度<10min")
    if any(w in text for w in ["孩子", "小孩", "儿童", "娃", "宝宝"]):
        hard_constraints.append("儿童友好")
    # 室内/室外约束
    if any(w in text for w in ["室内", "空调", "下雨", "雨天", "别中暑", "别淋", "别晒"]):
        hard_constraints.append("indoor_only")
    if any(w in text for w in ["海边", "户外", "露天", "草地", "沙滩"]):
        hard_constraints.append("outdoor_preferred")
    # 深夜/凌晨
    if any(w in text for w in ["凌晨", "深夜", "宵夜", "夜宵", "通宵", "半夜"]):
        hard_constraints.append("late_night")
    # 具体活动需求
    activity_map = {
        "游乐园": "needs_entertainment", "乐园": "needs_entertainment", "游乐场": "needs_entertainment",
        "海洋馆": "needs_entertainment", "海洋王国": "needs_entertainment", "水族馆": "needs_entertainment",
        "动物园": "needs_entertainment",
        "烧烤": "needs_bbq", "火锅": "needs_dining",
        "茶馆": "needs_teahouse", "茶室": "needs_teahouse", "品茶": "needs_teahouse",
        "书店": "needs_bookstore", "书吧": "needs_bookstore",
        "游泳": "needs_swimming", "泳池": "needs_swimming",
        "踢球": "needs_sports", "打球": "needs_sports", "爬山": "needs_hiking",
        "画画": "needs_art", "写生": "needs_art", "书法": "needs_calligraphy",
    }
    for kw, constraint in activity_map.items():
        if kw in text and constraint not in hard_constraints:
            hard_constraints.append(constraint)

    # 场景需求提取
    scene_requirements: list[str] = []
    scene_map = {
        "喝茶": ["茶馆", "品茶"], "听曲": ["曲艺表演", "传统文化"], "茶馆": ["茶馆"],
        "街边小吃": ["街边小店", "本地小吃"], "小吃街": ["小吃街", "夜市"],
        "拍照": ["拍照打卡", "网红景点"], "出片": ["出片", "拍照打卡"],
        "游乐园": ["游乐园", "儿童游乐"], "海洋馆": ["海洋馆", "水族馆"],
        "蹦迪": ["酒吧", "夜店"], "喝酒": ["酒吧", "清吧"],
        "烧烤": ["烧烤", "聚餐"], "火锅": ["火锅"],
        "书店": ["书店", "阅读空间"], "咖啡馆": ["咖啡馆"],
        "书法": ["书法", "传统文化"], "画画": ["艺术", "写生"],
        "日出": ["日出观景", "海边观景"], "日落": ["日落观景"],
        "夜景": ["夜景观景", "城市夜景"],
        "游泳": ["游泳", "水上运动"], "攀岩": ["攀岩"],
        "密室": ["密室逃脱", "剧本杀"],
        "长隆": ["长隆", "海洋王国", "游乐园"],
        "画画": ["安静画画", "艺术", "写生"], "安静画画": ["安静画画", "艺术"],
        "蹦迪": ["蹦迪", "酒吧", "夜店"],
    }
    for kw, scenes in scene_map.items():
        if kw in text:
            for s in scenes:
                if s not in scene_requirements:
                    scene_requirements.append(s)

    # 推断preferred_categories
    preferred_categories: list[str] = []
    _CAT_MAP = {
        "游乐园": ["景点", "娱乐"], "乐园": ["景点", "娱乐"], "游乐场": ["景点", "娱乐"],
        "海洋馆": ["景点", "娱乐"], "水族馆": ["景点", "娱乐"],
        "蹦迪": ["娱乐", "餐饮"], "酒吧": ["娱乐", "餐饮"], "夜店": ["娱乐"],
        "KTV": ["娱乐"], "密室": ["娱乐", "密室逃脱"], "剧本杀": ["娱乐", "剧本杀"],
        "烧烤": ["餐饮"], "火锅": ["餐饮"], "美食": ["餐饮"], "小吃": ["餐饮", "夜市小吃"],
        "宵夜": ["餐饮", "夜市", "夜市小吃"],
        "博物馆": ["文化"], "美术馆": ["文化"], "展览": ["文化"], "书法": ["文化"],
        "画画": ["文化", "文艺", "咖啡馆"], "安静画画": ["文化", "文艺", "咖啡馆"],
        "书店": ["书店", "文化"], "咖啡馆": ["咖啡馆", "海景咖啡馆"],
        "公园": ["景点", "运动"], "爬山": ["运动", "自然风光"], "运动": ["运动"],
        "海边": ["景点", "自然风光"], "沙滩": ["景点", "自然风光"],
        "购物": ["购物"], "逛街": ["购物"],
        "拍照": ["景点", "文化"], "打卡": ["景点", "文化"],
        "温泉": ["温泉SPA"], "游泳": ["水上运动场所"],
        "聚会": ["餐饮", "娱乐", "购物"], "朋友": ["餐饮", "娱乐", "购物"],
        "情侣": ["餐饮", "文化", "景点", "海景咖啡馆"],
        "亲子": ["景点", "运动", "娱乐"], "孩子": ["景点", "运动", "娱乐"],
        "退休": ["文化", "景点", "餐饮"],
    }
    for kw, cats in _CAT_MAP.items():
        if kw in text:
            for c in cats:
                if c not in preferred_categories:
                    preferred_categories.append(c)
    if not preferred_categories:
        preferred_categories = ["文化", "餐饮", "运动", "景点", "购物"]
    if "景点" not in preferred_categories:
        preferred_categories.append("景点")

    return {
        "city": city,
        "time": {"period": period, "start": start, "end": end},
        "budget": {"per_person": budget_per_person, "type": budget_type},
        "group": {"size": group_size, "type": group_type},
        "preferences": {
            "culture": culture,
            "food": food,
            "nature": nature,
            "social": social,
        },
        "pace": pace,
        "hard_constraints": hard_constraints,
        "scene_requirements": scene_requirements,
        "preferred_categories": preferred_categories,
        "emotion_need": detect_emotion_need(text),
        "location": None,
    }


# ---------------------------------------------------------------------------
# 画像匹配（改进版，基于20组画像的详细特征）
# ---------------------------------------------------------------------------


def _match_profile(intent: dict, available_profiles: dict, user_input: str = "") -> tuple[str, list[tuple[str, float, str]]]:
    """将解析结果与画像库进行模糊匹配，返回 (最佳画像ID, [(pid, score, name), ...])。

    兼容两种画像字段结构:
    - intent_parser.PROFILES 格式: keywords/constraints/budget(数字)
    - user_profiles.USER_PROFILES 格式: budget_level(字符串)/preferences(字典)
    """
    best_id = "P1"
    best_score = -1.0

    group_type = intent.get("group", {}).get("type", "独居")
    social = intent.get("preferences", {}).get("social", 0.5)
    pace = intent.get("pace", "平衡型")
    hard_constraints = intent.get("hard_constraints", [])

    match_text = user_input + " " + " ".join(hard_constraints)

    all_scores: list[tuple[str, float, str]] = []

    for pid, profile in available_profiles.items():
        score = 0.0

        # 群体类型匹配（权重 3.0）
        if profile.get("group_type") == group_type:
            score += 3.0

        # 社交倾向匹配（权重 3.0）
        profile_social = profile.get("social", 0.5)
        score += 3.0 * (1 - abs(profile_social - social))

        # 节奏匹配（权重 2.0）
        if profile.get("pace") == pace:
            score += 2.0

        # 预算匹配（兼容两套字段结构）
        user_budget = intent.get("budget", {}).get("per_person", 500)
        profile_budget_raw = profile.get("budget")  # 数字: intent_parser 格式
        if profile_budget_raw is not None and isinstance(profile_budget_raw, (int, float)):
            budget_diff = abs(profile_budget_raw - user_budget) / max(profile_budget_raw, user_budget)
            score += 1.0 * (1 - budget_diff)
        else:
            # USER_PROFILES 格式: budget_level = "低"/"中"/"高"
            _MAP = {"低": 0.2, "中": 0.5, "高": 0.8}
            profile_level = profile.get("budget_level", "中")
            user_level = "低" if user_budget < 200 else "中" if user_budget < 800 else "高"
            budget_diff = abs(_MAP.get(profile_level, 0.5) - _MAP.get(user_level, 0.5))
            score += 1.0 * (1 - budget_diff)

        # 文化偏好匹配（兼容两套结构）
        profile_culture = profile.get("culture") or profile.get("preferences", {}).get("culture", 0.5)
        user_culture = intent.get("preferences", {}).get("culture", 0.3)
        score += 1.0 * (1 - abs(profile_culture - user_culture))

        # 关键词匹配（兼容两套结构）
        keywords = profile.get("keywords", [])
        if not keywords:
            # USER_PROFILES 没有 keywords 字段，略过
            pass
        for kw in keywords:
            if kw in match_text:
                score += 2.0

        # 约束匹配（兼容两套结构）
        profile_constraints = profile.get("constraints") or profile.get("hard_constraints", [])
        pc_str = " ".join(profile_constraints) if isinstance(profile_constraints, list) else ""
        if "pet_friendly" in hard_constraints and "pet_friendly" in pc_str:
            score += 5.0
        if "accessible" in hard_constraints and "无障碍" in pc_str:
            score += 3.0
        if "儿童友好" in hard_constraints and "儿童" in pc_str:
            score += 3.0
        if "低人流" in hard_constraints and "低人流" in pc_str:
            score += 4.0

        # 社恐关键词强化
        profile_name = profile.get("name", "")
        if any(w in match_text for w in ["社恐", "不想人多", "安静", "独处"]) and "社恐" in profile_name:
            score += 5.0
        if any(w in match_text for w in ["宠物", "狗", "猫", "狗子"]) and "宠物" in profile_name:
            score += 5.0

        all_scores.append((pid, score, profile_name))
        if score > best_score:
            best_score = score
            best_id = pid

    all_scores.sort(key=lambda x: -x[1])
    return best_id, all_scores[:3]


# ---------------------------------------------------------------------------
# 时间工具
# ---------------------------------------------------------------------------


def _is_late_night_time(time_str: str) -> bool:
    """判断时间字符串是否在深夜时段（22:00-06:00）。"""
    try:
        h, m = time_str.split(":")
        hour = int(h)
        return hour >= 22 or hour < 6
    except:
        return False


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


async def parse_intent(user_input: str, available_profiles: dict | None = None) -> dict:
    """
    将用户自然语言输入解析为结构化出行需求。

    参数:
        user_input: 用户的自然语言出行需求
        available_profiles: 画像字典，默认使用内置 PROFILES

    返回:
        结构化意图字典，包含 time/budget/group/preferences/pace/hard_constraints/matched_profile_id
    """
    if available_profiles is None:
        available_profiles = PROFILES

    logger.info(f"[IntentParser] 收到用户输入: {user_input}")
    print(f"[IntentParser] 收到用户输入: {user_input}")

    # 尝试 LLM 解析（30 秒超时 — DeepSeek 首次调用较慢）
    intent: dict | None = None
    llm_used = False
    llm_error = ""
    try:
        intent = await asyncio.wait_for(_call_llm(user_input), timeout=30.0)
        if intent:
            llm_used = True
            logger.info("[IntentParser] LLM 解析成功")
            print("[IntentParser] LLM 解析成功")
        else:
            llm_error = "LLM 返回空结果"
    except asyncio.TimeoutError:
        llm_error = "LLM 超时（30s）"
        logger.warning(f"[IntentParser] {llm_error}，降级为规则匹配")
        print(f"[IntentParser] {llm_error}，降级为规则匹配")
    except Exception as e:
        llm_error = f"LLM 异常: {e}"
        logger.warning(f"[IntentParser] {llm_error}，降级为规则匹配")
        print(f"[IntentParser] {llm_error}，降级为规则匹配")

    # 降级方案
    if intent is None:
        intent = _rule_based_parse(user_input)
        logger.info("[IntentParser] 使用规则匹配结果")
        print("[IntentParser] 使用规则匹配结果")

    # 提取需求向量（来自LLM，或为规则匹配创建默认值）
    dv = intent.pop("demand_vector", None) if isinstance(intent, dict) else None
    if dv and all(k in dv for k in ("efficiency_seeking", "excitement_seeking", "tranquility_seeking")):
        intent["_demand_vector"] = dv
    else:
        intent["_demand_vector"] = {
            "efficiency_seeking": 0.5,
            "excitement_seeking": 0.5,
            "tranquility_seeking": 0.5,
            "budget_sensitivity": 0.5,
            "novelty_seeking": 0.5,
            "social_desire": 0.5,
            "physical_energy": 0.5,
        }

    # 后处理: 确保 emotion_need 存在
    if not intent.get("emotion_need"):
        need = detect_emotion_need(user_input)
        if need:
            intent["emotion_need"] = need

    # 后处理: 确保 scene_requirements 存在
    if not intent.get("scene_requirements"):
        intent["scene_requirements"] = []

    # 后处理: 如果用户提到深夜关键词但LLM没加late_night约束，补上
    _raw = user_input  # user_input是parse_intent的参数，此时_raw_input还未设置
    _LATE_NIGHT_KW = ["凌晨", "深夜", "通宵", "宵夜", "夜宵", "半夜"]
    if any(kw in _raw for kw in _LATE_NIGHT_KW):
        if "late_night" not in intent.get("hard_constraints", []):
            intent.setdefault("hard_constraints", []).append("late_night")
            print(f"[IntentParser] 补充late_night约束（检测到深夜关键词）")

    # 后处理: 深夜场景确保时间正确
    # 只在用户明确提到"凌晨/深夜/通宵/宵夜"时才强制设为深夜时段
    # "晚上/夜间/别太早回家"等不算深夜
    _LATE_NIGHT_KEYWORDS = {"凌晨", "深夜", "通宵", "宵夜", "夜宵", "半夜"}
    if "late_night" in intent.get("hard_constraints", []):
        time_info = intent.get("time", {})
        start = time_info.get("start", "")
        end = time_info.get("end", "")
        # 检查用户是否明确提到深夜关键词
        has_explicit_late = any(kw in _raw for kw in _LATE_NIGHT_KEYWORDS)
        if has_explicit_late:
            if start and not _is_late_night_time(start):
                intent["time"] = {"period": "深夜", "start": "22:00", "end": "06:00"}
                print(f"[IntentParser] 深夜时间修正: {start} → 22:00-06:00")
            elif not start:
                intent["time"] = {"period": "深夜", "start": "22:00", "end": "06:00"}
        else:
            # 没有明确深夜关键词 → 移除late_night约束，保留LLM返回的时间
            intent["hard_constraints"] = [c for c in intent.get("hard_constraints", []) if c != "late_night"]
            print(f"[IntentParser] 移除late_night约束（无明确深夜关键词）")

    # 画像匹配
    matched_id, top_scores = _match_profile(intent, available_profiles, user_input)
    intent["matched_profile_id"] = matched_id
    intent["_llm_used"] = llm_used
    intent["_llm_error"] = llm_error
    intent["_profile_top3"] = [
        {"id": pid, "score": round(s, 1), "name": nm}
        for pid, s, nm in top_scores
    ]

    logger.info(f"[IntentParser] 解析结果: {json.dumps(intent, ensure_ascii=False)}")
    print(
        f"[IntentParser] 匹配画像: {matched_id} - {available_profiles.get(matched_id, {}).get('name', '未知')}"
    )
    print(
        f"[IntentParser] 完整结果: {json.dumps(intent, ensure_ascii=False, indent=2)}"
    )

    return intent


# ---------------------------------------------------------------------------
# CLI 测试入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    test_input = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "周末想出去走走，不想去人多的地方"
    )
    result = asyncio.run(parse_intent(test_input))
    print("\n=== 最终结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
