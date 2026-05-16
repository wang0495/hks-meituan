"""生成小众珠海POI — 用LongCat JSON模式批量生成。
用法: python scripts/gen_niche_pois.py [数量]
"""
import asyncio, json, re, sys, httpx
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_KEY = "os.getenv("AMAP_API_KEY", "")"
DATA_PATH = Path("backend/data/city_poi_db.json")

async def llm_json(prompt: str, max_tokens=4000) -> dict | list | None:
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post("https://api.longcat.chat/anthropic/v1/messages",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": "LongCat-Flash-Lite", "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1, "response_format": {"type": "json_object"}})
        if r.status_code != 200:
            print(f"  API Error: {r.status_code}")
            return None
        text = r.json().get("content", [{}])[0].get("text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"  JSON Parse Error: {text[:200]}")
            return None

POI_TEMPLATE = """
类别可选: 文化, 运动, 餐饮, 购物, 景点, 其他
场景标签可选: 海滨, 山景, 公园, 夜景, 文化历史, 自然风光, 拍照出片, 打卡热点, 品质体验, 运动健身, 休闲放松, 亲子, 情侣, 美食, 购物
坐标范围: lat=22.0-22.5, lng=113.0-113.8

输出JSON格式:
{
  "pois": [
    {
      "name": "景点名",
      "category": "类别",
      "rating": 4.5,
      "avg_price": 0,
      "lat": 22.27,
      "lng": 113.57,
      "business_hours": "09:00-18:00",
      "tags": ["标签1","标签2","标签3"],
      "avg_stay_min": 90,
      "emotion_tags": {"excitement":0.5,"tranquility":0.5,"sociability":0.5,"culture_depth":0.5,"surprise":0.5,"physical_demand":0.3},
      "_scene_tags": ["场景1","场景2"],
      "_suitability": {"情侣友好":true,"亲子友好":true,"独自友好":true,"朋友友好":true}
    }
  ]
}"""

async def generate_batch(count: int, batch_num: int, existing_names: set) -> list[dict]:
    """生成一批小众POI。"""
    prompt = f"""你是珠海本地旅游专家。生成{count}个珠海小众但值得去的POI（非大众景点）。

要求：
- 必须是珠海真实存在的（不是澳门）
- 覆盖运动场地、隐藏景点、本地人推荐、文艺小店、特色公园、观景台等
- 不要重复已有景点: {', '.join(list(existing_names)[:10])}

{POI_TEMPLATE}

只输出JSON，不要其他文字。"""

    result = await llm_json(prompt, max_tokens=8000)
    if isinstance(result, dict) and "pois" in result:
        pois = result["pois"]
        print(f"  生成 {len(pois)} 个")
        return pois
    print(f"  解析失败")
    return []

async def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    batch_size = 20

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    existing_names = {p["name"].strip() for p in data}
    max_id = max(int(p["id"].split("_")[1]) for p in data if p["id"].startswith("poi_"))
    before = len(data)

    print(f"🌿 生成 {count} 个珠海小众POI (当前共 {before} POI)")
    total_added = 0
    batch_num = 1

    while total_added < count:
        batch_count = min(batch_size, count - total_added)
        print(f"\n📦 批次 {batch_num} (生成{batch_count}个)...")

        pois = await generate_batch(batch_count, batch_num, existing_names)
        if not pois:
            print("  重试...")
            await asyncio.sleep(2)
            continue

        added = 0
        for p in pois:
            name = p.get("name", "").strip()
            if not name or name in existing_names:
                continue
            max_id += 1
            poi = {
                "id": f"poi_{max_id:05d}",
                "name": name,
                "city": "珠海",
                "category": p.get("category", "景点"),
                "rating": min(5.0, max(3.0, p.get("rating", 4.0))),
                "avg_price": max(0, p.get("avg_price", 0)),
                "lat": p.get("lat", 22.27),
                "lng": p.get("lng", 113.57),
                "business_hours": p.get("business_hours", "09:00-18:00"),
                "tags": p.get("tags", []),
                "queue_prone": False,
                "avg_stay_min": max(15, p.get("avg_stay_min", 60)),
                "ugc_comments": [],
                "emotion_tags": p.get("emotion_tags", {"excitement":0.5,"tranquility":0.5,"sociability":0.5,"culture_depth":0.5,"surprise":0.5,"physical_demand":0.3}),
                "constraints": {"accessible":True,"pet_friendly":False,"queue_time_min":5,"opening_hours":p.get("business_hours", "09:00-18:00")},
                "_scene_tags": p.get("_scene_tags", []),
                "_suitability": p.get("_suitability", {}),
            }
            data.append(poi)
            existing_names.add(name)
            added += 1

        total_added += added
        print(f"  新增 {added}/{batch_count} 个 (去重后)")
        DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  已保存 (共 {len(data)} POI)")
        batch_num += 1
        if added == 0:
            print("  无法新增，可能已全部去重")
            break

    print(f"\n✅ 完成: 新增 {total_added} 个，总POI: {len(data)}")
    print(f"珠海: {sum(1 for p in data if p.get('city')=='珠海')}")

if __name__ == "__main__":
    asyncio.run(main())
