"""生成特殊场景POI：24h营业、室内场馆、宠物友好场所等。"""
import asyncio, json, httpx, re
from pathlib import Path

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
DATA_PATH = Path("backend/data/city_poi_db.json")

async def llm_json(prompt, max_tokens=8000):
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
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return json.loads(text.strip())
        except:
            print(f"  JSON Error: {text[:200]}")
            return None

BATCHES = [
    {
        "name": "室内场馆",
        "prompt": """生成15个珠海真实存在的室内场馆POI。
包括：博物馆、美术馆、科技馆、展览馆、天文馆、图书馆、室内展览中心、文化馆。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：名称真实、坐标准确、标注is_indoor=true

输出: {"pois": [{"name":"...","category":"文化","rating":4.5,"avg_price":0,"lat":22.27,"lng":113.57,"business_hours":"09:00-17:00","tags":["室内","博物馆"],"avg_stay_min":90,"is_indoor":true,"pet_friendly":false}]}"""
    },
    {
        "name": "24h营业/深夜场所",
        "prompt": """生成15个珠海真实存在的24小时营业或深夜营业场所。
包括：24h便利店、深夜食堂、通宵书店、24h咖啡馆、夜市、凌晨营业的茶餐厅、深夜网吧/电竞馆。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：business_hours标注真实营业时间（如"00:00-23:59"或"21:00-06:00"）

输出: {"pois": [{"name":"...","category":"餐饮","rating":4.0,"avg_price":30,"lat":22.27,"lng":113.57,"business_hours":"00:00-23:59","tags":["24小时","深夜"],"avg_stay_min":30,"is_indoor":true}]}"""
    },
    {
        "name": "宠物友好场所",
        "prompt": """生成15个珠海真实存在的宠物友好场所。
包括：宠物友好公园、可带狗的海滩、宠物咖啡馆、宠物友好餐厅、户外草坪、滨江步道。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：pet_friendly=true，标签含"宠物友好"

输出: {"pois": [{"name":"...","category":"景点","rating":4.3,"avg_price":0,"lat":22.27,"lng":113.57,"business_hours":"00:00-23:59","tags":["宠物友好","户外"],"avg_stay_min":60,"pet_friendly":true,"is_indoor":false}]}"""
    },
    {
        "name": "室内娱乐",
        "prompt": """生成15个珠海真实存在的室内娱乐场所。
包括：室内游乐场、蹦床公园、室内攀岩、VR体验馆、桌游吧、室内射箭、保龄球馆、室内卡丁车。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：is_indoor=true，适合雨天/高温天

输出: {"pois": [{"name":"...","category":"运动","rating":4.4,"avg_price":80,"lat":22.27,"lng":113.57,"business_hours":"10:00-22:00","tags":["室内","娱乐"],"avg_stay_min":90,"is_indoor":true}]}"""
    },
    {
        "name": "亲子游乐",
        "prompt": """生成15个珠海真实存在的亲子游乐场所。
包括：儿童乐园、海洋馆、动物园、儿童科技馆、亲子农场、儿童拓展、水上乐园。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：_suitability含"亲子友好":true

输出: {"pois": [{"name":"...","category":"景点","rating":4.6,"avg_price":100,"lat":22.27,"lng":113.57,"business_hours":"09:00-18:00","tags":["亲子","游乐"],"avg_stay_min":120,"is_indoor":false,"_suitability":{"亲子友好":true}}]}"""
    },
]

async def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    existing = {p["name"].strip() for p in data}
    max_id = max(int(p["id"].split("_")[1]) for p in data if p["id"].startswith("poi_"))
    total_added = 0

    for batch in BATCHES:
        print(f"\n📦 生成 {batch['name']}...")
        result = await llm_json(batch["prompt"], 10000)
        if not result or "pois" not in result:
            print("  失败")
            continue

        added = 0
        for p in result["pois"]:
            name = p.get("name", "").strip()
            if not name or name in existing:
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
                "business_hours": p.get("business_hours", "09:00-22:00"),
                "tags": p.get("tags", []),
                "queue_prone": False,
                "avg_stay_min": max(15, p.get("avg_stay_min", 60)),
                "ugc_comments": [],
                "emotion_tags": p.get("emotion_tags", {
                    "excitement": 0.5, "tranquility": 0.5, "sociability": 0.5,
                    "culture_depth": 0.5, "surprise": 0.5, "physical_demand": 0.3
                }),
                "constraints": {
                    "accessible": True,
                    "pet_friendly": p.get("pet_friendly", False),
                    "queue_time_min": 5,
                    "opening_hours": p.get("business_hours", "09:00-22:00"),
                    "is_indoor": p.get("is_indoor", False),
                },
                "_scene_tags": p.get("tags", []),
                "_suitability": p.get("_suitability", {}),
            }
            data.append(poi)
            existing.add(name)
            added += 1

        total_added += added
        print(f"  新增 {added} 个")
        DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ 总新增: {total_added}, 总POI: {len(data)}")

    # 统计
    indoor = sum(1 for p in data if p.get("constraints", {}).get("is_indoor"))
    pet = sum(1 for p in data if p.get("constraints", {}).get("pet_friendly") or p.get("pet_friendly"))
    h24 = sum(1 for p in data if "00:00" in p.get("business_hours", "") or "24" in p.get("business_hours", ""))
    print(f"室内: {indoor}, 宠物友好: {pet}, 24h: {h24}")

if __name__ == "__main__":
    asyncio.run(main())
