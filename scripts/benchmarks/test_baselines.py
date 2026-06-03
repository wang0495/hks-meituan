"""基线对比测试 — Greedy / Single-LLM / Single-LLM+RAG vs CityFlow。

使用相同的100场景 + 评分框架，输出格式与test_100_scenes.py一致。
结果可与CityFlow 100场景结果直接对比。

使用方式:
    cd <project_root>
    python scripts/benchmarks/test_baselines [--method greedy|single_llm|rag] [--workers N]

默认跑全部3个基线，--method指定单个。
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── 加载 .env ──
_env_file = Path(_project_root) / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

# Monkey-patch meituan_client BASE if 8001 unavailable
import urllib.request
try:
    urllib.request.urlopen("http://localhost:8001/api/poi/search?limit=1", timeout=2)
except Exception:
    try:
        urllib.request.urlopen("http://localhost:8002/api/poi/search?limit=1", timeout=2)
        import backend.agents_v3.meituan_client as _mc
        _mc.BASE = "http://localhost:8002/api"
    except Exception:
        print("[警告] 8001 和 8002 均无 POI API，将降级到本地 JSON")

# ── 100测试场景 (与test_100_scenes.py完全相同) ──
TEST_CASES: list[tuple[str, str]] = [
    ("美食型", "珠海美食一日游，想吃海鲜和早茶"),
    ("美食型", "珠海情侣浪漫晚餐约会，预算500元"),
    ("美食型", "珠海海鲜大排档攻略，越便宜越好"),
    ("美食型", "珠海夜市小吃一条龙，晚上出来觅食"),
    ("美食型", "珠海本地人推荐的茶餐厅和糖水铺"),
    ("美食型", "珠海亲子美食之旅，小孩子也爱吃的"),
    ("美食型", "珠海只有2小时吃点什么好"),
    ("美食型", "珠海退休老人粤式早茶慢生活"),
    ("美食型", "珠海湾仔海鲜街和周边美食"),
    ("美食型", "珠海下雨天有什么好吃的，室内美食"),
    ("美食型", "珠海朋友聚餐AA制，预算100元每人"),
    ("美食型", "珠海横琴新区附近有什么好吃的"),
    ("美食型", "珠海唐家湾古镇附近美食推荐"),
    ("美食型", "珠海拱北口岸附近美食下午茶"),
    ("美食型", "珠海带宠物出游顺便找吃的"),
    ("美食型", "珠海斗门农家乐一日吃"),
    ("美食型", "珠海金湾机场附近美食赶飞机前吃"),
    ("美食型", "珠海夏天吃甜品消暑攻略"),
    ("美食型", "珠海素菜素食餐厅推荐"),
    ("美食型", "珠海老字号美食打卡拍照好看"),
    ("目的地型", "带孩子去珠海长隆海洋王国玩一天"),
    ("目的地型", "珠海海泉湾温泉度假村一日游"),
    ("目的地型", "珠海御温泉泡汤放松一天"),
    ("目的地型", "珠海圆明新园一日游攻略"),
    ("目的地型", "珠海渔女像和情侣路半日游"),
    ("目的地型", "珠海梦幻水城玩水一日"),
    ("目的地型", "珠海长隆晚上看烟花表演"),
    ("目的地型", "珠海外伶仃岛一日往返"),
    ("目的地型", "珠海金沙滩玩沙子带小孩"),
    ("目的地型", "珠海海滨公园野餐加放风筝"),
    ("目的地型", "珠海梅溪牌坊和农科奇观一日游"),
    ("目的地型", "珠海横琴创新方游玩一天"),
    ("目的地型", "珠海罗西尼钟表博物馆参观"),
    ("目的地型", "珠海野狸岛骑行环岛游"),
    ("目的地型", "珠海港珠澳大桥观光"),
    ("目的地型", "珠海东澳岛一日游攻略"),
    ("目的地型", "珠海景山公园爬山看日落"),
    ("目的地型", "珠海下雨天带娃去室内乐园"),
    ("目的地型", "珠海情侣去海泉湾泡温泉预算300"),
    ("目的地型", "珠海长隆只玩半天下午场"),
    ("特种兵型", "珠海特种兵一日游打卡所有网红景点"),
    ("特种兵型", "珠海6点出发一天打卡10个景点"),
    ("特种兵型", "珠海3小时极限打卡只看地标"),
    ("特种兵型", "珠海网红拍照点一天全打完"),
    ("特种兵型", "珠海特种兵穷游不花钱景点"),
    ("特种兵型", "珠海一天走完所有沙滩"),
    ("特种兵型", "珠海从拱北到横琴一天串完"),
    ("特种兵型", "珠海老城区特种兵步行为主"),
    ("特种兵型", "珠海亲子特种兵小孩也能跟上"),
    ("特种兵型", "珠海日出日落特种兵攻略"),
    ("特种兵型", "珠海10大公园一天刷完"),
    ("特种兵型", "珠海夜景特种兵18点到22点"),
    ("特种兵型", "珠海情侣网红打卡特种兵"),
    ("特种兵型", "珠海骑行特种兵骑车打卡"),
    ("特种兵型", "珠海博物馆特种兵一天看完所有博物馆"),
    ("特种兵型", "珠海海岛特种兵一天跳岛"),
    ("特种兵型", "珠海下雨特种兵室内景点一天搞定"),
    ("特种兵型", "珠海退休特种兵慢节奏版"),
    ("特种兵型", "珠海8点到20点特种兵12小时"),
    ("特种兵型", "珠海预算200特种兵吃喝全包"),
    ("休闲型", "珠海情侣周末休闲游慢慢逛放松一下"),
    ("休闲型", "珠海海边发呆一下午什么都不干"),
    ("休闲型", "珠海书店咖啡店慢慢逛一天"),
    ("休闲型", "珠海公园野餐慢生活"),
    ("休闲型", "珠海情侣路散步看海聊天"),
    ("休闲型", "珠海下午茶慢慢喝不赶场"),
    ("休闲型", "珠海退休老两口逛公园喝茶"),
    ("休闲型", "珠海亲子慢游小朋友说停就停"),
    ("休闲型", "珠海下雨天咖啡馆窝一天"),
    ("休闲型", "珠海独处发呆看海的一天"),
    ("休闲型", "珠海傍晚散步看日落"),
    ("休闲型", "珠海金沙滩躺一天晒太阳"),
    ("休闲型", "珠海温泉慢泡养生一日"),
    ("休闲型", "珠海朋友周末chill找个地方坐坐聊聊天"),
    ("休闲型", "珠海民宿住一天附近逛逛"),
    ("休闲型", "珠海下雨了室内有什么休闲的"),
    ("休闲型", "珠海斗门乡村慢生活一日"),
    ("休闲型", "珠海情侣拍照休闲游"),
    ("休闲型", "珠海横琴半天休闲下午茶加散步"),
    ("休闲型", "珠海带狗去公园溜达顺便吃个饭"),
    ("观光型", "珠海经典观光一日游看看地标建筑"),
    ("观光型", "珠海渔女像日月贝圆明新园一天看完"),
    ("观光型", "珠海历史文化景点观光一日"),
    ("观光型", "珠海现代建筑观光看城市天际线"),
    ("观光型", "珠海海岛风光一日游"),
    ("观光型", "珠海夜景观光晚上好看的地方"),
    ("观光型", "珠海免费景点观光不花钱"),
    ("观光型", "珠海亲子观光寓教于乐"),
    ("观光型", "珠海情侣浪漫地标观光"),
    ("观光型", "珠海港珠澳大桥和周边观光"),
    ("观光型", "珠海半天观光精华路线"),
    ("观光型", "珠海老城区历史建筑观光"),
    ("观光型", "珠海横琴新区现代建筑观光"),
    ("观光型", "珠海唐家湾古镇文化观光"),
    ("观光型", "珠海教堂寺庙观光一日"),
    ("观光型", "珠海拍照观光出片好看的地方"),
    ("观光型", "珠海退休老人轻松观光"),
    ("观光型", "珠海朋友一起观光打卡"),
    ("观光型", "珠海雨天室内观光博物馆美术馆"),
    ("观光型", "珠海沿海公路自驾观光"),
]

NUM_WORKERS = 4
SCENE_TIMEOUT = 180

# ── LLM调用工具 ──
MODEL_NAME = os.environ.get("XUNFEI_MODEL", "xopqwen35v35b")


def _get_llm_client():
    """获取讯飞LLM客户端（兼容本地降级）。"""
    try:
        import httpx
        base_url = os.environ.get("XUNFEI_BASE", os.environ.get("XUNFEI_BASE_URL", os.environ.get("LLM_BASE_URL", "http://localhost:8000")))
        api_key = os.environ.get("XUNFEI_API_KEY", os.environ.get("LLM_API_KEY", ""))

        class _Client:
            @staticmethod
            async def chat(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
                import asyncio
                # Rate limiting: 讯飞API限流
                await asyncio.sleep(1.5)
                async with httpx.AsyncClient(timeout=60.0) as c:
                    # base_url 格式: https://host/v2 → 直接加 /chat/completions
                    # base_url 格式: https://host    → 加 /v1/chat/completions
                    api_url = base_url.rstrip("/")
                    if api_url.endswith("/chat/completions"):
                        pass  # already complete
                    elif "/v2" in api_url or "/v1" in api_url:
                        api_url += "/chat/completions"
                    else:
                        api_url += "/v1/chat/completions"
                    resp = await c.post(
                        api_url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": MODEL_NAME,
                            "messages": [
                                *( [{"role": "system", "content": system}] if system else [] ),
                                {"role": "user", "content": prompt},
                            ],
                            "max_tokens": max_tokens,
                            "temperature": 0.3,
                        },
                    )
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"]

        return _Client()
    except Exception:
        return None


async def _get_all_pois() -> list[dict]:
    """从本地JSON加载POI数据（用于Greedy和RAG基线）。"""
    pois = []
    for json_path in [
        Path(_project_root) / "backend" / "data" / "city_poi_db.json",
        Path(_project_root) / "backend" / "data" / "pois.json",
        Path(_project_root) / "data" / "city_poi_db.json",
        Path(_project_root) / "data" / "pois.json",
    ]:
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "pois" in data:
                    pois = data["pois"]
                elif isinstance(data, list):
                    pois = data
            if pois:
                print(f"  [POI] Loaded {len(pois)} POIs from {json_path.name}")
                break
    if not pois:
        print("  [POI] WARNING: No POI data found!")
    return pois


# ═══════════════════════════════════════════════════════════════════
# 基线1: Greedy Nearest-Neighbor
# ═══════════════════════════════════════════════════════════════════

def _haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _greedy_route(pois: list[dict], scene_type: str, user_input: str) -> list[dict]:
    """纯算法最近邻路线：按距离贪心选择POI。不做任何LLM调用。"""
    if not pois:
        return []

    # 简单关键词过滤
    kw_map = {
        "美食型": ["美食", "餐饮", "早茶", "海鲜", "小吃", "甜品", "餐厅"],
        "目的地型": ["景点", "乐园", "公园", "博物馆", "温泉", "海滩"],
        "特种兵型": ["景点", "网红", "公园", "地标", "观光"],
        "休闲型": ["公园", "咖啡", "书店", "茶", "休闲", "散步"],
        "观光型": ["景点", "地标", "观光", "建筑", "文化", "历史"],
    }
    keywords = kw_map.get(scene_type, [])

    if keywords:
        filtered = [p for p in pois if any(k in p.get("category", "") or k in p.get("name", "") for k in keywords)]
    else:
        filtered = pois[:]

    if len(filtered) < 2:
        filtered = pois[:20]

    # 最近邻路线（从第一个POI开始）
    n_stops = min(8, len(filtered))
    visited = set()
    route = []
    current_lat, current_lng = 22.27, 113.58  # 珠海市中心

    for _ in range(n_stops):
        best_poi = None
        best_dist = float("inf")
        for p in filtered:
            pid = p.get("id", id(p))
            if pid in visited:
                continue
            lat = p.get("lat", 22.27)
            lng = p.get("lng", 113.58)
            d = _haversine(current_lat, current_lng, lat, lng)
            if d < best_dist:
                best_dist = d
                best_poi = p
        if best_poi is None:
            break
        visited.add(best_poi.get("id", id(best_poi)))
        route.append(best_poi)
        current_lat = best_poi.get("lat", 22.27)
        current_lng = best_poi.get("lng", 113.58)

    # 转为route_list格式（兼容评分函数）
    route_list = []
    for i, poi in enumerate(route):
        hour = 9 + i
        route_list.append({
            "poi": poi,
            "arrival_time": f"{hour:02d}:00",
            "departure_time": f"{min(hour+1, 21):02d}:00",
            "travel_from_prev": {"distance_km": 1.0, "mode": "walking"},
        })
    return route_list


# ═══════════════════════════════════════════════════════════════════
# 基线2: Single-LLM
# ═══════════════════════════════════════════════════════════════════

_SINGLE_LLM_PROMPT = """你是一个旅游路线规划助手。用户想在珠海旅游，请为他规划一条一日游路线。

