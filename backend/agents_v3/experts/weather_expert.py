"""Weather expert: identify indoor/outdoor POIs, assess seasonal impact."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from backend.agents_v3.experts.base import (
    _llm_decide,
    _proposal,
    _sanitize_for_prompt,
    sse_expert,
)

if TYPE_CHECKING:
    from backend.agents_v3.state import TravelState


@sse_expert("weather")
async def weather_expert(state: TravelState) -> dict:
    """Assess weather impact on the itinerary via LLM."""
    weight = state.get("expert_weights", {}).get("weather", 0)
    if weight < 0.3:
        return {"proposals": []}

    candidates = state.get("expert_candidates", {}).get("weather", [])
    state.get("user_intent", {})
    user_input = str(state.get("user_input", ""))

    # Classify POIs as outdoor / indoor
    outdoor_pois: list[str] = []
    indoor_pois: list[str] = []
    for c in candidates[:15]:
        name = c.get("name", "")
        tags = c.get("tags", []) + c.get("_scene_tags", [])
        cat = c.get("category", "")
        is_outdoor = any(kw in str(tags) for kw in ["户外", "公园", "海滨", "沙滩", "徒步", "自然"])
        is_indoor = any(kw in str(tags) for kw in ["室内", "博物馆", "展览", "科学馆"])
        if is_outdoor or cat in ["公园", "自然"]:
            outdoor_pois.append(name)
        if is_indoor or "科学馆" in name or "博物馆" in name:
            indoor_pois.append(name)

    # Current season
    now = datetime.now()
    month = now.month
    season_map = {
        1: "冬季",
        2: "冬季",
        3: "春季",
        4: "春季",
        5: "夏季",
        6: "夏季",
        7: "夏季",
        8: "夏季",
        9: "秋季",
        10: "秋季",
        11: "秋季",
        12: "冬季",
    }
    season = season_map.get(month, "未知")

    # LLM decision
    system = """你是天气评估专家。分析天气对旅游行程的影响。

要求：
1. 根据当前月份评估珠海的天气状况（温度、降雨概率、日照）
2. 逐个分析户外POI的适宜性和最佳游览时段
3. 给出具体的行程调整建议（哪个POI放上午、哪个需要备选）

输出JSON: {"condition":"天气状况","temperature":"温度范围","outdoor_ok":true/false,"advice":"具体行程调整建议","rain_probability":0.3,"indoor_alternatives":["室内备选"],"confidence":0.8}
只输出JSON。"""

    user = f"""用户场景: {_sanitize_for_prompt(user_input)}
当前月份: {month}月（{season}）
城市: 珠海（华南沿海城市）
户外POI: {', '.join(outdoor_pois[:5]) if outdoor_pois else '无'}
室内POI: {', '.join(indoor_pois[:5]) if indoor_pois else '无'}"""

    result = await _llm_decide(system, user)

    if result:
        return {
            "proposals": [
                _proposal("weather", result, result.get("confidence", 0.8), "LLM天气评估")
            ]
        }

    # Fallback: season-based rules
    return {
        "proposals": [
            _proposal(
                "weather",
                {
                    "condition": "多云",
                    "temperature": "26-32°C",
                    "outdoor_ok": True,
                    "advice": f"{month}月珠海{season}气候，建议上午户外下午室内，注意防晒防暑",
                    "rain_probability": 0.35,
                    "indoor_alternatives": indoor_pois[:3] if indoor_pois else ["长隆海洋科学馆"],
                },
                0.6,
                "规则引擎：季节性天气评估",
            )
        ]
    }
