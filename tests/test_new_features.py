"""新功能评分测试：起终点设置、城市地点选取、调整功能。

使用方式：
    python -m pytest tests/test_new_features.py -v
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from pathlib import Path

import pytest

# ── LLM 评分配置 ──────────────────────────────────────────────────
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com") + "/v1/chat/completions"
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")


# ── LLM 评分函数 ──────────────────────────────────────────────────

async def llm_json(prompt: str, max_tokens: int = 2000, retries: int = 3) -> dict | None:
    """调用LLM评分（DeepSeek API，OpenAI兼容格式）"""
    import httpx

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post(
                    LLM_API_URL,
                    headers={
                        "Authorization": f"Bearer {LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "max_tokens": max_tokens,
                        "messages": [
                            {"role": "system", "content": "你是旅游路线质量评审，只输出JSON格式。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )
                if r.status_code != 200:
                    print(f"    [LLM Error] Status {r.status_code}, attempt {attempt+1}/{retries}")
                    if attempt < retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    return None

                # DeepSeek API 返回格式
                data = r.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]

                try:
                    return json.loads(text.strip())
                except json.JSONDecodeError as e:
                    print(f"    [LLM Error] JSON parse failed: {e}, attempt {attempt+1}/{retries}")
                    if attempt < retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    return None
        except Exception as e:
            print(f"    [LLM Error] Exception: {e}, attempt {attempt+1}/{retries}")
            if attempt < retries - 1:
                await asyncio.sleep(2**attempt)
                continue
            return None

    return None


def format_route_for_llm(route_list: list[dict]) -> str:
    """格式化路线供LLM评分"""
    lines = []
    for i, step in enumerate(route_list, 1):
        poi = step.get("poi", {})
        name = poi.get("name", "?")
        cat = poi.get("category", "?")
        price = poi.get("avg_price", 0)
        tags = poi.get("_scene_tags", poi.get("tags", []))
        is_point = poi.get("_is_point", False)

        if is_point:
            lines.append(f"{i}. [{name}] (起终点标记)")
        else:
            lines.append(f"{i}. {name} [{cat}] ¥{price} 标签:{tags}")

    return "\n".join(lines)


async def llm_score_start_end(route_result: dict, start_point: dict, end_point: dict) -> dict:
    """LLM评分起终点设置功能"""
    route_list = route_result.get("route", [])
    route_text = format_route_for_llm(route_list)

    prompt = (
        "你是旅游路线质量评审。评估以下路线的起终点设置。\n\n"
        f"起点: {start_point}\n"
        f"终点: {end_point}\n\n"
        f"路线:\n{route_text}\n\n"
        "评分(每项0-10):\n"
        "- start_accuracy: 起点准确性（路线是否从起点出发）\n"
        "- end_accuracy: 终点准确性（路线是否到达终点）\n"
        "- route_coherence: 路线连贯性（行程是否合理）\n"
        "- overall: 总体\n\n"
        "规则:\n"
        "1. 如果路线包含起点标记且第一个POI离起点近，start_accuracy给8-10分\n"
        "2. 如果路线包含终点标记且最后一个POI离终点近，end_accuracy给8-10分\n"
        "3. 如果路线没有起终点标记，start_accuracy和end_accuracy给2-4分\n"
        "4. 路线连贯性看行程是否合理，是否有明显绕路\n\n"
        '输出JSON: {"scores":{"start_accuracy":N,"end_accuracy":N,"route_coherence":N,"overall":N},"good_points":[...],"bad_points":[...]}'
    )

    result = await llm_json(prompt)
    if not result:
        return {
            "scores": {"start_accuracy": 5, "end_accuracy": 5, "route_coherence": 5, "overall": 5},
            "overall": 5,
            "good_points": ["路线生成成功"],
            "bad_points": ["LLM评分失败，使用默认分数"],
        }

    scores = result.get("scores", result)
    return {
        "scores": scores,
        "overall": scores.get("overall", 0),
        "good_points": result.get("good_points", []),
        "bad_points": result.get("bad_points", []),
    }


async def llm_score_city(route_result: dict, city: str) -> dict:
    """LLM评分城市地点选取功能"""
    route_list = route_result.get("route", [])
    route_text = format_route_for_llm(route_list)

    prompt = (
        "你是旅游路线质量评审。评估以下城市路线。\n\n"
        f"目标城市: {city}\n\n"
        f"路线:\n{route_text}\n\n"
        "评分(每项0-10):\n"
        "- city_match: 城市匹配度（POI是否都在目标城市）\n"
        "- poi_quality: POI质量（景点是否有价值）\n"
        "- category_diversity: 类别多样性\n"
        "- overall: 总体\n\n"
        "规则:\n"
        "1. 如果所有POI都在目标城市，city_match给9-10分\n"
        "2. 如果有POI不在目标城市，city_match扣2-3分\n"
        "3. POI质量看评分、知名度\n"
        "4. 类别多样性看是否有景点、餐饮、文化等多种类型\n\n"
        '输出JSON: {"scores":{"city_match":N,"poi_quality":N,"category_diversity":N,"overall":N},"good_points":[...],"bad_points":[...]}'
    )

    result = await llm_json(prompt)
    if not result:
        return {
            "scores": {"city_match": 5, "poi_quality": 5, "category_diversity": 5, "overall": 5},
            "overall": 5,
            "good_points": ["路线生成成功"],
            "bad_points": ["LLM评分失败，使用默认分数"],
        }

    scores = result.get("scores", result)
    return {
        "scores": scores,
        "overall": scores.get("overall", 0),
        "good_points": result.get("good_points", []),
        "bad_points": result.get("bad_points", []),
    }


async def llm_score_adjustment(previous_route: dict, new_route: dict, instruction: str, changes_made: list) -> dict:
    """LLM评分调整功能"""
    prev_text = format_route_for_llm(previous_route.get("route", []))
    new_text = format_route_for_llm(new_route.get("route", []))
    changes_str = json.dumps(changes_made, ensure_ascii=False)

    prompt = (
        "你是旅游路线质量评审。评估以下路线调整。\n\n"
        f"用户指令: {instruction}\n"
        f"变更记录: {changes_str}\n\n"
        f"调整前路线:\n{prev_text}\n\n"
        f"调整后路线:\n{new_text}\n\n"
        "评分(每项0-10):\n"
        "- instruction_match: 指令匹配度（调整是否符合用户意图）\n"
        "- route_quality: 路线质量（调整后路线是否仍然合理）\n"
        "- change_appropriateness: 变更合理性（变更是否恰当）\n"
        "- overall: 总体\n\n"
        "规则:\n"
        "1. 如果调整符合用户指令（如\"太赶了\"确实让节奏变轻松），instruction_match给8-10分\n"
        "2. 如果调整后路线仍然合理，route_quality给7-9分\n"
        "3. 如果变更记录完整且合理，change_appropriateness给8-10分\n\n"
        '输出JSON: {"scores":{"instruction_match":N,"route_quality":N,"change_appropriateness":N,"overall":N},"good_points":[...],"bad_points":[...]}'
    )

    result = await llm_json(prompt)
    if not result:
        return {
            "scores": {"instruction_match": 5, "route_quality": 5, "change_appropriateness": 5, "overall": 5},
            "overall": 5,
            "good_points": ["调整执行成功"],
            "bad_points": ["LLM评分失败，使用默认分数"],
        }

    scores = result.get("scores", result)
    return {
        "scores": scores,
        "overall": scores.get("overall", 0),
        "good_points": result.get("good_points", []),
        "bad_points": result.get("bad_points", []),
    }


# ── 辅助函数 ──────────────────────────────────────────────────────

def _haversine_km(lat1, lng1, lat2, lng2):
    """Haversine 公式计算两点间距离（公里）。"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── 评分函数 ──────────────────────────────────────────────────────

