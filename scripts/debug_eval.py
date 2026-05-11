"""Debug LLM scoring response."""
import asyncio, httpx, json, re

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"

async def test():
    route_str = "  1. 淇沙湾 [文化] ¥29 标签:['海滨','文化','经济']"
    prompt = f"""你是一个旅游路线质量评审专家。评估以下路线是否符合用户需求。

用户需求: 我一个人来珠海玩，想找一些安静的地方放松一下，预算大概200元以内
用户画像: 独处游客，偏好安静和休闲放松，预算有限
期望场景标签: ['海滨', '公园', '休闲放松']

路线:
{route_str}

从以下维度评分(0-10): intent_match, poi_quality, geo_continuity, budget_fit, scene_diversity, overall。
输出JSON:
{{"scores":{{"intent_match":0,"poi_quality":0,"geo_continuity":0,"budget_fit":0,"scene_diversity":0,"overall":0}}}}"""

    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.post("https://api.longcat.chat/anthropic/v1/messages",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": "LongCat-Flash-Lite", "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1})
        text = r.json().get("content", [{}])[0].get("text", "")
        print(f"RAW: [{text}]")
        print(f"LEN: {len(text)}")

        text2 = re.sub(r"```json\s*|\s*```|```", "", text)
        text2 = text2.replace("'", '"')
        m = re.search(r"\{[\s\S]*\}", text2)
        if m:
            try:
                data = json.loads(m.group())
                print(f"OK: {json.dumps(data, ensure_ascii=False)[:200]}")
            except json.JSONDecodeError as e:
                print(f"PARSE ERROR: {e}")
                print(f"CLEANED: [{text2[:300]}]")
        else:
            print("NO JSON FOUND")

asyncio.run(test())
