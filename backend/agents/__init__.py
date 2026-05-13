"""CityFlow Multi-Agent路线规划系统

架构:
- Agent1: IntentAgent - 意图理解 + 不可能需求检测
- Agent2: POIAgent - POI语义筛选评分
- Agent3: RouteAgent - 路线规划 + 合理性检查
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

# 加载.env中的LLM配置
def _load_llm_env():
    """确保.env中的LLM变量加载到os.environ"""
    if os.environ.get("_AGENT_ENV_LOADED"):
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
    os.environ["_AGENT_ENV_LOADED"] = "1"


_load_llm_env()

# DeepSeek V4 Flash配置
DEEPSEEK_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
DEEPSEEK_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")


def get_llm(model: str = DEEPSEEK_MODEL, temperature: float = 0.1) -> ChatOpenAI:
    """获取DeepSeek LLM实例"""
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        base_url=DEEPSEEK_BASE_URL,
        api_key=DEEPSEEK_API_KEY,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


# ---------------------------------------------------------------------------
# Agent 1: Intent Understanding Agent
# ---------------------------------------------------------------------------


class IntentAgent:
    """意图理解Agent

    任务:
    1. 深度理解用户自然语言意图
    2. 判断是否不可能需求(常识推理)
    3. 提取核心场景关键词(替代硬编码同义词表)
    4. 推荐合适区域/商圈
    """

    SYSTEM_PROMPT = """你是CityFlow路线规划系统的意图理解Agent。

你的任务是深度理解用户的出行意图，并输出结构化的分析结果。

【核心能力】
1. 常识判断: 判断用户需求是否可实现
   - "50元住五星海景房" → impossible (预算严重不足)
   - "凌晨吃宵夜" → possible (合理需求)
   - "3小时从拱北玩遍横琴" → impossible (距离太远)

2. 场景关键词提取: 从模糊描述中提取核心场景
   - "蹦迪" → ["酒吧", "夜店", "LiveHouse", "音乐现场", "夜生活"]
   - "长隆" → ["主题乐园", "海洋王国", "水上乐园", "动物表演"]
   - "看海日出" → ["海滨", "日出观景点", "情侣路", "沙滩", "灯塔"]

3. 区域推荐: 根据场景推荐合适商圈
   - 夜生活 → 拱北、夏湾夜市
   - 主题乐园 → 横琴长隆
   - 文化打卡 → 香洲老城区

【输出格式】严格输出JSON:
{
  "is_impossible": true/false,
  "impossible_reason": "如果不可能，说明原因",
  "alternative_suggestion": "如果不可能，给出替代建议",
  "core_scene": "核心场景类型(夜生活/亲子/文化/美食...)",
  "scene_keywords": ["关键词1", "关键词2", ...],
  "preferred_zones": ["推荐区域1", "推荐区域2"],
  "time_constraint": {
    "is_late_night": true/false,
    "preferred_start": "HH:MM",
    "preferred_end": "HH:MM"
  },
  "budget_constraint": {
    "is_tight": true/false,
    "suggested_per_person": 金额整数
  },
  "group_type": "独居/情侣/亲子/朋友/退休",
  "emotion_expectation": "放松/刺激/浪漫/安静..."
}

【示例】
用户: "凌晨2点想吃宵夜，便宜点的"
输出:
{
  "is_impossible": false,
  "core_scene": "深夜美食",
  "scene_keywords": ["夜市", "大排档", "烧烤", "宵夜", "24小时营业", "便宜实惠"],
  "preferred_zones": ["拱北夏湾夜市", "湾仔海鲜街"],
  "time_constraint": {"is_late_night": true, "preferred_start": "02:00", "preferred_end": "05:00"},
  "budget_constraint": {"is_tight": true, "suggested_per_person": 50},
  "group_type": "独居",
  "emotion_expectation": "轻松随性"
}

