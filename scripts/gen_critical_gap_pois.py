"""生成关键缺口类别的POI — 书店/咖啡馆/娱乐/夜市/密室逃脱/剧本杀

这些类别的POI数量严重不足，导致多个场景（文艺独处、朋友轰趴、深夜觅食等）
无法选出足够候选。本脚本针对珠海和广州两个城市批量生成。

用法:
    python scripts/gen_critical_gap_pois.py
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
DATA_PATH = Path("backend/data/city_poi_db.json")

# 每个批次定义：(类别名, 目标城市, 生成数量, prompt模板)
BATCHES = [
    # ── 珠海 ──
    {
        "label": "珠海书店",
        "city": "珠海",
        "category": "书店",
        "count": 20,
        "prompt": """你是珠海本地生活专家。生成20个珠海真实存在的书店/独立书店/书吧。
包括：独立书店、连锁书店（西西弗、言几又、方所）、旧书店、二手书吧、绘本馆、书咖复合空间。
坐标范围: lat=22.0-22.5, lng=113.0-113.8

要求：
- 名称真实可信（可用虚构但合理的店名）
- avg_price 0-80元（大部分免费进店，消费饮品20-50）
- avg_stay_min 60-120
- emotion_tags: tranquility 0.7+, culture_depth 0.7+, excitement 0.2-0.4, sociability 0.2-0.4
- tags含"书店""阅读""文艺""安静"等
- business_hours "10:00-22:00"
- constraints.is_indoor=true

输出: {"pois": [{"name":"...","category":"书店","rating":4.3,"avg_price":30,"lat":22.27,"lng":113.57,"business_hours":"10:00-22:00","tags":["书店","阅读","文艺"],"avg_stay_min":90,"emotion_tags":{"excitement":0.2,"tranquility":0.8,"sociability":0.3,"culture_depth":0.8,"surprise":0.3,"physical_demand":0.1},"constraints":{"is_indoor":true,"pet_friendly":false},"_suitability":{"独自友好":true,"情侣友好":true}}]}""",
    },
    {
        "label": "珠海咖啡馆",
        "city": "珠海",
        "category": "咖啡馆",
        "count": 20,
        "prompt": """你是珠海本地生活专家。生成20个珠海真实存在的独立咖啡馆/精品咖啡店。
包括：精品咖啡、手冲咖啡、网红咖啡、社区咖啡、文艺咖啡、猫咖、花咖。
坐标范围: lat=22.0-22.5, lng=113.0-113.8
排除：星巴克、瑞幸等连锁（已有黑名单过滤）

要求：
- avg_price 25-80元
- avg_stay_min 60-120
- emotion_tags: tranquility 0.6+, sociability 0.4-0.7, excitement 0.2-0.5
- tags含"咖啡""下午茶""文艺""安静"等
- constraints.is_indoor=true
- 部分允许宠物（猫咖/宠物咖啡）

输出: {"pois": [{"name":"...","category":"咖啡馆","rating":4.5,"avg_price":45,"lat":22.27,"lng":113.57,"business_hours":"09:00-22:00","tags":["咖啡","精品","文艺"],"avg_stay_min":90,"emotion_tags":{"excitement":0.3,"tranquility":0.7,"sociability":0.5,"culture_depth":0.3,"surprise":0.4,"physical_demand":0.1},"constraints":{"is_indoor":true,"pet_friendly":false},"_suitability":{"独自友好":true,"情侣友好":true}}]}""",
    },
    {
        "label": "珠海娱乐场所",
        "city": "珠海",
        "category": "娱乐",
        "count": 30,
        "prompt": """你是珠海本地生活专家。生成30个珠海真实存在的娱乐场所。
包括：KTV、酒吧、LiveHouse、桌游吧、保龄球馆、射箭馆、VR体验馆、蹦床公园、卡丁车、电玩城、密室逃脱、剧本杀场馆、真人CS、鬼屋、鬼屋探险。
坐标范围: lat=22.0-22.5, lng=113.0-113.8

要求：
- avg_price 30-200元
- avg_stay_min 60-180
- emotion_tags: excitement 0.6+, sociability 0.6+
- tags含"娱乐""聚会""朋友""好玩"等
- constraints.is_indoor=true
- _suitability含"朋友友好":true