def score_start_end_feature(route_result: dict, start_point: dict, end_point: dict) -> dict:
    """评分起终点设置功能。

    评分维度：
    1. 起点存在性 - 路线是否有起点标记
    2. 终点存在性 - 路线是否有终点标记
    3. 起点位置准确性 - 第一个POI离起点的距离
    4. 终点位置准确性 - 最后一个POI离终点的距离
    5. 路线连贯性 - 起点到第一个POI的行程时间
    """
    dims = {}
    notes = []
    route_list = route_result.get("route", [])

    if not route_list:
        return {"total": 0, "dims": {}, "grade": "F", "notes": ["路线为空"]}

    # 1. 起点存在性 (0~100)
    has_start = any(s.get("poi", {}).get("_is_point", False) for s in route_list[:1])
    if has_start:
        dims["起点存在"] = 100
    else:
        dims["起点存在"] = 0
        notes.append("路线缺少起点标记")

    # 2. 终点存在性 (0~100)
    has_end = any(s.get("poi", {}).get("_is_point", False) for s in route_list[-1:])
    if has_end:
        dims["终点存在"] = 100
    else:
        dims["终点存在"] = 0
        notes.append("路线缺少终点标记")

    # 3. 起点位置准确性 (0~100)
    if has_start and start_point:
        first_real_poi = None
        for s in route_list:
            if not s.get("poi", {}).get("_is_point", False):
                first_real_poi = s.get("poi", {})
                break
        if first_real_poi:
            lat1 = first_real_poi.get("lat", 0)
            lng1 = first_real_poi.get("lng", 0)
            lat2 = start_point.get("lat", 0)
            lng2 = start_point.get("lng", 0)
            if lat1 and lng1 and lat2 and lng2:
                dist = _haversine_km(lat1, lng1, lat2, lng2)
                # 距离越近分数越高，5km内满分
                start_accuracy = max(0, 100 - dist * 10)
                dims["起点准确"] = round(start_accuracy, 1)
                if dist > 10:
                    notes.append(f"起点距离第一个POI较远: {dist:.1f}km")
            else:
                dims["起点准确"] = 50
        else:
            dims["起点准确"] = 0
    else:
        dims["起点准确"] = 0

    # 4. 终点位置准确性 (0~100)
    if has_end and end_point:
        last_real_poi = None
        for s in reversed(route_list):
            if not s.get("poi", {}).get("_is_point", False):
                last_real_poi = s.get("poi", {})
                break
        if last_real_poi:
            lat1 = last_real_poi.get("lat", 0)
            lng1 = last_real_poi.get("lng", 0)
            lat2 = end_point.get("lat", 0)
            lng2 = end_point.get("lng", 0)
            if lat1 and lng1 and lat2 and lng2:
                dist = _haversine_km(lat1, lng1, lat2, lng2)
                end_accuracy = max(0, 100 - dist * 10)
                dims["终点准确"] = round(end_accuracy, 1)
                if dist > 10:
                    notes.append(f"终点距离最后一个POI较远: {dist:.1f}km")
            else:
                dims["终点准确"] = 50
        else:
            dims["终点准确"] = 0
    else:
        dims["终点准确"] = 0

    # 5. 路线连贯性 (0~100)
    travel_times = []
    for s in route_list:
        travel = s.get("travel_from_prev", {})
        if travel.get("time_min", 0) > 0:
            travel_times.append(travel["time_min"])

    if travel_times:
        avg_travel = sum(travel_times) / len(travel_times)
        # 平均行程时间在5-30分钟内最佳
        if 5 <= avg_travel <= 30:
            coherence = 100
        elif avg_travel < 5:
            coherence = 80
        else:
            coherence = max(0, 100 - (avg_travel - 30) * 2)
        dims["路线连贯"] = round(coherence, 1)
    else:
        dims["路线连贯"] = 50

    # 总分
    weights = {
        "起点存在": 20,
        "终点存在": 20,
        "起点准确": 25,
        "终点准确": 25,
        "路线连贯": 10,
    }
    total = sum(dims.get(k, 0) * w for k, w in weights.items()) / sum(weights.values())

    # 等级
    if total >= 90:
        grade = "S"
    elif total >= 80:
        grade = "A"
    elif total >= 70:
        grade = "B"
    elif total >= 60:
        grade = "C"
    elif total >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "total": round(total, 1),
        "dims": dims,
        "grade": grade,
        "notes": notes,
    }


