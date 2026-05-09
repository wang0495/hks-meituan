"""CityFlow 资源清理脚本。

运行方式：
    python -m backend.tools.run_cleanup
    python backend/tools/run_cleanup.py [--temp-dir DIR] [--cache-dir DIR] [--log-dir DIR]
"""

from __future__ import annotations

import argparse
import sys

from backend.tools.resource_cleaner import ResourceCleaner


def main(argv: list[str] | None = None) -> int:
    """执行资源清理，返回退出码。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 资源清理工具",
    )
    parser.add_argument(
        "--temp-dir",
        default="temp",
        help="临时文件目录（默认: temp）",
    )
    parser.add_argument(
        "--cache-dir",
        default="cache",
        help="缓存目录（默认: cache）",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="日志目录（默认: logs）",
    )
    parser.add_argument(
        "--temp-max-age",
        type=int,
        default=7,
        help="临时文件最大保留天数（默认: 7）",
    )
    parser.add_argument(
        "--cache-max-size",
        type=int,
        default=100,
        help="缓存大小上限 MB（默认: 100）",
    )
    parser.add_argument(
        "--log-max-age",
        type=int,
        default=30,
        help="日志文件最大保留天数（默认: 30）",
    )
    args = parser.parse_args(argv)

    cleaner = ResourceCleaner()

    print("=" * 40)
    print("  CityFlow 资源清理")
    print("=" * 40)
    print()

    # 1. 清理临时文件
    print("[1/3] 清理临时文件...")
    cleaner.clean_temp_files(
        temp_dir=args.temp_dir,
        max_age_days=args.temp_max_age,
    )

    # 2. 清理缓存
    print("[2/3] 清理缓存...")
    cleaner.clean_cache(
        cache_dir=args.cache_dir,
        max_size_mb=args.cache_max_size,
    )

    # 3. 清理日志
    print("[3/3] 清理日志...")
    cleaner.clean_logs(
        log_dir=args.log_dir,
        max_age_days=args.log_max_age,
    )

    # 汇总
    report = cleaner.get_report()

    print()
    print("-" * 40)
    print(f"  清理文件数: {report['cleaned_files']}")
    print(f"  释放空间:   {report['freed_space_mb']:.2f} MB")
    print("-" * 40)

    return 0


if __name__ == "__main__":
    sys.exit(main())