输出: {"pois": [{"name":"...","category":"娱乐","rating":4.3,"avg_price":80,"lat":22.27,"lng":113.57,"business_hours":"10:00-23:00","tags":["娱乐","室内","聚会"],"avg_stay_min":120,"emotion_tags":{"excitement":0.8,"tranquility":0.1,"sociability":0.8,"culture_depth":0.2,"surprise":0.6,"physical_demand":0.4},"constraints":{"is_indoor":true},"_suitability":{"朋友友好":true}}]}""",
    },
    {
        "label": "珠海夜市",
        "city": "珠海",
        "category": "夜市",
        "count": 15,
        "prompt": """你是珠海本地生活专家。生成15个珠海真实存在的夜市/夜市小吃街/深夜美食聚集地。
包括：夜市、小吃街、美食广场、大排档聚集区、深夜食堂区域、宵夜一条街。
坐标范围: lat=22.0-22.5, lng=113.0-113.8

要求：
- avg_price 20-60元
- avg_stay_min 60-120
- emotion_tags: excitement 0.5+, sociability 0.7+, surprise 0.5+
- tags含"夜市""小吃""宵夜""深夜"等
- business_hours到凌晨（如"17:00-02:00"或"18:00-01:00"）
- constraints.is_indoor=false

输出: {"pois": [{"name":"...","category":"夜市","rating":4.3,"avg_price":40,"lat":22.27,"lng":113.57,"business_hours":"17:00-02:00","tags":["夜市","小吃","宵夜","便宜"],"avg_stay_min":90,"emotion_tags":{"excitement":0.6,"tranquility":0.1,"sociability":0.8,"culture_depth":0.3,"surprise":0.6,"physical_demand":0.2},"constraints":{"is_indoor":false}}]}""",
    },
    {
        "label": "珠海密室逃脱",
        "city": "珠海",
        "category": "密室逃脱",
        "count": 15,
        "prompt": """你是珠海本地生活专家。生成15个珠海真实存在的密室逃脱场馆。
包括：恐怖密室、推理密室、机关密室、沉浸式密室、机械密室、剧情密室。
坐标范围: lat=22.0-22.5, lng=113.0-113.8

要求：
- avg_price 80-200元
- avg_stay_min 60-120
- emotion_tags: excitement 0.8+, surprise 0.7+, sociability 0.6+
- tags含"密室""逃脱""恐怖""推理"等
- constraints.is_indoor=true

输出: {"pois": [{"name":"...","category":"密室逃脱","rating":4.5,"avg_price":120,"lat":22.27,"lng":113.57,"business_hours":"10:00-22:00","tags":["密室","逃脱","恐怖","推理"],"avg_stay_min":90,"emotion_tags":{"excitement":0.9,"tranquility":0.1,"sociability":0.7,"culture_depth":0.2,"surprise":0.8,"physical_demand":0.3},"constraints":{"is_indoor":true},"_suitability":{"朋友友好":true}}]}""",
    },
    {
        "label": "珠海剧本杀",
        "city": "珠海",
        "category": "剧本杀",
        "count": 15,
        "prompt": """你是珠海本地生活专家。生成15个珠海真实存在的剧本杀场馆。
包括：情感本、硬核推理、欢乐本、恐怖本、阵营本、沉浸式剧场。
坐标范围: lat=22.0-22.5, lng=113.0-113.8

要求：
- avg_price 80-200元
- avg_stay_min 120-240
- emotion_tags: excitement 0.7+, surprise 0.7+, sociability 0.8+, culture_depth 0.4+
- tags含"剧本杀""推理""沉浸""社交"等
- constraints.is_indoor=true

输出: {"pois": [{"name":"...","category":"剧本杀","rating":4.4,"avg_price":128,"lat":22.27,"lng":113.57,"business_hours":"13:00-23:00","tags":["剧本杀","推理","沉浸","社交"],"avg_stay_min":180,"emotion_tags":{"excitement":0.8,"tranquility":0.1,"sociability":0.9,"culture_depth":0.5,"surprise":0.8,"physical_demand":0.2},"constraints":{"is_indoor":true},"_suitability":{"朋友友好":true}}]}""",
    },
    # ── 广州 ──
    {
        "label": "广州书店",
        "city": "广州",
        "category": "书店",
        "count": 20,
        "prompt": """你是广州本地生活专家。生成20个广州真实存在的书店/独立书店/书吧。
包括：独立书店（方所、1200bookshop）、连锁书店、旧书店、二手书吧、书咖复合空间。
坐标范围: lat=23.0-23.3, lng=113.1-113.5

要求同珠海书店，emotion_tags: tranquility 0.7+, culture_depth 0.7+