用户: "50块钱住五星级海景房"
输出:
{
  "is_impossible": true,
  "impossible_reason": "五星级海景房通常800-1500元/晚，50元预算严重不足",
  "alternative_suggestion": "可考虑青年旅舍(约80-150元)或钟点房，或改为白天游玩海滨景点",
  "core_scene": "住宿",
  "scene_keywords": ["经济型住宿", "青年旅舍"],
  "preferred_zones": [],
  "budget_constraint": {"is_tight": true, "suggested_per_person": 100}
}
"""

    def __init__(self, llm: ChatOpenAI | None = None):
        self.llm = llm or get_llm()

    async def analyze(self, user_input: str) -> dict[str, Any]:
        """分析用户意图"""
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"用户: {user_input}"),
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content

        try:
            # 解析JSON
            result = json.loads(content)
            result["_agent"] = "IntentAgent"
            result["_raw_input"] = user_input
            return result
        except json.JSONDecodeError:
            # JSON解析失败，返回默认结构
            return {
                "is_impossible": False,
                "core_scene": "通用休闲",
                "scene_keywords": [],
                "preferred_zones": [],
                "_agent": "IntentAgent",
                "_raw_input": user_input,
                "_parse_error": content[:200],
            }


# ---------------------------------------------------------------------------
# Agent 2: POI Screening Agent
# ---------------------------------------------------------------------------


class POIAgent:
    """POI筛选Agent

    任务:
    1. 基于IntentAgent输出的scene_keywords进行语义匹配
    2. 对候选POI进行LLM评分(替代硬编码同义词表)
    3. 过滤不符合场景的POI
    """

    SYSTEM_PROMPT = """你是CityFlow路线规划系统的POI筛选Agent。

你的任务是根据用户场景意图，对候选POI进行语义匹配评分。

【评分规则】
1. 场景匹配度(0-10):
   - 完全匹配核心场景 → 9-10分
   - 部分匹配 → 6-8分
   - 不相关 → 0-3分

2. 营业时间匹配:
   - 覆盖用户时段 → +2分
   - 不覆盖 → 0分(可能排除)

3. 价格合理性:
   - 符合预算 → +1分
   - 超预算 → -2分

4. 区域匹配:
   - 在推荐区域内 → +1分

【输出格式】严格输出JSON:
{
  "scored_pois": [
    {"id": "poi_xxx", "name": "POI名", "score": 8.5, "reason": "匹配原因"},
    ...
  ],
  "excluded_pois": [
    {"id": "poi_yyy", "name": "POI名", "reason": "排除原因"},
    ...
  ],
  "top_recommendations": ["poi_xxx", "poi_zzz", ...]
}

【重要】
- 只评分，不修改POI数据
- score为0-10的浮点数
- 排除原因要具体(如"营业时间不覆盖凌晨时段")
"""

    def __init__(self, llm: ChatOpenAI | None = None):
        self.llm = llm or get_llm()

    async def score_pois(
        self, intent_result: dict[str, Any], candidates: list[dict[str, Any]], max_score: int = 30
    ) -> dict[str, Any]:
        """对候选POI进行评分"""

        # 构建候选POI描述(简化版本，避免token过多)
        poi_descriptions = []
        for p in candidates[:100]:  # 最多评分100个
            desc = {
                "id": p.get("id", "?"),
                "name": p.get("name", "?"),
                "category": p.get("category", "?"),
                "tags": p.get("tags", [])[:3],  # 只取前3个标签
                "business_hours": p.get("business_hours", "?"),
                "avg_price": p.get("avg_price", 0),
                "lat": round(p.get("lat", 0), 3),
                "lng": round(p.get("lng", 0), 3),
            }
            poi_descriptions.append(desc)

        user_prompt = f"""用户场景分析:
{json.dumps(intent_result, ensure_ascii=False, indent=2)}

候选POI列表(共{len(poi_descriptions)}个):
{json.dumps(poi_descriptions, ensure_ascii=False, indent=2)}

请对每个POI进行场景匹配评分，输出JSON结果。"""

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content

        try:
            result = json.loads(content)
            result["_agent"] = "POIAgent"
            return result
        except json.JSONDecodeError:
            # 解析失败，返回默认评分(所有POI给5分)
            return {
                "scored_pois": [{"id": p.get("id"), "name": p.get("name"), "score": 5.0, "reason": "LLM评分失败，默认分数"} for p in candidates[:max_score]],
                "excluded_pois": [],
                "top_recommendations": [p.get("id") for p in candidates[:10]],
                "_agent": "POIAgent",
                "_parse_error": content[:200],
            }


# ---------------------------------------------------------------------------
# Agent 2.5: Feasibility Agent (场景可行性检测)
# ---------------------------------------------------------------------------


class FeasibilityAgent:
    """场景可行性检测Agent

    任务:
    1. 推理用户需求需要什么类型的POI/场所
    2. 检查数据库中是否存在这类POI
    3. 判断需求是否可行/部分可行/不可行
    4. 给出替代建议
    """

    SYSTEM_PROMPT = """你是CityFlow路线规划系统的场景可行性检测Agent。

