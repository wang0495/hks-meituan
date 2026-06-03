"""Local expert: surface hidden gems and insider tips via LLM."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.agents_v3.experts.base import (
    _llm_decide,
    _proposal,
    _sanitize_for_prompt,
    sse_expert,
)

if TYPE_CHECKING:
    from backend.agents_v3.state import TravelState


@sse_expert("local_expert")
async def local_expert(state: TravelState) -> dict:
    """Recommend niche / high-quality POIs and insider tips."""
    weight = state.get("expert_weights", {}).get("local_expert", 0)
    if weight < 0.3:
        return {"proposals": []}

    candidates = state.get("expert_candidates", {}).get("local_expert", [])
    intent = state.get("user_intent", {})
    user_input = str(state.get("user_input", ""))

    # Hidden gems: high rating + niche tags or LLM quality score
    hidden_gems: list[dict] = []
    for c in candidates:
        llm_q = c.get("_llm_quality", {})
        tags = c.get("tags", [])
        rating = c.get("rating", 0)
        if rating >= 4.0 and (llm_q.get("score", 0) >= 7 or any("小众" in str(t) for t in tags)):
            hidden_gems.append(
                {
                    "name": c.get("name", ""),
                    "category": c.get("category", ""),
                    "rating": rating,
                    "tags": tags[:3],
                }
            )

    # Already-selected popular POIs (for dedup in prompt)
    popular_names: list[str] = []
    for c in candidates[:15]:
        if c.get("rating") and c.get("rating", 0) >= 4.0:
            popular_names.append(c.get("name", ""))

    group_type = intent.get("group", {}).get("type", "")
    scene_reqs = intent.get("scene_requirements", [])

    # LLM decision
    system = f"""你是珠海本地达人，熟悉珠海的每一个角落。根据用户需求给出本地特色建议。

要求：
1. 推荐只有本地人才知道的宝藏地点（不要重复推荐热门景点）
2. 结合小众POI数据给出具体推荐
3. 给出实用的本地贴士（避坑、最佳时间等）
4. {f'场景适配：用户想{_sanitize_for_prompt(", ".join(scene_reqs))}，推荐符合场景的小众地点' if scene_reqs else ''}
5. {f'群体适配：{group_type}群体的特殊需求' if group_type else ''}

输出JSON: {{"tips":[{{"name":"推荐名","type":"类型","why":"为什么推荐","best_time":"最佳时间"}}]],"secrets":["隐藏的好去处"],"local_advice":"本地人建议","confidence":0.75}}
只输出JSON。"""

    user = f"""用户需求: {_sanitize_for_prompt(user_input)}
群体: {group_type or '未知'}
偏好: {_sanitize_for_prompt(json.dumps(intent.get('preferred_categories', []), ensure_ascii=False))}
场景要求: {_sanitize_for_prompt(json.dumps(scene_reqs, ensure_ascii=False)) if scene_reqs else '无'}
预算: {intent.get('budget', {}).get('per_person', '不限')}元

已选热门景点（不要再推荐这些）:
{', '.join(popular_names[:10]) if popular_names else '待定'}

小众POI数据:
{json.dumps(hidden_gems[:10], ensure_ascii=False) if hidden_gems else '无小众数据'}"""

    result = await _llm_decide(system, user)

    if result:
        return {
            "proposals": [
                _proposal("local_expert", result, result.get("confidence", 0.75), "LLM本地建议")
            ]
        }

    # Fallback: pick top hidden gems
    gems = (
        hidden_gems[:3]
        if hidden_gems
        else [{"name": "唐家湾古镇", "type": "小众景点", "why": "人少景美，岭南古村落"}]
    )
    return {
        "proposals": [
            _proposal(
                "local_expert",
                {
                    "tips": [
                        {
                            "name": g.get("name", ""),
                            "type": g.get("type", g.get("category", "")),
                            "why": g.get("why", "小众推荐"),
                        }
                        for g in gems
                    ],
                    "secrets": [g.get("name", "") for g in gems],
                    "local_advice": "珠海天气湿热，建议早出晚归避开正午高温",
                },
                0.4,
                "规则引擎：小众POI推荐",
            )
        ]
    }
