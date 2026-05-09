"""CityFlow YAML 配置验证 CLI。

运行方式：
    python -m backend.tools.validate_config
    python backend/tools/validate_config.py [--config PATH] [--check-env]
"""

from __future__ import annotations

import argparse
import sys

from backend.config.validator import ConfigValidator, ValidationResult


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
        description="CityFlow YAML 配置验证工具",
    )
    parser.add_argument(
        "--config",
        default="config/app.yaml",
        help="YAML 配置文件路径（默认: config/app.yaml）",
    )
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="同时验证环境变量（OPENAI_API_KEY, OPENAI_BASE_URL）",
    )
    parser.add_argument(
        "--env-var",
        action="append",
        default=[],
        help="额外需要验证的环境变量（可多次指定）",
    )
    args = parser.parse_args(argv)

    print("=" * 40)
    print("  CityFlow 配置验证")
    print("=" * 40)
    print()

    validator = ConfigValidator()
    all_ok = True

    # 1. 验证配置文件
    print("[1/2] 验证配置文件...")
    file_result = validator.validate_file(args.config)
    if not _print_result("配置文件", file_result):
        all_ok = False

    # 2. 验证环境变量（可选）
    print()
    if args.check_env or args.env_var:
        print("[2/2] 验证环境变量...")
        required_vars = args.env_var or ["OPENAI_API_KEY", "OPENAI_BASE_URL"]
        env_result = validator.validate_env_vars(required_vars)
        if not _print_result("环境变量", env_result):
            all_ok = False
    else:
        print("[2/2] 验证环境变量... 跳过（使用 --check-env 启用）")

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
