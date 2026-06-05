"""CityFlow 城市性格 + 非标体验服务。

基于 `city_personality.json` 和 `nonstandard_experiences.json` 提供：
- 城市性格查询
- 非标准体验推荐
- 文案风格调整指引

数据由 `data_service.py` 自动加载。
"""

from __future__ import annotations

from typing import Any

from backend.services.data_service import get_data

# ---------------------------------------------------------------------------
# 城市性格
# ---------------------------------------------------------------------------


def get_city_personality(city: str) -> dict[str, Any] | None:
    """获取城市性格数据。

    Args:
        city: 城市名（珠海 / 广州 / 湛江 / 深圳）

    Returns:
        城市性格字典，或 None（城市不存在）
    """
    data = get_data("city_personality")
    if isinstance(data, dict):
        return data.get(city)
    return None


def get_cities() -> list[str]:
    """获取所有有性格数据的城市列表。"""
    data = get_data("city_personality")
    if isinstance(data, dict):
        return list(data.keys())
    return []


def get_vibe_style_adjectives(vibe: str) -> list[str]:
    """根据城市 vibe 返回文案风格形容词。

    Args:
        vibe: relaxed / lively / rustic / energetic

    Returns:
        风格形容词列表
    """
    style_map: dict[str, list[str]] = {
        "relaxed": ["悠闲", "惬意", "慢节奏", "舒适", "自在"],
        "lively": ["热闹", "精彩", "丰富", "活力", "繁华"],
        "rustic": ["质朴", "原生态", "地道", "隐世", "纯粹"],
        "energetic": ["炫酷", "前沿", "动感", "时尚", "新潮"],
    }
    return style_map.get(vibe, ["舒适", "愉快"])


def get_city_based_opening(city: str, user_name: str = "你") -> str:
    """生成城市特色的开场白。

    Returns:
        风格化开场白字符串
    """
    personality = get_city_personality(city)
    if not personality:
        return f"{user_name}的{city}之旅即将开始！"

    vibe = personality.get("vibe", "")
    keywords = personality.get("keywords", [])
    kw = keywords[0] if keywords else ""

    openings: dict[str, str] = {
        "relaxed": f"{user_name}好，今天让我们一起在{city}放慢脚步，"
        f"感受这座{kw}城市的悠闲气息。",
        "lively": f"准备好开启{city}之旅了吗？这座{kw}的城市" f"有太多精彩等着{user_name}去发现！",
        "rustic": f"欢迎来到{city}，{user_name}." f"这座{kw}的城市藏着最地道的味道和故事。",
        "energetic": f"{user_name}，今天的目标是玩转{city}！" f"这座{kw}的城市到处都是惊喜和活力。",
    }
    return openings.get(vibe, f"开启{city}之旅！")


# ---------------------------------------------------------------------------
# 非标体验
# ---------------------------------------------------------------------------


def get_nonstandard_experiences(
    city: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """获取非标准体验列表。

    Args:
        city: 按城市筛选（可选）
        category: 按品类筛选（可选）

    Returns:
        匹配的非标体验列表
    """
    data = get_data("nonstandard_experiences")
    if not isinstance(data, list):
        return []

    result = data
    if city:
        result = [e for e in result if e.get("city") == city]
    if category:
        result = [e for e in result if e.get("category") == category]

    return result


def get_nse_for_route(
    city: str,
    hour_of_day: int,
    season: str = "spring",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """推荐符合当前时间和季节的非标体验。

    Args:
        city: 城市
        hour_of_day: 当前小时
        season: 季节
        limit: 最大返回数量
    """
    candidates = get_nonstandard_experiences(city=city)

    def score(nse: dict) -> float:
        s = 0.0
        best_time = nse.get("best_time", "")
        if best_time:
            try:
                start_h = int(best_time.split("-")[0].split(":")[0])
                end_h = int(best_time.split("-")[1].split(":")[0])
                if start_h <= hour_of_day <= end_h:
                    s += 2.0  # 时间匹配加分
            except (ValueError, IndexError):
                pass
        exp_seasons = nse.get("season", [])
        if season in exp_seasons:
            s += 1.0  # 季节匹配加分
        return s

    candidates.sort(key=score, reverse=True)
    return candidates[:limit]
