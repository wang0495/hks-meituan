"""CityFlow 依赖检查脚本。

在终端运行完整的依赖健康检查，包括：
    1. 过时依赖检查
    2. 安全漏洞扫描
    3. 依赖统计与更新建议

用法：
    python -m backend.tools.check_dependencies
    # 或
    python backend/tools/check_dependencies.py
"""

from __future__ import annotations

from backend.tools.dependency_checker import CheckResult, DependencyChecker

# ---------------------------------------------------------------------------
# 输出格式化
# ---------------------------------------------------------------------------


def _print_outdated(result: CheckResult) -> None:
    """打印过时依赖检查结果。"""
    if not result.success:
        print(f"   [FAIL] 检查失败: {result.message}")
        return

    if not result.data:
        print("   [OK] 所有依赖都是最新版本")
        return

    print(f"   发现 {len(result.data)} 个过时依赖:")
    for pkg in result.data[:10]:
        name = pkg.get("name", "?")
        ver = pkg.get("version", "?")
        latest = pkg.get("latest_version", "?")
        print(f"     - {name}: {ver} -> {latest}")

    if len(result.data) > 10:
        print(f"     ... 还有 {len(result.data) - 10} 个")


def _print_security(result: CheckResult) -> None:
    """打印安全漏洞检查结果。"""
    if not result.success:
        print(f"   [WARN] 检查工具不可用: {result.message}")
        return

    if not result.data:
        print("   [OK] 未发现安全漏洞")
        return

    print(f"   [ALERT] 发现 {len(result.data)} 个安全漏洞:")
    for vuln in result.data[:5]:
        name = vuln.get("name", vuln.get("package", "?"))
        vuln_id = vuln.get("vuln_id", vuln.get("id", "?"))
        ver = vuln.get("version", "?")
        print(f"     - {name} ({ver}): {vuln_id}")

    if len(result.data) > 5:
        print(f"     ... 还有 {len(result.data) - 5} 个")


def _print_tree(result: CheckResult) -> None:
    """打印依赖统计。"""
    if not result.success:
        print(f"   [FAIL] 获取失败: {result.message}")
        return

    print(f"   {result.message}")


def _print_recommendations(result: CheckResult) -> None:
    """打印更新建议。"""
    if not result.success:
        print(f"   [FAIL] 生成失败: {result.message}")
        return

    if not result.data:
        print("   [OK] 无需更新")
        return

    recs = result.data[0]  # get_update_recommendations 返回单元素列表
    for level, label in [
        ("patch", "补丁更新 (安全)"),
        ("minor", "次版本更新"),
        ("major", "主版本更新 (可能有破坏性变更)"),
    ]:
        pkgs = recs.get(level, [])
        if not pkgs:
            continue
        print(f"\n   {label} ({len(pkgs)} 个):")
        for pkg in pkgs[:5]:
            name = pkg.get("name", "?")
            ver = pkg.get("version", "?")
            latest = pkg.get("latest_version", "?")
            print(f"     - {name}: {ver} -> {latest}")
        if len(pkgs) > 5:
            print(f"     ... 还有 {len(pkgs) - 5} 个")


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------


def main() -> None:
    """运行依赖检查。"""
    checker = DependencyChecker()

    print("=" * 50)
    print("  CityFlow 依赖检查")
    print("=" * 50)

    # 1. 过时依赖检查
    print("\n[1/4] 检查过时依赖...")
    _print_outdated(checker.check_outdated())

    # 2. 安全漏洞扫描
    print("\n[2/4] 安全漏洞扫描...")
    _print_security(checker.check_security())

    # 3. 依赖统计
    print("\n[3/4] 依赖统计...")
    _print_tree(checker.get_dependency_tree())

    # 4. 更新建议
    print("\n[4/4] 更新建议...")
    _print_recommendations(checker.get_update_recommendations())

    print("\n" + "=" * 50)
    print("  检查完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
