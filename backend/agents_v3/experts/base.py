"""Shared utilities for all MoE experts.

Extracted from agents.py so every expert (poi, food, hotel, traffic, weather,
local_expert, insurance) can import from a single place instead of duplicating
helpers.  Keep this module free of agent-specific business logic -- only
low-level building blocks live here.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import uuid

from openai import AsyncOpenAI

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Names containing any of these keywords should be treated as food POIs and
# excluded from poi_agent selection.
_FOOD_NAME_KWS = [
    "美食街", "海鲜街", "小吃街", "美食城", "美食广场", "食街",
    "夜市", "大排档", "海鲜城", "海鲜市场", "水产市场",
    "餐厅", "茶餐厅", "火锅", "烧烤", "甜品店", "奶茶",
]

# ---------------------------------------------------------------------------
# Food sub-intent detection
# ---------------------------------------------------------------------------


def _food_intent_hint(scene_reqs_text: str, user_input: str) -> str:
    """Generate extra prompt hints for food_agent based on user sub-intent.

    Detects food-related keywords in scene_requirements and user_input,
    guiding the LLM to prioritise the corresponding food type.
    """
    text = scene_reqs_text + " " + user_input
    hints = []

    if any(kw in text for kw in ["甜品", "奶茶", "冰室", "甜点", "蛋糕"]):
        hints.append("   - \u26a0\ufe0f 用户核心需求是吃甜品！优先选甜品店/奶茶/冰室/茶餐厅甜品档，正餐最多选1家")
    if any(kw in text for kw in ["海鲜", "生蚝", "虾", "蟹"]):
        hints.append("   - \u26a0\ufe0f 用户核心需求是吃海鲜！优先选海鲜排档/海鲜市场/海鲜餐厅，少选粉面粥")
    if any(kw in text for kw in ["小吃", "粉", "面", "粥", "排档", "扫街"]):
        hints.append("   - \u26a0\ufe0f 用户核心需求是吃小吃！优先选粉面粥/排档/夜市小吃，正餐酒楼最多1家")
    if any(kw in text for kw in ["夜宵", "深夜", "凌晨", "宵夜", "夜市"]):
        hints.append("   - \u26a0\ufe0f 用户是深夜觅食！优先选大排档/深夜营业场所，正餐餐厅可能已关门")
    if any(kw in text for kw in ["茶餐厅", "早茶", "点心"]):
        hints.append("   - \u26a0\ufe0f 用户想吃茶餐厅/早茶！优先选粤式茶餐厅，其他类型最多1家")

    if hints:
        return "\n6. \u3010用户子意图\u00b7最重要\u3011\n" + "\n".join(hints)
    return ""


# ---------------------------------------------------------------------------
# Proposal constructor
# ---------------------------------------------------------------------------


def _proposal(agent: str, content: dict, confidence: float, reasoning: str) -> dict:
    return {
        "proposal_id": f"prop_{agent}_{uuid.uuid4().hex[:6]}",
        "agent": agent,
        "content": content,
        "confidence": round(confidence, 3),
        "reasoning": reasoning,
    }


# ---------------------------------------------------------------------------
# POI data loader
# ---------------------------------------------------------------------------


async def _load_all_pois() -> list[dict]:
    """Fetch all POI data from the Meituan API, falling back to local JSON."""
    try:
        from backend.agents_v3.meituan_client import fetch_pois

        return await fetch_pois()
    except Exception:
        # API unavailable -- fall back to local JSON
        try:
            from backend.services.data_service import get_data

            data = get_data()
            if isinstance(data, dict):
                return list(data.values())
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []


# ---------------------------------------------------------------------------
# LLM client (singleton)
# ---------------------------------------------------------------------------

_llm_client: AsyncOpenAI | None = None


def _get_llm_client() -> AsyncOpenAI:
    """Return a reused AsyncOpenAI client (singleton)."""
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        )
    return _llm_client


# ---------------------------------------------------------------------------
# LLM decision helper
# ---------------------------------------------------------------------------


async def _llm_decide(system_prompt: str, user_prompt: str, retries: int = 2) -> dict | None:
    """Call DeepSeek LLM for a decision, returning structured JSON output."""
    client = _get_llm_client()
    for attempt in range(retries):
        try:
            resp = await client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "deepseek-chat"),
                messages=[
                    {"role": "system", "content": system_prompt + "\n你必须输出合法JSON。"},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
            text = resp.choices[0].message.content or ""
            return json.loads(text)
        except Exception:
            if attempt < retries - 1:
                await asyncio.sleep(1)
    return None


# ---------------------------------------------------------------------------
# Geography helpers
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the Haversine distance between two points in kilometres."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def _is_likely_macau(name: str) -> bool:
    """Heuristic: detect POIs that are actually in Macau (mislabelled in data)."""
    macau_keywords = [
        "Museu", "Casa", "Troço", "Posto", "Esplanada", "Muralhas", "Taipa",
        "Prémio", "Macau", "Wynn", "Grand", "Lisboa", "Venetian", "Parisian",
        "Morrisson", "Guia", "Penha", "Barra", "Patane",
        "博物館露天", "大賽車", "沙梨頭", "噴泉表演 Fountain",
        "海事博物館", "倫記軟滑", "永利名店", "吉祥樹表演",
        "龍環葡韻", "東方基金", "舊城牆遺址",
        # Common Macau food establishments
        "檸檬車露", "義順鮮奶", "禮記", "榮暉", "氹仔", "馬交",
        "葡國菜", "葡式", "葡撻", "車厘哥夫", "潘榮",
        "六記", "誠昌", "木糠", "杏仁餅",
    ]
    for kw in macau_keywords:
        if kw in name:
            return True
    # Check for heavy Latin content (Macau POIs are often bilingual)
    chinese_chars = sum(1 for c in name if "\u4e00" <= c <= "\u9fff")
    latin_chars = sum(1 for c in name if ("a" <= c <= "z") or ("A" <= c <= "Z"))
    if latin_chars > chinese_chars and latin_chars > 5:
        return True
    return False


# ---------------------------------------------------------------------------
# Tag similarity
# ---------------------------------------------------------------------------


def _tag_similarity(poi: dict, keywords: list[str]) -> float:
    """Compute similarity between a POI and a list of keywords via tag matching."""
    score = 0.0
    name = poi.get("name", "")
    cat = poi.get("category", "")
    tags = poi.get("tags", [])
    scene_tags = poi.get("_scene_tags", [])
    suitability = poi.get("_suitability", {})
    all_text = (
        f"{name} {cat} {' '.join(tags)} {' '.join(scene_tags)} "
        f"{' '.join(str(v) for v in suitability.values())}"
    )

    matched = 0
    for kw in keywords:
        if kw in all_text:
            matched += 1
    if keywords:
        score = matched / len(keywords)
    return score


# ---------------------------------------------------------------------------
# Known Zhuhai landmarks (used for scoring boosts)
# ---------------------------------------------------------------------------

_LANDMARK_NAMES = {
    "长隆海洋王国", "海洋王国", "珠海渔女", "情侣路", "圆明新园",
    "海滨泳场", "野狸岛", "日月贝", "珠海大剧院", "港珠澳大桥",
    "外伶仃岛", "淇澳岛", "飞沙滩", "金海滩", "御温泉",
    "唐家湾古镇", "梅溪牌坊", "农科奇观", "梦幻水城",
    "湾仔海鲜街", "拱北口岸",
}
