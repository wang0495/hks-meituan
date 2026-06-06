"""反馈指令分类器：将用户调整指令映射为 rerun_experts + weight_adjust。

替代原 DialogueEngine 的 _classify_instruction，
输出直接供 feedback graph 使用。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 意图 → expert 重跑策略
_INTENT_MAP: dict[str, dict[str, Any]] = {
    "replace": {
        "rerun_experts": ["poi"],
        "weight_adjust": {"poi": +0.1},
        "reply": "好的，我来帮你调整景点选择。",
    },
    "pace_relax": {
        "rerun_experts": ["poi", "traffic"],
        "weight_adjust": {"poi": +0.1, "traffic": -0.2},
        "reply": "好的，我帮你调整为更轻松的行程。",
    },
    "pace_tight": {
        "rerun_experts": ["poi", "traffic"],
        "weight_adjust": {"poi": +0.2, "traffic": +0.1},
        "reply": "好的，我帮你安排更紧凑的行程。",
    },
    "budget_down": {
        "rerun_experts": ["food", "poi"],
        "weight_adjust": {"food": -0.2, "poi": -0.1},
        "reply": "好的，我帮你降低预算。",
    },
    "budget_up": {
        "rerun_experts": ["food", "poi"],
        "weight_adjust": {"food": +0.2, "poi": +0.1},
        "reply": "好的，我帮你提升品质。",
    },
    "time_early": {
        "rerun_experts": ["poi", "traffic"],
        "weight_adjust": {"traffic": +0.1},
        "reply": "好的，我帮你提前出发时间。",
    },
    "time_late": {
        "rerun_experts": ["poi", "traffic"],
        "weight_adjust": {"traffic": -0.1},
        "reply": "好的，我帮你推迟出发时间。",
    },
    "more_food": {
        "rerun_experts": ["food", "poi"],
        "weight_adjust": {"food": +0.3, "poi": -0.1},
        "reply": "好的，我帮你多加些美食推荐。",
    },
    "scenic_nature": {
        "rerun_experts": ["poi", "destination"],
        "weight_adjust": {"poi": +0.2, "destination": +0.2},
        "reply": "好的，我帮你增加自然风光。",
    },
    "cultural": {
        "rerun_experts": ["poi"],
        "weight_adjust": {"poi": +0.2},
        "reply": "好的，我帮你增加文化类景点。",
    },
    "local_hidden": {
        "rerun_experts": ["local_expert", "poi"],
        "weight_adjust": {"local_expert": +0.3, "poi": +0.1},
        "reply": "好的，我帮你找一些隐藏宝藏。",
    },
    "retry": {
        "rerun_experts": ["poi", "food", "traffic", "local_expert"],
        "weight_adjust": {},
        "reply": "好的，我重新为你规划路线。",
    },
    "emotion_relax": {
        "rerun_experts": ["poi", "local_expert"],
        "weight_adjust": {"poi": +0.1, "local_expert": +0.2},
        "reply": "好的，我帮你调整为治愈放松型路线。",
    },
    "emotion_exciting": {
        "rerun_experts": ["poi", "food"],
        "weight_adjust": {"poi": +0.2, "food": +0.1},
        "reply": "好的，我帮你增加更多刺激体验。",
    },
    "mood_calm": {
        "rerun_experts": ["poi", "local_expert"],
        "weight_adjust": {"poi": +0.1, "local_expert": +0.2},
        "reply": "好的，我帮你调整路线氛围。",
    },
}

_VALID_INTENTS = set(_INTENT_MAP.keys())


async def classify_feedback(
    instruction: str, history: list[dict] | None = None
) -> dict[str, Any]:
    """用 LLM 将用户指令映射为 rerun_experts + weight_adjust。

    Returns:
        {"intent": str, "rerun_experts": list, "weight_adjust": dict, "reply": str}
    """
    # 构造上下文
    context = ""
    if history:
        for msg in history[-4:]:
            role = msg.get("role", "")
            text = msg.get("content", "")
            if role == "user":
                context += f"用户：{text}\n"
            elif role == "assistant":
                context += f"助手：{text[:80]}\n"

    intents_desc = "\n".join(f"- {k}" for k in _INTENT_MAP)

    prompt = f"用户指令：「{instruction}」\n\n"
    if context:
        prompt += f"最近对话：\n{context}\n"
    prompt += (
        "可选意图类别：\n"
        f"{intents_desc}\n\n"
        "请返回最匹配的意图类别名，只返回名称，不要其他内容。"
    )

    try:
        from backend.services.llm_service import chat

        resp = await chat(prompt)
        resp = resp.strip().strip('"').strip("'").strip("。").strip("！").strip()
        # LLM 可能返回带前缀的，取最后一个词
        for candidate in [resp, resp.split("/")[-1], resp.split("：")[-1]]:
            if candidate in _VALID_INTENTS:
                intent = candidate
                break
        else:
            intent = resp if resp in _VALID_INTENTS else "retry"
    except Exception as e:
        logger.warning("[FeedbackClassifier] LLM 分类失败: %s", e)
        intent = "retry"

    result = dict(_INTENT_MAP[intent])
    result["intent"] = intent
    return result
