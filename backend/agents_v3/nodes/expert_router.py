"""LLM-based expert router for MoE architecture.

Classifies user intent via DeepSeek, activates relevant experts,
and computes per-expert candidate pools from the shared candidate list.

---
ADR-003: 专家路由器必须使用LLM，不能用规则替代
===

**决策**: expert_router 的核心分类逻辑必须调用LLM（DeepSeek），不能退化为纯规则匹配。

**背景**:
v1/v2 版本使用 `_classify_scene()` 做场景分类——一组 if/elif 关键词匹配：
- "吃"/"海鲜"/"小吃" → 美食型
- "长隆"/"海洋王国" → 目的地型
- 否则 → 观光型

这套规则导致严重的 whack-a-mole（打地鼠）问题：
1. "逛街想吃甜品" → 规则命中"吃" → 美食型（错误！逛街是主目的，吃是顺便）
2. "和闺蜜珠海逛街，想拍照+吃甜品" → 规则命中"吃" → 美食型（错误！观光型）
3. 修一个场景就破坏另一个，30场景测试始终卡在18/30通过

**原因**: 规则无法区分"吃是目的"vs"吃是顺便"这种语义差异。LLM可以通过
few-shot示例理解这种微妙区别，而关键词匹配永远做不到。

**规则预检查（_rule_precheck）的设计意图**:
仅用于明显无歧义的场景（如"珠海美食一日游"明确是美食型、"特种兵打卡"明确是特种兵型），
目的是**省掉LLM调用降低成本**，而不是替代LLM。对于模糊场景，必须走LLM。

**不要做的事**:
- 不要把 _rule_precheck 扩展到覆盖所有场景然后去掉LLM调用
- 不要把 _classify_scene 的规则当成主路径
- 不要因为"LLM有延迟"就改回纯规则（延迟可通过cache/async解决，但规则的根本缺陷无法解决）

**验证标准**: 30场景测试通过率 ≥ 23/30。如果去掉LLM只留规则，通过率会跌回18/30。
---
"""

from __future__ import annotations

import json
import logging

from backend.agents_v3.experts.base import (
    _FOOD_NAME_KWS,
    _haversine_km,
    _is_likely_macau,
)
from backend.agents_v3.state import TravelState, AGENT_META, sse_emit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEST_COORDS: dict[str, tuple[float, float]] = {
    # Fallback only — primary detection now uses LLM + POI data
    "长隆": (22.11, 113.54), "海洋王国": (22.11, 113.54),
    "御温泉": (22.17, 113.28), "圆明新园": (22.27, 113.55),
    "梦幻水城": (22.27, 113.55),
    # 扩展：覆盖更多核心目的地
    "海泉湾": (22.10, 113.26), "港珠澳大桥": (22.22, 113.58),
    "东澳岛": (22.01, 113.72), "外伶仃岛": (22.08, 114.00),
    "金沙滩": (22.06, 113.32), "创新方": (22.12, 113.52),
    "景山公园": (22.24, 113.57), "海滨公园": (22.26, 113.58),
    "海滨泳场": (22.22, 113.57), "梅溪牌坊": (22.28, 113.53),
    "野狸岛": (22.28, 113.59), "罗西尼": (22.30, 113.52),
    "唐家湾": (22.36, 113.58), "横琴": (22.12, 113.52),
    "飞沙滩": (22.04, 113.34), "三板村": (22.10, 113.35),
    "灯笼沙": (22.18, 113.25), "黄杨山": (22.25, 113.27),
    "斗门古街": (22.22, 113.29), "接霞庄": (22.20, 113.26),
}
_POI_EXCLUDE_CATS = {"住宿", "酒店", "民宿", "餐饮", "美食"}
_FOOD_CATS = {"餐饮", "美食", "小吃", "夜市小吃"}
_FOOD_NAME_PARTS = [
    "餐厅", "火锅", "烧烤", "甜品", "海鲜", "粉", "面",
    "粥", "茶餐厅", "早茶", "烧腊", "煲仔",
]
_HOTEL_CATS = {"住宿", "酒店", "民宿"}
_BUDGET_FREE_CATS = {"公园", "文化", "自然", "运动"}

