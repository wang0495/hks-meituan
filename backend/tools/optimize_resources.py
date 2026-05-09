"""CityFlow 资源优化 CLI 脚本。

采集系统 CPU、内存、磁盘指标并输出优化报告。

使用方式：
    python -m backend.tools.optimize_resources
"""

from __future__ import annotations

import sys

from backend.tools.resource_optimizer import ResourceOptimizer


def main() -> None:
    """采集资源指标并打印优化报告。"""
    optimizer = ResourceOptimizer()

    print("=== CityFlow 资源优化 ===\n")

    report = optimizer.get_optimization_report()

    cpu = report.cpu
    mem = report.memory
    disk = report.disk

    print(f"CPU 使用率:   {cpu.usage_percent:.1f}%  ({cpu.cores} 核)")
    print(
        f"内存使用率:   {mem.usage_percent:.1f}%  "
        f"(可用 {mem.available_bytes / (1024**3):.1f} GB)"
    )
    print(
        f"磁盘使用率:   {disk.usage_percent:.1f}%  "
        f"(可用 {disk.free_bytes / (1024**3):.1f} GB)"
    )

    if report.total_recommendations > 0:
        print(f"\n发现 {report.total_recommendations} 条优化建议:\n")
        for rec in cpu.recommendations + mem.recommendations + disk.recommendations:
            severity_icon = "!!" if rec.severity.value == "critical" else "!"
            print(f"  [{severity_icon}] {rec.issue}")
            print(f"      -> {rec.suggestion}\n")
        sys.exit(1)
    else:
        print("\n资源使用正常，无需优化。")

    print("\n=== 优化完成 ===")


if __name__ == "__main__":
    main()
