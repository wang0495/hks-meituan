# backend/tools/run_integration.py

from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，支持直接运行
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.tools.integration_test import IntegrationTestRunner


def main() -> None:
    """主函数"""
    runner = IntegrationTestRunner()

    print("=== CityFlow 集成测试 ===\n")

    # 生成报告
    report = runner.generate_report()

    # 所有测试
    print("1. 运行所有测试...")
    if report["all_tests"]["success"]:
        print("   [PASS] 所有测试通过")
    else:
        print("   [FAIL] 测试失败:")
        print(str(report["all_tests"]["output"])[:500])

    # 集成测试
    print("\n2. 运行集成测试...")
    if report["integration"]["success"]:
        print("   [PASS] 集成测试通过")
    else:
        print("   [FAIL] 集成测试失败:")
        print(str(report["integration"]["output"])[:500])

    # API测试
    print("\n3. 运行API测试...")
    if report["api"]["success"]:
        print("   [PASS] API测试通过")
    else:
        print("   [FAIL] API测试失败:")
        print(str(report["api"]["output"])[:500])

    # 总体结果
    result_text = "通过" if report["overall"] else "失败"
    print(f"\n=== 总体结果: {result_text} ===")


if __name__ == "__main__":
    main()