# ---------------------------------------------------------------------------
# Router prompt (system + 5 few-shot examples)
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """你是CityFlow出行规划系统的专家路由器。根据用户输入，判断场景类型并分配专家权重。

## 5种场景类型（必须选其一）
- **观光型**: 以观光、拍照、逛街、景点打卡为主，吃只是顺便
- **美食型**: 吃是核心目的，整条路线围绕美食展开
- **目的地型**: 围绕大型景区（长隆、御温泉等）规划
- **特种兵型**: 高强度打卡，一天跑很多地方
- **休闲型**: 慢节奏、放松、不赶路，或运动养生类

## 8位专家
- **poi**: 观光景点、地标、拍照打卡点（始终激活，权重>=0.3）
- **food**: 餐厅、美食街、夜市小吃（用户明确要吃/美食时激活）
- **hotel**: 住宿（仅检测到过夜时激活）
- **traffic**: 交通规划（>4个POI或跨区时激活）
- **weather**: 天气影响（仅户外活动时激活）
- **local_expert**: 小众秘境（用户想要独特体验时激活）
- **destination**: 大型景区如长隆、御温泉（仅目的地型激活）
- **budget_hacker**: 免费/省钱优化（预算<200或"穷游/免费"时激活）

## 判断规则（优先级从高到低）
1. 提到长隆/海洋王国/御温泉/圆明新园/海泉湾/港珠澳大桥/东澳岛/外伶仃岛/金沙滩/景山公园/海滨公园/梅溪牌坊/野狸岛 → 目的地型
2. 提到特种兵/打卡所有景点 → 特种兵型
3. 吃是"顺便"的 → 不是美食型！关键看用户的核心动词：
   - "逛街想吃甜品" → 逛街是目的，吃是顺便 → 观光型
   - "海边散步吃好吃的" → 散步是目的，吃是顺便 → 观光型
   - "珠海美食一日游" → 吃是目的 → 美食型
   - "珠海吃海鲜" → 吃是目的 → 美食型
   - "茶餐厅打卡" → 吃是目的 → 美食型
4. 慢节奏/安静/不累/晨练/文艺/独处/养老/喝茶 → 休闲型
5. 默认 → 观光型

## 输出JSON（仅列权重>=0.3的专家，active_experts按权重降序）
{"scene_type":"...", "expert_weights":{"poi":N,...}, "active_experts":["poi","food"], "scene_rationale":"..."}

## 参考案例（必须严格遵循）
"带6岁孩子去长隆海洋王国" → 目的地型, destination:0.95, food:0.4, weather:0.3
"珠海吃海鲜，想吃最新鲜最划算的" → 美食型, food:0.95, local_expert:0.3
"和闺蜜珠海逛街，想拍照+吃甜品" → 观光型, poi:0.8, food:0.7, local_expert:0.4
"异地恋见面了，想海边散步吃好吃的" → 观光型, poi:0.8, food:0.6
"珠海两日游，节奏慢，喜欢公园和海边" → 休闲型, poi:0.8, hotel:0.7, traffic:0.4
"带爸妈珠海一日游，不能太累" → 休闲型, poi:0.7, food:0.4
"社恐一个人珠海，安静地方" → 休闲型, poi:0.6
"珠海早起晨跑" → 休闲型, poi:0.5
"一个人文艺独处，咖啡馆书店" → 休闲型, poi:0.6, local_expert:0.4
"珠海茶餐厅打卡" → 美食型, food:0.9, poi:0.3
"4个人珠海玩一天，每人预算100" → 观光型, budget_hacker:0.9, poi:0.8, food:0.5

只输出JSON，不要其他内容。"""


