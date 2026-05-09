"""CityFlow 配置检查 CLI。

运行方式：
    python -m backend.tools.check_config
    python backend/tools/check_config.py [--env-file PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.tools.config_validator import ConfigValidator, ValidationResult


def _print_result(label: str, result: ValidationResult) -> bool:
    """打印单条验证结果，返回是否通过。"""
    status = "[OK]" if result.valid else "[FAIL]"
    print(f"  {status} {label}")

    for warning in result.warnings:
        print(f"       [WARN] {warning}")

    for error in result.errors:
        print(f"       [ERR]  {error}")

    return result.valid


def main(argv: list[str] | None = None) -> int:
    """主函数，返回退出码（0=全部通过，1=存在错误）。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 配置检查工具",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help=".env 文件路径（默认: .env）",
    )
    args = parser.parse_args(argv)

    env_file = Path(args.env_file)

    print("=" * 40)
    print("  CityFlow 配置检查")
    print("=" * 40)
    print()

    validator = ConfigValidator()
    all_ok = True

    # 1. .env 文件验证
    print("[1/3] 验证 .env 文件...")
    env_result = validator.validate_env_file(env_file)
    if not _print_result(".env 文件格式", env_result):
        all_ok = False

    # 2. 环境变量验证
    print()
    print("[2/3] 验证环境变量...")
    var_result = validator.validate_required_vars()
    if not _print_result("必需环境变量", var_result):
        all_ok = False

    # 3. 配置一致性验证
    print()
    print("[3/3] 验证配置一致性...")
    consistency_result = validator.validate_config_consistency()
    if not _print_result("配置一致性", consistency_result):
        all_ok = False

    # 汇总
    print()
    print("-" * 40)
    if all_ok:
        print("  所有检查通过。")
    else:
        print("  存在配置问题，请根据上述错误修复。")
    print("-" * 40)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