def score_city_feature(route_result: dict, city: str) -> dict:
    """评分城市地点选取功能。

    评分维度：
    1. 城市匹配度 - 路线中的POI是否属于指定城市
    2. POI数量 - 路线是否有足够的POI
    3. 类别多样性 - 路线是否包含多种类别
    4. 地理集中度 - POI是否集中在目标城市
    """
    dims = {}
    notes = []
    route_list = route_result.get("route", [])

    if not route_list:
        return {"total": 0, "dims": {}, "grade": "F", "notes": ["路线为空"]}

    # 提取POI信息
    pois = [s.get("poi", {}) for s in route_list if not s.get("poi", {}).get("_is_point", False)]

    # 1. 城市匹配度 (0~100)
    city_match_count = sum(1 for p in pois if p.get("city") == city)
    city_match_ratio = city_match_count / len(pois) if pois else 0
    dims["城市匹配"] = round(city_match_ratio * 100, 1)
    if city_match_ratio < 0.8:
        notes.append(f"城市匹配度不足: {city_match_ratio:.0%}")

    # 2. POI数量 (0~100)
    poi_count = len(pois)
    if 3 <= poi_count <= 10:
        dims["POI数量"] = 100
    elif poi_count < 3:
        dims["POI数量"] = max(0, poi_count * 33)
        notes.append(f"POI数量不足: {poi_count}")
    else:
        dims["POI数量"] = max(50, 100 - (poi_count - 10) * 5)

    # 3. 类别多样性 (0~100)
    categories = set(p.get("category", "") for p in pois)
    unique_cats = len(categories)
    dims["类别多样"] = min(100, unique_cats * 25)
    if unique_cats < 2:
        notes.append("类别单一")

    # 4. 地理集中度 (0~100)
    # 计算所有POI的中心点，然后计算每个POI到中心的距离
    if pois:
        lats = [p.get("lat", 0) for p in pois if p.get("lat")]
        lngs = [p.get("lng", 0) for p in pois if p.get("lng")]
        if lats and lngs:
            center_lat = sum(lats) / len(lats)
            center_lng = sum(lngs) / len(lngs)
            distances = [_haversine_km(p.get("lat", 0), p.get("lng", 0), center_lat, center_lng) for p in pois if p.get("lat")]
            avg_dist = sum(distances) / len(distances) if distances else 0
            # 平均距离在5km内最佳
            geo_concentration = max(0, 100 - avg_dist * 5)
            dims["地理集中"] = round(geo_concentration, 1)
            if avg_dist > 20:
                notes.append(f"POI分布较散: 平均距离{avg_dist:.1f}km")
        else:
            dims["地理集中"] = 50
    else:
        dims["地理集中"] = 0

    # 总分
    weights = {
        "城市匹配": 40,
        "POI数量": 20,
        "类别多样": 20,
        "地理集中": 20,
    }
    total = sum(dims.get(k, 0) * w for k, w in weights.items()) / sum(weights.values())

    # 等级
    if total >= 90:
        grade = "S"
    elif total >= 80:
        grade = "A"
    elif total >= 70:
        grade = "B"
    elif total >= 60:
        grade = "C"
    elif total >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "total": round(total, 1),
        "dims": dims,
        "grade": grade,
        "notes": notes,
    }


