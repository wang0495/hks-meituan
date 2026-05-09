"""CityFlow 基准测试套件。

提供 BenchmarkSuite 高层抽象，将多个基准测试场景组织为一个套件，
统一运行并生成 JSON 报告。

与 BaselineBenchmark 的关系：
    BaselineBenchmark  -- 单个函数的底层基准运行器
    BenchmarkSuite     -- 多场景聚合层，调用 BaselineBenchmark

用法::

    suite = BenchmarkSuite("CityFlow API 基准")

    @suite.register("健康检查", iterations=100)
    async def health():
        ...

    @suite.register("POI搜索", iterations=50, concurrency=5)
    async def poi_search():
        ...

    results = await suite.run_all()
    suite.save_report(Path("report.json"))
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Coroutine

from backend.benchmarks.baseline import BaselineBenchmark
from backend.benchmarks.metrics import (PERFORMANCE_THRESHOLDS,
                                        PerformanceMetrics, ThresholdViolation,
                                        check_thresholds)

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    """单个测试场景的注册配置。"""

    name: str
    func: Callable[..., Coroutine[Any, Any, Any]]
    iterations: int = 100
    concurrency: int = 1
    warmup: int = 5


@dataclass(slots=True)
class ScenarioResult:
    """单个场景的完整结果。"""

    name: str
    config_iterations: int
    config_concurrency: int
    metrics: PerformanceMetrics
    violations: list[ThresholdViolation]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        return {
            "name": self.name,
            "config": {
                "iterations": self.config_iterations,
                "concurrency": self.config_concurrency,
            },
            "metrics": self.metrics.to_dict(),
            "threshold_violations": [str(v) for v in self.violations],
            "passed": self.passed,
        }


@dataclass(slots=True)
class SuiteReport:
    """套件级报告。"""

    suite_name: str
    generated_at: str
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    total_duration_seconds: float
    scenarios: list[ScenarioResult]
    thresholds: dict[str, float]

    @property
    def all_passed(self) -> bool:
        return self.failed_scenarios == 0

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        return {
            "suite_name": self.suite_name,
            "generated_at": self.generated_at,
            "summary": {
                "total_scenarios": self.total_scenarios,
                "passed": self.passed_scenarios,
                "failed": self.failed_scenarios,
                "all_passed": self.all_passed,
                "total_duration_seconds": round(self.total_duration_seconds, 2),
            },
            "thresholds": self.thresholds,
            "scenarios": [s.to_dict() for s in self.scenarios],
        }


# ---------------------------------------------------------------------------
# 套件
# ---------------------------------------------------------------------------


class BenchmarkSuite:
    """基准测试套件。

    管理多个测试场景的注册、运行和报告生成。

    用法::

        suite = BenchmarkSuite("My Suite")

        @suite.register("场景A")
        async def scenario_a():
            ...

        report = await suite.run_all()
        print(report.to_dict())
    """

    def __init__(
        self,
        name: str = "CityFlow Benchmark Suite",
        *,
        thresholds: dict[str, float] | None = None,
    ) -> None:
        self._name = name
        self._scenarios: list[ScenarioConfig] = []
        self._thresholds = thresholds or PERFORMANCE_THRESHOLDS
        self._runner = BaselineBenchmark()
        self._last_report: SuiteReport | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def last_report(self) -> SuiteReport | None:
        return self._last_report

    def register(
        self,
        name: str,
        *,
        iterations: int = 100,
        concurrency: int = 1,
        warmup: int = 5,
    ) -> Callable[
        [Callable[..., Coroutine[Any, Any, Any]]],
        Callable[..., Coroutine[Any, Any, Any]],
    ]:
        """装饰器：注册一个基准测试场景。

        Args:
            name: 场景名称。
            iterations: 迭代次数。
            concurrency: 并发数。
            warmup: 预热轮次。

        Returns:
            装饰器，原函数不变。
        """

        def decorator(
            func: Callable[..., Coroutine[Any, Any, Any]],
        ) -> Callable[..., Coroutine[Any, Any, Any]]:
            self._scenarios.append(
                ScenarioConfig(
                    name=name,
                    func=func,
                    iterations=iterations,
                    concurrency=concurrency,
                    warmup=warmup,
                )
            )
            return func

        return decorator

    def add_scenario(
        self,
        name: str,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *,
        iterations: int = 100,
        concurrency: int = 1,
        warmup: int = 5,
    ) -> None:
        """程序化注册一个场景（非装饰器方式）。"""
        self._scenarios.append(
            ScenarioConfig(
                name=name,
                func=func,
                iterations=iterations,
                concurrency=concurrency,
                warmup=warmup,
            )
        )

    async def run_scenario(self, config: ScenarioConfig) -> ScenarioResult:
        """运行单个场景并返回结果。"""
        metrics = await self._runner.run_full(
            config.func,
            iterations=config.iterations,
            concurrency=config.concurrency,
            warmup=config.warmup,
        )
        violations = check_thresholds(metrics, self._thresholds)
        return ScenarioResult(
            name=config.name,
            config_iterations=config.iterations,
            config_concurrency=config.concurrency,
            metrics=metrics,
            violations=violations,
            passed=len(violations) == 0,
        )

    async def run_all(
        self,
        *,
        on_scenario_start: Callable[[str, int], None] | None = None,
        on_scenario_end: Callable[[ScenarioResult], None] | None = None,
    ) -> SuiteReport:
        """运行所有已注册场景，生成套件报告。

        Args:
            on_scenario_start: 可选回调，场景开始时调用 (name, index)。
            on_scenario_end: 可选回调，场景结束时调用 (result)。

        Returns:
            SuiteReport 完整报告。
        """
        if not self._scenarios:
            raise ValueError("套件中没有注册任何场景，请先调用 register()")

        scenarios: list[ScenarioResult] = []
        suite_start = time.perf_counter()

        for idx, config in enumerate(self._scenarios):
            if on_scenario_start:
                on_scenario_start(config.name, idx)

            result = await self.run_scenario(config)
            scenarios.append(result)

            if on_scenario_end:
                on_scenario_end(result)

        total_duration = time.perf_counter() - suite_start
        passed_count = sum(1 for s in scenarios if s.passed)

        report = SuiteReport(
            suite_name=self._name,
            generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            total_scenarios=len(scenarios),
            passed_scenarios=passed_count,
            failed_scenarios=len(scenarios) - passed_count,
            total_duration_seconds=total_duration,
            scenarios=scenarios,
            thresholds=dict(self._thresholds),
        )

        self._last_report = report
        return report

    def save_report(
        self,
        path: Path | None = None,
        *,
        report: SuiteReport | None = None,
    ) -> Path:
        """将报告保存为 JSON 文件。

        Args:
            path: 输出路径。默认保存到 backend/benchmarks/results/。
            report: 要保存的报告，默认使用最后一次 run_all 的结果。

        Returns:
            实际写入的文件路径。
        """
        target = report or self._last_report
        if target is None:
            raise RuntimeError("没有可保存的报告，请先运行 run_all()")

        if path is None:
            results_dir = Path(__file__).parent / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            path = results_dir / f"suite_report_{timestamp}.json"

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(target.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
