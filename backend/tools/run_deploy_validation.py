#!/usr/bin/env python3
"""CityFlow 部署验证脚本。

用法:
    python -m backend.tools.run_deploy_validation              # 完整验证
    python -m backend.tools.run_deploy_validation --skip-build  # 跳过 Docker 构建
    python -m backend.tools.run_deploy_validation --skip-health # 跳过健康检查
    python -m backend.tools.run_deploy_validation --json        # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.tools.deploy_validator import (CheckStatus,  # noqa: E402
                                            DeployValidator, ValidationReport)

# ---------------------------------------------------------------------------
# 终端输出
# ---------------------------------------------------------------------------

# ANSI 颜色
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _status_icon(status: CheckStatus) -> str:
    return {
        CheckStatus.PASS: f"{GREEN}PASS{RESET}",
        CheckStatus.FAIL: f"{RED}FAIL{RESET}",
        CheckStatus.SKIP: f"{YELLOW}SKIP{RESET}",
        CheckStatus.ERROR: f"{RED}ERR {RESET}",
    }[status]


def _format_duration(ms: float) -> str:
    if ms <= 0:
        return ""
    if ms < 1000:
        return f" ({ms:.0f}ms)"
    return f" ({ms / 1000:.1f}s)"


def print_report(report: ValidationReport) -> None:
    """以人类可读格式打印验证报告。"""
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  CityFlow 部署验证报告{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    for i, check in enumerate(report.checks, 1):
        icon = _status_icon(check.status)
        duration = _format_duration(check.duration_ms)
        print(f"  {i:2d}. [{icon}] {check.name}{duration}")

        if check.message:
            print(f"      {check.message}")

        # 显示失败/错误的详细信息
        if check.status in (CheckStatus.FAIL, CheckStatus.ERROR):
            if "stderr" in check.details:
                stderr = check.details["stderr"]
                if stderr:
                    for line in stderr.strip().splitlines()[:5]:
                        print(f"      {CYAN}|{RESET} {line}")
            if "error" in check.details:
                print(f"      {CYAN}error:{RESET} {check.details['error']}")

    # 汇总
    print(f"\n{BOLD}{'-' * 60}{RESET}")
    summary_parts = [
        f"{GREEN}{report.passed} 通过{RESET}",
        f"{RED}{report.failed} 失败{RESET}" if report.failed else "",
        f"{RED}{report.errors} 错误{RESET}" if report.errors else "",
        f"{YELLOW}{report.skipped} 跳过{RESET}" if report.skipped else "",
    ]
    summary = " | ".join(p for p in summary_parts if p)
    print(f"  汇总: {summary}")

    if report.overall_success:
        print(f"\n  {GREEN}{BOLD}部署验证通过{RESET}")
    else:
        print(f"\n  {RED}{BOLD}部署验证失败{RESET}")

    print(f"{BOLD}{'=' * 60}{RESET}\n")


def print_json(report: ValidationReport) -> None:
    """以 JSON 格式输出验证报告。"""
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CityFlow 部署验证工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="跳过 Docker 镜像构建测试（耗时较长）",
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="跳过健康检查端点测试（需要服务运行中）",
    )
    parser.add_argument(
        "--compose-file",
        default="docker-compose.yml",
        help="Docker Compose 文件名 (默认: docker-compose.yml)",
    )
    parser.add_argument(
        "--health-url",
        default="http://localhost:8000/health",
        help="健康检查 URL (默认: http://localhost:8000/health)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 格式输出报告",
    )
    return parser.parse_args()


def main() -> int:
    """主函数，返回退出码 (0=通过, 1=失败)。"""
    args = parse_args()

    validator = DeployValidator(
        health_url=args.health_url,
        compose_file=args.compose_file,
    )

    report = validator.validate_all(
        skip_build=args.skip_build,
        skip_health=args.skip_health,
    )

    if args.json_output:
        print_json(report)
    else:
        print_report(report)

    return 0 if report.overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
