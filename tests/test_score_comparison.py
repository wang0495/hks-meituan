"""对比 DeepSeek vs LongCat 评分客观性。

用同一批路线数据，分别用两个模型评分，对比：
1. 评分分布（是否过于集中或分散）
2. 通过率差异
3. 评分理由质量
"""
import asyncio, json, httpx, os, sys
from pathlib import Path

# DeepSeek配置
DEEPSEEK_KEY = os.getenv("LLM_API_KEY", "")
DEEPSEEK_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
if not DEEPSEEK_URL.rstrip("/").endswith("/v1"):
    DEEPSEEK_URL = DEEPSEEK_URL.rstrip("/") + "/v1"

# LongCat配置
LONGCAT_KEY = "os.getenv("AMAP_API_KEY", "")"
LONGCAT_URL = "https://api.longcat.chat/anthropic/v1/messages"

# 加载.env
env_path = Path('.env')
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())
    DEEPSEEK_KEY = os.getenv("LLM_API_KEY", DEEPSEEK_KEY)

PASS_THRESHOLD = 6.5

# 评分prompt（两个模型共用）
SCORING_PROMPT = """你是旅游路线质量评审。请客观公正地评估以下路线。

用户需求: {user_input}

路线:
{route_text}

评分标准(每项0-10分):

**intent_match** (意图匹配):
- 9-10: 完美匹配用户核心需求
- 7-8: 大部分匹配，有小偏差
- 5-6: 部分匹配，遗漏了重要需求
- 3-4: 匹配度低，但有相关性
- 0-2: 完全不相关

**poi_quality** (POI质量):
- 9-10: 所有POI都是值得专程去的优质景点
- 7-8: 大部分POI质量不错
- 5-6: POI质量一般，有些不太值得去
- 3-4: 多数POI质量偏低
- 0-2: POI基本不值得去

**geo_continuity** (地理合理性):
- 9-10: 路线流畅，无回头路
- 7-8: 基本合理，有轻微绕行
- 5-6: 有一定绕路但可接受
- 3-4: 明显不合理
- 0-2: 完全混乱

**scene_diversity** (场景多样性):
- 9-10: 类型丰富，体验多样
- 7-8: 有不错的多样性
- 5-6: 多样性一般
- 3-4: 较为单调
- 0-2: 完全单一

**overall** (总体): 综合以上维度，给出你的真实满意度评分。

重要规则:
1. 如果用户需求本身不可能实现（如50元住五星酒店），只要路线提供了合理的替代方案，intent_match给5-6分，overall给5-6分
2. 如果路线有3个以上POI且时间安排合理，geo_continuity至少给5分
3. 不要因为小问题给0分，0分只用于完全无意义的路线
4. 列出2-3个优点(good_points)和2-3个改进建议(bad_points)
5. 对于"不可能需求"场景，如果路线能正确识别需求不合理并提供替代方案，应给予肯定

输出JSON: {{"scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"overall":N}},"good_points":["优点1","优点2"],"bad_points":["建议1","建议2"]}}"""

# 测试路线数据（从历史测试中提取的典型场景）
TEST_ROUTES = [
    {
        "name": "穷游情侣(好路线)",
        "input": "零预算带女朋友浪漫一天，要拍照好看那种，别花一分钱",
        "route": "1. 情侣路 [运动] ¥0\n2. 凤凰山半山观景台 [景点] ¥0\n3. 吉大免税商场后巷咖啡屋 [餐饮] ¥45\n4. 珠海渔女 [文化] ¥0\n5. 海天公园 [景点] ¥0",
    },
    {
        "name": "深夜觅食(差路线)",
        "input": "凌晨2点还在珠海，哪儿还能吃宵夜？便宜点的",
        "route": "1. 珠海儿童公园 [景点] ¥0\n2. 诚品书店 [书店] ¥0",
    },
    {
        "name": "热浪求生(好路线)",
        "input": "40度高温天，带孩子室内玩，别中暑，预算不限但得凉快",
        "route": "1. 乐奇堡室内游乐场 [运动] ¥120\n2. 珠海市美术馆 [文化] ¥0\n3. 香洲区图书馆 [文化] ¥0\n4. 海底捞亲子乐园 [景点] ¥80\n5. 珠海科技馆 [文化] ¥30",
    },
    {
        "name": "矛盾需求(不可能)",
        "input": "预算就50块，但要住五星级海景房，还带早餐",
        "route": "1. 珠海渔女 [文化] ¥0\n2. 情侣路 [运动] ¥0\n3. 海天公园 [景点] ¥0\n4. 吉大免税商场后巷咖啡屋 [餐饮] ¥45",
    },
    {
        "name": "朋友轰趴(中等路线)",
        "input": "5个朋友聚会，要能玩又能吃，预算人均150，下午到晚上",
        "route": "1. 凤凰山半山观景台 [景点] ¥0\n2. 前山旧街市集 [购物] ¥50\n3. 得月舫 [餐饮] ¥80\n4. 吉大免税商场后街 [购物] ¥30",
    },
    {
        "name": "退休夫妇(差路线)",
        "input": "老两口想慢慢逛，找个公园喝茶听曲，预算200以内",
        "route": "1. 凤凰山登山径 [运动] ¥0\n2. 红旗镇湿地公园 [景点] ¥0\n3. 珠海渔女 [文化] ¥0\n4. 梅溪牌坊 [景点] ¥0\n5. 情侣路 [运动] ¥0",
    },
]


