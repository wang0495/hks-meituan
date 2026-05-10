"""生成定向缺失POI类型 — 密室逃脱/温泉/冲浪/攀岩/沙滩排球等"""
import asyncio, json, httpx
from pathlib import Path

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
DATA_PATH = Path("backend/data/city_poi_db.json")

MISSING_CATEGORIES = """
1. 密室逃脱/剧本杀场馆 (室内娱乐, avg_price=80-150, stay_min=90)
2. 真人CS/射击场馆 (运动射击, avg_price=100-200)
3. 温泉/汤泉 (休闲放松, avg_price=80-200, 情侣/退休友好)
4. 沙滩排球场/飞盘场地 (户外运动, avg_price=0-50)
5. 冲浪/桨板体验点 (水上运动, avg_price=100-300)
6. 攀岩馆/抱石馆 (运动健身, avg_price=50-150)
7. 海景咖啡馆 (餐饮+海滨, avg_price=30-80)
8. 艺术展览/画廊 (文化, avg_price=0-50)
9. 骑行/徒步俱乐部 (运动, avg_price=0)
10. 珠海本地小吃街/夜市 (美食, avg_price=20-80)
"""

async def llm_json(prompt, max_tokens=4000):
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post("https://api.longcat.chat/anthropic/v1/messages",
            headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"},
            json={"model":"LongCat-Flash-Lite","max_tokens":max_tokens,
                  "messages":[{"role":"user","content":prompt}],
                  "temperature":0.1,"response_format":{"type":"json_object"}})
        if r.status_code != 200: return None
        try: return json.loads(r.json().get("content",[{}])[0].get("text",""))
        except: return None

async def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    existing = {p["name"].strip() for p in data}
    max_id = max(int(p["id"].split("_")[1]) for p in data if p["id"].startswith("poi_"))

    for cat_name in ["密室剧本杀", "温泉SPA", "水上运动", "攀岩", "海景咖啡馆", "夜市小吃"]:
        print(f"\n📦 生成 {cat_name}...")
        prompt = f"""你是珠海本地生活专家。生成20个珠海真实存在的{cat_name}场所的JSON数据。

要求：名称真实、坐标准确(lat=22.0-22.5, lng=113.0-113.8)、价格合理。
不要重复已有: {', '.join(list(existing)[-5:])}

输出 {{"pois": [{{"name":"...","category":"...","rating":4.5,"avg_price":50,"lat":22.27,"lng":113.57,"business_hours":"10:00-22:00","tags":[],"avg_stay_min":90,"_scene_tags":[],"_suitability":{{"情侣友好":true,"亲子友好":false,"独自友好":true,"朋友友好":true}}}}]}}"""

        result = await llm_json(prompt, 8000)
        if not isinstance(result, dict) or "pois" not in result:
            print("  failed")
            continue

        added = 0
        for p in result["pois"]:
            name = p.get("name","").strip()
            if not name or name in existing: continue
            max_id += 1
            data.append({
                "id": f"poi_{max_id:05d}", "name": name, "city": "珠海",
                "category": p.get("category","景点"), "rating": min(5.0,max(3.0,p.get("rating",4.0))),
                "avg_price": max(0,p.get("avg_price",0)), "lat": p.get("lat",22.27), "lng": p.get("lng",113.57),
                "business_hours": "09:00-22:00", "tags": p.get("tags",[]),
                "queue_prone": False, "avg_stay_min": max(30,p.get("avg_stay_min",60)),
                "ugc_comments": [],
                "emotion_tags": {"excitement":0.6,"tranquility":0.3,"sociability":0.7,"culture_depth":0.3,"surprise":0.5,"physical_demand":0.3},
                "constraints": {"accessible":True,"pet_friendly":False,"queue_time_min":5,"opening_hours":"09:00-22:00"},
                "_scene_tags": p.get("_scene_tags",[]),
                "_suitability": p.get("_suitability",{}),
            })
            existing.add(name)
            added += 1

        print(f"  新增 {added} 个")
        DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    zhuhai = sum(1 for p in data if p.get('city')=='珠海')
    print(f"\n✅ 完成! 总POI: {len(data)}, 珠海: {zhuhai}")

asyncio.run(main())
