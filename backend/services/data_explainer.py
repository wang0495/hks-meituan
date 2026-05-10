"""CityFlow 数据解释层。

将后端内部数据结构翻译为人类可读文本。
用于 TUI 调试面板展示。

原则:
- 不改变原始数据，只提供解释
- 解释要简洁、有意义
- 支持不同详细程度（brief / normal / detailed）
"""

from __future__ import annotations

from typing import Any


# ── 需求向量解释 ─────────────────────────────────────────────────────

_DEMAND_LABELS: dict[str, tuple[str, str, str]] = {
    # key: (中文标签, 高值含义, 低值含义)
    "efficiency_seeking": ("效率", "追求高效打卡", "愿意慢慢逛"),
    "excitement_seeking": ("刺激", "追求刺激体验", "偏好安静平和"),
    "tranquility_seeking": ("宁静", "追求宁静放松", "喜欢热闹"),
    "budget_sensitivity": ("预算", "对价格敏感", "不太在意价格"),
    "novelty_seeking": ("新颖", "追求新奇体验", "偏好熟悉路线"),
    "social_desire": ("社交", "喜欢社交互动", "偏好独处"),
    "physical_energy": ("体力", "体力充沛", "体力有限"),
}


def explain_demand_vector(demand_vector: dict[str, float], mode: str = "normal") -> str:
    """解释需求向量。

    参数:
        demand_vector: {"efficiency_seeking": 0.8, ...}
        mode: "brief" | "normal" | "detailed"

    返回:
        "追求高效打卡，偏好安静平和，对价格敏感"
    """
    if not demand_vector:
        return "无需求信息"

    if mode == "brief":
        # 只显示显著偏离中性的维度
        parts = []
        for key, value in sorted(demand_vector.items()):
            if key.startswith("_"):
                continue
            if key not in _DEMAND_LABELS:
                continue
            label, high, low = _DEMAND_LABELS[key]
            if value > 0.65:
                parts.append(f"{label}↑")
            elif value < 0.35:
                parts.append(f"{label}↓")
        return " ".join(parts) if parts else "需求适中"

    elif mode == "detailed":
        parts = []
        for key, value in sorted(demand_vector.items()):
            if key.startswith("_"):
                continue
            if key not in _DEMAND_LABELS:
                continue
            label, high, low = _DEMAND_LABELS[key]
            if value > 0.65:
                parts.append(f"{high}({value:.0%})")
            elif value < 0.35:
                parts.append(f"{low}({value:.0%})")
        return "；".join(parts) if parts else "各项需求适中"

    else:  # normal
        parts = []
        for key, value in sorted(demand_vector.items()):
            if key.startswith("_"):
                continue
            if key not in _DEMAND_LABELS:
                continue
            label, high, low = _DEMAND_LABELS[key]
            if value > 0.65:
                parts.append(high)
            elif value < 0.35:
                parts.append(low)
        return "，".join(parts) if parts else "各项需求适中"


# ── 权重解释 ─────────────────────────────────────────────────────────

_WEIGHT_LABELS: dict[str, tuple[str, str, str]] = {
    # key: (中文标签, 高值含义, 低值含义)
    "alpha": ("路线紧凑度", "路线更紧凑高效", "路线更宽松悠闲"),
    "beta": ("体验收益权重", "更看重体验质量", "更看重效率"),
    "gamma": ("疲劳敏感度", "对疲劳更敏感", "不太怕累"),
    "delta": ("多样性偏好", "更追求多样化", "可以重复类型"),
    "budget_strictness": ("预算严格度", "预算约束更严格", "预算更灵活"),
}

_WEIGHT_BASELINE = {
    "alpha": 1.0,
    "beta": 0.5,
    "gamma": 0.2,
    "delta": 0.8,
    "budget_strictness": 0.5,
}