你的任务是判断用户的场景需求在当前城市是否可实现。

【推理步骤】
1. 分析用户核心需求需要什么类型的场所
   例: "蹦迪" → 需要酒吧/夜店/KTV/LiveHouse
   例: "拍霓虹灯" → 需要商业区/地标建筑/城市灯光带
   例: "游乐园海洋馆" → 需要主题乐园/海洋馆/水上乐园

2. 根据提供的POI统计数据，判断是否存在匹配场所

3. 给出可行性判断:
   - feasible: 完全可行，有足够匹配POI
   - partial: 部分可行，有相关但不完全匹配的POI
   - infeasible: 不可行，缺乏必要POI

【输出格式】严格输出JSON:
{
  "feasibility": "feasible/partial/infeasible",
  "required_poi_types": ["类型1", "类型2"],
  "found_poi_count": 数字,
  "reason": "判断原因",
  "alternative_suggestion": "如果不可行或部分可行，给出替代建议",
  "partial_match_types": ["部分匹配的POI类型"],
  "confidence": 0.0-1.0
}

【示例】
用户: "下午想蹦迪"
POI统计: {"酒吧": 0, "夜店": 0, "KTV": 3, "LiveHouse": 0}
输出:
{
  "feasibility": "partial",
  "required_poi_types": ["酒吧", "夜店", "KTV", "LiveHouse"],
  "found_poi_count": 3,
  "reason": "珠海暂无专业酒吧/夜店，但有3家KTV可提供类似娱乐体验",
  "alternative_suggestion": "可前往KTV唱歌，或建议前往澳门体验更丰富的夜生活",
  "partial_match_types": ["KTV"],
  "confidence": 0.7
}
"""

    def __init__(self, llm: ChatOpenAI | None = None):
        self.llm = llm or get_llm()

    async def check_feasibility(
        self,
        user_input: str,
        intent_result: dict[str, Any],
        poi_stats: dict[str, int],
    ) -> dict[str, Any]:
        """检查场景可行性

        Args:
            user_input: 用户原始输入
            intent_result: IntentAgent的分析结果
            poi_stats: POI分类统计 {"category": count}

        Returns:
            可行性判断结果
        """
        user_prompt = f"""用户需求: {user_input}

意图分析结果:
{json.dumps(intent_result, ensure_ascii=False, indent=2)}

当前城市POI分类统计:
{json.dumps(poi_stats, ensure_ascii=False, indent=2)}

请判断该需求在当前城市是否可实现，输出JSON结果。"""

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content

        try:
            result = json.loads(content)
            result["_agent"] = "FeasibilityAgent"
            return result
        except json.JSONDecodeError:
            return {
                "feasibility": "feasible",  # 默认可行，让后续流程处理
                "required_poi_types": [],
                "found_poi_count": 0,
                "reason": "可行性检测失败，默认继续规划",
                "alternative_suggestion": "",
                "confidence": 0.5,
                "_agent": "FeasibilityAgent",
                "_parse_error": content[:200],
            }


# ---------------------------------------------------------------------------
# Agent 3: Route Planning Agent (合理性检查)
# ---------------------------------------------------------------------------


class RouteAgent:
    """路线规划Agent

    任务:
    1. 对已生成的路线进行合理性检查
    2. 发现问题并提出修正建议
    3. 验证是否符合用户核心意图
    """

    SYSTEM_PROMPT = """你是CityFlow路线规划系统的路线审核Agent。

你的任务是审核生成的路线是否合理，是否符合用户意图。

【审核维度】
1. 意图匹配: 路线是否满足用户核心需求
   - 用户要"蹦迪"但选了博物馆 → ❌ 严重偏离
   - 用户要"便宜宵夜"但选了109元咖啡馆 → ❌ 预算不符

2. 时间合理性:
   - 营业时间是否覆盖用户时段
   - 行程时长是否合理

3. 地理连续性:
   - 是否有明显绕路(单站>25km)
   - 是否跨区跳跃不合理

4. 场景多样性:
   - 是否过于单一(全是餐饮)
   - 是否缺少必要配套(如餐饮/休息)