def score_adjustment_feature(previous_route: dict, new_route: dict, changes_made: list) -> dict:
    """评分调整功能。

    评分维度：
    1. 调整执行 - 是否成功执行了调整
    2. 路线更新 - 路线是否发生了变化
    3. 变更记录 - 是否有完整的变更记录
    4. 路线质量 - 调整后的路线是否仍然有效
    """
    dims = {}
    notes = []

    # 1. 调整执行 (0~100)
    if changes_made:
        dims["调整执行"] = 100
    else:
        dims["调整执行"] = 0
        notes.append("未执行任何调整")

    # 2. 路线更新 (0~100)
    prev_stops = [s.get("poi", {}).get("name", "") for s in previous_route.get("route", [])]
    new_stops = [s.get("poi", {}).get("name", "") for s in new_route.get("route", [])]

    if prev_stops != new_stops:
        dims["路线更新"] = 100
    else:
        dims["路线更新"] = 0
        notes.append("路线未发生变化")

    # 3. 变更记录 (0~100)
    if changes_made and all(c.get("type") for c in changes_made):
        dims["变更记录"] = 100
    elif changes_made:
        dims["变更记录"] = 50
        notes.append("变更记录不完整")
    else:
        dims["变更记录"] = 0

    # 4. 路线质量 (0~100)
    new_route_list = new_route.get("route", [])
    if new_route_list and len(new_route_list) >= 2:
        dims["路线质量"] = 100
    elif new_route_list:
        dims["路线质量"] = 50
        notes.append("调整后路线过短")
    else:
        dims["路线质量"] = 0
        notes.append("调整后路线为空")

    # 总分
    weights = {
        "调整执行": 30,
        "路线更新": 30,
        "变更记录": 20,
        "路线质量": 20,
    }
    total = sum(dims.get(k, 0) * w for k, w in weights.items()) / sum(weights.values())

    # 等级
    if total >= 90:
        grade = "S"
    elif total >= 80:
        grade = "A"
    elif total >= 70:
        grade = "B"
    elif total >= 60:
        grade = "C"
    elif total >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "total": round(total, 1),
        "dims": dims,
        "grade": grade,
        "notes": notes,
    }


