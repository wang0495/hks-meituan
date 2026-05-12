"""第一层：意图探测与矛盾调解网络。

包含:
- IntentProbe: 多轮意图探测智能体
- ContradictionMediator: 矛盾调解智能体
"""

from __future__ import annotations

import json
from typing import Any

from backend.agents_v2.state import FederatedState, IntentPackage, Contradiction, SubNeed


class IntentProbeAgent:
    """意图探测智能体 - 多轮深入理解用户需求。"""

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.max_probe_rounds = 3

    async def probe(self, user_input: str) -> dict[str, Any]:
        """多轮探测用户真实意图。"""
        # 简化实现：直接调用现有intent_parser
        from backend.services.intent_parser import parse_intent
        from backend.services.user_profiles import USER_PROFILES

        base_intent = await parse_intent(user_input, USER_PROFILES)

        # 提取潜在矛盾信号
        contradiction_signals = self._detect_signals(user_input, base_intent)

        return {
            "core_intent": base_intent,
            "signals": contradiction_signals,
            "probe_questions": self._generate_questions(base_intent, contradiction_signals),
        }

    def _detect_signals(self, raw_input: str, intent: dict) -> list[dict]:
        """检测潜在矛盾信号。"""
        signals = []

        # 信号1: 预算与需求矛盾
        budget = intent.get("budget", {}).get("per_person", 500)
        if budget < 100 and any(kw in raw_input for kw in ["五星", "豪华", "高端"]):
            signals.append({
                "type": "budget_demand_mismatch",
                "description": f"预算¥{budget}与高端需求矛盾",
            })

        # 信号2: 群体与活动矛盾
        group_type = intent.get("group", {}).get("type", "")
        if group_type == "亲子" and any(kw in raw_input for kw in ["蹦迪", "酒吧", "夜店"]):
            signals.append({
                "type": "group_activity_mismatch",
                "description": "亲子群体与夜生活活动矛盾",
            })

        # 信号3: 时间与覆盖矛盾
        time_info = intent.get("time", {})
        start = time_info.get("start", "09:00")
        end = time_info.get("end", "22:00")
        if any(kw in raw_input for kw in ["遍", "吃遍", "玩遍"]):
            signals.append({
                "type": "time_coverage_mismatch",
                "description": f"时间有限({start}-{end})但想覆盖多处",
            })

        # 信号4: 情绪矛盾（感性vs理性）
        if any(kw in raw_input for kw in ["安静", "独处", "安静"]) and \
           any(kw in raw_input for kw in ["热闹", "刺激", "蹦迪"]):
            signals.append({
                "type": "emotion_contradiction",
                "description": "同时要求安静和热闹",
            })

        return signals

    def _generate_questions(self, intent: dict, signals: list) -> list[str]:
        """根据信号生成追问问题。"""
        questions = []

        for sig in signals:
            if sig["type"] == "budget_demand_mismatch":
                questions.append("您的预算有限，但提到了高端需求。您更看重性价比，还是愿意为某个特别体验增加预算？")
            elif sig["type"] == "group_activity_mismatch":
                questions.append("带孩子出行但提到了夜生活。您希望平衡亲子活动和家长休闲时间吗？")
            elif sig["type"] == "time_coverage_mismatch":
                questions.append("时间有限但想玩遍多处。您更看重深度体验还是打卡数量？")
            elif sig["type"] == "emotion_contradiction":
                questions.append("您既想安静又想热闹。这是想分时段体验（上午安静下午热闹），还是主要看 mood？")

        return questions