【输出格式】严格输出JSON:
{
  "is_valid": true/false,
  "issues": [
    {"type": "intent_mismatch", "severity": "high/medium/low", "description": "问题描述", "suggestion": "修正建议"},
    ...
  ],
  "overall_score": 0-10,
  "summary": "整体评价",
  "alternative_stations": [
    {"index": 2, "original": "原POI名", "suggested": "建议替换POI名", "reason": "替换原因"}
  ]
}
"""

    def __init__(self, llm: ChatOpenAI | None = None):
        self.llm = llm or get_llm()

    async def review_route(
        self, intent_result: dict[str, Any], route: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """审核路线合理性"""

        # 构建路线描述
        route_description = []
        for i, step in enumerate(route):
            poi = step.get("poi", {})
            route_description.append(
                {
                    "index": i + 1,
                    "name": poi.get("name", "?"),
                    "category": poi.get("category", "?"),
                    "tags": poi.get("tags", [])[:3],
                    "business_hours": poi.get("business_hours", "?"),
                    "avg_price": poi.get("avg_price", 0),
                    "arrival_time": step.get("arrival_time", "?"),
                    "departure_time": step.get("departure_time", "?"),
                }
            )

        user_prompt = f"""用户场景分析:
{json.dumps(intent_result, ensure_ascii=False, indent=2)}

生成路线(共{len(route_description)}站):
{json.dumps(route_description, ensure_ascii=False, indent=2)}

请审核路线合理性，输出JSON结果。"""

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content

        try:
            result = json.loads(content)
            result["_agent"] = "RouteAgent"
            return result
        except json.JSONDecodeError:
            return {
                "is_valid": True,
                "issues": [],
                "overall_score": 6,
                "summary": "LLM审核失败，默认通过",
                "_agent": "RouteAgent",
                "_parse_error": content[:200],
            }


# ---------------------------------------------------------------------------
# Multi-Agent Pipeline
# ---------------------------------------------------------------------------


async def run_agent_pipeline(
    user_input: str, candidates: list[dict[str, Any]], llm: ChatOpenAI | None = None
) -> dict[str, Any]:
    """运行完整的Agent流水线

    Args:
        user_input: 用户自然语言输入
        candidates: 原始POI候选列表
        llm: LLM实例(可选)

    Returns:
        {
            "intent": IntentAgent结果,
            "poi": POIAgent结果,
            "filtered_candidates": 经过Agent筛选的候选,
            "is_impossible": 是否不可能需求
        }
    """
    llm = llm or get_llm()

    # Agent 1: 意图理解
    intent_agent = IntentAgent(llm)
    intent_result = await intent_agent.analyze(user_input)

    # 如果是不可能需求，直接返回，不需要后续Agent
    if intent_result.get("is_impossible"):
        return {
            "intent": intent_result,
            "poi": None,
            "filtered_candidates": [],
            "is_impossible": True,
            "impossible_reason": intent_result.get("impossible_reason"),
            "alternative_suggestion": intent_result.get("alternative_suggestion"),
        }

    # Agent 2: POI评分筛选
    poi_agent = POIAgent(llm)
    poi_result = await poi_agent.score_pois(intent_result, candidates)

    # 根据评分过滤候选
    scored_pois = poi_result.get("scored_pois", [])
    top_ids = set(poi_result.get("top_recommendations", []))

    # 按分数排序
    scored_dict = {p["id"]: p.get("score", 5) for p in scored_pois}
    filtered = []
    for p in candidates:
        p_id = p.get("id")
        if p_id in top_ids or p_id in scored_dict:
            p["_agent_score"] = scored_dict.get(p_id, 5)
            filtered.append(p)

    # 按评分排序
    filtered.sort(key=lambda p: p.get("_agent_score", 0), reverse=True)

    return {
        "intent": intent_result,
        "poi": poi_result,
        "filtered_candidates": filtered[:30],  # 最多30个候选
        "is_impossible": False,
    }


# ---------------------------------------------------------------------------
# 新的LangGraph多智能体系统 (2026-05-12)
# ---------------------------------------------------------------------------

try:
    from backend.agents.graph import build_graph, get_graph
    from backend.agents.state import (
        PlanningState,
        AgentIssue,
        ValidatorResult,
        ArbitrationResult,
    )
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    build_graph = None
    get_graph = None


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

__all__ = [
    # 旧Agent系统 (保持兼容)
    "IntentAgent",
    "FeasibilityAgent",
    "POIAgent",
    "RouteAgent",
    "run_agent_pipeline",
    "get_llm",
    # 新LangGraph系统
    "build_graph",
    "get_graph",
    "PlanningState",
    "AgentIssue",
    "ValidatorResult",
    "ArbitrationResult",
    "LANGGRAPH_AVAILABLE",
]