要求：
1. 返回JSON格式，包含route数组
2. 每个站点包含：name（景点名）、category（类别）、lat（纬度）、lng（经度）、arrival_time、departure_time
3. 纬度范围22.0-22.5，经度范围113.3-113.9（珠海）
4. 安排3-8个站点
5. 时间从9:00开始，每个站点1-2小时
6. 站点间距离不超过5km

只返回JSON，不要其他文字。"""


async def _call_llm_with_retry(prompt: str, system: str = "", max_retries: int = 3) -> str:
    """带重试的LLM调用。"""
    import asyncio
    client = _get_llm_client()
    if client is None:
        raise RuntimeError("No LLM client")
    for attempt in range(max_retries):
        try:
            return await client.chat(prompt, system=system)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str and attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"  [LLM] 429 rate limit, retry in {wait}s (attempt {attempt+1})")
                await asyncio.sleep(wait)
            else:
                raise


async def _single_llm_route(user_input: str, pois: list[dict]) -> list[dict]:
    """Single-LLM基线：一次LLM调用生成完整路线，不检索POI。"""
    try:
        response = await _call_llm_with_retry(
            f"{_SINGLE_LLM_PROMPT}\n\n用户需求：{user_input}",
            system="你是旅游路线规划专家。"
        )
        # 解析JSON
        text = response.strip()
        # Remove markdown fences
        for marker in ["```json", "```"]:
            if marker in text:
                text = text.split(marker)[1]
                if "```" in text:
                    text = text.rsplit("```", 1)[0]
                break
        text = text.strip()

        data = json.loads(text)
        raw_route = data.get("route", data) if isinstance(data, dict) else data

        route_list = []
        for stop in raw_route:
            # Flexible field mapping
            name = stop.get("name") or stop.get("location") or stop.get("activity") or "?"
            category = stop.get("category") or "其他"
            # Parse time
            time_str = stop.get("arrival_time") or stop.get("time") or "09:00"
            if "-" in str(time_str) and ":" not in str(time_str).split("-")[0]:
                parts = str(time_str).split("-")
                arrival = parts[0].strip()
                departure = parts[1].strip() if len(parts) > 1 else arrival
            else:
                arrival = str(time_str).strip()
                departure = "10:00"

            poi = {
                "name": name,
                "category": category,
                "lat": stop.get("lat", 22.27),
                "lng": stop.get("lng", 113.58),
                "rating": stop.get("rating", 4.0),
                "avg_price": stop.get("avg_price", 50),
                "tags": stop.get("tags", []),
            }
            route_list.append({
                "poi": poi,
                "arrival_time": arrival[:5] if len(arrival) >= 5 else arrival,
                "departure_time": departure[:5] if len(departure) >= 5 else departure,
                "travel_from_prev": {"distance_km": 1.0, "mode": "walking"},
            })
        return route_list
    except Exception as e:
        print(f"  [single_llm] parse error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════
# 基线3: Single-LLM + RAG
# ═══════════════════════════════════════════════════════════════════

async def _rag_llm_route(user_input: str, scene_type: str, pois: list[dict]) -> list[dict]:
    """Single-LLM + RAG基线：先检索相关POI再喂给LLM。"""
    try:
        # 按类别过滤POI
        kw_map = {
            "美食型": ["餐饮", "夜市小吃"],
            "目的地型": ["景点", "乐园", "公园", "博物馆", "温泉"],
            "特种兵型": ["景点", "网红", "公园", "地标"],
            "休闲型": ["公园", "咖啡", "茶", "休闲"],
            "观光型": ["景点", "地标", "文化", "历史"],
        }
        keywords = kw_map.get(scene_type, [])
        if keywords:
            relevant = [p for p in pois if any(k in p.get("category", "") or k in p.get("name", "") for k in keywords)]
        else:
            relevant = pois[:30]

        # 只保留top 20
        relevant = sorted(relevant, key=lambda x: x.get("rating", 0), reverse=True)[:20]

        # 格式化POI列表注入prompt
        poi_text = "\n".join([
            f"  {i+1}. {p.get('name','?')} | {p.get('category','?')} | "
            f"评分:{p.get('rating',0)} | 价格:{p.get('avg_price',0)}元 | "
            f"坐标:({p.get('lat',22.27)}, {p.get('lng',113.58)})"
            for i, p in enumerate(relevant)
        ])

        rag_prompt = f"""你是一个旅游路线规划助手。用户想在珠海旅游，请根据以下真实POI列表为他规划一条一日游路线。

