"""测试Multi-Agent系统效果

对比:
1. Agent架构 vs 原硬编码架构
2. IntentAgent不可能需求检测准确率
3. POIAgent语义匹配准确率
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agents import IntentAgent, POIAgent, get_llm
from backend.services.data_service import get_data


# 测试场景(聚焦失败场景)
TEST_SCENARIOS = [
    # 不可能需求场景
    {"name": "矛盾需求", "input": "预算就50块，但要住五星级海景房，还带早餐"},
    {"name": "预算冲突", "input": "想住情侣酒店，但只给100块预算，怎么办"},
    {"name": "时间压缩", "input": "3小时从拱北到横琴，玩3个景点，可能吗"},

    # 意图匹配失败场景
    {"name": "朋友拼单", "input": "3个人想去长隆，但不想住酒店，有没有一日游路线"},
    {"name": "情绪切换", "input": "上午想安静画画，下午突然想蹦迪，怎么安排"},
    {"name": "雨夜漫步", "input": "下大雨的晚上，和伴侣在珠海散步，要有情调，别淋太多"},

    # 深夜场景(已修复，验证Agent是否更好)
    {"name": "深夜觅食", "input": "凌晨2点还在珠海，哪儿还能吃宵夜？便宜点的"},
    {"name": "深夜独白", "input": "凌晨一个人在珠海街头走走，安全又有点意思的地方"},

    # 正常场景(对照组)
    {"name": "穷游情侣", "input": "零预算带女朋友浪漫一天，要拍照好看那种，别花一分钱"},
    {"name": "宠物同行", "input": "带我家金毛去海边玩，不能进收费区，要能遛狗的地方"},
]


async def test_intent_agent():
    """测试IntentAgent不可能需求检测"""
    print("\n" + "=" * 60)
    print("Agent 1: IntentAgent 不可能需求检测测试")
    print("=" * 60)

    llm = get_llm()
    agent = IntentAgent(llm)

    results = []
    correct = 0

    for sc in TEST_SCENARIOS:
        name = sc["name"]
        input_text = sc["input"]

        print(f"\n[{name}] {input_text[:40]}...")

        try:
            result = await agent.analyze(input_text)

            is_impossible = result.get("is_impossible", False)
            reason = result.get("impossible_reason", "")
            alternative = result.get("alternative_suggestion", "")
            keywords = result.get("scene_keywords", [])
            zones = result.get("preferred_zones", [])

            # 验证判断是否正确
            expected_impossible = name in ["矛盾需求", "预算冲突", "时间压缩"]
            is_correct = is_impossible == expected_impossible

            if is_correct:
                correct += 1
                status = "✓ 正确"
            else:
                status = "✗ 错误"

            print(f"  {status}")
            print(f"  is_impossible: {is_impossible}")
            if is_impossible:
                print(f"  原因: {reason[:60]}...")
                print(f"  替代建议: {alternative[:60]}...")
            else:
                print(f"  关键词: {keywords[:5]}")
                print(f"  推荐区域: {zones[:3]}")

            results.append({
                "name": name,
                "input": input_text,
                "is_impossible": is_impossible,
                "is_correct": is_correct,
                "scene_keywords": keywords,
                "preferred_zones": zones,
                "impossible_reason": reason,
            })

        except Exception as e:
            print(f"  ✗ 异常: {e}")
            results.append({"name": name, "error": str(e)})

    # 统计
    print("\n" + "-" * 40)
    print(f"IntentAgent准确率: {correct}/{len(TEST_SCENARIOS)} = {correct/len(TEST_SCENARIOS)*100:.0f}%")

    return results


async def test_poi_agent(intent_results: list[dict]):
    """测试POIAgent语义匹配"""
    print("\n" + "=" * 60)
    print("Agent 2: POIAgent 语义匹配测试")
    print("=" * 60)

    # 加载POI数据
    pois = get_data("city_poi_db") or []
    if not pois:
        # 如果city_poi_db不存在，尝试合并所有数据集
        pois = get_data()
    print(f"加载POI: {len(pois)}个")

    llm = get_llm()
    agent = POIAgent(llm)

    # 只测试非不可能需求的场景
    test_cases = [r for r in intent_results if not r.get("is_impossible") and not r.get("error")]

    results = []

    for tc in test_cases[:5]:  # 只测试5个避免耗时太长
        name = tc["name"]
        keywords = tc.get("scene_keywords", [])

        print(f"\n[{name}] 关键词: {keywords[:3]}")

        try:
            # 粗筛候选(城市+简单过滤)
            city = "珠海"
            candidates = [p for p in pois if p.get("city") == city][:50]

            start = time.time()
            poi_result = await agent.score_pois(tc, candidates)
            elapsed = time.time() - start

            top_ids = poi_result.get("top_recommendations", [])
            scored = poi_result.get("scored_pois", [])

            # 查找top推荐的POI详情
            top_pois = []
            for p in candidates:
                if p.get("id") in top_ids[:5]:
                    top_pois.append({
                        "name": p.get("name"),
                        "category": p.get("category"),
                        "score": next((s.get("score") for s in scored if s.get("id") == p.get("id")), 5),
                    })

            print(f"  耗时: {elapsed:.1f}s")
            print(f"  Top推荐POI:")
            for p in top_pois:
                print(f"    - {p['name']} [{p['category']}] score={p['score']}")

            results.append({
                "name": name,
                "elapsed": elapsed,
                "top_pois": top_pois,
                "scored_count": len(scored),
            })

        except Exception as e:
            print(f"  ✗ 异常: {e}")
            results.append({"name": name, "error": str(e)})

    return results


async def main():
    """运行完整测试"""
    print("CityFlow Multi-Agent 测试")
    print("=" * 60)

    # 测试IntentAgent
    intent_results = await test_intent_agent()

    # 测试POIAgent
    poi_results = await test_poi_agent(intent_results)

    # 保存结果
    output = {
        "intent_results": intent_results,
        "poi_results": poi_results,
    }

    Path("test_agent_results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n" + "=" * 60)
    print("测试完成，结果保存到 test_agent_results.json")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())