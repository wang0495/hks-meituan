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
  "time": {"period": "上午/下午/全天", "start": "HH:MM", "end": "HH:MM"},
  "budget": {"per_person": 金额整数, "type": "硬约束/弹性"},
  "group": {"size": 人数整数, "type": "独居/情侣/亲子/朋友/退休"},
  "preferences": {"culture": 0到1的小数, "food": 0到1的小数, "nature": 0到1的小数, "social": 0到1的小数},
  "pace": "特种兵型/平衡型/闲逛型",
  "hard_constraints": ["约束1", "约束2"]
}

规则：
- period: 根据时间词判断，无明确时间则默认"全天"
- budget: 无明确预算则 per_person=500, type="弹性"
- group.type: 根据同行人判断，默认"独居"
- preferences: 根据关键词推断偏好强度（0=完全不感兴趣, 1=非常感兴趣）
  - culture: 文化/历史/艺术/博物馆/展览
  - food: 美食/餐厅/小吃/探店
  - nature: 自然/公园/山/湖/植物
  - social: 社交/聚会/热闹/人多
- pace: "特种兵型"=赶场打卡, "平衡型"=适中, "闲逛型"=慢节奏
- hard_constraints: 提取明确的限制条件，如"不想排队""要无障碍""带宠物""带婴儿车"
- 社恐/不想人多 → social 设低值(0.1-0.2)
- 带宠物/狗/猫 → hard_constraints 加 "pet_friendly"
- 婴儿车/轮椅/无障碍 → hard_constraints 加 "accessible"
"""

# ---------------------------------------------------------------------------
# LLM 调用（带超时降级）
# ---------------------------------------------------------------------------

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        api_key = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        _client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return _client


async def _call_llm(user_input: str) -> dict | None:
    """调用 LLM 解析意图，返回解析结果或 None（失败时）。"""
    client = _get_client()
    try:
        resp = await client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        raw = resp.choices[0].message.content or ""
        # 提取 JSON（兼容 markdown 代码块）
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.warning(f"LLM 调用失败: {e}")
    return None


# ---------------------------------------------------------------------------
# 关键词规则匹配（降级方案）
# ---------------------------------------------------------------------------


def _rule_based_parse(user_input: str) -> dict:
    """基于关键词的降级解析。"""
    text = user_input.lower()

    # 时间
    period, start, end = "全天", "08:00", "22:00"
    if any(w in text for w in ["上午", "早上", "早晨"]):
        period, start, end = "上午", "08:00", "12:00"
    elif any(w in text for w in ["下午", "午后"]):
        period, start, end = "下午", "13:00", "18:00"
    elif any(w in text for w in ["晚上", "夜间", "夜"]):
        period, start, end = "晚上", "18:00", "22:00"

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

    return {
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
    }


# ---------------------------------------------------------------------------
# 画像匹配（改进版，基于20组画像的详细特征）
# ---------------------------------------------------------------------------


def _match_profile(intent: dict, available_profiles: dict, user_input: str = "") -> str:
    """将解析结果与画像库进行模糊匹配，返回最佳画像 ID。"""
    best_id = "P1"
    best_score = -1.0

    group_type = intent.get("group", {}).get("type", "独居")
    social = intent.get("preferences", {}).get("social", 0.5)
    pace = intent.get("pace", "平衡型")
    hard_constraints = intent.get("hard_constraints", [])
    budget = intent.get("budget", {}).get("per_person", 500)
    culture_pref = intent.get("preferences", {}).get("culture", 0.3)

    # 合并用户原始输入用于关键词匹配
    match_text = user_input + " " + " ".join(hard_constraints)

    for pid, profile in available_profiles.items():
        score = 0.0

        # 群体类型匹配（权重最高）
        if profile.get("group_type") == group_type:
            score += 3.0

        # 社交偏好的相似度（权重提高）
        profile_social = profile.get("social", 0.5)
        score += 3.0 * (1 - abs(profile_social - social))

        # 节奏匹配
        if profile.get("pace") == pace:
            score += 2.0

        # 预算匹配
        profile_budget = profile.get("budget", 500)
        budget_diff = abs(profile_budget - budget) / max(profile_budget, budget)
        score += 1.0 * (1 - budget_diff)

        # 文化偏好匹配
        profile_culture = profile.get("culture", 0.5)
        score += 1.0 * (1 - abs(profile_culture - culture_pref))

        # 关键词匹配（检查用户原始输入）
        keywords = profile.get("keywords", [])
        for kw in keywords:
            if kw in match_text:
                score += 2.0

        # 特殊硬约束加权
        profile_name = profile.get("name", "")
        profile_constraints = profile.get("constraints", [])

        if "pet_friendly" in hard_constraints and "pet_friendly" in profile_constraints:
            score += 5.0
        if "accessible" in hard_constraints and "无障碍" in " ".join(profile_constraints):
            score += 3.0
        if "儿童友好" in hard_constraints and "儿童" in " ".join(profile_constraints):
            score += 3.0
        if "低人流" in hard_constraints and "低人流" in profile_constraints:
            score += 4.0
        if "低人流" in hard_constraints and "社恐" in profile_name:
            score += 4.0
        # 社恐关键词匹配
        if any(w in match_text for w in ["社恐", "不想人多", "安静", "独处"]) and "社恐" in profile_name:
            score += 5.0

        if score > best_score:
            best_score = score
            best_id = pid

    return best_id


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

    # 尝试 LLM 解析（5 秒超时）
    intent: dict | None = None
    try:
        intent = await asyncio.wait_for(_call_llm(user_input), timeout=5.0)
        if intent:
            logger.info("[IntentParser] LLM 解析成功")
            print("[IntentParser] LLM 解析成功")
    except asyncio.TimeoutError:
        logger.warning("[IntentParser] LLM 超时，降级为规则匹配")
        print("[IntentParser] LLM 超时（5s），降级为规则匹配")
    except Exception as e:
        logger.warning(f"[IntentParser] LLM 异常: {e}，降级为规则匹配")
        print(f"[IntentParser] LLM 异常: {e}，降级为规则匹配")

    # 降级方案
    if intent is None:
        intent = _rule_based_parse(user_input)
        logger.info("[IntentParser] 使用规则匹配结果")
        print("[IntentParser] 使用规则匹配结果")

    # 画像匹配
    matched_id = _match_profile(intent, available_profiles, user_input)
    intent["matched_profile_id"] = matched_id

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
