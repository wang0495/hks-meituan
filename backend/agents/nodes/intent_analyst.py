"""intent_analyst 节点。

合并原IntentAgent和intent_parser的LLM逻辑，单次LLM调用完成：
1. 意图理解
2. 不可能需求检测
3. 场景关键词提取
4. 用户画像匹配增强
"""

from __future__ import annotations

import json
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from backend.agents.state import PlanningState
from backend.config.settings import settings

# 合并后的系统提示词
SYSTEM_PROMPT = """你是CityFlow旅行规划系统的意图分析专家。

你的任务是深度理解用户的自然语言输入，提取结构化意图，并检测潜在问题。

## 分析维度

1. **核心意图**
   - 用户真正想要什么类型的体验？
   - 提取关键词：场景类型、偏好的POI类别、时间/预算约束

2. **不可能需求检测**
   - 判断用户需求是否现实中可行
   - 例如：凌晨3点参观博物馆、100元玩遍全城、带轮椅去爬山等

3. **用户画像推断**
   - 从用词推断群体类型：独居/情侣/亲子/朋友/退休
   - 推断偏好：文化/美食/自然/社交/刺激
   - 推断节奏：闲逛型/平衡型/特种兵型

4. **潜在矛盾识别**
   - 需求内部是否有冲突？
   - 例如：想要刺激体验但体力需求低、预算紧张但要吃米其林

## 输出格式

必须返回严格的JSON：
{
    "is_impossible": false,
    "impossible_reason": "",
    "alternative_suggestion": "",
    "core_scene": "文化历史",
    "scene_keywords": ["文化", "历史", "博物馆"],
    "preferred_zones": ["香洲"],
    "group_type": "情侣",
    "pace_preference": "平衡型",
    "budget_level": "中等",
    "time_constraint": {"start": "09:00", "duration_hours": 4},
    "emotion_expectation": "温馨浪漫",
    "potential_contradictions": [],
    "enhanced_intent": "完整的增强意图描述"
}"""


def _get_llm() -> ChatOpenAI:
    """获取LLM实例。"""
    return ChatOpenAI(
        model=settings.llm.model,
        temperature=0.3,
        base_url=settings.llm.base_url,
        api_key=settings.llm.api_key,
        max_retries=settings.llm.max_retries,
    )


def _rule_based_fallback(user_input: str) -> dict[str, Any]:
    """规则回退：当LLM失败时使用。"""
    # 简单的关键词匹配
    keywords = {
        "情侣": {"group_type": "情侣", "emotion_expectation": "浪漫"},
        "亲子": {"group_type": "亲子", "emotion_expectation": "温馨"},
        "孩子": {"group_type": "亲子", "emotion_expectation": "教育"},
        "朋友": {"group_type": "朋友", "emotion_expectation": "欢乐"},
        "独自": {"group_type": "独居", "emotion_expectation": "放松"},
        "文化": {"scene_keywords": ["文化", "历史"]},
        "美食": {"scene_keywords": ["美食", "餐饮"]},
        "自然": {"scene_keywords": ["自然", "户外"]},
        "便宜": {"budget_level": "经济"},
        "贵": {"budget_level": "高端"},
        "慢": {"pace_preference": "闲逛型"},
        "快": {"pace_preference": "特种兵型"},
    }

    result = {
        "is_impossible": False,
        "impossible_reason": "",
        "alternative_suggestion": "",
        "core_scene": "综合",
        "scene_keywords": [],
        "preferred_zones": [],
        "group_type": "未知",
        "pace_preference": "平衡型",
        "budget_level": "中等",
        "time_constraint": {},
        "emotion_expectation": "放松",
        "potential_contradictions": [],
        "enhanced_intent": user_input,
    }

    for keyword, values in keywords.items():
        if keyword in user_input:
            result.update(values)

    return result


def node(state: PlanningState) -> dict:
    """意图分析节点。

    使用LLM深度分析用户意图，合并原IntentAgent和intent_parser的LLM逻辑。

    Args:
        state: 当前规划状态，需包含user_input和user_intent

    Returns:
        dict: 包含增强后的user_intent
    """
    user_input = state.get("user_input", "")
    base_intent = state.get("user_intent", {})

    if not user_input:
        return {"user_intent": base_intent}

    try:
        llm = _get_llm()
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"用户输入：{user_input}\n基础意图：{json.dumps(base_intent, ensure_ascii=False)}"),
        ]

        response = llm.invoke(messages)
        content = response.content

        # 提取JSON
        try:
            # 尝试直接解析
            analysis = json.loads(content)
        except json.JSONDecodeError:
            # 尝试从markdown代码块提取
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
                analysis = json.loads(json_str)
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
                analysis = json.loads(json_str)
            else:
                raise

        # 合并到基础意图
        enhanced_intent = {**base_intent, **analysis}

        # 检查是否不可能
        if analysis.get("is_impossible"):
            return {
                "user_intent": enhanced_intent,
                "errors": state.get("errors", []) + [f"不可能需求: {analysis.get('impossible_reason', '')}"],
            }

        return {"user_intent": enhanced_intent}

    except Exception as e:
        # LLM失败，使用规则回退
        fallback = _rule_based_fallback(user_input)
        enhanced_intent = {**base_intent, **fallback}
        return {
            "user_intent": enhanced_intent,
            "errors": state.get("errors", []) + [f"意图分析LLM失败，使用规则回退: {e}"],
        }
