"""CityFlow POI 场景标签 + 路线合理性审核。

给 POI 打场景标签（海边/山景/市区/亲子/情侣等），
并在规划完成后审核路线合理性。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── 场景标签规则 ────────────────────────────────────────────────

# 关键词 → 场景标签
_NAME_TAGS: list[tuple[str, str]] = [
    # 海边/水边
    ("海", "海滨"),
    ("沙滩", "海滨"),
    ("沙", "海滨"),
    ("湾", "海滨"),
    ("浪", "海滨"),
    ("岛", "海滨"),
    ("码头", "海滨"),
    ("渔", "海滨"),
    ("滨", "海滨"),
    ("沿岸", "海滨"),
    # 山/自然
    ("山", "山景"),
    ("公园", "公园"),
    ("植物", "自然"),
    ("森林", "自然"),
    ("湖", "自然"),
    ("自然", "自然"),
    # 市区
    ("街", "市区"),
    ("广场", "市区"),
    ("中心", "市区"),
    ("城", "市区"),
    # 文化
    ("历史", "文化"),
    ("博物馆", "文化"),
    ("展览", "文化"),
    ("艺术", "文化"),
    ("文化", "文化"),
    ("纪念", "文化"),
    ("祠", "文化"),
    ("宫", "文化"),
    ("寺", "文化"),
    ("馆", "文化"),
    ("书院", "文化"),
    ("大学", "文化"),
    # 亲子
    ("儿童", "亲子"),
    ("亲子", "亲子"),
    ("乐园", "亲子"),
    ("游乐", "亲子"),
    ("主题公园", "亲子"),
    # 情侣
    ("浪漫", "情侣"),
    ("咖啡", "情侣"),
    ("甜品", "情侣"),
    # 运动
    ("健身", "运动"),
    ("瑜伽", "运动"),
    ("跑步", "运动"),
    ("球", "运动"),
    ("泳", "运动"),
    ("运动", "运动"),
    # 餐饮
    ("餐", "餐饮"),
    ("美食", "餐饮"),
    ("小吃", "餐饮"),
    ("茶", "餐饮"),
    ("厅", "餐饮"),
    ("吧", "餐饮"),
    ("食堂", "餐饮"),
    # 购物
    ("购物", "购物"),
    ("商", "购物"),
    ("市场", "购物"),
    # 夜景
    ("夜景", "夜景"),
    ("夜市", "夜景"),
]

# 已有 tag → 场景标签
_TAG_MAP: dict[str, str] = {
    "免费": "经济",
    "涨知识": "文化",
    "值得去": "经典",
    "拍照": "出片",
    "打卡": "出片",
    "悠闲": "休闲",
    "适合拍照": "出片",
    "夜景": "夜景",
    "自然": "自然",
    "亲子": "亲子",
    "浪漫": "情侣",
}


def tag_poi(poi: dict) -> list[str]:
    """给单个 POI 打场景标签。

    基于 POI 名称、tags、category 生成场景标签。
    结果会写入 poi["_scene_tags"]。

    返回: 场景标签列表
    """
    name = poi.get("name", "")
    tags = poi.get("tags", [])
    category = poi.get("category", "")
    name_lower = name.lower()

    scenes: list[str] = []

    # 1. 名称匹配
    for kw, tag in _NAME_TAGS:
        if kw in name_lower or kw in name:
            if tag not in scenes:
                scenes.append(tag)

    # 2. tag 匹配
    for t in tags:
        mapped = _TAG_MAP.get(t)
        if mapped and mapped not in scenes:
            scenes.append(mapped)

    # 3. category 推断
    if category == "餐饮" and "餐饮" not in scenes:
        scenes.append("餐饮")
    if category == "运动" and "运动" not in scenes:
        scenes.append("运动")
    if category == "文化" and "文化" not in scenes:
        scenes.append("文化")
    if category == "购物" and "购物" not in scenes:
        scenes.append("购物")

    # 4. 酒店不过滤（可能重要但少推）
    if category == "酒店" and "住宿" not in scenes:
        scenes.append("住宿")

    poi["_scene_tags"] = scenes
    return scenes


def tag_all_pois(pois: list[dict]) -> None:
    """批量打标签。"""
    for poi in pois:
        tag_poi(poi)


# ── 路线合理性审核 ──────────────────────────────────────────────

RouteAudit = dict[str, Any]


def audit_route(route_result: dict, user_intent: dict | None = None) -> list[RouteAudit]:
    """审核路线合理性，返回问题列表。

    检查项:
    1. 地理回跳 - 前后 POI 距离过远（>10km）
    2. 时间不合理 - 时间重叠或顺序错误
    3. 类别重复 - 连续同类 POI
    4. 预算超限 - 超出意图预算
    5. 路线过于松散/紧凑
    6. 未形成回路（最后没回家）

    返回: [{"severity": "error"/"warning", "message": str, "detail": dict}, ...]
    """
    issues: list[RouteAudit] = []
    route = route_result.get("route", [])
    if not route:
        return issues

    # 1. 地理回跳检查
    _check_geo_backtrack(route, issues)

    # 2. 时间合理性
    _check_time_order(route, issues)

    # 3. 类别重复
    _check_category_repeat(route, issues)

    # 4. 预算
    if user_intent:
        _check_budget(route, user_intent, issues)

    # 5. 节奏
    _check_pace(route, issues)

    # 6. 回路检查（如果有起点）
    if route_result.get("start_location"):
        _check_return_home(route, route_result.get("start_location", ""), issues)

    return issues


def _check_geo_backtrack(route: list[dict], issues: list) -> None:
    """检查地理回跳。"""
    from backend.services.geo import poi_distance as calc_dist

    for i in range(1, len(route)):
        prev = route[i - 1].get("poi", {})
        curr = route[i].get("poi", {})
        if not prev or not curr:
            continue

        dist = calc_dist(prev, curr)
        if dist > 10000:  # >10km
            issues.append(
                {
                    "severity": "warning",
                    "message": f"步骤{i}→{i+1}距离{dist/1000:.1f}km，可能跨区",
                    "detail": {
                        "from": prev.get("name"),
                        "to": curr.get("name"),
                        "distance_m": dist,
                    },
                }
            )

    # 首尾距离（回路检查）
    if len(route) >= 3:
        first = route[0].get("poi", {})
        last = route[-1].get("poi", {})
        if first and last:
            end_dist = calc_dist(first, last)
            if end_dist > 10000:
                issues.append(
                    {
                        "severity": "warning",
                        "message": f"末站距首站{end_dist/1000:.1f}km，返程可能较远",
                        "detail": {"distance_m": end_dist},
                    }
                )


def _check_time_order(route: list[dict], issues: list) -> None:
    """检查时间顺序。"""
    for i in range(1, len(route)):
        prev_arr = route[i - 1].get("arrival_time", "")
        curr_arr = route[i].get("arrival_time", "")
        if prev_arr and curr_arr and prev_arr >= curr_arr:
            issues.append(
                {
                    "severity": "error",
                    "message": f"步骤{i}→{i+1}时间倒流: {prev_arr}→{curr_arr}",
                    "detail": {"index": i},
                }
            )


def _check_category_repeat(route: list[dict], issues: list) -> None:
    """检查类别重复。"""
    consecutive = 0
    last_cat = ""
    for i, step in enumerate(route, 1):
        cat = step.get("poi", {}).get("category", "")
        if cat == last_cat and cat:
            consecutive += 1
            if consecutive >= 3:
                issues.append(
                    {
                        "severity": "warning",
                        "message": f"连续{consecutive+1}个同类景点（{cat}），体验单调",
                        "detail": {"index": i, "category": cat},
                    }
                )
        else:
            consecutive = 0
            last_cat = cat


def _check_budget(route: list[dict], user_intent: dict, issues: list) -> None:
    """检查预算。"""
    budget_limit = user_intent.get("budget", {}).get("per_person", 0)
    if not budget_limit:
        return

    total = sum(step.get("poi", {}).get("avg_price", 0) for step in route)
    if total > budget_limit * 1.2:
        issues.append(
            {
                "severity": "warning",
                "message": f"总花费¥{total}超出预算¥{budget_limit}",
                "detail": {"total": total, "limit": budget_limit},
            }
        )


def _check_pace(route: list[dict], issues: list) -> None:
    """检查节奏合理性。"""
    if len(route) >= 6:
        issues.append(
            {
                "severity": "info",
                "message": f"路线共{len(route)}站，可能较紧凑",
                "detail": {"count": len(route)},
            }
        )


def _check_return_home(route: list[dict], start_location: str, issues: list) -> None:
    """检查是否形成回路。"""
    first = route[0].get("poi", {})
    last = route[-1].get("poi", {})

    if not first or not last:
        return

    # 简单提示：末站不是起点
    issues.append(
        {
            "severity": "info",
            "message": f"起点: {first.get('name','?')} 末站: {last.get('name','?')}，建议规划返程路线",
            "detail": {"start": start_location},
        }
    )
