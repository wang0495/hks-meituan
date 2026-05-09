"""CityFlow 异步测试运行器：支持并行执行、覆盖率收集和报告生成。

功能：
1. 异步执行 pytest（asyncio subprocess）
2. 支持 pytest-xdist 并行运行（自动检测是否安装）
3. 支持运行全部 / 指定模块 / 指定标记 / 名称模式的测试
4. 自动生成覆盖率报告和 HTML 测试报告
5. 失败自动重试（--retry）
6. Dry-run 模式（--dry-run）

用法：
    from backend.tools.test_runner import TestRunner

    runner = TestRunner()
    result = await runner.run_tests()
    result = await runner.run_specific_test("tests/test_circuit_breaker.py")
    result = await runner.run_tests_by_name("circuit_breaker")
    result = await runner.run_tests_with_retry(max_retries=2)
    result = await runner.run_with_coverage()

CLI:
    python -m backend.tools.test_runner
    python -m backend.tools.test_runner --module tests/test_circuit_breaker.py
    python -m backend.tools.test_runner -k "circuit_breaker or retry"
    python -m backend.tools.test_runner --retry 2
    python -m backend.tools.test_runner --dry-run
    python -m backend.tools.test_runner --no-parallel --no-coverage
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from backend.tools.test_config import (ROOT, TEST_CONFIG, TestConfig,
                                       build_pytest_args)

# ---------------------------------------------------------------------------
# 检测 pytest-xdist 是否可用
# ---------------------------------------------------------------------------
_HAS_XDIST = importlib.util.find_spec("xdist") is not None  # type: ignore[attr-defined]


@dataclass
class TestRunResult:
    """单次测试运行结果。"""

    success: bool
    return_code: int
    stdout: str
    stderr: str
    duration: float
    test_count: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    parallel: bool = False
    report_html: Path | None = None

    @property
    def summary(self) -> str:
        """一行摘要。"""
        status = "PASS" if self.success else "FAIL"
        return (
            f"[{status}] {self.test_count} tests | "
            f"{self.passed} passed, {self.failed} failed, "
            f"{self.errors} errors, {self.skipped} skipped | "
            f"{self.duration:.2f}s"
        )


class TestRunner:
    """异步测试运行器。

    通过 asyncio 管理 pytest 子进程，支持并行执行和报告生成。
    """

    def __init__(
        self, config: TestConfig | None = None, *, dry_run: bool = False
    ) -> None:
        self._config = config or TEST_CONFIG
        self._history: list[TestRunResult] = []
        self._dry_run = dry_run

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    async def run_tests(
        self,
        *,
        parallel: bool | None = None,
        markers: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """运行全部测试。

        Args:
            parallel: 是否并行，None 则使用配置值
            markers: 只运行指定标记的测试
            extra_args: 额外 pytest 参数

        Returns:
            TestRunResult 实例
        """
        use_parallel = parallel if parallel is not None else self._config.parallel

        # 如果要求并行但 xdist 未安装，降级为串行
        if use_parallel and not _HAS_XDIST:
            use_parallel = False

        # 构建参数时临时覆盖配置
        if use_parallel != self._config.parallel:
            cfg = TestConfig(
                test_paths=self._config.test_paths,
                parallel=use_parallel,
                workers=self._config.workers,
                coverage=self._config.coverage,
                coverage_source=self._config.coverage_source,
                timeout=self._config.timeout,
                exclude_slow=self._config.exclude_slow,
                junit_xml=self._config.junit_xml,
                coverage_xml=self._config.coverage_xml,
                report_html=self._config.report_html,
                coverage_html_dir=self._config.coverage_html_dir,
            )
        else:
            cfg = self._config

        args = build_pytest_args(cfg, markers=markers, extra=extra_args)
        return await self._execute(args, parallel=use_parallel)

    async def run_specific_test(
        self,
        test_file: str,
        *,
        parallel: bool = False,
    ) -> TestRunResult:
        """运行指定的测试文件或目录。

        Args:
            test_file: 测试文件路径（相对于项目根目录）
            parallel: 是否并行

        Returns:
            TestRunResult 实例
        """
        args = build_pytest_args(self._config, module=test_file)
        return await self._execute(args, parallel=parallel)

    async def run_tests_by_name(
        self,
        pattern: str,
        *,
        parallel: bool = False,
    ) -> TestRunResult:
        """按名称模式运行测试（使用 pytest -k）。

        Args:
            pattern: pytest -k 表达式（如 "intent or solver"）
            parallel: 是否并行

        Returns:
            TestRunResult 实例
        """
        args = build_pytest_args(self._config, extra=["-k", pattern])
        return await self._execute(args, parallel=parallel)

    async def run_tests_with_retry(
        self,
        *,
        max_retries: int = 2,
        parallel: bool | None = None,
        markers: list[str] | None = None,
    ) -> TestRunResult:
        """运行测试，失败时自动重试。

        Args:
            max_retries: 最大重试次数
            parallel: 是否并行
            markers: 只运行指定标记的测试

        Returns:
            最后一次运行的 TestRunResult 实例
        """
        result = await self.run_tests(parallel=parallel, markers=markers)

        retries = 0
        while not result.success and retries < max_retries:
            retries += 1
            print(f"\n[RETRY] 第 {retries}/{max_retries} 次重试...")
            result = await self.run_tests(parallel=parallel, markers=markers)

        if retries > 0:
            print(
                f"\n[RETRY] 共重试 {retries} 次，最终结果: {'PASS' if result.success else 'FAIL'}"
            )

        return result

    async def run_with_coverage(
        self,
        *,
        module: str | None = None,
    ) -> TestRunResult:
        """运行测试并强制生成覆盖率报告。

        Args:
            module: 指定测试模块，None 则运行全部

        Returns:
            TestRunResult 实例
        """
        cfg = TestConfig(
            test_paths=self._config.test_paths,
            parallel=self._config.parallel,
            workers=self._config.workers,
            coverage=True,  # 强制开启
            coverage_source=self._config.coverage_source,
            timeout=self._config.timeout,
            exclude_slow=self._config.exclude_slow,
            junit_xml=self._config.junit_xml,
            coverage_xml=self._config.coverage_xml,
            report_html=self._config.report_html,
            coverage_html_dir=self._config.coverage_html_dir,
        )
        args = build_pytest_args(cfg, module=module)
        return await self._execute(args, parallel=cfg.parallel)

    @property
    def history(self) -> list[TestRunResult]:
        """返回历史运行结果。"""
        return list(self._history)

    # ------------------------------------------------------------------
    # 报告生成（委托给 TestReportGenerator）
    # ------------------------------------------------------------------

    def generate_html_report(self, result: TestRunResult) -> Path | None:
        """从最近一次运行结果生成 HTML 报告。

        Args:
            result: TestRunResult 实例

        Returns:
            报告文件路径，失败返回 None
        """
        try:
            from backend.tools.test_report import TestReportGenerator

            generator = TestReportGenerator(project_name="CityFlow")

            if self._config.junit_xml.exists():
                generator.load_from_xml(self._config.junit_xml)

            if self._config.coverage_xml.exists():
                generator.load_coverage_xml(self._config.coverage_xml)

            report_path = generator.save_report(self._config.report_html)
            return report_path
        except Exception as exc:
            print(f"[ERROR] 生成 HTML 报告失败: {exc}", file=sys.stderr)
            return None

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    async def _execute(
        self,
        args: list[str],
        *,
        parallel: bool = False,
    ) -> TestRunResult:
        """执行 pytest 子进程并解析结果。"""
        cmd = [sys.executable, "-m", "pytest", *args]
        print(f"\n{'=' * 60}")
        print(f"  运行测试 {'(并行)' if parallel else '(串行)'}")
        print(f"  命令: {' '.join(cmd)}")
        print(f"{'=' * 60}\n")

        if self._dry_run:
            print("[DRY RUN] 仅显示命令，不实际执行。")
            return TestRunResult(
                success=True,
                return_code=0,
                stdout="",
                stderr="",
                duration=0.0,
                parallel=parallel,
            )

        start = time.monotonic()

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ROOT),
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        duration = time.monotonic() - start

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # 打印输出
        if stdout:
            print(stdout)
        if stderr:
            print(stderr, file=sys.stderr)

        # 解析 pytest 输出摘要行
        parsed = self._parse_pytest_output(stdout)

        result = TestRunResult(
            success=process.returncode == 0,
            return_code=process.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            duration=duration,
            parallel=parallel,
            **parsed,
        )

        # 生成 HTML 报告
        report_path = self.generate_html_report(result)
        result.report_html = report_path

        self._history.append(result)
        return result

    @staticmethod
    def _parse_pytest_output(output: str) -> dict[str, int]:
        """从 pytest 输出中解析测试统计。

        pytest 典型输出行：
            ===== 25 passed, 2 failed, 1 error in 3.45s =====
        """
        import re

        stats: dict[str, int] = {
            "test_count": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
        }

        # 匹配 pytest 汇总行
        summary_re = re.compile(r"=+\s*(.*?)\s+in\s+[\d.]+s?\s*=+")
        for line in output.splitlines():
            m = summary_re.search(line)
            if not m:
                continue
            content = m.group(1)

            for key, pattern in [
                ("passed", r"(\d+)\s+passed"),
                ("failed", r"(\d+)\s+failed"),
                ("errors", r"(\d+)\s+error"),
                ("skipped", r"(\d+)\s+skipped"),
            ]:
                match = re.search(pattern, content)
                if match:
                    stats[key] = int(match.group(1))

            stats["test_count"] = (
                stats["passed"] + stats["failed"] + stats["errors"] + stats["skipped"]
            )
            break

        return stats


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


async def _cli_main() -> None:
    """CLI 异步入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="CityFlow 异步测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m backend.tools.test_runner                          # 运行全部测试
  python -m backend.tools.test_runner --no-parallel             # 串行运行
  python -m backend.tools.test_runner --no-coverage             # 跳过覆盖率
  python -m backend.tools.test_runner --module tests/test_circuit_breaker.py
  python -m backend.tools.test_runner --markers integration     # 只跑集成测试
        """,
    )
    parser.add_argument(
        "--module",
        type=str,
        default=None,
        help="指定测试模块或文件",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="禁用并行运行",
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="跳过覆盖率收集",
    )
    parser.add_argument(
        "--markers",
        nargs="+",
        default=None,
        help="只运行指定标记的测试（如 slow integration）",
    )
    parser.add_argument(
        "--include-slow",
        action="store_true",
        help="包含慢速测试",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="HTML 报告输出路径",
    )
    parser.add_argument(
        "-k",
        "--keyword",
        type=str,
        default=None,
        help="按名称模式过滤测试（pytest -k 表达式）",
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=0,
        help="失败时自动重试的次数",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅显示 pytest 命令，不实际执行",
    )

    args = parser.parse_args()

    # 构建配置
    cfg = TestConfig(
        parallel=not args.no_parallel,
        coverage=not args.no_coverage,
        exclude_slow=not args.include_slow,
    )
    if args.output:
        cfg = TestConfig(
            test_paths=cfg.test_paths,
            parallel=cfg.parallel,
            workers=cfg.workers,
            coverage=cfg.coverage,
            coverage_source=cfg.coverage_source,
            timeout=cfg.timeout,
            exclude_slow=cfg.exclude_slow,
            report_html=Path(args.output),
        )

    runner = TestRunner(config=cfg, dry_run=args.dry_run)

    if args.keyword:
        result = await runner.run_tests_by_name(args.keyword)
    elif args.module:
        result = await runner.run_specific_test(args.module)
    elif args.retry > 0:
        result = await runner.run_tests_with_retry(
            max_retries=args.retry,
            markers=args.markers,
        )
    else:
        result = await runner.run_tests(markers=args.markers)

    print(f"\n{'=' * 60}")
    print(f"  {result.summary}")
    print(f"{'=' * 60}")

    if result.report_html:
        print(f"  HTML 报告: {result.report_html}")

    sys.exit(0 if result.success else 1)


def main() -> None:
    """CLI 同步入口。"""
    asyncio.run(_cli_main())


if __name__ == "__main__":
    main()
