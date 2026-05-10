"""POI 场景标签生成 — 调用 LLM 批量打标签。

用法: python scripts/enrich_poi_scenes.py

使用 longcat API (Anthropic 格式) 为所有 POI 生成场景标签。
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
API_URL = "https://api.longcat.chat/anthropic/v1/messages"
MODEL = "LongCat-Flash-Lite"

# 场景标签体系
SCENE_CATEGORIES = [
    "海滨", "山景", "公园", "市区", "夜景",
    "亲子", "情侣", "朋友聚会", "独处",
    "文化历史", "自然风光", "美食", "购物",
    "运动健身", "休闲放松", "拍照出片", "打卡热点",
    "经济实惠", "品质体验",
]


async def call_llm(batch: list[dict]) -> list[dict]:
    """调用 longcat API 为一批 POI 打标签。"""
    import httpx

    poi_list = "\n".join(
        f'{p["id"]}: name="{p["name"]}" category="{p["category"]}" tags={p.get("tags",[])}'
        for p in batch
    )

    categories_str = ', '.join(SCENE_CATEGORIES)
    prompt = f"""你是一个POI数据标注专家。请为以下每个POI添加场景标签。

可选标签: {categories_str}

对每个POI，从可选标签中选择 2-4 个最合适的标签。
同时为每个POI添加 suitability 字段：{{"情侣友好": true/false, "亲子友好": true/false, "独自友好": true/false, "朋友友好": true/false}}

只输出 JSON 数组，格式：
[
  {{"id": "poi_00001", "scene_tags": ["海滨", "拍照出片"], "suitability": {{"情侣友好": true, "亲子友好": false, "独自友好": true, "朋友友好": false}}}},
  ...
]

POI列表:
{poi_list}
"""

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
        )
        if resp.status_code != 200:
            print(f"  API 错误: {resp.status_code} {resp.text[:200]}")
            return []

        data = resp.json()
        content = data.get("content", [{}])[0].get("text", "")

        # 提取 JSON
        import re
        json_match = re.search(r"\[[\s\S]*\]", content)
        if json_match:
            return json.loads(json_match.group())
        print(f"  无法解析返回: {content[:200]}")
        return []


async def main():
    print("🌿 加载 POI 数据...")
    data_path = Path(__file__).parent.parent / "backend" / "data" / "city_poi_db.json"
    pois = json.loads(data_path.read_text(encoding="utf-8"))
    print(f"  共 {len(pois)} 个 POI")

    # 强制覆盖：清除旧标签，全部重新生成（LLM比规则更准）
    for p in pois:
        p.pop("_scene_tags", None)
        p.pop("_suitability", None)
    to_process = pois
    print(f"  待处理(全部): {len(to_process)} 个")

    if not to_process:
        print("  全部已标注，跳过")
        return

    # 分批处理（每批 30 个）
    BATCH_SIZE = 30
    total = len(to_process)
    updated = 0

    for i in range(0, total, BATCH_SIZE):
        batch = to_process[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n📦 批次 {batch_num}/{total_batches} ({len(batch)}个)")

        result = await call_llm(batch)
        if not result:
            print(f"  ⚠ 批次失败，跳过")
            continue

        # 回写标签
        tag_map = {r["id"]: r for r in result}
        for poi in batch:
            enriched = tag_map.get(poi["id"])
            if enriched:
                poi["_scene_tags"] = enriched.get("scene_tags", [])
                poi["_suitability"] = enriched.get("suitability", {})
                updated += 1

        print(f"  ✅ {updated}/{total}")

        # 每批保存一次
        data_path.write_text(
            json.dumps(pois, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"\n{'='*40}")
    print(f"完成！共标注 {updated} 个 POI")


if __name__ == "__main__":
    asyncio.run(main())
