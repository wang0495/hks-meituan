"""生成缺失的珠海知名景点 — 两步法：先生成名录，再逐个展开。"""
import asyncio, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"

async def llm(prompt: str) -> str | None:
    import httpx
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(API_URL, headers={"Content-Type":"application/json","Authorization":f"Bearer {API_KEY}"},
            json={"model":"LongCat-Flash-Lite","max_tokens":4000,"messages":[{"role":"user","content":prompt}],"temperature":0.1})
        return r.json().get("content",[{}])[0].get("text","") if r.status_code==200 else None

def extract(text: str):
    text = text.replace("'",'"')
    text = re.sub(r',\s*([}\]])', r'\1', text)
    m = re.search(r'\[[\s\S]*?\]', text)
    if m:
        try: return json.loads(m.group())
        except: pass
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try: return json.loads(m.group())
        except: pass
    return None

async def main():
    path = Path("backend/data/city_poi_db.json")
    pois = json.loads(path.read_text(encoding="utf-8"))
    existing = {p["name"].strip() for p in pois}
    max_id = max(int(p["id"].split("_")[1]) for p in pois if p["id"].startswith("poi_"))

    print("Step 1: 生成缺失景点名录...")
    text = await llm("""列出15个珠海真实存在的著名旅游景点，这些景点在city_poi_db.json中很可能缺失。
要求：必须是珠海本地的、非澳门的、真正值得去的景点。
包括：长隆海洋王国、情侣路、野狸岛、圆明新园、日月贝、珠海横琴湿地公园、石景山公园、海滨泳场、爱情邮局、景山道、唐家湾古镇、金台寺、梅溪牌坊、农科奇观、板樟山森林公园。
输出JSON数组：["景点名1","景点名2",...]
只输出JSON。""")
    names = extract(text)
    if not isinstance(names, list):
        print(f"解析失败: {text[:200]}")
        return
    print(f"  得到 {len(names)} 个景点: {names}")

    # 过滤已存在的
    names = [n for n in names if n not in existing]
    print(f"  新增 {len(names)} 个")

    for name in names:
        print(f"\n生成: {name}")
        text = await llm(f"""为珠海景点"{name}"生成完整POI JSON数据。

已知同城POI数据样本：
{{
  "id": "poi_XXXXX",
  "name": "景点名",
  "city": "珠海",
  "category": "景点",
  "rating": 4.5,
  "avg_price": 0,
  "lat": 22.25,
  "lng": 113.55,
  "business_hours": "09:00-18:00",
  "tags": ["标签1","标签2"],
  "queue_prone": false,
  "avg_stay_min": 90,
  "emotion_tags": {{"excitement":0.5,"tranquility":0.5,"sociability":0.5,"culture_depth":0.5,"surprise":0.5,"physical_demand":0.3}},
  "constraints": {{"accessible":true,"pet_friendly":false,"queue_time_min":10,"opening_hours":"09:00-18:00"}},
  "_scene_tags": ["自然风光","拍照出片"],
  "_suitability": {{"情侣友好":true,"亲子友好":true,"独自友好":true,"朋友友好":true}}
}}

请为"{name}"生成类似JSON。只需输出JSON对象，不要其他文字。
场景标签从以下选2-4个：海滨,山景,公园,夜景,文化历史,自然风光,拍照出片,打卡热点,品质体验,运动健身,休闲放松,亲子,情侣,美食,购物
坐标参考珠海范围：lat=22.0-22.5, lng=113.0-113.8
价格是每人参考价格。""")
        poi = extract(text)
        if isinstance(poi, dict) and "name" in poi:
            poi["id"] = f"poi_{max_id+1:05d}"
            poi.setdefault("city", "珠海")
            max_id += 1
            pois.append(poi)
            existing.add(name)
            path.write_text(json.dumps(pois, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ✅ 已添加")
        else:
            print(f"  ❌ 解析失败: {text[:150]}")

    print(f"\n✅ 完成! 总POI: {len(pois)}")

if __name__ == "__main__":
    asyncio.run(main())