# ---------------------------------------------------------------------------
# Rule-based fallback (mirrors rule_guard._classify_scene)
# ---------------------------------------------------------------------------
def _classify_scene(user_input: str, intent: dict) -> str:
    text = user_input.lower()
    prefs = intent.get("preferred_categories", [])
    if any(kw in text for kw in ["美食", "海鲜", "小吃", "特色菜", "夜市", "吃货"]):
        return "美食型"
    if any(kw in text for kw in [
        "长隆", "海洋王国", "圆明新园", "御温泉", "梦幻水城",
        "海泉湾", "港珠澳大桥", "东澳岛", "外伶仃岛",
        "金沙滩", "创新方", "景山公园", "海滨公园",
        "海滨泳场", "梅溪牌坊", "野狸岛", "飞沙滩",
    ]):
        return "目的地型"
    if "特种兵" in text or "特种兵" in intent.get("pace", ""):
        return "特种兵型"
    if any(kw in text for kw in ["休闲", "慢", "闲逛", "养老", "散步", "轻松", "不累", "安静", "晨练", "晨跑", "文艺", "独处", "喝茶"]) or "闲逛" in intent.get("pace", ""):
        return "休闲型"
    return "观光型"


_VALID_SCENE_TYPES = {"美食型", "目的地型", "特种兵型", "休闲型", "观光型"}

# Map common LLM mis-outputs to valid scene types
_SCENE_TYPE_ALIASES: dict[str, str] = {
    "destination": "目的地型",
    "food": "美食型",
    "sightseeing": "观光型",
    "leisure": "休闲型",
    "intensive": "特种兵型",
    "教育型": "观光型",
    "亲子型": "观光型",
    "购物型": "观光型",
    "文化型": "观光型",
}

# Keywords that unambiguously signal a specific scene type
_UNAMBIGUOUS_RULES: list[tuple[list[str], str]] = [
    (["长隆", "海洋王国", "圆明新园", "御温泉", "梦幻水城",
      "海泉湾", "港珠澳大桥", "东澳岛", "外伶仃岛",
      "金沙滩", "创新方", "景山公园", "海滨公园",
      "海滨泳场", "梅溪牌坊", "野狸岛", "飞沙滩"], "目的地型"),
    (["特种兵"], "特种兵型"),
    (["美食游", "美食一日游", "吃海鲜", "吃遍", "扫街吃", "一路吃"], "美食型"),
]


def _normalize_scene_type(raw: str) -> str:
    """Normalize LLM-returned scene_type to one of the 5 valid types."""
    s = raw.strip()
    if s in _VALID_SCENE_TYPES:
        return s
    # Try alias map
    alias = _SCENE_TYPE_ALIASES.get(s)
    if alias:
        return alias
    # Fuzzy: if the raw string contains a valid type as substring
    for vt in _VALID_SCENE_TYPES:
        # Match e.g. "美食" in "美食之旅"
        core = vt.replace("型", "")
        if core in s:
            return vt
    return "观光型"


def _rule_precheck(user_input: str, intent: dict) -> str | None:
    """Return a scene_type if the input is unambiguous, else None.

    Used to skip the LLM call for clear-cut cases.
    """
    text = user_input.lower()
    for keywords, scene_type in _UNAMBIGUOUS_RULES:
        if any(kw in text for kw in keywords):
            return scene_type
    # Also use the full rule classifier as a confidence signal
    rule_scene = _classify_scene(user_input, intent)
    # The rule-based classifier is reliable for 美食型 ONLY when user text
    # contains unambiguous food keywords. Do NOT use preferred_categories here
    # because "餐饮" appears in almost every scene's prefs (even "逛街想吃甜品"
    # gets "餐饮" in prefs), which causes misclassification.
    food_explicit = any(kw in text for kw in ["美食", "海鲜", "小吃", "夜市", "吃货"])
    if rule_scene == "美食型" and food_explicit:
        return "美食型"
    if rule_scene == "特种兵型":
        return "特种兵型"
    return None


_FALLBACK_WEIGHTS: dict[str, dict[str, float]] = {
    "美食型": {"food": 0.9, "poi": 0.3},
    "目的地型": {"destination": 0.9, "food": 0.4},
    "特种兵型": {"poi": 0.9, "food": 0.5, "traffic": 0.5},
    "休闲型": {"poi": 0.7, "hotel": 0.5},
    "观光型": {"poi": 0.8, "food": 0.5},
}


