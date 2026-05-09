"""CityFlow 安全扫描 CLI 脚本。

运行方式::

    python -m backend.security.run_scan
    # 或
    python backend/security/run_scan.py
"""

from __future__ import annotations

import sys

from backend.security.scanner import SecurityScanner


def _print_banner() -> None:
    """打印扫描横幅。"""
    print("=" * 50)
    print("  CityFlow 安全扫描")
    print("=" * 50)
    print()


def _print_bandit(result: dict) -> None:
    """打印 Bandit 扫描结果。"""
    print("[1/3] Bandit 代码扫描...")
    if not result["success"]:
        print(f"  ! 执行失败: {result.get('error', '未知错误')}")
    elif result["has_issues"]:
        print(f"  ! {result['summary']}")
        for issue in result["issues"][:10]:
            print(
                f"    - {issue['file']}:{issue['line']} "
                f"[{issue['severity']}/{issue['confidence']}] "
                f"{issue['message']}"
            )
        if len(result["issues"]) > 10:
            print(f"    ... 还有 {len(result['issues']) - 10} 个问题")
    else:
        print(f"  OK {result['summary']}")


def _print_safety(result: dict) -> None:
    """打印 Safety 检查结果。"""
    print("[2/3] Safety 依赖检查...")
    if not result["success"]:
        print(f"  ! 执行失败: {result.get('error', '未知错误')}")
    elif result["has_issues"]:
        print(f"  ! {result['summary']}")
        for issue in result["issues"][:10]:
            cve = issue.get("cve") or "N/A"
            print(f"    - {issue['package']} {issue['installed']} (CVE: {cve})")
            if issue.get("advisory"):
                # 截取前 80 字符
                adv = issue["advisory"][:80]
                print(f"      {adv}...")
        if len(result["issues"]) > 10:
            print(f"    ... 还有 {len(result['issues']) - 10} 个漏洞")
    else:
        print(f"  OK {result['summary']}")


def _print_pip_audit(result: dict) -> None:
    """打印 pip-audit 审计结果。"""
    print("[3/3] pip-audit 包审计...")
    if not result["success"]:
        print(f"  ! 执行失败: {result.get('error', '未知错误')}")
    elif result["has_issues"]:
        print(f"  ! {result['summary']}")
        for issue in result["issues"][:10]:
            vuln_ids = ", ".join(v["id"] for v in issue["vulns"])
            fixes = []
            for v in issue["vulns"]:
                if v.get("fix_versions"):
                    fixes.extend(v["fix_versions"])
            fix_str = f" -> 升级到: {', '.join(fixes)}" if fixes else ""
            print(f"    - {issue['name']} {issue['version']} ({vuln_ids}){fix_str}")
        if len(result["issues"]) > 10:
            print(f"    ... 还有 {len(result['issues']) - 10} 个包")
    else:
        print(f"  OK {result['summary']}")


def _print_summary(report: dict) -> None:
    """打印总体摘要。"""
    print()
    print("=" * 50)
    status_map = {
        "clean": "ALL CLEAR - 未发现安全问题",
        "issues_found": "WARNING - 发现安全问题，请尽快处理",
        "partial_failure": "PARTIAL - 部分扫描工具执行失败",
    }
    print(f"  {status_map.get(report['status'], 'UNKNOWN')}")
    print("=" * 50)


def main() -> None:
    """主函数 —— 运行安全扫描并输出报告。"""
    _print_banner()

    scanner = SecurityScanner()
    report = scanner.generate_report()

    _print_bandit(report["bandit"])
    print()
    _print_safety(report["safety"])
    print()
    _print_pip_audit(report["pip_audit"])
    _print_summary(report)

    # 如果发现问题或工具执行失败，以非零退出码退出
    if report["status"] != "clean":
        sys.exit(1)


if __name__ == "__main__":
    main()
