"""批量生成缺失场景POI — 覆盖评分中发现的场景缺口。

场景类别：
1. 深夜餐饮（24h便利店、深夜食堂、凌晨茶餐厅）
2. 亲子游乐（儿童乐园、海洋馆、动物园）
3. 文化休闲（茶馆、书法馆、曲艺场所）
4. 夜生活（酒吧、LiveHouse、夜店）
5. 室内娱乐（保龄球、射箭、VR、桌游吧）
6. 特色小吃（街边小店、本地小吃、夜市）
"""
import asyncio, json, httpx
from pathlib import Path

API_KEY = "os.getenv("AMAP_API_KEY", "")"
DATA_PATH = Path("backend/data/city_poi_db.json")

BATCHES = [
    {
        "name": "深夜餐饮（24h/凌晨营业）",
        "count": 25,
        "prompt": """生成25个珠海真实存在的深夜/凌晨餐饮场所。
包括：24h便利店（7-Eleven、全家、美宜佳）、深夜茶餐厅、凌晨粉面店、通宵糖水铺、深夜大排档。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：
- business_hours必须是深夜/凌晨营业（如"00:00-23:59"或"21:00-06:00"或"18:00-03:00"）
- avg_price 10-50元（便宜实惠）
- tags含"深夜""24小时""宵夜""便宜"等
- is_indoor=true

输出: {"pois": [{"name":"...","category":"餐饮","rating":4.0,"avg_price":20,"lat":22.27,"lng":113.57,"business_hours":"00:00-23:59","tags":["24小时","深夜","便宜"],"avg_stay_min":30,"is_indoor":true}]}"""
    },
    {
        "name": "亲子游乐场所",
        "count": 25,
        "prompt": """生成25个珠海真实存在的亲子游乐场所。
包括：儿童乐园、室内游乐场、海洋馆、水族馆、儿童科技馆、亲子农场、儿童拓展、水上乐园、动物园。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：
- _suitability含"亲子友好":true
- tags含"亲子""儿童""游乐"等
- avg_price 0-200元
- 部分室内(is_indoor=true)，部分室外

输出: {"pois": [{"name":"...","category":"景点","rating":4.5,"avg_price":100,"lat":22.27,"lng":113.57,"business_hours":"09:00-18:00","tags":["亲子","游乐","室内"],"avg_stay_min":120,"is_indoor":true,"_suitability":{"亲子友好":true}}]}"""
    },
    {
        "name": "文化休闲（茶馆/书法/曲艺）",
        "count": 20,
        "prompt": """生成20个珠海真实存在的文化休闲场所。
包括：茶馆、茶室、书法体验馆、国画工坊、传统文化馆、粤曲茶座、文玩市场、古玩店。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：
- tags含"茶馆""传统文化""书法""曲艺"等
- avg_price 20-100元
- is_indoor=true
- emotion_tags.tranquility较高(0.7+)
- emotion_tags.culture_depth较高(0.7+)

输出: {"pois": [{"name":"...","category":"文化","rating":4.3,"avg_price":50,"lat":22.27,"lng":113.57,"business_hours":"10:00-22:00","tags":["茶馆","传统文化","安静"],"avg_stay_min":90,"is_indoor":true,"emotion_tags":{"excitement":0.2,"tranquility":0.8,"sociability":0.3,"culture_depth":0.8,"surprise":0.3,"physical_demand":0.1}}]}"""
    },
    {
        "name": "夜生活场所",
        "count": 20,
        "prompt": """生成20个珠海真实存在的夜生活场所。
包括：酒吧、清吧、LiveHouse、夜店、音乐现场、精酿啤酒馆、鸡尾酒吧、夜市小吃街。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：
- business_hours在晚上营业（如"18:00-02:00"或"20:00-04:00"）
- tags含"酒吧""夜生活""音乐""蹦迪"等
- avg_price 30-200元
- emotion_tags.excitement较高(0.7+)
- emotion_tags.sociability较高(0.7+)

输出: {"pois": [{"name":"...","category":"餐饮","rating":4.2,"avg_price":80,"lat":22.27,"lng":113.57,"business_hours":"20:00-02:00","tags":["酒吧","夜生活","音乐"],"avg_stay_min":120,"is_indoor":true,"emotion_tags":{"excitement":0.8,"tranquility":0.1,"sociability":0.9,"culture_depth":0.2,"surprise":0.5,"physical_demand":0.2}}]}"""
    },
    {
        "name": "室内娱乐",
        "count": 20,
        "prompt": """生成20个珠海真实存在的室内娱乐场所。
包括：保龄球馆、射箭馆、VR体验馆、桌游吧、密室逃脱、剧本杀、电竞馆、卡丁车馆、蹦床公园。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：
- is_indoor=true
- tags含"室内""娱乐""互动"等
- avg_price 50-200元
- 适合雨天/高温天

输出: {"pois": [{"name":"...","category":"运动","rating":4.4,"avg_price":80,"lat":22.27,"lng":113.57,"business_hours":"10:00-22:00","tags":["室内","娱乐","互动"],"avg_stay_min":90,"is_indoor":true}]}"""
    },
    {
        "name": "特色小吃街/夜市",
        "count": 15,
        "prompt": """生成15个珠海真实存在的特色小吃街/夜市/本地美食聚集地。
包括：夜市、小吃街、美食广场、大排档聚集区、本地人推荐的美食街。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
要求：
- tags含"夜市""小吃街""本地美食""便宜"等
- avg_price 20-60元
- business_hours到晚上较晚（如"17:00-01:00"）
- 适合"街边小吃""本地人推荐"场景

输出: {"pois": [{"name":"...","category":"餐饮","rating":4.3,"avg_price":40,"lat":22.27,"lng":113.57,"business_hours":"17:00-01:00","tags":["夜市","小吃街","本地美食","便宜"],"avg_stay_min":60,"is_indoor":false}]}"""
    },
]

async def llm_json(prompt, max_tokens=10000):
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

async def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    existing = {p["name"].strip() for p in data}
    max_id = max(int(p["id"].split("_")[1]) for p in data if p["id"].startswith("poi_"))
    total_added = 0

    for batch in BATCHES:
        print(f"\n📦 生成 {batch['name']}...")
        result = await llm_json(batch["prompt"])
        if not result or "pois" not in result:
            print("  失败，重试...")
            result = await llm_json(batch["prompt"])
            if not result or "pois" not in result:
                print("  二次失败，跳过")
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

    # 统计
    zhuhai = sum(1 for p in data if p.get('city') == '珠海')
    indoor = sum(1 for p in data if p.get("constraints", {}).get("is_indoor"))
    pet = sum(1 for p in data if p.get("constraints", {}).get("pet_friendly"))
    h24 = sum(1 for p in data if "00:00" in p.get("business_hours", ""))
    print(f"\n✅ 总新增: {total_added}")
    print(f"总POI: {len(data)}, 珠海: {zhuhai}")
    print(f"室内: {indoor}, 宠物友好: {pet}, 24h: {h24}")

if __name__ == "__main__":
    asyncio.run(main())
