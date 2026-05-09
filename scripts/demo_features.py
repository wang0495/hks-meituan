# scripts/demo_features.py

import asyncio
import httpx

async def demo_intent_parsing():
    """演示意图解析"""
    print("=== 意图解析演示 ===")

    test_cases = [
        "周末想出去走走，不想去人多的地方",
        "周末一家人带娃出去，让他消耗体力",
        "和女朋友约会，想找有氛围的地方"
    ]

    async with httpx.AsyncClient() as client:
        for user_input in test_cases:
            print(f"\n输入: {user_input}")

            response = await client.post(
                "http://localhost:8000/api/plan",
                json={"user_input": user_input}
            )

            print(f"状态: {response.status_code}")

async def demo_poi_search():
    """演示POI搜索"""
    print("\n=== POI搜索演示 ===")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/poi/search",
            json={"region": "珠海", "categories": ["文化"]}
        )

        data = response.json()
        print(f"找到 {len(data.get('pois', []))} 个POI")

async def main():
    """主函数"""
    print("=== CityFlow 功能演示 ===\n")

    await demo_intent_parsing()
    await demo_poi_search()

    print("\n=== 演示完成 ===")

if __name__ == "__main__":
    asyncio.run(main())