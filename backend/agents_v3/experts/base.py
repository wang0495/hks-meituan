"""Shared utilities for all MoE experts.

Extracted from agents.py so every expert (poi, food, hotel, traffic, weather,
local_expert, insurance) can import from a single place instead of duplicating
helpers.  Keep this module free of agent-specific business logic -- only
low-level building blocks live here.

═════════════════════════════════════════════════════════════
  架构决策记录（ADR）
═════════════════════════════════════════════════════════════

ADR-B1: LLM client池必须用prefix参数化，不用单例
  - 原来：4个文件各自有独立的AsyncOpenAI client（agents.py, expert_router.py,
    rule_guard.py, review.py），共~190行重复代码
  - 问题1：rule_guard每次调用都new一个client（不是singleton），浪费连接
  - 问题2：review.py、expert_router.py只读LLM_*不读EXPERT_LLM_*，无法按节点分模型
  - 修复：统一到_llm_clients池，prefix="EXPERT_LLM"读qwen3.5-flash，
    prefix="LLM"读DeepSeek。所有节点通过_llm_decide(prefix=...)指定模型

ADR-B2: _extract_json 必须校验返回类型
  - LLM有时返回 {"picks": ["景点名"]} 而非 {"picks": [{"name": "景点名"}]}
  - 导致下游 pick.get("name") 调用 str.get → AttributeError 间歇性崩溃
  - 修复：_extract_json 检查 json.loads 结果必须是dict，否则 raise ValueError
  - 同步修复：_llm_decide 中过滤非dict列表项，防御 str 被当成 dict

ADR-B3: 不要把expert规则化来省LLM调用
  - 尝试过：把hotel/traffic/weather/destination/budget_hacker改为纯规则（不调LLM）
  - 失败：这些expert在baseline用的是qwen3.5-flash（不是DeepSeek），
    规则化不是"省一个DeepSeek调用"，而是"用规则替代qwen3.5-flash的智能"
  - 效果：从4/5通过(6.8)降到3-4/5通过(6.4-6.6)
  - 教训：先搞清楚baseline用的什么模型再优化，不要假设"规则化=省成本"
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import math
import re as _re
import time
import uuid

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM response cache (in-memory, TTL-based)
# ---------------------------------------------------------------------------

_llm_cache: dict[str, tuple[dict, float]] = {}  # key -> (result, timestamp)
_LLM_CACHE_TTL = 300  # 5 minutes


def _llm_cache_key(system_prompt: str, user_prompt: str, prefix: str, temperature: float) -> str:
    """Generate a deterministic cache key for an LLM call."""
    model = _llm_model(prefix)
    raw = f"{model}|{temperature}|{system_prompt}|{user_prompt}"
    return hashlib.md5(raw.encode()).hexdigest()


def _llm_cache_get(key: str) -> dict | None:
    """Check LLM cache; return result if still valid."""
    entry = _llm_cache.get(key)
    if entry is None:
        return None
    result, ts = entry
    if time.monotonic() - ts > _LLM_CACHE_TTL:
        del _llm_cache[key]
        return None
    return result


def _llm_cache_set(key: str, result: dict) -> None:
    """Store LLM result in cache."""
    _llm_cache[key] = (result, time.monotonic())
    # Evict expired entries if cache grows too large
    if len(_llm_cache) > 500:
        now = time.monotonic()
        expired = [k for k, (_, ts) in _llm_cache.items() if now - ts > _LLM_CACHE_TTL]
        for k in expired:
            del _llm_cache[k]


from backend.agents_v3.state import AGENT_META, sse_emit  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Names containing any of these keywords should be treated as food POIs and
# excluded from poi_agent selection.
_FOOD_NAME_KWS = [
    "美食街",
    "海鲜街",
    "小吃街",
    "美食城",
    "美食广场",
    "食街",
    "夜市",
    "大排档",
    "海鲜城",
    "海鲜市场",
    "水产市场",
    "餐厅",
    "茶餐厅",
    "火锅",
    "烧烤",
    "甜品店",
]


# Food subcategory definitions for diversity checking
_FOOD_SUBCATS: dict[str, list[str]] = {
    "海鲜": ["海鲜", "蚝", "鱼排", "渔港"],
    "正餐": ["餐厅", "烧", "煲", "火锅", "烧烤"],
    "小吃": ["粉", "面", "粥", "小吃", "排档"],
    "茶餐厅/甜品": ["茶餐厅", "甜品", "奶茶", "冰", "柠檬", "饮品"],
    "综合美食街": ["夜市", "美食街", "海鲜街", "老街"],
}
_FOOD_CATEGORIES = {"餐饮", "美食", "小吃", "夜市"}
_FOOD_KEYWORDS = ["餐厅", "海鲜", "粉", "面", "粥", "甜品", "茶餐厅", "烧烤", "火锅", "夜市"]
_LIANGCHA_KEYWORDS = {"凉茶", "草本", "龟苓膏"}


# ---------------------------------------------------------------------------
# Prompt injection sanitization
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = [
    # English injection phrases
    r"(?i)ignore\s+(all\s+)?previous\s+instructions",
    r"(?i)ignore\s+(all\s+)?above",
    r"(?i)forget\s+(everything|all|your\s+instructions)",
    r"(?i)you\s+are\s+now\s+(?:a|an)\s+",
    r"(?i)act\s+as\s+(?:if\s+)?you\s+(?:are|were)\s+",
    r"(?i)pretend\s+(?:that\s+)?you\s+(?:are|were)\s+",
    r"(?i)do\s+not\s+follow\s+(?:your|the)\s+instructions",
    r"(?i)new\s+instructions?\s*:",
    r"(?i)system\s*:\s*",
    r"(?i)override\s+(?:previous|all|default)\s+",
    # Chinese injection phrases
    r"忽略(所有|以上|之前的)?指令",
    r"不要(遵守|遵循)(你的|系统)?指令",
    r"假装你是",
    r"你现在是一个",
    r"新指令\s*[：:]",
    r"系统\s*[：:]",
    r"覆盖(之前的|原有)?指令",
    r"从现在开始(你是|你扮演)",
    # DAN-style
    r"(?i)do\s+anything\s+now",
    r"(?i)DAN\s*(?:mode|jailbreak)",
]

# ---------------------------------------------------------------------------
# ML-based injection scanner (optional, lazy-loaded)
# ---------------------------------------------------------------------------

_ML_SCANNER = None  # lazily initialised PromptInjection scanner
_ML_SCANNER_LOADED = False
_ML_INJECTION_THRESHOLD = 0.85  # only block at high confidence


def _get_ml_scanner():
    """Lazy-load the llm-guard PromptInjection scanner.

    Returns None if llm-guard is not installed or the model is not cached,
    so the system gracefully degrades to regex-only defense.
    Pre-download: python -c "from llm_guard.input_scanners import PromptInjection; PromptInjection()"
    """
    global _ML_SCANNER, _ML_SCANNER_LOADED
    if _ML_SCANNER_LOADED:
        return _ML_SCANNER
    _ML_SCANNER_LOADED = True
    try:
        # Quick local-cache check — skip if model not already downloaded
        from pathlib import Path as _Path

        from llm_guard.input_scanners import PromptInjection

        _hf_cache = _Path.home() / ".cache" / "huggingface" / "hub"
        _cached = (
            any("prompt-injection" in p.name for p in _hf_cache.glob("models--*"))
            if _hf_cache.exists()
            else False
        )
        if not _cached:
            logger.debug("llm-guard model not cached, ML injection scan disabled")
            return None
        _ML_SCANNER = PromptInjection()
        logger.info("llm-guard PromptInjection scanner loaded")
    except ImportError:
        logger.debug("llm-guard not installed, ML injection scan disabled")
    except Exception as e:
        logger.debug("llm-guard scanner unavailable: %s", e)
    return _ML_SCANNER


def _ml_injection_check(text: str) -> tuple[bool, float]:
    """Run ML-based injection check. Returns (is_safe, risk_score).

    is_safe=True means the text looks clean.
    risk_score in [0, 1] — higher means more likely injection.
    Fails open: on any error returns (True, 0.0).
    """
    scanner = _get_ml_scanner()
    if scanner is None:
        return True, 0.0
    try:
        _, is_valid, risk_score = scanner.scan(text)
        return is_valid, risk_score
    except Exception as e:
        logger.warning("ML injection scan error: %s", e)
        return True, 0.0


def _sanitize_for_prompt(text: str) -> str:
    """Sanitize user input before including in LLM prompt.

    Layer 1: regex-based pattern removal (fast, always available).
    Layer 2: ML-based injection detection via llm-guard (optional).
    The primary defense remains structured JSON output parsing
    in _extract_json and the rule_guard validation.
    """
    if not isinstance(text, str):
        return str(text)
    sanitized = text
    for pattern in _INJECTION_PATTERNS:
        sanitized = _re.sub(pattern, "[已过滤]", sanitized)
    # Truncate to prevent context window abuse
    if len(sanitized) > 500:
        sanitized = sanitized[:500] + "...[截断]"
    return sanitized


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
        hints.append(
            "   - \u26a0\ufe0f 用户核心需求是吃甜品！优先选甜品店/奶茶/冰室/茶餐厅甜品档，正餐最多选1家"
        )
    if any(kw in text for kw in ["海鲜", "生蚝", "虾", "蟹"]):
        hints.append(
            "   - \u26a0\ufe0f 用户核心需求是吃海鲜！优先选海鲜排档/海鲜市场/海鲜餐厅，少选粉面粥"
        )
    if any(kw in text for kw in ["小吃", "粉", "面", "粥", "排档", "扫街"]):
        hints.append(
            "   - \u26a0\ufe0f 用户核心需求是吃小吃！优先选粉面粥/排档/夜市小吃，正餐酒楼最多1家"
        )
    if any(kw in text for kw in ["夜宵", "深夜", "凌晨", "宵夜", "夜市"]):
        hints.append(
            "   - \u26a0\ufe0f 用户是深夜觅食！优先选大排档/深夜营业场所，正餐餐厅可能已关门"
        )
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
        logger.debug("meituan API unavailable, falling back to local JSON", exc_info=True)
        try:
            from backend.services.data_service import get_data

            data = get_data()
            if isinstance(data, dict):
                return list(data.values())
            if isinstance(data, list):
                return data
        except Exception:
            logger.debug("local JSON fallback also failed", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# LLM client pool (parameterised by env var prefix)
# ---------------------------------------------------------------------------

_llm_clients: dict[str, AsyncOpenAI] = {}


def _get_llm_client(prefix: str = "EXPERT_LLM") -> AsyncOpenAI:
    """Return a reused AsyncOpenAI client,优先从 pydantic settings 读取配置。"""
    if prefix not in _llm_clients:
        from backend.config.settings import get_settings

        settings = get_settings()
        # EXPERT_LLM 前缀用 settings.llm（.env 中 LLM_* 变量），
        # 因为 .env 没有 EXPERT_LLM_* 变量，统一走 LLM_* 配置
        base_url = settings.llm.base_url
        api_key = settings.llm.api_key
        _llm_clients[prefix] = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return _llm_clients[prefix]


def clear_llm_cache():
    """Clear cached LLM clients so next call picks up new env vars."""
    _llm_clients.clear()


def _llm_model(prefix: str = "EXPERT_LLM") -> str:
    """Return the model name, 优先从 pydantic settings 读取。"""
    from backend.config.settings import get_settings

    return get_settings().llm.model


def _is_deepseek(prefix: str = "EXPERT_LLM") -> bool:
    """Check if current LLM provider is DeepSeek (needs special params)."""
    model = _llm_model(prefix)
    from backend.config.settings import get_settings

    base_url = get_settings().llm.base_url
    return "deepseek" in model.lower() or "deepseek" in base_url


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, handling markdown code fences.

    Returns dict only. Raises ValueError if LLM returns non-dict JSON
    (e.g. a bare string or array) so the retry loop in _llm_decide catches it.
    """
    if "```" in text:
        text = text.split("```")[1].split("```")[0]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON dict, got {type(result).__name__}: {str(result)[:80]}")
    # Strip injected fields that LLM may have added from user prompt
    _DANGEROUS_KEYS = {"admin", "role", "superuser", "password", "secret", "token", "api_key"}
    for key in _DANGEROUS_KEYS:
        result.pop(key, None)
    return result


