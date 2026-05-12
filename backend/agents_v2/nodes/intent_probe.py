"""Layer 1节点：意图探测与矛盾调解。

完整实现：
- Phase 1: 规则快速扫描（8种矛盾模式）
- Phase 2: LLM深度理解
- Phase 3: 追问生成
- Phase 4: 矛盾调解与子需求分解
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from backend.agents_v2.state import (
    FederatedState,
    IntentPackage,
    Contradiction,
    SubNeed,
    ProbeQuestion,
)


# ============================================================================
# 矛盾信号检测规则
# ============================================================================

CONTRADICTION_RULES = [
    {
        "type": "budget_vs_quality",
        "patterns": [
            (["五星", "豪华", "高端", "海景房"], lambda i, b: b < 200, "预算有限但提到高端需求"),
            (["长隆", "海洋王国"], lambda i, b: b < 100, "长隆门票约¥300+，预算不足"),
        ],
        "severity": "high",
        "resolution": "分解为核心体验(高预算)+辅助活动(节省)",
    },
    {
        "type": "group_vs_activity",
        "patterns": [
            (["蹦迪", "酒吧", "夜店", "喝酒"], lambda i, b: i.get("group", {}).get("type") == "亲子", "亲子群体与夜生活矛盾"),
            (["徒步", "爬山", "骑行"], lambda i, b: i.get("group", {}).get("type") == "退休", "高强度运动与老年群体矛盾"),
        ],
        "severity": "high",
        "resolution": "分时安排:家庭时段+成人时段",
    },
    {
        "type": "time_vs_coverage",
        "patterns": [
            (["遍", "吃遍", "玩遍", "打卡"], lambda i, b: "time" in i, "时间有限但想覆盖多处"),
        ],
        "severity": "medium",
        "resolution": "聚焦核心区域，减少景点数量",
    },
    {
        "type": "emotion_shift",
        "patterns": [
            (["安静", "独处", "宁静"], ["热闹", "刺激", "蹦迪"], "同时要求安静和热闹"),
        ],
        "severity": "medium",
        "resolution": "分时段设计情绪曲线",
    },
    {
        "type": "weather_activity_mismatch",
        "patterns": [
            (["雨天", "下雨", "大雨"], ["户外", "海边", "烧烤"], "雨天安排户外活动"),
        ],
        "severity": "high",
        "resolution": "替换为室内活动或增加天气保险",
    },
    {
        "type": "pace_coverage_mismatch",
        "patterns": [
            (["悠闲", "慢慢", "闲逛"], lambda i, b: "遍" in str(i), "悠闲节奏与全覆盖矛盾"),
        ],
        "severity": "low",
        "resolution": "减少景点数量，延长每个停留时间",
    },
    {
        "type": "accessibility_mismatch",
        "patterns": [
            (["婴儿车", "轮椅", "老人"], ["爬山", "徒步", "山"], "无障碍需求与山地活动矛盾"),
        ],
        "severity": "high",
        "resolution": "选择平地景点或有缆车的山区",
    },
    {
        "type": "emotion_group_mismatch",
        "patterns": [
            (["独处", "一个人", "安静"], lambda i, b: i.get("group", {}).get("size", 1) > 2, "独处需求与多人同行矛盾"),
        ],
        "severity": "medium",
        "resolution": "安排个人时间+团队活动交替",
    },
]


def detect_contradiction_signals(raw_input: str, intent: dict) -> list[dict]:
    """检测矛盾信号（8种模式）。"""
    signals = []
    budget = intent.get("budget", {}).get("per_person", 500)

    for rule in CONTRADICTION_RULES:
        for pattern in rule["patterns"]:
            # 检查是否匹配
            matched = False
            description = ""

            if len(pattern) == 3:
                # 模式: (关键词列表, 判断函数, 描述)
                keywords, condition, desc = pattern
                if isinstance(keywords, list):
                    if any(kw in raw_input for kw in keywords):
                        if callable(condition):
                            matched = condition(intent, budget)
                        description = desc
                elif isinstance(keywords, str) and keywords in raw_input:
                    if callable(condition):
                        matched = condition(intent, budget)
                    description = desc

            if matched:
                signals.append({
                    "type": rule["type"],
                    "severity": rule["severity"],
                    "description": description,
                    "resolution": rule["resolution"],
                })

    return signals


async def llm_deep_understanding(raw_input: str, intent: dict, signals: list) -> dict:
    """LLM深度理解矛盾和隐含需求。"""
    try:
        from backend.services.intent_parser import _call_llm

        prompt = f"""你是旅游需求分析专家。请分析以下用户需求，识别潜在的矛盾、隐含需求，并提供分解建议。