def _fallback_result(user_input: str, intent: dict) -> dict:
    scene = _classify_scene(user_input, intent)
    weights = _FALLBACK_WEIGHTS.get(scene, _FALLBACK_WEIGHTS["观光型"]).copy()
    text = user_input.lower()
    budget = intent.get("budget", {}).get("per_person", 0)
    if (budget and budget < 200) or any(kw in text for kw in ["穷游", "免费", "不花钱"]):
        weights["budget_hacker"] = 0.9
    if any(kw in text for kw in ["两日", "二日", "过夜", "住宿"]):
        weights["hotel"] = 0.6
    weights["poi"] = max(weights.get("poi", 0), 0.3)
    active = sorted([k for k, v in weights.items() if v > 0], key=lambda k: weights[k], reverse=True)
    return {"scene_type": scene, "expert_weights": weights, "active_experts": active}


# ---------------------------------------------------------------------------
# Candidate pool computation
# ---------------------------------------------------------------------------
def _has_food_name(name: str) -> bool:
    return any(kw in name for kw in _FOOD_NAME_KWS)


def _is_food_poi(p: dict) -> bool:
    cat = p.get("category", "")
    name = p.get("name", "")
    return cat in _FOOD_CATS or any(kw in name for kw in _FOOD_NAME_PARTS)


async def _detect_destination_center(user_input: str, candidates: list[dict]) -> tuple[str | None, tuple[float, float] | None]:
    """LLM 从候选 POI 中识别用户的目的地，返回 (名称, 坐标) 或 (None, None)。"""
    # Level 1: 硬编码关键词（常见目的地零延迟）
    for name_kw, coords in _DEST_COORDS.items():
        if name_kw in user_input:
            return name_kw, coords

    # Level 2: 从全量 POI 中模糊匹配
    _SCENIC_WORDS = {"温泉", "乐园", "沙滩", "大桥", "公园", "景区", "海洋", "王国",
                     "岛屿", "沙滩", "古镇", "博物馆", "水城", "创新方", "海泉湾"}
    best_match = None
    best_score = 0
    for p in candidates:
        name = p.get("name", "")
        lat, lng = p.get("lat"), p.get("lng")
        if not lat or not lng or len(name) < 2:
            continue
        # POI 名完全出现在 user_input 里（最强匹配）
        if name in user_input:
            score = len(name) * 20 + 200
            if score > best_score:
                best_match = (name, (float(lat), float(lng)))
                best_score = score
            continue
        # user_input 的2-5字片段出现在 POI 名里
        for flen in range(min(5, len(user_input)), 1, -1):
            for si in range(len(user_input) - flen + 1):
                frag = user_input[si:si + flen]
                if frag in name and len(frag) >= 2:
                    # 景点名匹配大幅加分，普通词匹配低分
                    is_scenic = any(w in frag for w in _SCENIC_WORDS)
                    score = len(frag) * 10 + (200 if is_scenic else 10 if len(frag) >= 3 else 0)
                    if score > best_score:
                        best_match = (name, (float(lat), float(lng)))
                        best_score = score
                    break
    if best_match:
        return best_match

    # Level 3: LLM 检测（兜底）
    top_pois = [
        {"name": p.get("name", ""), "category": p.get("category", ""), "rating": p.get("rating", 0)}
        for p in candidates[:80]
        if p.get("lat") and p.get("lng") and p.get("rating", 0) >= 3.5
    ]
    if not top_pois:
        return None, None

    if not result or not result.get("destination"):
        return None, None

    dest_name = result["destination"]
    for p in candidates:
        if dest_name in p.get("name", "") or p.get("name", "") in dest_name:
            lat, lng = p.get("lat"), p.get("lng")
            if lat and lng:
                return p.get("name"), (float(lat), float(lng))
    return dest_name, None