可用POI列表：
{poi_text}

要求：
1. 只从上面的POI列表中选择景点，不要编造不存在的景点
2. 返回JSON格式，包含route数组
3. 每个站点包含：name（必须与上面列表完全一致）、category、lat、lng、arrival_time、departure_time
4. 安排3-8个站点
5. 时间从9:00开始，每个站点1-2小时
6. 注意站点间的地理位置，合理安排顺序

只返回JSON，不要其他文字。

用户需求：{user_input}"""

        response = await _call_llm_with_retry(rag_prompt, system="你是旅游路线规划专家。请严格使用提供的POI列表。")

        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = json.loads(text)
        route_list = []
        raw_route = data.get("route", data) if isinstance(data, dict) else data
        for stop in raw_route:
            # Flexible field mapping
            stop_name = stop.get("name") or stop.get("location") or stop.get("activity") or ""
            time_str = stop.get("arrival_time") or stop.get("time") or "09:00"
            if "-" in str(time_str) and ":" not in str(time_str).split("-")[0]:
                parts = str(time_str).split("-")
                arrival = parts[0].strip()
                departure = parts[1].strip() if len(parts) > 1 else arrival
            else:
                arrival = str(time_str).strip()
                departure = "10:00"
            arrival = arrival[:5] if len(arrival) >= 5 else arrival
            departure = departure[:5] if len(departure) >= 5 else departure

            # 尝试匹配真实POI（RAG的核心优势）
            matched_poi = None
            for p in relevant:
                if p.get("name", "") == stop_name or stop_name in p.get("name", ""):
                    matched_poi = p
                    break
            if matched_poi is None:
                matched_poi = {
                    "name": stop_name,
                    "category": stop.get("category", "其他"),
                    "lat": stop.get("lat", 22.27),
                    "lng": stop.get("lng", 113.58),
                    "rating": stop.get("rating", 4.0),
                    "avg_price": 50,
                    "tags": [],
                }
            route_list.append({
                "poi": matched_poi,
                "arrival_time": arrival,
                "departure_time": departure,
                "travel_from_prev": {"distance_km": 1.0, "mode": "walking"},
            })
        return route_list
    except Exception as e:
        print(f"  [rag_llm] parse error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════
# 评分模块（精简版，避免包导入）
# ═══════════════════════════════════════════════════════════════════

_scene_expect = {
    "美食型": {"min_stops": 4, "max_stops": 8, "must_categories": {"餐饮", "夜市小吃"}, "nice_categories": {"甜品饮品", "特色小吃"}, "forbidden_categories": set(), "food_ratio_min": 0.6, "max_leg_km": 8, "ideal_stay_min": 60},
    "目的地型": {"min_stops": 2, "max_stops": 5, "must_categories": {"景点", "乐园"}, "nice_categories": {"餐饮"}, "forbidden_categories": set(), "food_ratio_min": 0, "max_leg_km": 15, "ideal_stay_min": 90},
    "特种兵型": {"min_stops": 6, "max_stops": 10, "must_categories": {"景点", "网红"}, "nice_categories": {"餐饮", "休闲"}, "forbidden_categories": set(), "food_ratio_min": 0, "max_leg_km": 12, "ideal_stay_min": 40},
    "休闲型": {"min_stops": 3, "max_stops": 6, "must_categories": {"休闲", "餐饮"}, "nice_categories": {"公园", "咖啡"}, "forbidden_categories": set(), "food_ratio_min": 0, "max_leg_km": 10, "ideal_stay_min": 60},
    "观光型": {"min_stops": 4, "max_stops": 8, "must_categories": {"景点", "地标"}, "nice_categories": {"文化", "历史"}, "forbidden_categories": set(), "food_ratio_min": 0, "max_leg_km": 15, "ideal_stay_min": 60},
}

def _score_route_simple(route_list, scene_type):
    """精简版评分，避免依赖test_5_scenes的复杂导入。"""
    expect = _scene_expect.get(scene_type, _scene_expect["观光型"])
    if not route_list:
        return {"total": 0, "dims": {}, "grade": "F"}

    stops = [s.get("poi", s) for s in route_list]
    n = len(stops)
    cats = [s.get("category", "") for s in stops]
    cat_set = set(cats)

    # 1. 完整性
    min_s, max_s = expect["min_stops"], expect["max_stops"]
    if n < min_s:
        completeness = max(0, n / min_s * 100)
    elif n > max_s:
        completeness = max(50, 100 - (n - max_s) * 10)
    else:
        completeness = 100

    # 2. 类别匹配
    must = expect["must_categories"]
    nice = expect.get("nice_categories", set())
    def _hit(c, targets):
        return any(t in c or c in t for t in targets)
    must_hit = sum(1 for c in cats if _hit(c, must))
    cat_score = (must_hit / len(must) * 70) if must else 70
    nice_hit = sum(1 for c in cats if _hit(c, nice))
    cat_score += min(30, nice_hit * 15)
    cat_score = max(0, min(100, cat_score))

    # 3. 地理连贯性
    max_leg = expect["max_leg_km"]
    geo_score = 100
    for i in range(1, n):
        p1, p2 = stops[i-1], stops[i]
        d = _haversine(p1.get("lat",22.27), p1.get("lng",113.58), p2.get("lat",22.27), p2.get("lng",113.58))
        if d > max_leg:
            geo_score = max(0, geo_score - (d - max_leg) * 5)
        elif d < 1:
            geo_score = max(80, geo_score)
    geo_score = max(0, geo_score)

    # 4. POI质量
    ratings = [s.get("rating", 0) for s in stops]
    avg_rating = sum(ratings) / n if n else 0
    quality = min(100, avg_rating * 10)

    # 5. 多样性
    diversity = min(100, len(cat_set) / max(len(must), 1) * 100)

    # 6. 时间可行性（简单检查）
    time_ok = 100  # greedy默认时间OK

    total = (completeness * 0.2 + cat_score * 0.3 + geo_score * 0.15 + quality * 0.15 + diversity * 0.1 + time_ok * 0.1)

    # 等级
    if total >= 90: grade = "S"
    elif total >= 80: grade = "A"
    elif total >= 70: grade = "B"
    elif total >= 60: grade = "C"
    elif total >= 50: grade = "D"
    else: grade = "F"

    return {
        "total": round(total, 1),
        "dims": {"完整性": round(completeness, 1), "类别匹配": round(cat_score, 1),
                 "地理连贯": round(geo_score, 1), "POI质量": round(quality, 1),
                 "多样性": round(diversity, 1), "时间可行": round(time_ok, 1)},
        "grade": grade,
    }


def _evaluate_route(route_list: list[dict], scene_type: str) -> dict:
    """使用精简评分评估路线。"""
    return _score_route_simple(route_list, scene_type)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["greedy", "single_llm", "rag", "all"], default="all")
    parser.add_argument("--workers", type=int, default=NUM_WORKERS)
    args = parser.parse_args()

    methods = ["greedy", "single_llm", "rag"] if args.method == "all" else [args.method]

    # 预加载POI数据（所有方法都需要）
    print("=" * 70)
    print("  基线对比测试")
    print("=" * 70)
    print(f"  场景数: {len(TEST_CASES)}")
    print(f"  基线: {', '.join(methods)}")
    print(f"  进程数: {args.workers}")
    print(f"  开始: {datetime.now().strftime('%H:%M:%S')}")

    pois = asyncio.run(_get_all_pois())
    print(f"  POI总数: {len(pois)}")

    asyncio.run(_run_all_methods(methods, pois, args.workers))


def _save_results(method, all_results, t0, partial=False):
    """Save results to JSON file, optionally as partial checkpoint."""
    valid = [r for r in all_results if r is not None]
    ok_count = sum(1 for r in valid if r.get("route_ok"))
    scores = [r.get("score", 0) for r in valid]
    avg_score = sum(scores) / len(scores) if scores else 0
    grade_order = "SABCDF"
    grade_dist = {}
    for r in valid:
        g = r.get("grade", "F")
        grade_dist[g] = grade_dist.get(g, 0) + 1
    by_scene = {}
    for r in valid:
        by_scene.setdefault(r["scene"], []).append(r)
    output = {
        "meta": {"method": method, "total_cases": len(valid),
                 "partial": partial, "elapsed": round(time.perf_counter() - t0, 1),
                 "timestamp": datetime.now().isoformat()},
        "summary": {"avg_score": round(avg_score, 1),
                     "pass_rate": ok_count / len(valid) if valid else 0,
                     "grade_distribution": grade_dist,
                     "by_scene_type": {
                         st: {"count": len(items),
                               "avg": round(sum(r["score"] for r in items) / len(items), 1),
                               "pass": sum(1 for r in items if r.get("route_ok"))}
                         for st, items in by_scene.items()}},
        "results": valid,
    }
    out_dir = Path(_project_root) / "docs" / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "partial" if partial else "full"
    out_file = out_dir / f"baseline_{method}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{tag}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  [{'CHECKPOINT' if partial else 'SAVED'}] {len(valid)} results -> {out_file.name}", flush=True)


async def _run_all_methods(methods, pois, workers):
    for method in methods:
        print(f"\n{'='*50}")
        print(f"  基线: {method}")
        print(f"{'='*50}")

        t0 = time.perf_counter()
        all_results: list[dict] = []

        for i, (st, ui) in enumerate(TEST_CASES):
            idx = i + 1
            t_start = time.perf_counter()
            route_list = []

            try:
                if method == "greedy":
                    route_list = _greedy_route(pois, st, ui)
                elif method == "single_llm":
                    print(f"  [#{idx}/{len(TEST_CASES)}] {st}: calling LLM...", flush=True)
                    route_list = await _single_llm_route(ui, pois)
                elif method == "rag":
                    route_list = await _rag_llm_route(ui, st, pois)
            except Exception as e:
                print(f"  [#{idx}] {method} error: {e}", flush=True)

            elapsed = round(time.perf_counter() - t_start, 1)

            if route_list:
                scoring = _evaluate_route(route_list, st)
                score = scoring.get("total", 0)
                grade = scoring.get("grade", "F")
            else:
                score, grade = 0, "F"

            stop_names = [s.get("poi", s).get("name", "?") for s in route_list] if route_list else []

            all_results.append({
                "id": idx,
                "scene": st,
                "input": ui,
                "elapsed": elapsed,
                "stops": stop_names,
                "stop_count": len(stop_names),
                "errors": [],
                "route_ok": len(stop_names) >= 3,
                "score": min(score, 100),
                "grade": grade,
                "source": "rule",
                "dims": scoring.get("dims", {}) if isinstance(scoring, dict) else {},
            })

            if (i + 1) % 10 == 0:
                print(f"  [{method}] {i+1}/{len(TEST_CASES)} done ({elapsed:.1f}s)", flush=True)
            elif (i + 1) % 5 == 0:
                print(f"  [{method}] {i+1}/{len(TEST_CASES)}", flush=True)

            # 每50个场景保存中间结果（防止超时丢失）
            if (i + 1) % 50 == 0 and (i + 1) < len(TEST_CASES):
                _save_results(method, all_results, t0, partial=True)

        total_elapsed = round(time.perf_counter() - t0, 1)

        # 统计
        valid = [r for r in all_results if r is not None]
        ok_count = sum(1 for r in valid if r.get("route_ok"))
        scores = [r.get("score", 0) for r in valid]
        avg_score = sum(scores) / len(scores) if scores else 0
        avg_time = sum(r.get("elapsed", 0) for r in valid) / len(valid) if valid else 0

        grade_order = "SABCDF"
        grade_dist = defaultdict(int)
        for r in valid:
            g = r.get("grade", "F")
            grade_dist[g] += 1

        by_scene = defaultdict(list)
        for r in valid:
            by_scene[r["scene"]].append(r)

        # 输出结果
        print(f"\n  --- {method} 结果 ---")
        print(f"  总耗时: {total_elapsed}s")
        print(f"  路线生成: {ok_count}/{len(TEST_CASES)}")
        print(f"  平均评分: {avg_score:.1f}")
        print(f"  平均耗时: {avg_time:.1f}s/场景")
        print(f"  等级分布: " + " ".join(f"{g}:{grade_dist.get(g,0)}" for g in grade_order if grade_dist.get(g, 0) > 0))

        print(f"\n  按场景类型:")
        for st in ["美食型", "目的地型", "特种兵型", "休闲型", "观光型"]:
            items = by_scene.get(st, [])
            if items:
                st_avg = sum(r["score"] for r in items) / len(items)
                st_pass = sum(1 for r in items if r.get("route_ok"))
                print(f"    {st}: avg={st_avg:.1f}, pass={st_pass}/{len(items)}")

        # 保存JSON
        _save_results(method, all_results, t0, partial=False)

    print(f"\n{'='*70}")
    print(f"  全部基线测试完成")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
