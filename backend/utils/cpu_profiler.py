"""CityFlow CPU 分析器。

基于 cProfile 提供 CPU 级别的函数调用分析，
支持按累计耗时 / 自身耗时 / 调用次数排序。
"""

from __future__ import annotations

import cProfile
import io
import logging
import pstats
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FunctionStat:
    """单个函数的 CPU 统计。"""

    file: str
    line: int
    function: str
    ncalls: int
    tottime: float
    cumtime: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "function": self.function,
            "ncalls": self.ncalls,
            "tottime": round(self.tottime, 6),
            "cumtime": round(self.cumtime, 6),
        }


@dataclass
class CPUProfileResult:
    """一次 CPU 分析的结果。"""

    label: str
    functions: list[FunctionStat] = field(default_factory=list)
    total_calls: int = 0
    total_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "total_calls": self.total_calls,
            "total_time": round(self.total_time, 6),
            "functions": [f.to_dict() for f in self.functions],
        }


class CPUProfiler:
    """CPU 分析器。

    用法::

        cpu_profiler = CPUProfiler()

        # 方式 1: 上下文管理器
        with cpu_profiler.run("my_block"):
            do_heavy_work()

        # 方式 2: 装饰器
        @cpu_profiler.profile("my_func")
        def my_func():
            ...

        # 方式 3: 手动启停
        cpu_profiler.start()
        do_work()
        result = cpu_profiler.stop("work_label")

        # 查看结果
        print(cpu_profiler.get_top_functions(limit=20))
    """

    def __init__(self) -> None:
        self._profiler: cProfile.Profile | None = None
        self._results: dict[str, CPUProfileResult] = {}
        self._enabled: bool = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> None:
        """开始 CPU 分析。"""
        if self._profiler is None:
            self._profiler = cProfile.Profile()
        self._profiler.enable()
        self._enabled = True
        logger.debug("CPUProfiler 已启动")

    def stop(self, label: str = "default") -> CPUProfileResult:
        """停止分析并生成结果。

        Args:
            label: 本次分析的标签。

        Returns:
            分析结果。
        """
        if self._profiler is None:
            raise RuntimeError("CPUProfiler 未启动，请先调用 start()")

        self._profiler.disable()
        self._enabled = False

        result = self._build_result(label)
        self._results[label] = result
        logger.info(
            "CPUProfiler [%s]: %d 次调用, 总耗时 %.4fs",
            label,
            result.total_calls,
            result.total_time,
        )
        return result

    def run(self, label: str = "default") -> _CPURunContext:
        """返回上下文管理器，在退出时自动分析。

        用法::

            with cpu_profiler.run("my_block"):
                do_work()
        """
        return _CPURunContext(self, label)

    def profile(self, name: str | None = None) -> Any:
        """装饰器，对单个函数进行 CPU 分析。

        用法::

            @cpu_profiler.profile("heavy_func")
            def heavy_func():
                ...
        """

        def decorator(func: Any) -> Any:
            func_name = name or func.__name__

            def wrapper(*args: Any, **kwargs: Any) -> Any:
                self.start()
                try:
                    return func(*args, **kwargs)
                finally:
                    self.stop(func_name)

            wrapper.__name__ = func.__name__
            wrapper.__qualname__ = func.__qualname__
            return wrapper

        return decorator

    def get_top_functions(
        self,
        limit: int = 20,
        label: str | None = None,
        sort_by: str = "cumtime",
    ) -> list[dict[str, Any]]:
        """获取 CPU 耗时 Top N 函数。

        Args:
            limit: 返回条数。
            label: 指定分析结果标签，为 None 时取最新的。
            sort_by: 排序字段，可选 "cumtime"（累计）、"tottime"（自身）、"ncalls"（调用次数）。

        Returns:
            排序后的函数统计列表。
        """
        result = self._get_result(label)
        if result is None:
            return []

        key_map = {
            "cumtime": lambda f: f.cumtime,
            "tottime": lambda f: f.tottime,
            "ncalls": lambda f: f.ncalls,
        }
        key_fn = key_map.get(sort_by, key_map["cumtime"])

        sorted_funcs = sorted(result.functions, key=key_fn, reverse=True)
        return [f.to_dict() for f in sorted_funcs[:limit]]

    def get_pstats_text(self, label: str | None = None, sort_by: str = "cumulative") -> str:
        """获取 pstats 原始文本输出（便于调试）。

        Args:
            label: 指定分析结果标签。
            sort_by: pstats 排序键，如 "cumulative", "tottime", "calls"。

        Returns:
            格式化的文本报告。
        """
        result = self._get_result(label)
        if result is None:
            return ""

        # 需要重新从 profiler 获取 pstats
        if self._profiler is None:
            return ""

        stream = io.StringIO()
        stats = pstats.Stats(self._profiler, stream=stream)
        stats.sort_stats(sort_by)
        stats.print_stats()
        return stream.getvalue()

    def get_all_labels(self) -> list[str]:
        """返回所有分析结果的标签。"""
        return list(self._results.keys())

    def remove_result(self, label: str) -> bool:
        """删除指定分析结果。"""
        if label in self._results:
            del self._results[label]
            return True
        return False

    def reset(self) -> None:
        """清空所有结果并重置 profiler。"""
        self._results.clear()
        self._profiler = None
        self._enabled = False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_result(self, label: str | None) -> CPUProfileResult | None:
        if label is not None:
            return self._results.get(label)
        if not self._results:
            return None
        # 返回最新的
        return list(self._results.values())[-1]

    def _build_result(self, label: str) -> CPUProfileResult:
        assert self._profiler is not None

        stream = io.StringIO()
        stats = pstats.Stats(self._profiler, stream=stream)
        stats.sort_stats("cumulative")

        functions: list[FunctionStat] = []
        total_calls = 0
        total_time = 0.0

        for key, value in stats.stats.items():  # type: ignore[attr-defined]
            filename, line, func_name = key
            ncalls = value[0]
            tottime = value[2]
            cumtime = value[3]

            functions.append(
                FunctionStat(
                    file=filename,
                    line=line,
                    function=func_name,
                    ncalls=ncalls,
                    tottime=tottime,
                    cumtime=cumtime,
                )
            )
            total_calls += ncalls
            total_time += cumtime

        return CPUProfileResult(
            label=label,
            functions=functions,
            total_calls=total_calls,
            total_time=total_time,
        )


class _CPURunContext:
    """CPUProfiler.run() 返回的上下文管理器。"""

    def __init__(self, profiler: CPUProfiler, label: str) -> None:
        self._profiler = profiler
        self._label = label

    def __enter__(self) -> _CPURunContext:
        self._profiler.start()
        return self

    def __exit__(self, exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        self._profiler.stop(self._label)
