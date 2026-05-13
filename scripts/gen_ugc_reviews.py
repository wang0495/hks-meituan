"""批量生成POI的UGC评价 — 用龙猫LongCat生成真实感用户评论。

用法: python scripts/gen_ugc_reviews.py
"""

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

API_KEY = "sk-1aad8fc6f2bb4614be106bcdb747478f"
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
DATA_PATH = Path(__file__).parent.parent / "backend" / "data" / "city_poi_db.json"

# 每批处理的POI数量
BATCH_SIZE = 10
# 并发请求数
CONCURRENCY = 3
# 信号量
_sem = asyncio.Semaphore(CONCURRENCY)


async def call_llm(prompt: str, max_tokens: int = 6000) -> str | None:
    """调用 DeepSeek OpenAI接口 + JSON模式。"""
    import httpx
    async with _sem:
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    resp = await client.post(
                        API_URL,
                        headers={
                            "Authorization": f"Bearer {API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": MODEL,
                            "max_tokens": max_tokens,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    if resp.status_code != 200:
                        print(f"  API错误 {resp.status_code}: {resp.text[:100]}")
                        if attempt < 2:
                            await asyncio.sleep(1)
                            continue
                        return None
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"  请求异常: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
                else:
                    return None
        return None


def extract_json(text: str):
    """从LLM响应中提取JSON。JSON模式直接解析。"""
    try:
        data = json.loads(text)
        # 处理 {"data": [...]} 包装
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data
    except json.JSONDecodeError:
        pass
    # 降级：尝试提取
    text = text.replace("'", '"')
    text = re.sub(r",\s*([}\]])", r"\1", text)
    json_match = re.search(r"\[[\s\S]*\]", text) or re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data
        except json.JSONDecodeError:
            pass
    return None


def build_batch_prompt(pois: list[dict]) -> str:
    """构建批次UGC生成prompt。"""
    poi_lines = []
    for i, p in enumerate(pois):
        poi_lines.append(
            f'{i+1}. {p["name"]} (类别:{p.get("category","")} 评分:{p.get("rating",0)} '
            f'价格:{p.get("avg_price",0)}元 标签:{",".join(p.get("tags",[])[:3])})'
        )

    return f"""你是真实用户评价生成器。为以下{len(pois)}个珠海商户/景点生成2-3条逼真的UGC用户评价。

要求：
- 每条评价要有具体细节（提到菜品/景色/体验），不能泛泛而谈
- 评价内容要匹配POI的类别和标签（景点写景色体验，餐厅写菜品口味）
- 评分应与POI整体评分接近（高分POI的评价偏向正面）
- 允许有1条中肯的建议（如"人多要排队""停车不方便"），增加真实感
- 每条评价30-80字，用户名用2-3字中文名
- 每个POI生成2-3条评价

POI列表:
{chr(10).join(poi_lines)}

输出JSON对象，格式: {{"data":[{{"name":"POI名称","reviews":[{{"user":"用户名","rating":4,"content":"评价内容"}}]}}]}}
只输出JSON对象。"""


async def process_batch(pois: list[dict], batch_idx: int) -> list[dict]:
    """处理一个批次的POI，返回生成的评价。"""
    prompt = build_batch_prompt(pois)
    text = await call_llm(prompt, max_tokens=4000)
    if not text:
        return []

    result = extract_json(text)
    if not isinstance(result, list):
        print(f"  批次{batch_idx}: JSON解析失败")
        return []

    return result


async def main():
    print("=" * 60)
    print("📝 UGC评价批量生成（LongCat）")
    print("=" * 60)

    pois = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    print(f"\n总POI: {len(pois)}")

    # 只处理珠海 + 有ugc_comments但content为空的
    zhuhai = [p for p in pois if p.get("city") == "珠海"]
    need_ugc = []
    for p in zhuhai:
        comments = p.get("ugc_comments", [])
        # 没有实质内容的需要生成
        has_content = any(c.get("content", "").strip() for c in comments)
        if not has_content:
            need_ugc.append(p)

    print(f"珠海POI: {len(zhuhai)}")
    print(f"需要生成UGC: {len(need_ugc)}")

    if not need_ugc:
        print("所有POI已有UGC评价，无需生成。")
        return

    # 分批处理
    batches = [need_ugc[i : i + BATCH_SIZE] for i in range(0, len(need_ugc), BATCH_SIZE)]
    print(f"分{len(batches)}批处理，并发{CONCURRENCY}")

    # 并发处理多个批次
    total_generated = 0
    total_reviews = 0

    for round_start in range(0, len(batches), CONCURRENCY):
        round_batches = batches[round_start : round_start + CONCURRENCY]
        tasks = []
        for j, batch in enumerate(round_batches):
            tasks.append(process_batch(batch, round_start + j))

        results = await asyncio.gather(*tasks)

        # 将结果写入POI数据
        name_map = {p["name"]: p for p in pois}
        for result in results:
            if not result:
                continue
            for item in result:
                name = item.get("name", "")
                poi = name_map.get(name)
                if not poi:
                    # 模糊匹配
                    for p in pois:
                        if name in p["name"] or p["name"] in name:
                            poi = p
                            break
                if poi and item.get("reviews"):
                    new_reviews = item["reviews"]
                    # 保留原有的rating字段结构，补上content
                    if "ugc_comments" not in poi:
                        poi["ugc_comments"] = []
                    # 替换为新生成的评价
                    poi["ugc_comments"] = new_reviews
                    total_generated += 1
                    total_reviews += len(new_reviews)

        # 每轮保存
        DATA_PATH.write_text(
            json.dumps(pois, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        done = min(round_start + CONCURRENCY, len(batches))
        print(f"  进度: {done}/{len(batches)}批 | 已生成{total_generated}个POI的{total_reviews}条评价")

    print(f"\n{'='*60}")
    print(f"完成! 共为{total_generated}个POI生成{total_reviews}条UGC评价")

    # 验证
    has_content = sum(
        1 for p in pois
        if any(c.get("content", "").strip() for c in p.get("ugc_comments", []))
    )
    print(f"有实质评价内容的POI: {has_content}/{len(pois)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