# Generic tool schema for Qwen models — avoids response_format's NotEnoughCvError
_GENERIC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_result",
            "description": "Submit the structured analysis result",
            "parameters": {
                "type": "object",
            },
        },
    },
]
_GENERIC_TOOL_CHOICE = {"type": "function", "function": {"name": "submit_result"}}


def _validate_llm_result(result: dict) -> str | None:
    """验证LLM结果，返回错误信息或None。"""
    bad_keys = []
    for key in ("picks", "issues", "ordered_stops"):
        items = result.get(key)
        if isinstance(items, list):
            before = len(items)
            result[key] = [i for i in items if isinstance(i, dict)]
            if len(result[key]) < before:
                bad_keys.append(f"{key}: 列表中有{before - len(result[key])}个非dict元素被过滤")
    return "JSON结构问题: " + "; ".join(bad_keys) if bad_keys else None


def _build_llm_kwargs(
    model: str, is_ds: bool, system_prompt: str, user_content: str, temperature: float
) -> tuple[dict, bool]:
    """构建LLM调用参数。"""
    kwargs: dict = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt + "\n你必须输出合法JSON。"},
            {"role": "user", "content": user_content},
        ],
        temperature=temperature,
        max_tokens=2000,
    )
    use_tools = False
    if is_ds:
        kwargs["response_format"] = {"type": "json_object"}
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    elif "qwen" in model.lower():
        use_tools = True
        kwargs["tools"] = _GENERIC_TOOLS
        kwargs["tool_choice"] = _GENERIC_TOOL_CHOICE
    else:
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs, use_tools