class ContradictionMediatorAgent:
    """矛盾调解智能体 - 识别、分解、标注矛盾。"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def mediate(
        self,
        core_intent: dict,
        signals: list[dict],
        raw_input: str
    ) -> IntentPackage:
        """调解矛盾，输出带标注的意图包。"""

        # 识别矛盾
        contradictions = self._identify_contradictions(signals, raw_input)

        # 分解子需求
        sub_needs = self._decompose_needs(core_intent, contradictions, raw_input)

        return {
            "core_intent": core_intent,
            "contradictions": contradictions,
            "decomposed_sub_needs": sub_needs,
            "raw_input": raw_input,
        }

    def _identify_contradictions(
        self,
        signals: list[dict],
        raw_input: str
    ) -> list[Contradiction]:
        """识别具体矛盾。"""
        contradictions = []

        for sig in signals:
            if sig["type"] == "budget_demand_mismatch":
                contradictions.append({
                    "type": "budget_vs_quality",
                    "description": sig["description"],
                    "resolution": "建议分解为'核心体验(高预算)'+'辅助活动(节省)'",
                })
            elif sig["type"] == "group_activity_mismatch":
                contradictions.append({
                    "type": "group_vs_activity",
                    "description": sig["description"],
                    "resolution": "建议分时安排:亲子时段+成人时段",
                })
            elif sig["type"] == "emotion_contradiction":
                contradictions.append({
                    "type": "emotion_shift",
                    "description": sig["description"],
                    "resolution": "建议分时段设计情绪曲线",
                })
            elif sig["type"] == "time_coverage_mismatch":
                contradictions.append({
                    "type": "time_vs_coverage",
                    "description": sig["description"],
                    "resolution": "建议聚焦核心区域，放弃全面覆盖",
                })

        return contradictions

    def _decompose_needs(
        self,
        core_intent: dict,
        contradictions: list[Contradiction],
        raw_input: str
    ) -> list[SubNeed]:
        """将矛盾需求分解为子需求。"""
        sub_needs = []

        # 基础需求
        sub_needs.append({
            "id": "base_001",
            "description": "核心活动安排",
            "constraints": core_intent,
            "priority": 10,
        })

        # 根据矛盾类型分解
        for i, contra in enumerate(contradictions):
            if contra["type"] == "emotion_shift":
                # 情绪切换：分解为两个时段
                sub_needs.append({
                    "id": f"sub_{i}_a",
                    "description": "上午/前半段:安静独处",
                    "constraints": {"emotion": "宁静", "activity_type": "静态"},
                    "priority": 8,
                })
                sub_needs.append({
                    "id": f"sub_{i}_b",
                    "description": "下午/后半段:热闹刺激",
                    "constraints": {"emotion": "兴奋", "activity_type": "动态"},
                    "priority": 8,
                })
            elif contra["type"] == "group_vs_activity":
                # 亲子vs夜生活：分时
                sub_needs.append({
                    "id": f"sub_{i}_family",
                    "description": "亲子时段:白天活动",
                    "constraints": {"group": "亲子", "time": "day"},
                    "priority": 9,
                })
                sub_needs.append({
                    "id": f"sub_{i}_adult",
                    "description": "成人时段:夜间活动",
                    "constraints": {"group": "成人", "time": "night"},
                    "priority": 7,
                })
            elif contra["type"] == "budget_vs_quality":
                # 预算vs品质：核心+辅助
                sub_needs.append({
                    "id": f"sub_{i}_core",
                    "description": "核心体验:值得花钱",
                    "constraints": {"priority": "high", "budget_ratio": 0.7},
                    "priority": 9,
                })
                sub_needs.append({
                    "id": f"sub_{i}_aux",
                    "description": "辅助活动:节省预算",
                    "constraints": {"priority": "low", "budget_ratio": 0.3},
                    "priority": 6,
                })

        return sub_needs


# LangGraph节点函数
async def layer1_intent_node(state: FederatedState) -> FederatedState:
    """第一层节点：意图探测+矛盾调解。"""
    try:
        # 意图探测
        probe_agent = IntentProbeAgent()
        probe_result = await probe_agent.probe(state["user_input"])

        # 矛盾调解
        mediator = ContradictionMediatorAgent()
        intent_package = await mediator.mediate(
            probe_result["core_intent"],
            probe_result["signals"],
            state["user_input"]
        )

        state["intent_package"] = intent_package
        return state

    except Exception as e:
        state["errors"].append(f"Layer1错误: {e}")
        # 降级：返回基础意图
        from backend.services.intent_parser import parse_intent
        from backend.services.user_profiles import USER_PROFILES

        base_intent = await parse_intent(state["user_input"], USER_PROFILES)
        state["intent_package"] = {
            "core_intent": base_intent,
            "contradictions": [],
            "decomposed_sub_needs": [],
            "raw_input": state["user_input"],
        }
        return state
