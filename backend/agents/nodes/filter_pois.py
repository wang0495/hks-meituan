"""filter_pois 节点。

包装原filters.filter_candidates()服务，作为LangGraph工具节点。
"""

from __future__ import annotations

from backend.agents.state import PlanningState
from backend.services.filters import filter_candidates as original_filter_candidates
from backend.services.data_service import get_data


def node(state: PlanningState) -> dict:
    """筛选POI候选。

    从数据服务加载POI，应用用户意图的约束过滤。

    Args:
        state: 当前规划状态，需包含user_intent

    Returns:
        dict: 包含candidates的更新片段
    """
    user_intent = state.get("user_intent", {})
    city = user_intent.get("city", "珠海")

    try:
        # 获取POI数据
        all_pois = get_data("city_poi_db")
        city_pois = [p for p in all_pois if p.get("city") == city]

        if not city_pois:
            return {
                "candidates": [],
                "errors": state.get("errors", []) + [f"城市 {city} 没有POI数据"],
            }

        # 应用过滤
        candidates = original_filter_candidates(city_pois, user_intent)

        return {"candidates": candidates}

    except Exception as e:
        return {
            "candidates": [],
            "errors": state.get("errors", []) + [f"POI筛选失败: {e}"],
        }
