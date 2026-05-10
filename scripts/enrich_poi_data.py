"""CityFlow POI 数据增强 — 用龙猫生成真实景点 + 清洗数据。

用法: python scripts/enrich_poi_data.py
"""

import asyncio
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
MODEL = "LongCat-Flash-Lite"
DATA_PATH = Path(__file__).parent.parent / "backend" / "data" / "city_poi_db.json"


async def call_llm(prompt: str, max_tokens: int = 4000) -> str | None:
    """调用 LongCat API。"""
    import httpx
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
        )
        if resp.status_code != 200:
            print(f"  API 错误: {resp.status_code}")
            return None
        data = resp.json()
        return data.get("content", [{}])[0].get("text", "")


def extract_json(text: str) -> list | dict | None:
    """从 LLM 响应中提取 JSON。"""
    text = text.replace("'", '"')
    text = re.sub(r",\s*([}\]])", r"\1", text)
    json_match = re.search(r"\[[\s\S]*\]", text) or re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None


# ═══════════════════════════════════════════════════════════════
# Phase 1: 生成缺失的珠海真实景点
# ═══════════════════════════════════════════════════════════════

GENERATE_PROMPT = """你是一个珠海旅游专家。生成 40 个珠海真实存在的著名旅游景点/场所的JSON数据。

要求：
1. 必须真实存在于珠海（不是澳门）
2. 覆盖：自然景点、文化场馆、主题公园、美食街区、购物中心、网红打卡点
3. 包括所有知名地标：长隆海洋王国、情侣路、日月贝、圆明新园、横琴湿地、野狸岛、珠海渔女（已有）、海滨泳场、爱情邮局、外伶仃岛、东澳岛、庙湾岛、金台寺、唐家湾古镇、梅溪牌坊、农科奇观、石景山公园、板樟山、横琴长隆剧院、富华里商圈、玖洲道、华发商都、夏湾夜市、港珠澳大桥口岸等
4. 不重复已有的常见POI
5. 优先缺失的知名景点

每个POI格式：
{{
  "name": "景点名称",
  "city": "珠海",
  "category": "文化/运动/购物/餐饮/景点/其他",
  "rating": 4.x (3.5-5.0),
  "avg_price": 价格数字,
  "lat": 纬度 (22.0-22.5),
  "lng": 经度 (113.0-113.8),
  "business_hours": "09:00-18:00",
  "tags": ["标签1", "标签2", "标签3"],
  "queue_prone": true/false,
  "avg_stay_min": 建议游玩分钟,
  "emotion_tags": {{
    "excitement": 0.0-1.0,
    "tranquility": 0.0-1.0,
    "sociability": 0.0-1.0,
    "culture_depth": 0.0-1.0,
    "surprise": 0.0-1.0,
    "physical_demand": 0.0-1.0
  }},
  "constraints": {{
    "accessible": true/false,
    "pet_friendly": true/false,
    "queue_time_min": 排队分钟,
    "opening_hours": "09:00-18:00"
  }},
  "_scene_tags": ["场景标签1", "场景标签2"],
  "_suitability": {{
    "情侣友好": true/false,
    "亲子友好": true/false,
    "独自友好": true/false,
    "朋友友好": true/false
  }}
}}

场景标签可选：海滨, 山景, 公园, 夜景, 文化历史, 自然风光, 拍照出片, 打卡热点, 品质体验, 运动健身, 休闲放松, 亲子, 情侣, 美食, 购物

只输出 JSON 数组。"""


async def generate_missing_pois() -> list[dict]:
    """生成缺失的珠海景点。"""
    print("\n📦 [Phase 1] 生成缺失的珠海真实景点...")
    text = await call_llm(GENERATE_PROMPT, max_tokens=8000)
    if not text:
        print("  ❌ 生成失败")
        return []

    data = extract_json(text)
    if isinstance(data, list):
        print(f"  ✅ 生成了 {len(data)} 个景点")
        return data
    print(f"  ⚠ 解析失败: {text[:200]}")
    return []


# ═══════════════════════════════════════════════════════════════
# Phase 2: 批量评估 POI 质量
# ═══════════════════════════════════════════════════════════════

QUALITY_PROMPT = """你是一个POI质量评审专家。评估以下POI是否适合作为旅游规划的目的地。

对每个POI，输出：
1. "id": POI编号
2. "is_tourist": true/false（是否是真正的旅游目的地）
3. "quality_score": 1-10（作为旅游景点的质量）
4. "issues": ["问题1", "问题2"]（如果有问题）
5. "better_city": 如果坐标在澳门而非珠海，填"澳门"

POI列表：
{poi_list}

只输出 JSON 数组，格式：
[{{"id": "poi_00001", "is_tourist": true, "quality_score": 8, "issues": [], "better_city": ""}}, ...]
"""


