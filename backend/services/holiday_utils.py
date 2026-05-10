"""CityFlow 节假日与上下文工具。

检测中国法定节假日、周末、时段，构建完整上下文信息。
支持固定公休 + 农历节日查表（2025-2027）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# 固定公休节日 (月, 日) → 名称
# ---------------------------------------------------------------------------

_FIXED_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "元旦",
    (5, 1): "劳动节",
    (10, 1): "国庆节",
    (10, 2): "国庆节",
    (10, 3): "国庆节",
}

# ---------------------------------------------------------------------------
# 农历节日查表（覆盖 2025-2027）
# 键: 年份 → {(月, 日): 名称}
# ---------------------------------------------------------------------------

_LUNAR_HOLIDAYS: dict[int, dict[tuple[int, int], str]] = {
    2025: {
        (1, 28): "春节",
        (1, 29): "春节",
        (1, 30): "春节",
        (1, 31): "春节",
        (2, 1): "春节",
        (4, 4): "清明节",
        (5, 31): "端午节",
        (10, 6): "中秋节",
    },
    2026: {
        (2, 16): "春节",
        (2, 17): "春节",
        (2, 18): "春节",
        (2, 19): "春节",
        (2, 20): "春节",
        (4, 5): "清明节",
        (6, 19): "端午节",
        (9, 27): "中秋节",
    },
    2027: {
        (2, 5): "春节",
        (2, 6): "春节",
        (2, 7): "春节",
        (2, 8): "春节",
        (2, 9): "春节",
        (4, 5): "清明节",
        (6, 8): "端午节",
        (9, 15): "中秋节",
    },
}

# ---------------------------------------------------------------------------
# 温度等级划分
# ---------------------------------------------------------------------------

_TEMPERATURE_LEVELS: list[tuple[float, float, str]] = [
    (35, 999, "hot"),
    (28, 35, "warm"),
    (18, 28, "comfortable"),
    (8, 18, "cool"),
    (-999, 8, "cold"),
]


def _temperature_level(temp: float) -> str:
    for lo, hi, level in _TEMPERATURE_LEVELS:
        if lo <= temp < hi:
            return level
    return "comfortable"


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def get_holiday_info(dt: datetime | None = None) -> dict[str, Any]:
    """获取指定日期（默认当天）的节假日信息。

    返回:
    {
        "is_holiday": True,
        "name": "春节",
        "is_weekend": True,
        "day_type": "holiday",   # holiday / weekend / workday
    }
    """
    if dt is None:
        dt = datetime.now()

    year = dt.year
    month = dt.month
    day = dt.day
    weekday = dt.weekday() + 1  # 1=周一 ... 7=周日
    is_weekend = weekday >= 6

    # 先查农历节日表
    holiday_name = _LUNAR_HOLIDAYS.get(year, {}).get((month, day))
    # 再查固定公休
    if not holiday_name:
        holiday_name = _FIXED_HOLIDAYS.get((month, day))

    is_holiday = holiday_name is not None

    # day_type: holiday > weekend > workday
    if is_holiday:
        day_type = "holiday"
    elif is_weekend:
        day_type = "weekend"
    else:
        day_type = "workday"

    return {
        "is_holiday": is_holiday,
        "name": holiday_name,
        "is_weekend": is_weekend,
        "day_type": day_type,
    }


def get_period(hour: int) -> str:
    """根据小时返回时段。"""
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 14:
        return "noon"
    elif 14 <= hour < 18:
        return "afternoon"
    else:
        return "evening"


def build_context(
    weather: str = "sunny",
    temperature: float = 25.0,
    hour_of_day: int = 9,
    day_of_week: int = 0,
    season: str = "spring",
    dt: datetime | None = None,
    source: str = "user_initiated",
) -> dict[str, Any]:
    """构建完整的上下文字典（用于 LTM trip_history.context）。

    参数:
        weather: sunny/rainy/cloudy/hot/cold
        temperature: 摄氏度
        hour_of_day: 0-23
        day_of_week: 0=周一
        season: spring/summer/autumn/winter
        dt: 日期（默认当天）
        source: 来源 user_initiated/quick_button/dialogue_adjust

    返回:
    {
        "date": "2026-05-09",
        "weekday": 6,
        "is_weekend": True,
        "period": "morning",
        "holiday": {"is_holiday": False, "name": None, "day_type": "weekend"},
        "weather": "sunny",
        "temperature": 25.0,
        "temperature_level": "comfortable",
        "season": "spring",
        "source": "user_initiated",
    }
    """
    if dt is None:
        dt = datetime.now()

    holiday_info = get_holiday_info(dt)
    # day_of_week: 从 0=周一 转为 1=周一..7=周日
    weekday_num = day_of_week + 1

    return {
        "date": dt.strftime("%Y-%m-%d"),
        "weekday": weekday_num,
        "is_weekend": weekday_num >= 6,
        "period": get_period(hour_of_day),
        "holiday": {
            "is_holiday": holiday_info["is_holiday"],
            "name": holiday_info["name"],
            "day_type": holiday_info["day_type"],
        },
        "weather": weather,
        "temperature": round(temperature, 1),
        "temperature_level": _temperature_level(temperature),
        "season": season,
        "source": source,
    }


def format_context_summary(context: dict[str, Any]) -> str:
    """将上下文字典格式化为人类可读的短句。

    示例:
        "☀️ 晴 25°C · 周六 · 春季"
        "🌧️ 小雨 18°C · 国庆节 · 秋季"
    """
    weather_icons = {
        "sunny": "☀️", "rainy": "🌧️", "cloudy": "☁️",
        "hot": "🌡️", "cold": "❄️",
    }
    icon = weather_icons.get(context.get("weather", ""), "")
    parts = [
        f"{icon} {context.get('weather', '?')}",
        f"{context.get('temperature', '?')}°C",
    ]

    weekday_names = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
    holiday = context.get("holiday", {})
    if holiday.get("is_holiday"):
        parts.append(f"· {holiday['name']}")
    elif context.get("is_weekend"):
        parts.append("· 周末")
    else:
        wd = weekday_names.get(context.get("weekday", "?"), f"周{context.get('weekday', '?')}")
        parts.append(f"· {wd}")

    parts.append(f"· {context.get('season', '?')}")
    return " ".join(parts)
