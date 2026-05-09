"""CityFlow 内存分析器。

基于 tracemalloc 提供内存分配追踪能力，
支持快照对比、Top N 排查、增量分析。
"""

from __future__ import annotations

import logging
import tracemalloc
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AllocationInfo:
    """单条内存分配记录。"""

    file: str
    line: int
    size: int
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "size": self.size,
            "size_human": _human_size(self.size),
            "count": self.count,
        }


@dataclass
class SnapshotInfo:
    """快照摘要。"""

    label: str
    allocations: list[AllocationInfo] = field(default_factory=list)
    total_size: int = 0
    total_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "total_size": self.total_size,
            "total_size_human": _human_size(self.total_size),
            "total_count": self.total_count,
            "allocations": [a.to_dict() for a in self.allocations],
        }


def _human_size(size_bytes: int) -> str:
    """将字节数转为可读字符串。"""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"


class MemoryProfiler:
    """内存分析器。

    用法::

        mem_profiler = MemoryProfiler()
        mem_profiler.start()

        # ... 执行代码 ...

        snapshot = mem_profiler.take_snapshot("after_load")
        print(mem_profiler.get_top_allocations(limit=10))

        # 对比两次快照
        mem_profiler.take_snapshot("after_process")
        diff = mem_profiler.compare_snapshots("after_load", "after_process")

        mem_profiler.stop()
    """

    def __init__(self, nframes: int = 1) -> None:
        self._snapshots: dict[str, tracemalloc.Snapshot] = {}
        self._enabled: bool = False
        self._nframes: int = nframes

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self, nframes: int | None = None) -> None:
        """启动内存追踪。

        Args:
            nframes: 每个分配记录保存的栈帧层数，默认 1。
                     层数越大越精确，但开销也越大。
        """
        if nframes is not None:
            self._nframes = nframes
        tracemalloc.start(self._nframes)
        self._enabled = True
        logger.info("MemoryProfiler 已启动 (nframes=%d)", self._nframes)

    def stop(self) -> None:
        """停止内存追踪并清空快照。"""
        tracemalloc.stop()
        self._enabled = False
        self._snapshots.clear()
        logger.info("MemoryProfiler 已停止")

    def take_snapshot(self, label: str = "default") -> SnapshotInfo | None:
        """拍摄内存快照。

        Args:
            label: 快照标签，用于后续对比。

        Returns:
            快照摘要，未启用时返回 None。
        """
        if not self._enabled:
            logger.warning("MemoryProfiler 未启动，无法拍摄快照")
            return None

        raw = tracemalloc.take_snapshot()
        self._snapshots[label] = raw

        stats = raw.statistics("lineno")
        allocations = [
            AllocationInfo(
                file=stat.traceback[0].filename,
                line=stat.traceback[0].lineno,
                size=stat.size,
                count=stat.count,
            )
            for stat in stats
        ]

        info = SnapshotInfo(
            label=label,
            allocations=allocations,
            total_size=sum(s.size for s in stats),
            total_count=sum(s.count for s in stats),
        )
        logger.info(
            "MemoryProfiler 快照 [%s]: %s, %d 处分配",
            label,
            _human_size(info.total_size),
            info.total_count,
        )
        return info

    def get_top_allocations(
        self, limit: int = 10, label: str = "default"
    ) -> list[dict[str, Any]]:
        """获取内存分配 Top N。

        Args:
            limit: 返回条数。
            label: 使用哪个快照。

        Returns:
            按内存大小降序排列的分配列表。
        """
        if label not in self._snapshots:
            logger.warning("快照 [%s] 不存在", label)
            return []

        snapshot = self._snapshots[label]
        stats = snapshot.statistics("lineno")

        result: list[dict[str, Any]] = []
        for stat in stats[:limit]:
            result.append(
                {
                    "file": stat.traceback[0].filename,
                    "line": stat.traceback[0].lineno,
                    "size": stat.size,
                    "size_human": _human_size(stat.size),
                    "count": stat.count,
                }
            )
        return result

    def compare_snapshots(
        self,
        label_before: str,
        label_after: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """对比两个快照，返回内存增量 Top N。

        Args:
            label_before: 基准快照标签。
            label_after: 后续快照标签。
            limit: 返回条数。

        Returns:
            按增量降序排列的对比结果。
        """
        if label_before not in self._snapshots:
            logger.warning("基准快照 [%s] 不存在", label_before)
            return []
        if label_after not in self._snapshots:
            logger.warning("对比快照 [%s] 不存在", label_after)
            return []

        before = self._snapshots[label_before]
        after = self._snapshots[label_after]
        diffs = after.compare_to(before, "lineno")

        result: list[dict[str, Any]] = []
        for diff in diffs[:limit]:
            result.append(
                {
                    "file": diff.traceback[0].filename,
                    "line": diff.traceback[0].lineno,
                    "size_diff": diff.size_diff,
                    "size_diff_human": _human_size(diff.size_diff),
                    "size": diff.size,
                    "size_human": _human_size(diff.size),
                    "count_diff": diff.count_diff,
                }
            )
        return result

    def get_snapshot_labels(self) -> list[str]:
        """返回所有已保存的快照标签。"""
        return list(self._snapshots.keys())

    def remove_snapshot(self, label: str) -> bool:
        """删除指定快照。"""
        if label in self._snapshots:
            del self._snapshots[label]
            return True
        return False