async def evaluate_poi_quality(pois: list[dict]) -> list[dict]:
    """批量评估 POI 质量。"""
    poi_lines = "\n".join(
        f'{p["id"]}: name="{p.get("name","")}" city={p.get("city","")} cat={p.get("category","")} lat={p.get("lat",0)} lng={p.get("lng",0)} tags={p.get("tags",[])}'
        for p in pois
    )
    prompt = QUALITY_PROMPT.format(poi_list=poi_lines)
    text = await call_llm(prompt, max_tokens=4000)
    if not text:
        return []
    data = extract_json(text)
    if isinstance(data, list):
        return data
    return []


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("🌿 CityFlow POI 数据增强")
    print("=" * 60)

    # 加载当前数据
    pois = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    existing_names = {p["name"].strip() for p in pois}
    print(f"\n当前 POI 数: {len(pois)}")
    print(f"珠海 POI: {sum(1 for p in pois if p.get('city')=='珠海')}")

    # Phase 1: 生成缺失景点
    new_pois = await generate_missing_pois()
    if new_pois:
        added = 0
        for np in new_pois:
            name = np.get("name", "").strip()
            if not name or name in existing_names:
                continue
            # 生成唯一 ID
            max_id = max(int(p["id"].split("_")[1]) for p in pois if p["id"].startswith("poi_"))
            np["id"] = f"poi_{max_id + added + 1:05d}"
            # 确保必要字段
            np.setdefault("city", "珠海")
            np.setdefault("_scene_tags", [])
            np.setdefault("_suitability", {})
            pois.append(np)
            existing_names.add(name)
            added += 1
        print(f"  ✅ 新增 {added} 个景点到数据库")

        # 立即保存
        DATA_PATH.write_text(json.dumps(pois, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  💾 已保存 ({len(pois)} POI)")

    # Phase 2: 批量清洗 POI 质量（分批处理）
    print("\n📦 [Phase 2] 批量清洗 POI 质量...")
    # 只处理珠海 POI + 非酒店
    zhuhai_pois = [p for p in pois if p.get("city") == "珠海" and p.get("category") != "酒店"]
    print(f"  待清洗: {len(zhuhai_pois)} 个珠海 POI")

    BATCH_SIZE = 30
    cleaned_count = 0
    removed_count = 0
    macau_count = 0

    for i in range(0, len(zhuhai_pois), BATCH_SIZE):
        batch = zhuhai_pois[i : i + BATCH_SIZE]
        results = await evaluate_poi_quality(batch)
        if not results:
            continue

        quality_map = {r["id"]: r for r in results}
        for poi in batch:
            q = quality_map.get(poi["id"])
            if q is None:
                continue
            poi["_llm_quality"] = {
                "is_tourist": q.get("is_tourist", True),
                "score": q.get("quality_score", 5),
                "issues": q.get("issues", []),
            }
            # 澳门坐标修正
            better_city = q.get("better_city", "")
            if better_city:
                poi["_llm_city_fix"] = better_city

        cleaned_count += len(batch)
        # 每批保存
        DATA_PATH.write_text(json.dumps(pois, ensure_ascii=False, indent=2), encoding="utf-8")

        # 进度
        total = len(zhuhai_pois)
        pct = min(100, (i + BATCH_SIZE) / total * 100)
        print(f"  📊 {min(i+BATCH_SIZE, total)}/{total} ({pct:.0f}%)")

    # 统计
    all_quality = [p.get("_llm_quality", {}) for p in pois if "_llm_quality" in p]
    tourist_count = sum(1 for q in all_quality if q.get("is_tourist"))
    not_tourist = [p for p in pois if p.get("_llm_quality", {}).get("is_tourist") is False]

    print(f"\n  ✅ 清洗完成:")
    print(f"     旅游POI: {tourist_count}/{len(all_quality)}")
    print(f"     非旅游POI: {len(not_tourist)}")
    print(f"     需要移除的非旅游POI示例:")
    for p in not_tourist[:10]:
        print(f"       - {p.get('name')} ({p.get('category')}) issues={p.get('_llm_quality',{}).get('issues',[])}")

    # 澳门POI修复
    macau_fixes = [p for p in pois if p.get("_llm_city_fix")]
    print(f"\n     需修正城市的POI(澳门): {len(macau_fixes)}")
    for p in macau_fixes:
        print(f"       - {p.get('name')} (原城市={p.get('city')})")

    # 最终统计
    print(f"\n{'='*60}")
    print(f"📊 最终统计")
    print(f"  POI 总数: {len(pois)}")
    print(f"  珠海: {sum(1 for p in pois if p.get('city')=='珠海')}")
    print(f"  广州: {sum(1 for p in pois if p.get('city')=='广州')}")
    print(f"  湛江: {sum(1 for p in pois if p.get('city')=='湛江')}")
    print(f"  澳门(待修正): {len(macau_fixes)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