def explain_weights(computed_weights: dict[str, float], mode: str = "normal") -> str:
    """解释求解器权重。

    参数:
        computed_weights: {"alpha": 1.2, "beta": 0.5, ...}
        mode: "brief" | "normal" | "detailed"

    返回:
        "路线更紧凑高效，更看重体验质量"
    """
    if not computed_weights:
        return "使用默认权重"

    if mode == "brief":
        parts = []
        for key in ["alpha", "beta", "gamma", "delta"]:
            if key not in computed_weights:
                continue
            value = computed_weights[key]
            baseline = _WEIGHT_BASELINE.get(key, 0.5)
            label = _WEIGHT_LABELS.get(key, (key, "", ""))[0]
            diff = value - baseline
            if abs(diff) > 0.15:
                direction = "↑" if diff > 0 else "↓"
                parts.append(f"{label[:2]}{direction}")
        return " ".join(parts) if parts else "默认"

    elif mode == "detailed":
        parts = []
        for key, value in computed_weights.items():
            if key.startswith("_"):
                continue
            baseline = _WEIGHT_BASELINE.get(key, 0.5)
            label, high, low = _WEIGHT_LABELS.get(key, (key, "", ""))
            diff = value - baseline
            if abs(diff) > 0.05:
                direction = high if diff > 0 else low
                parts.append(f"{label}: {direction}(权重{value:.2f}, 基准{baseline:.2f})")
        return "；".join(parts) if parts else "全部使用默认权重"

    else:  # normal
        parts = []
        for key, value in computed_weights.items():
            if key.startswith("_"):
                continue
            baseline = _WEIGHT_BASELINE.get(key, 0.5)
            label, high, low = _WEIGHT_LABELS.get(key, (key, "", ""))
            diff = value - baseline
            if abs(diff) > 0.1:
                parts.append(high if diff > 0 else low)
        return "，".join(parts) if parts else "使用默认权重配置"


# ── 用户增量解释 ─────────────────────────────────────────────────────

def explain_user_deltas(user_deltas: dict[str, dict[str, float]], mode: str = "normal") -> str:
    """解释用户个性化偏移量。

    参数:
        user_deltas: {"alpha": {"efficiency_seeking": 0.1}, ...}
        mode: "brief" | "normal" | "detailed"

    返回:
        "该用户比平均更看重效率，对疲劳更敏感"
    """
    if not user_deltas:
        return "无个性化调整"

    # 收集所有非零 delta
    significant: list[tuple[str, str, float]] = []  # (weight_name, dim, delta)
    for weight_name, dims in user_deltas.items():
        for dim, delta in dims.items():
            if abs(delta) > 0.02:
                significant.append((weight_name, dim, delta))

    if not significant:
        return "无显著个性化调整"

    if mode == "brief":
        count = len(significant)
        return f"已学习{count}项个性化调整"

    # 分析趋势
    trends = []
    for weight_name, dim, delta in significant:
        if dim not in _DEMAND_LABELS:
            continue
        label = _DEMAND_LABELS[dim][0]
        if delta > 0.05:
            trends.append(f"更看重{label}")
        elif delta < -0.05:
            trends.append(f"不太在意{label}")

    if not trends:
        return "有轻微个性化调整"

    return "，".join(trends[:3])


# ── LTM 预测解释 ─────────────────────────────────────────────────────

def explain_ltm_prediction(prediction: dict[str, Any], mode: str = "normal") -> str:
    """解释 LTM 预测结果。

    参数:
        prediction: {"data_points": 5, "confidence": 0.75, "predicted_pace": "闲逛型", ...}
        mode: "brief" | "normal" | "detailed"

    返回:
        "匹配5条历史，置信度75%，预测偏好：闲逛型、预算¥200"
    """
    data_points = prediction.get("data_points", 0)
    confidence = prediction.get("confidence", 0.0)

    if data_points == 0:
        return "新用户，无历史记录"

    if mode == "brief":
        return f"{data_points}条历史，置信{confidence:.0%}"

    parts = [f"匹配{data_points}条历史"]

    if mode == "detailed":
        parts.append(f"置信度{confidence:.0%}")

    pace = prediction.get("predicted_pace")
    if pace:
        parts.append(f"节奏「{pace}」")

    budget = prediction.get("predicted_budget", 0)
    if budget > 0:
        parts.append(f"预算¥{budget}")

    categories = prediction.get("predicted_categories", [])
    if categories:
        parts.append(f"偏好{'+'.join(categories[:2])}")

    emotion_need = prediction.get("predicted_emotion_need")
    if emotion_need and mode == "detailed":
        parts.append(f"情感需求「{emotion_need}」")

    return "，".join(parts)