async def _compute_pools(candidates: list[dict], state: TravelState) -> dict[str, list[dict]]:
    user_input = state.get("user_input", "")
    pools: dict[str, list[dict]] = {}

    pools["poi"] = [
        p for p in candidates
        if p.get("category", "") not in _POI_EXCLUDE_CATS
        and not _has_food_name(p.get("name", ""))
        and not _is_likely_macau(p.get("name", ""))
        and p.get("rating") is not None
    ]
    pools["food"] = [
        p for p in candidates
        if _is_food_poi(p)
        and not _is_likely_macau(p.get("name", ""))
        and p.get("rating") is not None
    ]
    pools["hotel"] = [p for p in candidates if p.get("category", "") in _HOTEL_CATS]
    pools["traffic"] = sorted(candidates, key=lambda p: float(p.get("rating", 0)), reverse=True)[:15]
    pools["weather"] = list(candidates)
    pools["local_expert"] = [
        p for p in candidates
        if p.get("rating") is not None and float(p["rating"]) >= 4.0
    ]

    # 目的地候选池：LLM 识别目的地坐标，5km 范围内过滤
    dest_name, dest_coords = await _detect_destination_center(user_input, candidates)
    pools["destination"] = []
    if dest_coords:
        dlat, dlng = dest_coords
        pools["destination"] = [
            p for p in candidates
            if _haversine_km(dlat, dlng, float(p.get("lat", 0)), float(p.get("lng", 0))) <= 5.0
        ]
    # 把目的地信息存到 extra 供下游使用
    pools["_dest_name"] = dest_name
    pools["_dest_coords"] = dest_coords

    pools["budget_hacker"] = [
        p for p in candidates
        if p.get("avg_price", 999) == 0
        or float(p.get("avg_price", 999)) <= 50
        or p.get("category", "") in _BUDGET_FREE_CATS
    ]
    return pools


# ---------------------------------------------------------------------------
# Main exported function
# ---------------------------------------------------------------------------
async def expert_router(state: TravelState) -> dict:
    """LLM-based expert router: classify scene, activate experts, compute pools."""
    meta = AGENT_META.get("expert_router", {})
    await sse_emit(state, "agent_start", {"agent": "expert_router", **meta})
    await sse_emit(state, "agent_thinking", {"agent": "expert_router", "text": "LLM 分析场景类型，决定激活哪些专家..."})

    user_input = state.get("user_input", "")
    user_intent = state.get("user_intent", {})
    candidates = state.get("candidates", [])

    # --- LLM classification (2 retries, fallback to rules on failure) ---
    from backend.agents_v3.experts.base import _llm_decide

    result = None
    try:
        result = await _llm_decide(
            _SYSTEM_PROMPT,
            f"用户输入：{user_input}",
            prefix="LLM",
            temperature=0.05,
        )
    except Exception:
        logger.warning("LLM intent enrichment failed, falling back to rules", exc_info=True)

    if result is None:
        result = _fallback_result(user_input, user_intent)

    # Normalize LLM-returned scene_type to a valid type
    result["scene_type"] = _normalize_scene_type(result.get("scene_type", ""))

    # --- Normalize weights ---
    weights = result.get("expert_weights", {})
    weights["poi"] = max(float(weights.get("poi", 0)), 0.3)
    active = result.get("active_experts") or sorted(
        [k for k, v in weights.items() if float(v) >= 0.3],
        key=lambda k: float(weights[k]),
        reverse=True,
    )
    # Ensure "poi" is always in active_experts
    if "poi" not in active:
        active.append("poi")
    # Ensure "food" has floor >= 0.3 unless user explicitly excludes food
    _no_food_keywords = ["不要餐饮", "不要吃", "不需要吃", "只玩不吃", "不用吃饭", "无餐饮"]
    user_text = user_input.lower()
    if not any(kw in user_text for kw in _no_food_keywords):
        weights["food"] = max(float(weights.get("food", 0)), 0.3)
        if "food" not in active:
            active.append("food")
    pools = await _compute_pools(candidates, state)

    await sse_emit(state, "agent_result", {"agent": "expert_router", "summary": f"场景: {result['scene_type']}，激活: {', '.join(active)}"})

    ret = {
        "scene_type": result["scene_type"],
        "expert_weights": weights,
        "active_experts": active,
        "expert_candidates": {k: v for k, v in pools.items() if not k.startswith("_")},
        "errors": [],
    }
    # 传递目的地信息到下游 state
    if pools.get("_dest_name"):
        ret["destination_name"] = pools["_dest_name"]
    if pools.get("_dest_coords"):
        ret["destination_center"] = pools["_dest_coords"]
    return ret