async def _llm_decide(
    system_prompt: str,
    user_prompt: str,
    *,
    retries: int = 5,
    prefix: str = "EXPERT_LLM",
    temperature: float = 0.1,
) -> dict | None:
    """Call LLM for a decision, returning structured JSON output."""
    cache_key = _llm_cache_key(system_prompt, user_prompt, prefix, temperature)
    if temperature <= 0.2:
        cached = _llm_cache_get(cache_key)
        if cached is not None:
            return {**cached}

    is_safe, risk = _ml_injection_check(user_prompt)
    if not is_safe and risk > _ML_INJECTION_THRESHOLD:
        logger.warning(
            "LLM call blocked: ML injection check failed risk=%.2f prefix=%s prompt=%.100s",
            risk,
            prefix,
            user_prompt[:100],
        )
        return None

    client = _get_llm_client(prefix)
    model = _llm_model(prefix)
    is_ds = _is_deepseek(prefix)
    error_feedback = ""

    for attempt in range(retries):
        try:
            user_content = user_prompt + (
                f"\n\n【上次输出有误，请修正】\n{error_feedback}\n请重新输出正确的JSON。"
                if error_feedback
                else ""
            )
            kwargs, use_tools = _build_llm_kwargs(
                model, is_ds, system_prompt, user_content, temperature
            )
            resp = await client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            text = (
                msg.tool_calls[0].function.arguments
                if use_tools and msg.tool_calls
                else msg.content
            ) or ""

            result = _extract_json(text)
            validation_error = _validate_llm_result(result)
            if validation_error:
                error_feedback = validation_error
            else:
                if temperature <= 0.2:
                    _llm_cache_set(cache_key, result)
                return result
        except Exception as e:
            error_feedback = f"解析失败: {str(e)[:200]}"
            if attempt < retries - 1:
                await asyncio.sleep(2)

    logger.warning(
        "_llm_decide failed after %d retries: prefix=%s, error=%s", retries, prefix, error_feedback
    )
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
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def _is_likely_macau(name: str) -> bool:
    """Heuristic: detect POIs that are actually in Macau (mislabelled in data)."""
    macau_keywords = [
        "Museu",
        "Casa",
        "Troço",
        "Posto",
        "Esplanada",
        "Muralhas",
        "Taipa",
        "Prémio",
        "Macau",
        "Wynn",
        "Grand",
        "Lisboa",
        "Venetian",
        "Parisian",
        "Morrisson",
        "Guia",
        "Penha",
        "Barra",
        "Patane",
        "博物館露天",
        "大賽車",
        "沙梨頭",
        "噴泉表演 Fountain",
        "海事博物館",
        "倫記軟滑",
        "永利名店",
        "吉祥樹表演",
        "龍環葡韻",
        "東方基金",
        "舊城牆遺址",
        # Common Macau food establishments
        "檸檬車露",
        "義順鮮奶",
        "禮記",
        "榮暉",
        "氹仔",
        "馬交",
        "葡國菜",
        "葡式",
        "葡撻",
        "車厘哥夫",
        "潘榮",
        "六記",
        "誠昌",
        "木糠",
        "杏仁餅",
    ]
    for kw in macau_keywords:
        if kw in name:
            return True
    # Check for heavy Latin content (Macau POIs are often bilingual)
    chinese_chars = sum(1 for c in name if "\u4e00" <= c <= "\u9fff")
    latin_chars = sum(1 for c in name if ("a" <= c <= "z") or ("A" <= c <= "Z"))
    return bool(latin_chars > chinese_chars and latin_chars > 5)


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
    "长隆海洋王国",
    "海洋王国",
    "珠海渔女",
    "情侣路",
    "圆明新园",
    "海滨泳场",
    "野狸岛",
    "日月贝",
    "珠海大剧院",
    "港珠澳大桥",
    "外伶仃岛",
    "淇澳岛",
    "飞沙滩",
    "金海滩",
    "御温泉",
    "唐家湾古镇",
    "梅溪牌坊",
    "农科奇观",
    "梦幻水城",
    "湾仔海鲜街",
    "拱北口岸",
}