用户输入: {raw_input}

结构化意图: {intent}

已识别的矛盾信号: {signals}

请输出JSON格式:
{{
  "contradictions": [
    {{
      "type": "矛盾类型",
      "description": "详细描述",
      "severity": "high/medium/low",
      "conflicting_aspects": ["冲突点1", "冲突点2"],
      "resolution": "建议的解决方案"
    }}
  ],
  "latent_needs": ["隐含需求1", "隐含需求2"],
  "suggested_decomposition": [
    {{
      "id": "sub_need_1",
      "description": "子需求描述",
      "constraints": {{}},
      "priority": 1-10,
      "time_window": ["HH:MM", "HH:MM"]
    }}
  ]
}}"""

        result = await asyncio.wait_for(
            _call_llm(prompt),
            timeout=15.0
        )

        if result and "contradictions" in result:
            return result

    except Exception:
        pass

    # 降级：使用规则检测结果
    return {
        "contradictions": [],
        "latent_needs": [],
        "suggested_decomposition": [],
    }


def generate_probe_questions(signals: list, intent: dict) -> list[ProbeQuestion]:
    """生成追问问题。"""
    questions = []

    question_templates = {
        "budget_vs_quality": {
            "question": "您的预算有限，但提到了高品质需求。您更看重性价比，还是愿意为某个特别体验增加预算？",
            "options": ["性价比优先", "愿意为体验加预算", "给我推荐免费替代"],
        },
        "group_vs_activity": {
            "question": "您带着孩子/家人，但提到了成人活动。您希望平衡亲子时间和成人休闲吗？",
            "options": ["以亲子为主", "平衡两者", "分开安排"],
        },
        "emotion_shift": {
            "question": "您既想安静又想热闹。这是想分时段体验，还是看当天心情决定？",
            "options": ["上午安静下午热闹", "看心情", "都要兼顾"],
        },
        "time_vs_coverage": {
            "question": "时间有限但想玩遍多处。您更看重深度体验还是打卡数量？",
            "options": ["深度体验", "多打卡", "推荐最优平衡"],
        },
        "weather_activity_mismatch": {
            "question": "天气预报有雨，您提到的活动多为户外。是否需要准备室内替代方案？",
            "options": ["准备室内备选", "坚持户外", "看情况调整"],
        },
    }

    for signal in signals[:3]:  # 最多3个问题
        template = question_templates.get(signal["type"])
        if template:
            questions.append({
                "question_id": f"q_{uuid.uuid4().hex[:6]}",
                "question": template["question"],
                "options": template.get("options"),
                "related_contradiction": signal["type"],
            })

    return questions


def decompose_needs(intent: dict, contradictions: list, signals: list) -> list[SubNeed]:
    """将矛盾需求分解为子需求。"""
    sub_needs = []

    # 基础需求
    sub_needs.append({
        "id": "core",
        "description": "核心出行需求",
        "constraints": intent,
        "priority": 10,
        "time_window": None,
    })

    # 根据矛盾类型分解
    for i, contra in enumerate(contradictions + signals):
        contra_type = contra.get("type", "")

        if contra_type == "emotion_shift":
            # 情绪切换：分解为两个时段
            sub_needs.append({
                "id": f"sub_{i}_quiet",
                "description": "上午/前半段:安静体验",
                "constraints": {"emotion": "宁静", "activity_type": "静态"},
                "priority": 8,
                "time_window": ("09:00", "13:00"),
            })
            sub_needs.append({
                "id": f"sub_{i}_active",
                "description": "下午/后半段:热闹体验",
                "constraints": {"emotion": "兴奋", "activity_type": "动态"},
                "priority": 8,
                "time_window": ("14:00", "20:00"),
            })

        elif contra_type == "group_vs_activity":
            # 亲子vs成人：分时
            sub_needs.append({
                "id": f"sub_{i}_family",
                "description": "家庭时段:亲子活动",
                "constraints": {"group_type": "亲子", "time": "day"},
                "priority": 9,
                "time_window": ("09:00", "18:00"),
            })
            sub_needs.append({
                "id": f"sub_{i}_adult",
                "description": "成人时段:休闲活动",
                "constraints": {"group_type": "成人", "time": "night"},
                "priority": 7,
                "time_window": ("19:00", "22:00"),
            })

        elif contra_type == "budget_vs_quality":
            # 预算vs品质：核心+辅助
            sub_needs.append({
                "id": f"sub_{i}_core_exp",
                "description": "核心体验:值得投入",
                "constraints": {"priority": "high", "budget_ratio": 0.7},
                "priority": 9,
                "time_window": None,
            })
            sub_needs.append({
                "id": f"sub_{i}_aux_exp",
                "description": "辅助活动:节省预算",
                "constraints": {"priority": "low", "budget_ratio": 0.3, "free": True},
                "priority": 6,
                "time_window": None,
            })

    # 去重
    seen = set()
    unique = []
    for sn in sub_needs:
        if sn["id"] not in seen:
            seen.add(sn["id"])
            unique.append(sn)

    return unique[:10]  # 最多10个子需求


async def intent_probe_node(state: FederatedState) -> FederatedState:
    """Layer 1节点：意图探测与矛盾调解。"""
    try:
        raw_input = state["user_input"]

        # Step 1: 调用基础意图解析
        from backend.services.intent_parser import parse_intent
        from backend.services.user_profiles import USER_PROFILES

        base_intent = await parse_intent(raw_input, USER_PROFILES)

        # Step 2: 规则快速扫描
        signals = detect_contradiction_signals(raw_input, base_intent)

        # Step 3: LLM深度理解（异步，超时降级）
        llm_result = await llm_deep_understanding(raw_input, base_intent, signals)
        llm_contradictions = llm_result.get("contradictions", [])
        latent_needs = llm_result.get("latent_needs", [])
        llm_decomposition = llm_result.get("suggested_decomposition", [])

        # 合并矛盾
        all_contradictions = []
        seen_types = set()

        for c in llm_contradictions:
            all_contradictions.append({
                "type": c.get("type", "unknown"),
                "description": c.get("description", ""),
                "severity": c.get("severity", "medium"),
                "conflicting_aspects": c.get("conflicting_aspects", []),
                "resolution": c.get("resolution", ""),
            })
            seen_types.add(c.get("type"))

        for s in signals:
            if s["type"] not in seen_types:
                all_contradictions.append({
                    "type": s["type"],
                    "description": s["description"],
                    "severity": s["severity"],
                    "conflicting_aspects": [],
                    "resolution": s["resolution"],
                })

        # Step 4: 生成追问问题
        probe_questions = generate_probe_questions(signals + llm_contradictions, base_intent)
        state["probe_questions"] = probe_questions

        # Step 5: 分解子需求
        if llm_decomposition:
            decomposed = [
                {
                    "id": d.get("id", f"sub_{i}"),
                    "description": d.get("description", ""),
                    "constraints": d.get("constraints", {}),
                    "priority": d.get("priority", 5),
                    "time_window": tuple(d.get("time_window", [])) if d.get("time_window") else None,
                }
                for i, d in enumerate(llm_decomposition)
            ]
        else:
            decomposed = decompose_needs(base_intent, all_contradictions, signals)

        # 如果没有分解出子需求，使用核心意图
        if not decomposed:
            decomposed = [{
                "id": "core",
                "description": "核心出行需求",
                "constraints": base_intent,
                "priority": 10,
                "time_window": None,
            }]

        # 构建IntentPackage
        state["intent_package"] = {
            "core_intent": base_intent,
            "contradictions": all_contradictions,
            "decomposed_sub_needs": decomposed,
            "probe_questions": probe_questions,
            "latent_needs": latent_needs,
            "raw_input": raw_input,
        }

        return state

    except Exception as e:
        state["errors"].append(f"Layer1错误: {e}")
        # 降级：创建基础IntentPackage
        state["intent_package"] = {
            "core_intent": {},
            "contradictions": [],
            "decomposed_sub_needs": [{
                "id": "core",
                "description": "核心需求",
                "constraints": {},
                "priority": 10,
                "time_window": None,
            }],
            "probe_questions": [],
            "latent_needs": [],
            "raw_input": state["user_input"],
        }
        return state