输出: {"pois": [{"name":"...","category":"书店","rating":4.3,"avg_price":30,"lat":23.12,"lng":113.26,"business_hours":"10:00-22:00","tags":["书店","阅读","文艺"],"avg_stay_min":90,"emotion_tags":{"excitement":0.2,"tranquility":0.8,"sociability":0.3,"culture_depth":0.8,"surprise":0.3,"physical_demand":0.1},"constraints":{"is_indoor":true},"_suitability":{"独自友好":true}}]}""",
    },
    {
        "label": "广州咖啡馆",
        "city": "广州",
        "category": "咖啡馆",
        "count": 20,
        "prompt": """你是广州本地生活专家。生成20个广州真实存在的独立咖啡馆/精品咖啡店。
包括：精品咖啡、手冲咖啡、网红咖啡、社区咖啡、文艺咖啡、猫咖。
坐标范围: lat=23.0-23.3, lng=113.1-113.5
排除：星巴克、瑞幸等连锁

要求同珠海咖啡馆。

输出: {"pois": [{"name":"...","category":"咖啡馆","rating":4.5,"avg_price":45,"lat":23.12,"lng":113.26,"business_hours":"09:00-22:00","tags":["咖啡","精品","文艺"],"avg_stay_min":90,"emotion_tags":{"excitement":0.3,"tranquility":0.7,"sociability":0.5,"culture_depth":0.3,"surprise":0.4,"physical_demand":0.1},"constraints":{"is_indoor":true},"_suitability":{"独自友好":true,"情侣友好":true}}]}""",
    },
    {
        "label": "广州娱乐场所",
        "city": "广州",
        "category": "娱乐",
        "count": 30,
        "prompt": """你是广州本地生活专家。生成30个广州真实存在的娱乐场所。
包括：KTV、酒吧、LiveHouse、桌游吧、保龄球馆、射箭馆、VR体验馆、蹦床公园、卡丁车、电玩城、密室逃脱、剧本杀、真人CS。
坐标范围: lat=23.0-23.3, lng=113.1-113.5

要求同珠海娱乐场所。

输出: {"pois": [{"name":"...","category":"娱乐","rating":4.3,"avg_price":80,"lat":23.12,"lng":113.26,"business_hours":"10:00-23:00","tags":["娱乐","室内","聚会"],"avg_stay_min":120,"emotion_tags":{"excitement":0.8,"tranquility":0.1,"sociability":0.8,"culture_depth":0.2,"surprise":0.6,"physical_demand":0.4},"constraints":{"is_indoor":true},"_suitability":{"朋友友好":true}}]}""",
    },
    {
        "label": "广州夜市",
        "city": "广州",
        "category": "夜市",
        "count": 15,
        "prompt": """你是广州本地生活专家。生成15个广州真实存在的夜市/夜市小吃街/深夜美食聚集地。
包括：北京路夜市、上下九步行街美食、体育西横街、龙洞步行街、车陂夜市等。
坐标范围: lat=23.0-23.3, lng=113.1-113.5

要求同珠海夜市。

输出: {"pois": [{"name":"...","category":"夜市","rating":4.3,"avg_price":40,"lat":23.12,"lng":113.26,"business_hours":"17:00-02:00","tags":["夜市","小吃","宵夜"],"avg_stay_min":90,"emotion_tags":{"excitement":0.6,"tranquility":0.1,"sociability":0.8,"culture_depth":0.3,"surprise":0.6,"physical_demand":0.2},"constraints":{"is_indoor":false}}]}""",
    },
    {
        "label": "广州密室逃脱",
        "city": "广州",
        "category": "密室逃脱",
        "count": 15,
        "prompt": """你是广州本地生活专家。生成15个广州真实存在的密室逃脱场馆。
包括：恐怖密室、推理密室、机关密室、沉浸式密室、机械密室。
坐标范围: lat=23.0-23.3, lng=113.1-113.5

要求同珠海密室逃脱。

输出: {"pois": [{"name":"...","category":"密室逃脱","rating":4.5,"avg_price":120,"lat":23.12,"lng":113.26,"business_hours":"10:00-22:00","tags":["密室","逃脱","恐怖","推理"],"avg_stay_min":90,"emotion_tags":{"excitement":0.9,"tranquility":0.1,"sociability":0.7,"culture_depth":0.2,"surprise":0.8,"physical_demand":0.3},"constraints":{"is_indoor":true},"_suitability":{"朋友友好":true}}]}""",
    },
    {
        "label": "广州剧本杀",
        "city": "广州",
        "category": "剧本杀",
        "count": 15,
        "prompt": """你是广州本地生活专家。生成15个广州真实存在的剧本杀场馆。
