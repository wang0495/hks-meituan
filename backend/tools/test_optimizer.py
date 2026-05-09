"""CityFlow 测试优化器：并行执行、智能选择和优化报告。

功能：
1. 并行执行优化（使用 pytest-xdist，自动检测最优 worker 数）
2. 智能测试选择（根据变更文件只运行受影响的测试）
3. 测试分组（按执行时间分桶，优化负载均衡）
4. 优化报告生成

用法：
    from backend.tools.test_optimizer import TestOptimizer

    optimizer = TestOptimizer()

    # 并行执行优化
    result = optimizer.optimize_parallel_execution()

    # 智能选择
    result = optimizer.optimize_test_selection(["backend/services/intent_parser.py"])

    # 生成报告
    report = optimizer.generate_report()

CLI:
    python -m backend.tools.test_optimizer                        # 并行执行全部
    python -m backend.tools.test_optimizer --select file1 file2   # 智能选择
    python -m backend.tools.test_optimizer --dry-run               # 仅显示命令
"""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TestOptimizer", "OptimizationResult", "AffectedTest"]

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent.parent

# 检测 pytest-xdist 是否可用
_HAS_XDIST = importlib.util.find_spec("xdist") is not None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 源文件 -> 测试文件 映射规则
# ---------------------------------------------------------------------------

# 模式: (源文件路径中的关键字, 对应的测试文件)
_SOURCE_TO_TESTS: list[tuple[str, list[str]]] = [
    # services -> tests/
    ("services/intent_parser", ["tests/test_intent.py", "tests/test_intent_mock.py"]),
    ("services/filters", ["tests/test_filters.py"]),
    ("services/solver", ["tests/test_solver.py"]),
    ("services/geo", ["tests/test_integration.py"]),
    ("services/dialogue", ["tests/test_dialogue.py"]),
    ("services/narrator", ["tests/test_narrator.py"]),
    ("services/parallel", ["tests/test_parallel.py"]),
    ("services/vectorized", ["tests/test_vectorized.py"]),
    ("services/logger", ["tests/test_logger.py"]),
    ("services/task_queue", ["tests/test_task_queue.py"]),
    ("services/metrics", ["tests/test_performance.py"]),
    ("services/emotion", ["tests/test_intent.py"]),
    ("services/time_utils", ["tests/test_intent.py"]),
    ("services/llm_service", ["tests/test_intent_mock.py"]),
    ("services/session", ["tests/test_dialogue.py"]),
    ("services/data_service", ["tests/test_integration.py"]),
    ("services/user_profiles", ["tests/test_intent.py"]),
    ("services/log_rotation", ["tests/test_logger.py"]),
    ("services/circuit_breaker", ["backend/tests/test_circuit_breaker.py"]),
    ("services/retry", ["backend/tests/test_retry.py"]),
    ("services/fallback", ["backend/tests/test_fallback.py"]),
    ("services/resilient_service", ["tests/test_resilience.py"]),
    ("services/registry", ["backend/tests/test_registry.py"]),
    ("services/websocket", ["tests/test_integration.py"]),
    ("services/notification", ["tests/test_integration.py"]),
    ("services/message_handlers", ["tests/test_integration.py"]),
    ("services/cache", ["tests/test_cache.py"]),
    ("services/cache_warmer", ["tests/test_cache_warmer.py"]),
    ("services/health_checker", ["backend/tests/test_health_checker.py"]),
    ("services/auto_recovery", ["backend/tests/test_auto_recovery.py"]),
    ("services/resource_monitor", ["backend/tests/test_resource_monitor.py"]),
    ("services/backup", ["backend/tests/test_backup.py"]),
    ("services/scheduled_backup", ["backend/tests/test_scheduled_backup.py"]),
    ("services/alert_notifier", ["backend/tests/test_alert_notifier.py"]),
    ("services/audit_logger", ["backend/tests/test_audit_logger.py"]),
    ("services/adaptive_rate_limiter", ["backend/tests/test_adaptive_rate_limiter.py"]),
    ("services/ip_rate_limiter", ["backend/tests/test_ip_rate_limiter.py"]),
    ("services/user_rate_limiter", ["backend/tests/test_user_rate_limiter.py"]),
    ("services/quota", ["backend/tests/test_quota.py"]),
    ("services/template_engine", ["tests/test_template_engine.py"]),
    ("services/message_queue", ["tests/test_message_queue.py"]),
    ("services/event_bus", ["tests/test_event_system.py"]),
    ("services/discovery", ["backend/tests/test_registry.py"]),
    # routers -> 集成测试
    ("routers/", ["tests/test_integration.py"]),
    # middleware -> 中间件测试
    ("middleware/rate_limit", ["backend/tests/test_rate_limiter.py"]),
    ("middleware/validation", ["tests/test_middleware_pipeline.py"]),
    ("middleware/security", ["tests/test_auth.py"]),
    ("middleware/session", ["tests/test_dialogue.py"]),
    # models -> schema 相关测试
    ("models/schemas", ["tests/test_intent.py"]),
    # database
    ("database/", ["tests/test_database.py"]),
    # graphql
    ("graphql/", ["tests/test_integration.py"]),
    # events
    ("events/", ["tests/test_event_system.py"]),
    # errors
    ("errors.py", ["backend/tests/test_errors.py"]),
    # config
    ("config_loader", ["tests/test_integration.py"]),
]


