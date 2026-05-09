# scripts/demo_performance.py

import asyncio
import time
import httpx

async def demo_concurrent_requests():
    """演示并发请求"""
    print("=== 并发请求演示 ===")

    async def make_request(client, index):
        start = time.time()
        response = await client.get("http://localhost:8000/health")
        duration = (time.time() - start) * 1000
        return duration

    async with httpx.AsyncClient() as client:
        # 并发10个请求
        tasks = [make_request(client, i) for i in range(10)]
        durations = await asyncio.gather(*tasks)

        avg_duration = sum(durations) / len(durations)
        print(f"平均响应时间: {avg_duration:.2f}ms")

async def demo_load_test():
    """演示负载测试"""
    print("\n=== 负载测试演示 ===")

    total_requests = 50
    successful = 0

    async with httpx.AsyncClient() as client:
        start = time.time()

        for i in range(total_requests):
            try:
                response = await client.get("http://localhost:8000/health")
                if response.status_code == 200:
                    successful += 1
            except Exception:
                pass

        total_time = time.time() - start
        rps = total_requests / total_time

        print(f"总请求: {total_requests}")
        print(f"成功: {successful}")
        print(f"RPS: {rps:.2f}")

async def main():
    """主函数"""
    print("=== CityFlow 性能演示 ===\n")

    await demo_concurrent_requests()
    await demo_load_test()

    print("\n=== 演示完成 ===")

if __name__ == "__main__":
    asyncio.run(main())