包括：情感本、硬核推理、欢乐本、恐怖本、沉浸式剧场。
坐标范围: lat=23.0-23.3, lng=113.1-113.5

要求同珠海剧本杀。

输出: {"pois": [{"name":"...","category":"剧本杀","rating":4.4,"avg_price":128,"lat":23.12,"lng":113.26,"business_hours":"13:00-23:00","tags":["剧本杀","推理","沉浸","社交"],"avg_stay_min":180,"emotion_tags":{"excitement":0.8,"tranquility":0.1,"sociability":0.9,"culture_depth":0.5,"surprise":0.8,"physical_demand":0.2},"constraints":{"is_indoor":true},"_suitability":{"朋友友好":true}}]}""",
    },
]


async def llm_json(prompt: str, max_tokens: int = 10000) -> dict | None:
    """调用龙猫API生成JSON"""
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(
            "https://api.longcat.chat/anthropic/v1/messages",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "LongCat-Flash-Lite",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
        )
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
        except json.JSONDecodeError:
            print(f"  JSON parse error: {text[:200]}")
            return None


def merge_poi(raw: dict, city: str, category: str, next_id: int, existing: set[str]) -> dict | None:
    """将LLM输出转为标准POI格式，去重"""
    name = raw.get("name", "").strip()
    if not name or name in existing:
        return None

    default_emotion = {
        "excitement": 0.5,
        "tranquility": 0.5,
        "sociability": 0.5,
        "culture_depth": 0.5,
        "surprise": 0.5,
        "physical_demand": 0.3,
    }

    biz_hours = raw.get("business_hours", "10:00-22:00")
    constraints = raw.get("constraints", {})
    if "opening_hours" not in constraints:
        constraints["opening_hours"] = biz_hours

    return {
        "id": f"poi_{next_id:05d}",
        "name": name,
        "city": city,
        "category": raw.get("category", category),
        "rating": min(5.0, max(3.0, raw.get("rating", 4.3))),
        "avg_price": max(0, raw.get("avg_price", 0)),
        "lat": raw.get("lat", 22.27),
        "lng": raw.get("lng", 113.57),
        "business_hours": biz_hours,
        "tags": raw.get("tags", []),
        "queue_prone": False,
        "avg_stay_min": max(15, raw.get("avg_stay_min", 60)),
        "ugc_comments": [],
        "emotion_tags": {**default_emotion, **raw.get("emotion_tags", {})},
        "constraints": {
            "accessible": True,
            "pet_friendly": constraints.get("pet_friendly", False),
            "queue_time_min": 5,
            **constraints,
        },
        "_scene_tags": raw.get("tags", []),
        "_suitability": raw.get("_suitability", {}),
    }


async def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    existing = {p["name"].strip() for p in data}
    max_id = max(
        int(p["id"].split("_")[1]) for p in data if p["id"].startswith("poi_")
    )

    total_added = 0
    stats: dict[str, int] = {}

    for batch in BATCHES:
        label = batch["label"]
        print(f"\n{'='*50}")
        print(f"  生成 {label} (目标 {batch['count']} 个)")
        print(f"{'='*50}")

        result = await llm_json(batch["prompt"])
        if not result or "pois" not in result:
            print("  首次失败，重试...")
            await asyncio.sleep(2)
            result = await llm_json(batch["prompt"])
            if not result or "pois" not in result:
                print("  二次失败，跳过")
                stats[label] = 0
                continue

        added = 0
        for raw_poi in result["pois"]:
            max_id += 1
            poi = merge_poi(
                raw_poi, batch["city"], batch["category"], max_id, existing
            )
            if poi:
                data.append(poi)
                existing.add(poi["name"])
                added += 1

        stats[label] = added
        total_added += added
        print(f"  新增 {added} 个")

        # 每批写入一次，防止中途失败丢数据
        DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        await asyncio.sleep(1)

    # 打印统计
    print(f"\n{'='*60}")
    print(f"  生成完成!")
    print(f"{'='*60}")
    for label, count in stats.items():
        print(f"  {label}: +{count}")
    print(f"\n  总新增: {total_added}")
    print(f"  总POI: {len(data)}")

    # 按类别统计
    cat_counts: dict[str, int] = {}
    for p in data:
        cat = p.get("category", "未知")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    print("\n  当前各类别数量:")
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {cnt}")


if __name__ == "__main__":
    asyncio.run(main())
