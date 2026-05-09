"""CityFlow 时间处理公共模块。

提供时间解析、格式化、营业时间解析等函数，
消除 solver.py / dialogue.py / filters.py 中的重复实现。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

# ---------------------------------------------------------------------------
# 基础时间解析
# ---------------------------------------------------------------------------


def parse_time(time_str: str) -> datetime:
    """解析 HH:MM 时间字符串为 datetime 对象（基准日 2000-01-01）。

    Args:
        time_str: 时间字符串，格式 "HH:MM"

    Returns:
        datetime 对象
    """
    return datetime.strptime(time_str, "%H:%M")


def format_time(dt: datetime) -> str:
    """格式化 datetime 为 HH:MM 字符串。

    Args:
        dt: datetime 对象

    Returns:
        时间字符串，格式 "HH:MM"
    """
    return dt.strftime("%H:%M")


# ---------------------------------------------------------------------------
# 时间运算
# ---------------------------------------------------------------------------


def add_minutes(time_str: str, minutes: int) -> str:
    """时间加分钟。

    Args:
        time_str: 时间字符串
        minutes: 分钟数

    Returns:
        新的时间字符串
    """
    dt = parse_time(time_str) + timedelta(minutes=minutes)
    return format_time(dt)


def time_difference(time1: str, time2: str) -> int:
    """计算时间差（分钟）。

    Args:
        time1: 起始时间
        time2: 结束时间

    Returns:
        时间差（分钟），正数表示 time2 晚于 time1
    """
    return int((parse_time(time2) - parse_time(time1)).total_seconds() / 60)


def is_time_in_range(time_str: str, start: str, end: str) -> bool:
    """检查时间是否在范围内。

    Args:
        time_str: 时间字符串
        start: 开始时间
        end: 结束时间

    Returns:
        是否在范围内
    """
    t = parse_time(time_str)
    return parse_time(start) <= t <= parse_time(end)


# ---------------------------------------------------------------------------
# 营业时间解析
# ---------------------------------------------------------------------------


def parse_opening_hours(hours_str: str) -> tuple[str, str]:
    """解析营业时间字符串为 (开始, 结束) 时间元组。

    Args:
        hours_str: 营业时间字符串，格式 "HH:MM-HH:MM"

    Returns:
        (开始时间, 结束时间) 字符串元组

    Raises:
        ValueError: 格式不合法时
    """
    parts = hours_str.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid opening hours format: {hours_str}")
    return parts[0].strip(), parts[1].strip()


def get_poi_opening_hours(poi: dict[str, Any]) -> tuple[datetime, datetime]:
    """获取 POI 的营业开始/结束时间。

    优先读 constraints.opening_hours，回退到 business_hours，
    最终回退到 "00:00-23:59"。

    Args:
        poi: POI 字典

    Returns:
        (开门时间, 关门时间) datetime 元组
    """
    hours_str = poi.get("constraints", {}).get("opening_hours") or poi.get(
        "business_hours", "00:00-23:59"
    )
    start_str, end_str = parse_opening_hours(hours_str)
    return parse_time(start_str), parse_time(end_str)


def parse_time_window(time_info: dict[str, str]) -> tuple[int, int]:
    """将时间信息字典转为 (start_minutes, end_minutes)。

    Args:
        time_info: 包含 "start" 和 "end" 键的字典，值为 "HH:MM" 格式

    Returns:
        (起始分钟数, 结束分钟数)
    """

    def _to_min(t: str) -> int:
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    return _to_min(time_info["start"]), _to_min(time_info["end"])


def parse_hours_to_minutes(hours_str: str) -> tuple[int, int]:
    """将营业时间字符串转为分钟数。

    Args:
        hours_str: 营业时间字符串，格式 "HH:MM-HH:MM"

    Returns:
        (开门分钟数, 关门分钟数)
    """
    start_str, end_str = parse_opening_hours(hours_str)

    def _to_min(t: str) -> int:
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    return _to_min(start_str), _to_min(end_str)