# ── 用户状态解释 ─────────────────────────────────────────────────────

def explain_user_status(user_info: dict[str, Any], mode: str = "normal") -> str:
    """解释用户身份状态。

    参数:
        user_info: {"user_id": "小王", "is_new": False, "interaction_count": 5, ...}
        mode: "brief" | "normal" | "detailed"

    返回:
        "老用户「小王」，已交互5次"
    """
    user_id = user_info.get("user_id", "?")
    is_new = user_info.get("is_new", True)
    count = user_info.get("interaction_count", 0)

    if mode == "brief":
        status = "新" if is_new else "老"
        return f"{status}用户{count}次"

    status = "新用户" if is_new else "老用户"

    if mode == "detailed":
        context_info = user_info.get("context_info", "")
        if is_new:
            return f"{status}「{user_id}」，首次使用"
        else:
            msg = f"{status}「{user_id}」，已交互{count}次"
            if context_info:
                msg += f"，{context_info}"
            return msg

    if is_new:
        return f"{status}「{user_id}」"
    else:
        return f"{status}「{user_id}」，已交互{count}次"


# ── 综合解释 ─────────────────────────────────────────────────────────

def explain_weight_mapper_debug(data: dict[str, Any], mode: str = "normal") -> dict[str, str]:
    """综合解释 weight_mapper 调试信息。

    参数:
        data: {
            "demand_vector": {...},
            "computed_weights": {...},
            "user_deltas": {...},
            "summary": "..."
        }
        mode: "brief" | "normal" | "detailed"

    返回:
        {
            "demand_explanation": "追求高效打卡，偏好安静平和",
            "weights_explanation": "路线更紧凑高效",
            "deltas_explanation": "该用户比平均更看重效率",
            "summary": "一句话总结"
        }
    """
    demand_vector = data.get("demand_vector", {})
    computed_weights = data.get("computed_weights", {})
    user_deltas = data.get("user_deltas", {})

    demand_exp = explain_demand_vector(demand_vector, mode)
    weights_exp = explain_weights(computed_weights, mode)
    deltas_exp = explain_user_deltas(user_deltas, mode)

    # 生成一句话总结
    if mode == "brief":
        summary = f"需求:{demand_exp} | 权重:{weights_exp}"
    else:
        summary = f"需求分析：{demand_exp}。权重调整：{weights_exp}"
        if deltas_exp != "无个性化调整" and deltas_exp != "无显著个性化调整":
            summary += f"。个性化：{deltas_exp}"

    return {
        "demand_explanation": demand_exp,
        "weights_explanation": weights_exp,
        "deltas_explanation": deltas_exp,
        "summary": summary,
    }


def explain_memory_status(memory_status: dict[str, Any], mode: str = "normal") -> str:
    """解释记忆状态。

    参数:
        memory_status: {"message": "已记住偏好", "trip_count": 5}
        mode: "brief" | "normal" | "detailed"

    返回:
        "已记住偏好（累计5次行程）"
    """
    message = memory_status.get("message", "")
    trip_count = memory_status.get("trip_count", 0)

    if not message:
        return "等待记忆保存…"

    if mode == "brief":
        return f"{message}" if not trip_count else f"{message}({trip_count}次)"

    if mode == "detailed":
        return f"{message}（累计{trip_count}次行程记录）"

    return f"{message}" if not trip_count else f"{message}（累计{trip_count}次）"