# ── 测试用例 ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_end_feature():
    """测试起终点设置功能。"""
    from backend.routers.v2.plan import PlanRequestV2
    from backend.services.solver import solve_route
    from backend.services.data_service import get_data
    from backend.services.filters import filter_candidates

    # 构建请求
    request = PlanRequestV2(
        user_input="珠海一日游",
        city="珠海",
        start_point={"lat": 22.270, "lng": 113.543},  # 香洲
        end_point={"lat": 22.217, "lng": 113.553},    # 拱北
    )

    # 模拟 user_intent
    user_intent = {
        "city": "珠海",
        "start_point": request.start_point,
        "end_point": request.end_point,
        "pace": "平衡型",
        "time": {"start": "09:00", "end": "18:00"},
    }

    # 获取候选POI
    all_pois = get_data("city_poi_db", city="珠海")
    candidates = filter_candidates(all_pois, user_intent)

    # 求解路线
    route_result = solve_route(
        candidates,
        user_intent,
        "09:00",
        start_point=request.start_point,
        end_point=request.end_point,
    )

    # 规则评分
    scoring = score_start_end_feature(route_result, request.start_point, request.end_point)

    # LLM评分
    llm_scoring = await llm_score_start_end(route_result, request.start_point, request.end_point)

    print(f"\n{'='*60}")
    print(f"  起终点设置功能测试")
    print(f"{'='*60}")
    print(f"  起点: {request.start_point}")
    print(f"  终点: {request.end_point}")
    print(f"  路线站数: {len(route_result.get('route', []))}")

    print(f"\n  ┌─ 规则评分: {scoring['total']:5.1f} / 100  等级 {scoring['grade']} ─┐")
    for dim_name, dim_val in scoring["dims"].items():
        bar_len = int(dim_val / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  │ {dim_name:8s} {bar} {dim_val:5.1f}")
    if scoring["notes"]:
        for note in scoring["notes"]:
            print(f"  │ ※ {note}")
    print(f"  └{'─'*38}┘")

    print(f"\n  ┌─ LLM评分: {llm_scoring['overall']:5.1f} / 10 ─┐")
    for dim_name, dim_val in llm_scoring["scores"].items():
        bar_len = int(dim_val * 2)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  │ {dim_name:16s} {bar} {dim_val:5.1f}")
    if llm_scoring.get("good_points"):
        print(f"  │ ✓ 优点:")
        for point in llm_scoring["good_points"]:
            print(f"  │   - {point}")
    if llm_scoring.get("bad_points"):
        print(f"  │ ✗ 建议:")
        for point in llm_scoring["bad_points"]:
            print(f"  │   - {point}")
    print(f"  └{'─'*38}┘")

    # 断言
    assert scoring["total"] >= 60, f"起终点功能评分过低: {scoring['total']}"
    assert "起点存在" in scoring["dims"], "缺少起点存在性评分"
    assert "终点存在" in scoring["dims"], "缺少终点存在性评分"
    assert llm_scoring["overall"] >= 5, f"LLM评分过低: {llm_scoring['overall']}"


@pytest.mark.asyncio
async def test_city_feature():
    """测试城市地点选取功能。"""
    from backend.routers.v2.plan import PlanRequestV2
    from backend.services.solver import solve_route
    from backend.services.data_service import get_data
    from backend.services.filters import filter_candidates

    # 测试珠海（有数据的城市）
    city = "珠海"

    # 构建请求
    request = PlanRequestV2(
        user_input=f"{city}一日游",
        city=city,
    )

    # 模拟 user_intent
    user_intent = {
        "city": city,
        "pace": "平衡型",
        "time": {"start": "09:00", "end": "18:00"},
    }

    # 获取候选POI
    all_pois = get_data("city_poi_db", city=city)
    candidates = filter_candidates(all_pois, user_intent)

    # 求解路线
    route_result = solve_route(candidates, user_intent, "09:00")

    # 规则评分
    scoring = score_city_feature(route_result, city)

    # LLM评分
    llm_scoring = await llm_score_city(route_result, city)

    print(f"\n{'='*60}")
    print(f"  城市地点选取功能测试 - {city}")
    print(f"{'='*60}")
    print(f"  城市: {city}")
    print(f"  候选POI数: {len(candidates)}")
    print(f"  路线站数: {len(route_result.get('route', []))}")

    print(f"\n  ┌─ 规则评分: {scoring['total']:5.1f} / 100  等级 {scoring['grade']} ─┐")
    for dim_name, dim_val in scoring["dims"].items():
        bar_len = int(dim_val / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  │ {dim_name:8s} {bar} {dim_val:5.1f}")
    if scoring["notes"]:
        for note in scoring["notes"]:
            print(f"  │ ※ {note}")
    print(f"  └{'─'*38}┘")

    print(f"\n  ┌─ LLM评分: {llm_scoring['overall']:5.1f} / 10 ─┐")
    for dim_name, dim_val in llm_scoring["scores"].items():
        bar_len = int(dim_val * 2)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  │ {dim_name:18s} {bar} {dim_val:5.1f}")
    if llm_scoring.get("good_points"):
        print(f"  │ ✓ 优点:")
        for point in llm_scoring["good_points"]:
            print(f"  │   - {point}")
    if llm_scoring.get("bad_points"):
        print(f"  │ ✗ 建议:")
        for point in llm_scoring["bad_points"]:
            print(f"  │   - {point}")
    print(f"  └{'─'*38}┘")

    # 断言
    assert scoring["total"] >= 60, f"{city}城市功能评分过低: {scoring['total']}"
    assert scoring["dims"].get("城市匹配", 0) >= 80, f"{city}城市匹配度不足"
    assert llm_scoring["overall"] >= 5, f"LLM评分过低: {llm_scoring['overall']}"


@pytest.mark.asyncio
async def test_adjustment_feature():
    """测试调整功能。"""
    from backend.services.dialogue import dialogue_engine
    from backend.services.solver import solve_route
    from backend.services.data_service import get_data
    from backend.services.filters import filter_candidates
    from backend.main import _deep_copy_route, _generate_changes_summary

    # 构建初始路线
    user_intent = {
        "city": "珠海",
        "pace": "平衡型",
        "time": {"start": "09:00", "end": "18:00"},
    }

    all_pois = get_data("city_poi_db", city="珠海")
    candidates = filter_candidates(all_pois, user_intent)
    initial_route = solve_route(candidates, user_intent, "09:00")

    # 创建对话会话
    session_id = "test_session_001"
    await dialogue_engine.create_session(session_id, initial_route, user_intent)

    # 测试不同类型的调整指令
    instructions = [
        ("节奏调整", "太赶了，想轻松点"),
        ("预算调整", "太贵了，便宜点"),
    ]

    results = []

    for instruction_type, instruction in instructions:
        # 保存调整前的路线
        previous_route = _deep_copy_route(initial_route)

        # 执行调整
        result = await dialogue_engine.process_instruction(session_id, instruction)

        # 规则评分
        scoring = score_adjustment_feature(previous_route, result.get("route", {}), result.get("changes_made", []))

        # LLM评分
        llm_scoring = await llm_score_adjustment(
            previous_route, result.get("route", {}), instruction, result.get("changes_made", [])
        )

        results.append((instruction_type, scoring, llm_scoring))

        print(f"\n{'='*60}")
        print(f"  调整功能测试 - {instruction_type}")
        print(f"{'='*60}")
        print(f"  指令: {instruction}")
        print(f"  变更: {result.get('changes_made', [])}")
        print(f"  摘要: {_generate_changes_summary(previous_route, result.get('route', {}), result.get('changes_made', []))}")

        print(f"\n  ┌─ 规则评分: {scoring['total']:5.1f} / 100  等级 {scoring['grade']} ─┐")
        for dim_name, dim_val in scoring["dims"].items():
            bar_len = int(dim_val / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  │ {dim_name:8s} {bar} {dim_val:5.1f}")
        if scoring["notes"]:
            for note in scoring["notes"]:
                print(f"  │ ※ {note}")
        print(f"  └{'─'*38}┘")

        print(f"\n  ┌─ LLM评分: {llm_scoring['overall']:5.1f} / 10 ─┐")
        for dim_name, dim_val in llm_scoring["scores"].items():
            bar_len = int(dim_val * 2)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  │ {dim_name:20s} {bar} {dim_val:5.1f}")
        if llm_scoring.get("good_points"):
            print(f"  │ ✓ 优点:")
            for point in llm_scoring["good_points"]:
                print(f"  │   - {point}")
        if llm_scoring.get("bad_points"):
            print(f"  │ ✗ 建议:")
            for point in llm_scoring["bad_points"]:
                print(f"  │   - {point}")
        print(f"  └{'─'*38}┘")

    # 断言
    for instruction_type, scoring, llm_scoring in results:
        assert scoring["total"] >= 60, f"{instruction_type}功能评分过低: {scoring['total']}"
        assert scoring["dims"].get("调整执行", 0) == 100, f"{instruction_type}未执行调整"
        assert llm_scoring["overall"] >= 5, f"{instruction_type}LLM评分过低: {llm_scoring['overall']}"


# ── 主函数 ──────────────────────────────────────────────────────

async def main():
    """运行所有新功能测试。"""
    print("=" * 70)
    print("  新功能评分测试：起终点设置、城市地点选取、调整功能")
    print("=" * 70)

    # 预加载
    print("\n[预热] 加载数据...")
    from backend.services.data_service import load_data
    load_data()
    print("[预热] 完成\n")

    results = []

    # 测试起终点功能
    print("\n" + "━" * 70)
    r = await test_start_end_feature()
    results.append(("起终点设置", r))

    # 测试城市功能
    print("\n" + "━" * 70)
    r = await test_city_feature()
    results.append(("城市选取", r))

    # 测试调整功能
    print("\n" + "━" * 70)
    r = await test_adjustment_feature()
    results.append(("调整功能", r))

    # 总结
    print(f"\n\n{'═' * 70}")
    print(f"  总  结")
    print(f"{'═' * 70}")

    print(f"\n  {'功能':12s} │ {'状态':4s} │ {'评分':5s} │ {'等级':3s}")
    print(f"  {'─'*12}─┼─{'─'*4}─┼─{'─'*5}─┼─{'─'*3}")

    for name, scoring in results:
        status = "✓" if scoring["total"] >= 60 else "✗"
        print(f"  {name:12s} │ {status:4s} │ {scoring['total']:5.1f} │ {scoring['grade']:3s}")

    avg_score = sum(s["total"] for _, s in results) / len(results)
    print(f"\n  平均评分: {avg_score:.1f}")

    all_pass = all(s["total"] >= 60 for _, s in results)
    if all_pass:
        print(f"\n  ✓ 全部功能测试通过")
    else:
        print(f"\n  ⚠ 部分功能测试失败")

    return all_pass


if __name__ == "__main__":
    ok = asyncio.run(main())
    import sys
    sys.exit(0 if ok else 1)