async def score_with_deepseek(user_input: str, route_text: str) -> dict | None:
    """用DeepSeek评分。"""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(base_url=DEEPSEEK_URL, api_key=DEEPSEEK_KEY)
        prompt = SCORING_PROMPT.format(user_input=user_input, route_text=route_text)
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content or ""
        result = json.loads(text)
        if "scores" not in result:
            # 平铺格式
            expected = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
            if expected & set(result.keys()):
                result = {"scores": {k: result[k] for k in expected if k in result},
                          "good_points": result.get("good_points", []),
                          "bad_points": result.get("bad_points", [])}
        return result
    except Exception as e:
        print(f"  DeepSeek error: {e}")
        return None


async def score_with_longcat(user_input: str, route_text: str) -> dict | None:
    """用LongCat评分。"""
    try:
        prompt = SCORING_PROMPT.format(user_input=user_input, route_text=route_text)
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(LONGCAT_URL,
                headers={"Authorization": f"Bearer {LONGCAT_KEY}", "Content-Type": "application/json"},
                json={"model": "LongCat-Flash-Lite", "max_tokens": 1000,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.1, "response_format": {"type": "json_object"}})
            if r.status_code != 200:
                return None
            text = r.json().get("content", [{}])[0].get("text", "")
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            result = json.loads(text.strip())
            if "scores" not in result:
                expected = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
                if expected & set(result.keys()):
                    result = {"scores": {k: result[k] for k in expected if k in result},
                              "good_points": result.get("good_points", []),
                              "bad_points": result.get("bad_points", [])}
            return result
    except Exception as e:
        print(f"  LongCat error: {e}")
        return None


async def main():
    print("=" * 70)
    print("评分模型对比: DeepSeek vs LongCat")
    print("=" * 70)

    results = {"deepseek": [], "longcat": []}

    for route in TEST_ROUTES:
        print(f"\n{'─'*50}")
        print(f"场景: {route['name']}")
        print(f"需求: {route['input'][:50]}...")
        print(f"路线: {route['route'][:60]}...")
        print(f"{'─'*50}")

        # 并行评分
        ds_result, lc_result = await asyncio.gather(
            score_with_deepseek(route["input"], route["route"]),
            score_with_longcat(route["input"], route["route"]),
        )

        # DeepSeek结果
        if ds_result and "scores" in ds_result:
            ds_scores = ds_result["scores"]
            ds_overall = ds_scores.get("overall", 0)
            ds_passed = "✅" if ds_overall >= PASS_THRESHOLD else "❌"
            print(f"  DeepSeek: {ds_passed} overall={ds_overall} intent={ds_scores.get('intent_match','?')} quality={ds_scores.get('poi_quality','?')}")
            if ds_result.get("bad_points"):
                print(f"    问题: {ds_result['bad_points'][0][:50]}")
            results["deepseek"].append({"name": route["name"], "scores": ds_scores, "overall": ds_overall})
        else:
            print(f"  DeepSeek: 评分失败")

        # LongCat结果
        if lc_result and "scores" in lc_result:
            lc_scores = lc_result["scores"]
            lc_overall = lc_scores.get("overall", 0)
            lc_passed = "✅" if lc_overall >= PASS_THRESHOLD else "❌"
            print(f"  LongCat:  {lc_passed} overall={lc_overall} intent={lc_scores.get('intent_match','?')} quality={lc_scores.get('poi_quality','?')}")
            if lc_result.get("bad_points"):
                print(f"    问题: {lc_result['bad_points'][0][:50]}")
            results["longcat"].append({"name": route["name"], "scores": lc_scores, "overall": lc_overall})
        else:
            print(f"  LongCat:  评分失败")

    # 汇总对比
    print(f"\n\n{'='*70}")
    print("汇总对比")
    print(f"{'='*70}")

    for model_name, model_results in results.items():
        if not model_results:
            continue
        overalls = [r["overall"] for r in model_results]
        passed = sum(1 for o in overalls if o >= PASS_THRESHOLD)
        avg = sum(overalls) / len(overalls)
        print(f"\n{model_name}:")
        print(f"  通过率: {passed}/{len(overalls)} ({passed/len(overalls)*100:.0f}%)")
        print(f"  平均分: {avg:.1f}")
        print(f"  分数分布: {sorted(overalls)}")

        # 各维度平均
        dims = ["intent_match", "poi_quality", "geo_continuity", "scene_diversity"]
        for dim in dims:
            vals = [r["scores"].get(dim, 0) for r in model_results if dim in r.get("scores", {})]
            if vals:
                print(f"  {dim}: avg={sum(vals)/len(vals):.1f}")

    # 一致性分析
    print(f"\n{'='*70}")
    print("一致性分析")
    print(f"{'='*70}")
    for i, route in enumerate(TEST_ROUTES):
        ds = results["deepseek"][i] if i < len(results["deepseek"]) else None
        lc = results["longcat"][i] if i < len(results["longcat"]) else None
        if ds and lc:
            diff = abs(ds["overall"] - lc["overall"])
            status = "一致" if diff <= 1 else "分歧" if diff <= 2 else "严重分歧"
            print(f"  {route['name']}: DS={ds['overall']} LC={lc['overall']} 差={diff:.0f} [{status}]")


if __name__ == "__main__":
    asyncio.run(main())