# ---------------------------------------------------------------------------
# SSE-aware expert decorator
# ---------------------------------------------------------------------------

# Thinking messages per expert type
_THINKING_MSGS: dict[str, list[str]] = {
    "poi": ["加载候选景点，按分类分层抽样...", "LLM 分析景点匹配度...", "筛选高匹配景点..."],
    "food": ["加载餐饮POI，5子类各取TOP3...", "LLM 选餐厅中...", "偏好匹配..."],
    "hotel": ["分析住宿需求...", "LLM 选酒店中...", "价格位置评分权衡..."],
    "traffic": ["分析POI地理分布...", "LLM 规划交通方案...", "估算出行时间..."],
    "weather": ["获取天气数据...", "LLM 评估天气影响...", "调整行程建议..."],
    "local_expert": ["搜索非热门高评地点...", "LLM 生成本地建议...", "匹配独处场景..."],
    "destination": ["分析目的地偏好...", "LLM 匹配目的地...", "综合推荐..."],
    "budget_hacker": ["总预算分析...", "免费景点占比优化...", "体验杠杆优化..."],
}


def sse_expert(agent_id: str):
    """Decorator: automatically emit agent_start/agent_thinking/agent_result SSE events."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(state, *args, **kwargs):
            meta = AGENT_META.get(
                agent_id, {"name": agent_id, "icon": "🤖", "role": "", "color": "#5ea2ff"}
            )
            # Agent starts
            await sse_emit(state, "agent_start", {"agent": agent_id, **meta})
            # Thinking messages
            for msg in _THINKING_MSGS.get(agent_id, ["分析中..."])[:2]:
                await sse_emit(state, "agent_thinking", {"agent": agent_id, "text": msg})
            # Run the actual expert
            result = await func(state, *args, **kwargs)
            # Agent result summary
            proposals = result.get("proposals", []) if isinstance(result, dict) else []
            summary = f"完成，{len(proposals)}个提案" if proposals else "完成"
            if proposals:
                # Try to make a nicer summary
                first = proposals[0].get("content", {}) if proposals else {}
                if isinstance(first, dict):
                    names = [
                        p.get("content", {}).get("name", "")
                        for p in proposals[:3]
                        if isinstance(p.get("content"), dict)
                    ]
                    if names:
                        summary = f"推荐: {', '.join(n for n in names if n)[:50]}"
            await sse_emit(state, "agent_result", {"agent": agent_id, "summary": summary})
            return result

        return wrapper

    return decorator
