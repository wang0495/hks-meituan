"""CityFlow 日志查询脚本。

命令行工具，用于快速查看日志统计、搜索错误日志。

用法::

    python -m backend.tools.query_logs                  # 显示统计
    python -m backend.tools.query_logs --search error   # 搜索关键词
    python -m backend.tools.query_logs --level ERROR    # 按级别过滤
    python -m backend.tools.query_logs --dir logs       # 指定日志目录
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.tools.log_analyzer import LogAnalyzer


def _build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 日志查询工具",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="logs",
        help="日志目录路径（默认: logs）",
    )
    parser.add_argument(
        "--search",
        type=str,
        default=None,
        help="搜索关键词",
    )
    parser.add_argument(
        "--level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="按日志级别过滤",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="最大显示条数（默认: 50）",
    )
    return parser


def show_statistics(analyzer: LogAnalyzer) -> None:
    """显示日志统计信息。

    Args:
        analyzer: 日志分析器实例。
    """
    stats = analyzer.get_statistics()

    print("=== 日志统计 ===")
    print(f"  扫描文件数: {stats.file_count}")
    print(f"  日志总条数: {stats.total_entries}")
    print()

    if stats.level_counts:
        print("  级别分布:")
        for level, count in sorted(
            stats.level_counts.items(), key=lambda x: x[1], reverse=True
        ):
            pct = count / stats.total_entries * 100 if stats.total_entries else 0
            print(f"    {level:<10} {count:>6}  ({pct:.1f}%)")
    else:
        print("  未找到可解析的日志条目。")

    print()
    if stats.has_critical_issues:
        print(
            f"  [!] 检测到 {stats.error_count} 条 ERROR、{stats.critical_count} 条 CRITICAL"
        )


def search_and_display(
    analyzer: LogAnalyzer,
    keyword: str | None,
    level: str | None,
    limit: int,
) -> None:
    """搜索日志并显示结果。

    Args:
        analyzer: 日志分析器实例。
        keyword: 搜索关键词。
        level: 日志级别过滤。
        limit: 最大显示条数。
    """
    if keyword:
        results = analyzer.search_logs(keyword, level=level)
        header = f'搜索 "{keyword}"'
        if level:
            header += f" (级别: {level})"
    elif level:
        results = analyzer.search_logs("", level=level)
        header = f"级别过滤: {level}"
    else:
        print("请指定 --search 或 --level 参数。")
        return

    print(f"=== {header} ===")
    print(f"  匹配条数: {len(results)}")
    print()

    if not results:
        print("  无匹配结果。")
        return

    shown = results[:limit]
    for entry in shown:
        print(f"  [{entry.timestamp}] {entry.level:<8} {entry.message}")

    if len(results) > limit:
        print(f"\n  ... 仅显示前 {limit} 条，共 {len(results)} 条")


def main() -> None:
    """主函数。"""
    parser = _build_parser()
    args = parser.parse_args()

    log_dir = Path(args.dir)
    if not log_dir.is_dir():
        print(f"错误: 日志目录不存在 -> {log_dir}", file=sys.stderr)
        sys.exit(1)

    analyzer = LogAnalyzer(log_dir)

    if args.search or args.level:
        search_and_display(analyzer, args.search, args.level, args.limit)
    else:
        show_statistics(analyzer)


if __name__ == "__main__":
    main()
