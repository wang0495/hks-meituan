"""CityFlow API 测试运行器 + 报告生成。

接收 ``TestCaseGenerator`` 生成的用例列表，逐条执行并输出结构化报告。

用法::

    runner = APITestRunner("http://localhost:8000")
    report = await runner.run_tests(tests)
    runner.print_report(report)
    runner.save_report(report, "api_test_report.json")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tests.api_client import APITestClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 单条测试结果
# ---------------------------------------------------------------------------


class TestResult:
    """单条测试执行结果。"""

    __slots__ = (
        "description",
        "elapsed_ms",
        "error",
        "expected_status",
        "method",
        "name",
        "passed",
        "path",
        "response_data",
        "status_code",
    )

    def __init__(
        self,
        name: str,
        method: str,
        path: str,
        description: str,
        passed: bool,
        status_code: int,
        expected_status: int | list[int],
        response_data: Any = None,
        error: str | None = None,
        elapsed_ms: float = 0.0,
    ) -> None:
        self.name = name
        self.method = method
        self.path = path
        self.description = description
        self.passed = passed
        self.status_code = status_code
        self.expected_status = expected_status
        self.response_data = response_data
        self.error = error
        self.elapsed_ms = elapsed_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "method": self.method,
            "path": self.path,
            "description": self.description,
            "passed": self.passed,
            "status_code": self.status_code,
            "expected_status": self.expected_status,
            "response_data": self.response_data,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
        }


# ---------------------------------------------------------------------------
# 测试报告
# ---------------------------------------------------------------------------


class TestReport:
    """聚合的测试报告。"""

    def __init__(self, results: list[TestResult]) -> None:
        self.results = results
        self.total = len(results)
        self.passed = sum(1 for r in results if r.passed)
        self.failed = self.total - self.passed
        self.pass_rate = self.passed / self.total if self.total > 0 else 0.0
        self.total_elapsed_ms = sum(r.elapsed_ms for r in results)
        self.generated_at = datetime.now(UTC).isoformat()

    @property
    def failed_results(self) -> list[TestResult]:
        return [r for r in self.results if not r.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "pass_rate": round(self.pass_rate * 100, 2),
                "total_elapsed_ms": round(self.total_elapsed_ms, 2),
                "generated_at": self.generated_at,
            },
            "results": [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# 测试运行器
# ---------------------------------------------------------------------------


class APITestRunner:
    """API 测试运行器。

    Args:
        base_url: 服务地址，默认 http://localhost:8000
        concurrency: 并发数（1 = 串行），默认 1
        fail_fast: 遇到失败是否立即停止，默认 False
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        concurrency: int = 1,
        fail_fast: bool = False,
    ) -> None:
        self._base_url = base_url
        self._concurrency = concurrency
        self._fail_fast = fail_fast

    async def run_tests(self, tests: list[dict[str, Any]]) -> TestReport:
        """执行测试用例列表并返回报告。"""
        async with APITestClient(self._base_url) as client:
            if self._concurrency <= 1:
                results = await self._run_serial(client, tests)
            else:
                results = await self._run_concurrent(client, tests)
        return TestReport(results)

    # ------------------------------------------------------------------
    # 执行策略
    # ------------------------------------------------------------------

    async def _run_serial(
        self, client: APITestClient, tests: list[dict[str, Any]]
    ) -> list[TestResult]:
        """串行执行。"""
        results: list[TestResult] = []
        for test in tests:
            result = await self._execute_one(client, test)
            results.append(result)
            self._log_result(result)
            if self._fail_fast and not result.passed:
                logger.warning("fail_fast 触发，停止后续测试")
                break
        return results

    async def _run_concurrent(
        self, client: APITestClient, tests: list[dict[str, Any]]
    ) -> list[TestResult]:
        """并发执行（使用信号量控制并发数）。"""
        sem = asyncio.Semaphore(self._concurrency)
        results: list[TestResult] = []

        async def _run(test: dict[str, Any]) -> TestResult:
            async with sem:
                return await self._execute_one(client, test)

        tasks = [asyncio.create_task(_run(t)) for t in tests]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            self._log_result(result)
            if self._fail_fast and not result.passed:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                break

        return results

    # ------------------------------------------------------------------
    # 单条执行
    # ------------------------------------------------------------------

    async def _execute_one(self, client: APITestClient, test: dict[str, Any]) -> TestResult:
        """执行单条测试用例。"""
        method = test["method"].upper()
        path = test["path"]
        name = test.get("name", f"{method} {path}")
        description = test.get("description", "")
        expected = test.get("expected_status", 200)
        body = test.get("body")
        params = test.get("params")

        try:
            start = time.monotonic()

            # 特殊处理 SSE 端点
            if test.get("content_type") == "text/event-stream":
                events = await client.stream_sse(path, json=body)
                elapsed = (time.monotonic() - start) * 1000
                # SSE 总是 200，只要有事件就算成功
                passed = len(events) > 0
                return TestResult(
                    name=name,
                    method=method,
                    path=path,
                    description=description,
                    passed=passed,
                    status_code=200,
                    expected_status=expected,
                    response_data={"event_count": len(events), "events": events[:5]},
                    elapsed_ms=round(elapsed, 2),
                )

            # 普通请求
            result = await client.request(method, path, json=body, params=params)
            elapsed = result["elapsed_ms"]
            status = result["status_code"]

            # 判断通过
            if isinstance(expected, list):
                passed = status in expected
            else:
                passed = status == expected

            return TestResult(
                name=name,
                method=method,
                path=path,
                description=description,
                passed=passed,
                status_code=status,
                expected_status=expected,
                response_data=result["data"],
                error=result["error"],
                elapsed_ms=elapsed,
            )

        except Exception as exc:
            logger.exception("测试 %s 执行异常", name)
            return TestResult(
                name=name,
                method=method,
                path=path,
                description=description,
                passed=False,
                status_code=0,
                expected_status=expected,
                error=str(exc),
                elapsed_ms=0.0,
            )

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    @staticmethod
    def _log_result(result: TestResult) -> None:
        tag = "PASS" if result.passed else "FAIL"
        logger.info(
            "[%s] %s %s -> %d (expected %s) %.1fms",
            tag,
            result.method,
            result.path,
            result.status_code,
            result.expected_status,
            result.elapsed_ms,
        )

    # ------------------------------------------------------------------
    # 报告输出
    # ------------------------------------------------------------------

    @staticmethod
    def print_report(report: TestReport) -> None:
        """在控制台打印可读报告。"""
        s = report.summary
        print()
        print("=" * 60)
        print("  CityFlow API 测试报告")
        print("=" * 60)
        print(f"  总用例数:   {s['total']}")
        print(f"  通过:       {s['passed']}")
        print(f"  失败:       {s['failed']}")
        print(f"  通过率:     {s['pass_rate']}%")
        print(f"  总耗时:     {s['total_elapsed_ms']:.0f} ms")
        print(f"  生成时间:   {s['generated_at']}")
        print("-" * 60)

        if report.failed_results:
            print("\n  失败用例:")
            for r in report.failed_results:
                print(f"    [{r.method}] {r.path}")
                print(f"      描述:   {r.description}")
                print(f"      状态码: {r.status_code} (期望 {r.expected_status})")
                if r.error:
                    print(f"      错误:   {r.error[:200]}")
                print()

        print("=" * 60)
        print()

    @staticmethod
    def save_report(report: TestReport, path: str | Path, *, indent: int = 2) -> Path:
        """将报告保存为 JSON 文件。"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=indent),
            encoding="utf-8",
        )
        logger.info("报告已保存至 %s", p)
        return p