@dataclass
class AffectedTest:
    """受影响的测试文件信息。"""

    test_path: str
    source_files: list[str] = field(default_factory=list)
    priority: int = 0  # 越高越优先运行


@dataclass
class OptimizationResult:
    """优化执行结果。"""

    optimization: str
    success: bool
    duration: float = 0.0
    test_count: int = 0
    output: str = ""
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class TestOptimizer:
    """测试优化器。

    提供并行执行优化、智能测试选择和优化报告功能。
    与现有 TestRunner/TestConfig 集成，不重复已有能力。
    """

    def __init__(self, *, dry_run: bool = False) -> None:
        self._dry_run = dry_run
        self._results: list[OptimizationResult] = []
        self._source_to_tests = list(_SOURCE_TO_TESTS)

    # ------------------------------------------------------------------
    # 并行执行优化
    # ------------------------------------------------------------------

    def optimize_parallel_execution(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> OptimizationResult:
        """优化并行执行。

        自动检测最优 worker 数，使用 loadfile 分发策略
        让同一文件的测试在同一个 worker 中运行（共享 fixture）。

        Args:
            test_paths: 测试路径列表，默认 ["tests/", "backend/tests/"]
            extra_args: 额外 pytest 参数

        Returns:
            OptimizationResult 实例
        """
        if not _HAS_XDIST:
            result = OptimizationResult(
                optimization="并行执行",
                success=False,
                error="pytest-xdist 未安装，无法并行执行。请运行: pip install pytest-xdist",
            )
            self._results.append(result)
            return result

        paths = test_paths or ["tests/", "backend/tests/"]
        # 只保留存在的路径
        existing_paths = [p for p in paths if (ROOT / p).exists()]

        if not existing_paths:
            result = OptimizationResult(
                optimization="并行执行",
                success=False,
                error=f"测试路径不存在: {paths}",
            )
            self._results.append(result)
            return result

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            *existing_paths,
            "-n",
            "auto",
            "--dist=loadfile",
            "--timeout=300",
            "--tb=short",
            "-q",
        ]

        if extra_args:
            cmd.extend(extra_args)

        result = self._run_command(cmd, "并行执行")
        result.optimization = "并行执行"
        result.details = {
            "strategy": "loadfile",
            "workers": "auto",
            "paths": existing_paths,
        }

        self._results.append(result)
        return result

    # ------------------------------------------------------------------
    # 智能测试选择
    # ------------------------------------------------------------------

    def optimize_test_selection(
        self,
        changed_files: list[str],
        *,
        extra_args: list[str] | None = None,
    ) -> OptimizationResult:
        """根据变更文件智能选择需要运行的测试。

        Args:
            changed_files: 变更的源文件路径列表（相对于项目根目录）
            extra_args: 额外 pytest 参数

        Returns:
            OptimizationResult 实例
        """
        affected = self.find_affected_tests(changed_files)

        if not affected:
            result = OptimizationResult(
                optimization="智能选择",
                success=True,
                test_count=0,
                output="无受影响的测试文件",
                details={"affected_tests": [], "changed_files": changed_files},
            )
            self._results.append(result)
            return result

        test_files = [t.test_path for t in affected]

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            *test_files,
            "--timeout=300",
            "--tb=short",
            "-v",
        ]

        if _HAS_XDIST:
            cmd.extend(["-n", "auto", "--dist=loadfile"])

        if extra_args:
            cmd.extend(extra_args)

        result = self._run_command(cmd, "智能选择")
        result.optimization = "智能选择"
        result.test_count = len(test_files)
        result.details = {
            "affected_tests": test_files,
            "changed_files": changed_files,
            "mapping_count": len(affected),
        }

        self._results.append(result)
        return result

    def find_affected_tests(self, changed_files: list[str]) -> list[AffectedTest]:
        """查找受变更文件影响的测试。

        Args:
            changed_files: 变更的源文件路径列表

        Returns:
            受影响的测试列表（去重，按优先级排序）
        """
        seen: dict[str, AffectedTest] = {}

        for changed in changed_files:
            normalized = changed.replace("\\", "/")

            for pattern, test_files in self._source_to_tests:
                if pattern in normalized:
                    for tf in test_files:
                        if tf in seen:
                            if normalized not in seen[tf].source_files:
                                seen[tf].source_files.append(normalized)
                        else:
                            # 检查测试文件是否存在
                            if not (ROOT / tf).exists():
                                logger.debug("测试文件不存在，跳过: %s", tf)
                                continue
                            seen[tf] = AffectedTest(
                                test_path=tf,
                                source_files=[normalized],
                                priority=self._calc_priority(tf),
                            )

        # 按优先级降序排列
        return sorted(seen.values(), key=lambda t: t.priority, reverse=True)

    @staticmethod
    def _calc_priority(test_path: str) -> int:
        """计算测试文件优先级（单元测试 > 集成测试 > 其他）。"""
        name = Path(test_path).stem.lower()
        if "unit" in name or name in (
            "test_intent.py",
            "test_filters.py",
            "test_solver.py",
        ):
            return 10
        if "mock" in name:
            return 8
        if "integration" in name or "e2e" in name:
            return 5
        return 3

    # ------------------------------------------------------------------
    # Git 变更检测
    # ------------------------------------------------------------------

    def get_changed_files_from_git(
        self,
        base_ref: str = "HEAD~1",
    ) -> list[str]:
        """从 Git 获取变更文件列表。

        Args:
            base_ref: 比较基准（默认 HEAD~1，即上一次提交）

        Returns:
            变更文件路径列表
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", base_ref],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning("git diff 失败: %s", result.stderr.strip())
                return []

            files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
            return files

        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning("获取 Git 变更失败: %s", exc)
            return []

    # ------------------------------------------------------------------
    # 测试分组优化
    # ------------------------------------------------------------------

    def group_tests_by_module(
        self, test_paths: list[str] | None = None
    ) -> dict[str, list[str]]:
        """按模块对测试文件分组，用于优化并行分发。

        同一模块的测试在同一组中，共享 fixtures 和导入缓存。

        Args:
            test_paths: 测试目录列表

        Returns:
            {module_group: [test_files]} 字典
        """
        paths = test_paths or ["tests/", "backend/tests/"]
        groups: dict[str, list[str]] = {}

        for test_dir in paths:
            dir_path = ROOT / test_dir
            if not dir_path.exists():
                continue

            for test_file in sorted(dir_path.glob("test_*.py")):
                # 提取模块名（去掉 test_ 前缀）
                stem = test_file.stem
                module = stem.removeprefix("test_").split("_")[0]

                rel_path = str(test_file.relative_to(ROOT)).replace("\\", "/")
                groups.setdefault(module, []).append(rel_path)

        return groups

    # ------------------------------------------------------------------
    # 优化报告
    # ------------------------------------------------------------------

    def generate_report(self) -> dict[str, Any]:
        """生成优化报告。

        Returns:
            包含所有优化结果和建议的报告字典
        """
        total = len(self._results)
        successful = sum(1 for r in self._results if r.success)
        total_duration = sum(r.duration for r in self._results)

        suggestions = self._generate_suggestions()

        return {
            "summary": {
                "total_optimizations": total,
                "successful": successful,
                "failed": total - successful,
                "total_duration": round(total_duration, 2),
            },
            "results": [
                {
                    "optimization": r.optimization,
                    "success": r.success,
                    "duration": round(r.duration, 2),
                    "test_count": r.test_count,
                    "output": r.output[:500] if r.output else "",
                    "error": r.error[:500] if r.error else "",
                    "details": r.details,
                }
                for r in self._results
            ],
            "suggestions": suggestions,
        }

    def _generate_suggestions(self) -> list[str]:
        """根据优化结果生成改进建议。"""
        suggestions: list[str] = []

        if not _HAS_XDIST:
            suggestions.append(
                "安装 pytest-xdist 以启用并行测试执行: pip install pytest-xdist"
            )

        if not importlib.util.find_spec("pytest_timeout"):  # type: ignore[attr-defined]
            suggestions.append(
                "安装 pytest-timeout 以防止测试挂起: pip install pytest-timeout"
            )

        failed = [r for r in self._results if not r.success]
        if failed:
            suggestions.append(f"有 {len(failed)} 个优化步骤失败，请检查错误日志")

        slow_results = [r for r in self._results if r.duration > 60]
        if slow_results:
            suggestions.append(
                "部分测试执行超过 60 秒，考虑使用 @pytest.mark.slow 标记慢速测试"
            )

        return suggestions

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _run_command(self, cmd: list[str], label: str) -> OptimizationResult:
        """执行子进程命令。"""
        logger.info("[%s] 执行: %s", label, " ".join(cmd))

        if self._dry_run:
            return OptimizationResult(
                optimization=label,
                success=True,
                output=f"[DRY RUN] {' '.join(cmd)}",
                details={"command": cmd},
            )

        start = time.monotonic()

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                timeout=600,  # 10 分钟超时
            )
            duration = time.monotonic() - start

            return OptimizationResult(
                optimization=label,
                success=proc.returncode == 0,
                duration=duration,
                output=proc.stdout,
                error=proc.stderr,
                details={"return_code": proc.returncode, "command": cmd},
            )

        except subprocess.TimeoutExpired:
            return OptimizationResult(
                optimization=label,
                success=False,
                duration=time.monotonic() - start,
                error="命令执行超时（600 秒）",
            )
        except FileNotFoundError as exc:
            return OptimizationResult(
                optimization=label,
                success=False,
                error=f"命令未找到: {exc}",
            )

    @property
    def results(self) -> list[OptimizationResult]:
        """返回历史优化结果。"""
        return list(self._results)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI 入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="CityFlow 测试优化器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m backend.tools.test_optimizer                         # 并行执行全部
  python -m backend.tools.test_optimizer --select backend/services/intent_parser.py
  python -m backend.tools.test_optimizer --from-git HEAD~1       # 从 Git 变更选择
  python -m backend.tools.test_optimizer --dry-run               # 仅显示命令
  python -m backend.tools.test_optimizer --group                 # 显示测试分组
        """,
    )
    parser.add_argument(
        "--select",
        nargs="+",
        default=None,
        help="根据变更文件选择测试（源文件路径列表）",
    )
    parser.add_argument(
        "--from-git",
        type=str,
        default=None,
        metavar="REF",
        help="从 Git 变更自动选择测试（如 HEAD~1, main 等）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅显示命令，不实际执行",
    )
    parser.add_argument(
        "--group",
        action="store_true",
        help="显示测试文件分组信息",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="生成优化报告（JSON 格式输出到 stdout）",
    )

    args = parser.parse_args()

    optimizer = TestOptimizer(dry_run=args.dry_run)

    # 显示分组信息
    if args.group:
        groups = optimizer.group_tests_by_module()
        print("\n测试文件分组:")
        print("=" * 50)
        for module, files in sorted(groups.items()):
            print(f"\n  [{module}]")
            for f in files:
                print(f"    {f}")
        return

    # 从 Git 获取变更
    if args.from_git:
        changed = optimizer.get_changed_files_from_git(args.from_git)
        if not changed:
            print(f"未检测到相对于 {args.from_git} 的变更文件")
            return
        print(f"检测到 {len(changed)} 个变更文件:")
        for f in changed:
            print(f"  {f}")
        args.select = changed

    # 智能选择
    if args.select:
        result = optimizer.optimize_test_selection(args.select)
        print(f"\n{'=' * 50}")
        print(f"  优化: {result.optimization}")
        print(f"  成功: {result.success}")
        print(f"  受影响测试数: {result.test_count}")
        if result.duration > 0:
            print(f"  耗时: {result.duration:.2f}s")
        if result.output:
            print(f"\n{result.output}")
        if result.error:
            print(f"\n[ERROR] {result.error}", file=sys.stderr)
    else:
        # 默认：并行执行
        result = optimizer.optimize_parallel_execution()
        print(f"\n{'=' * 50}")
        print(f"  优化: {result.optimization}")
        print(f"  成功: {result.success}")
        if result.duration > 0:
            print(f"  耗时: {result.duration:.2f}s")
        if result.output:
            print(f"\n{result.output}")
        if result.error:
            print(f"\n[ERROR] {result.error}", file=sys.stderr)

    # 生成报告
    if args.report:
        import json

        report = optimizer.generate_report()
        print("\n" + json.dumps(report, ensure_ascii=False, indent=2))

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
