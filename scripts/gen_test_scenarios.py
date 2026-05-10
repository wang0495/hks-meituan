"""用龙猫生成复杂/极限测试场景，覆盖各种边界情况。"""
import asyncio, json, httpx
from pathlib import Path

API_KEY = "ak_2C232w6Wj58e9Pw8a86gd2id76U58"
OUT_PATH = Path("eval_data/llm_scenarios.json")

async def llm_json(prompt, max_tokens=8000):
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post("https://api.longcat.chat/anthropic/v1/messages",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": "LongCat-Flash-Lite", "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.7, "response_format": {"type": "json_object"}})
        if r.status_code != 200:
            print(f"API Error: {r.status_code}")
            return None
        text = r.json().get("content", [{}])[0].get("text", "")
        # 清理markdown代码块
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            return json.loads(text)
        except:
            print(f"JSON Error: {text[:300]}")
            return None

async def main():
    prompt = """你是珠海旅游产品经理，需要设计30个极端/复杂的旅行规划测试场景。

覆盖以下维度的组合：
1. 时间约束：极短(1-2h)、短(3-4h)、半天、全天
2. 预算约束：0元、50元、100元、200元、不限
3. 人群类型：独行、情侣、亲子、朋友、退休夫妻
4. 特殊需求：带宠物、摄影出片、夜猫子(只晚上)、早起党
5. 情绪偏好：浪漫、刺激冒险、安静文艺、纯美食
6. 天气/季节：下雨天、大热天
7. 矛盾组合：低预算+高品质、短时间+多地点、带娃+运动
8. 边界情况：完全模糊的需求、emoji输入

每个场景包含：
- name: 简短场景名(10字以内)
- input: 用户自然语言输入(口语化，可有错别字)
- banned_cats: 不应出现的category列表
- max_budget: 预算上限(元)
- difficulty: easy/medium/hard/extreme
- edge_case: 测试的边界点说明

输出JSON: {"scenarios": [...]}
注意：input要像真人说话，有些故意模糊/矛盾"""

    print("生成30个复杂测试场景...")
    result = await llm_json(prompt, max_tokens=15000)
    if not result or "scenarios" not in result:
        print("生成失败")
        return

    scenarios = result["scenarios"]
    print(f"生成 {len(scenarios)} 个场景")

    # 统计
    from collections import Counter
    diff_dist = Counter(s.get("difficulty", "?") for s in scenarios)
    print(f"难度分布: {dict(diff_dist)}")

    # 保存
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(scenarios, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"保存到 {OUT_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
