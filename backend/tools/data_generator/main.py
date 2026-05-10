#!/usr/bin/env python3
"""
CityFlow 数据生成工具 - CLI 入口

用法:
  # 干跑模式（只输出统计信息和示例提示，不调用 LLM）
  python -m backend.tools.data_generator.main --dry-run

  # 使用 Stub（测试数据，不连真实 LLM）
  python -m backend.tools.data_generator.main --task all --stub

  # 使用 OpenAI（需要设置 OPENAI_API_KEY）
  python -m backend.tools.data_generator.main --task all

  # 只生成某个任务
  python -m backend.tools.data_generator.main --task highlights
  python -m backend.tools.data_generator.main --task constraints
  python -m backend.tools.data_generator.main --task experiences
  python -m backend.tools.data_generator.main --task supplement

  # 自定义 provider
  python -m backend.tools.data_generator.main \\
    --task all \\
    --provider my_module.MyProvider \\
    --provider-args '{"key": "val"}'
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.tools.data_generator.pipeline import DataPipeline
from backend.tools.data_generator.providers import LLMProvider, StubProvider


def resolve_provider(provider_spec: str, args_json: str | None) -> LLMProvider:
    """解析 provider 参数，返回 LLMProvider 实例

    支持格式:
      - "stub"                    → StubProvider
      - "OpenAIProvider"          → 从 providers 模块导入
      - "my_module.MyProvider"    → 从自定义模块导入
    """
    if provider_spec == "stub":
        return StubProvider()

    # 尝试从 providers 模块导入
    if "." not in provider_spec:
        provider_spec = f"backend.tools.data_generator.providers.{provider_spec}"

    module_path, class_name = provider_spec.rsplit(".", 1)

    try:
        module = importlib.import_module(module_path)
        provider_cls = getattr(module, class_name)

        kwargs = {}
        if args_json:
            kwargs = json.loads(args_json)

        return provider_cls(**kwargs)

    except (ImportError, AttributeError) as e:
        print(f"❌ 无法加载 provider '{provider_spec}': {e}")
        print("   使用 --stub 或实现自己的 LLMProvider 子类。")
        sys.exit(1)


TASKS = {
    "highlights": "run_highlights",
    "constraints": "run_constraints",
    "experiences": "run_experiences",
    "supplement": "run_supplement",
}


def main():
    parser = argparse.ArgumentParser(
        description="CityFlow 数据生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m backend.tools.data_generator.main --dry-run
  python -m backend.tools.data_generator.main --task all --stub
  python -m backend.tools.data_generator.main --task highlights --stub
  python -m backend.tools.data_generator.main --task all
        """,
    )

    parser.add_argument(
        "--task",
        choices=list(TASKS.keys()) + ["all"],
        default="all",
        help="要执行的任务",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="使用 StubProvider（返回测试数据，不连真实 LLM）",
    )
    parser.add_argument(
        "--provider",
        default="OpenAIProvider",
        help="LLM Provider 类路径（默认: OpenAIProvider）",
    )
    parser.add_argument(
        "--provider-args",
        default=None,
        help="传给 Provider 构造函数的 JSON 参数，如 '{\"model\":\"gpt-4o\"}'",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干跑模式：只输出统计信息，不调用 LLM",
    )

    args = parser.parse_args()

    # ========== 初始化 Provider ==========
    if args.dry_run:
        print(f"{'='*60}")
        print("🏃 CityFlow 数据生成工具 - 干跑模式")
        print(f"{'='*60}")
        pipeline = DataPipeline(provider=StubProvider())
        pipeline.run_dry_run()
        return

    provider = StubProvider() if args.stub else resolve_provider(args.provider, args.provider_args)

    # ========== 打印配置信息 ==========
    print(f"{'='*60}")
    print("🏃 CityFlow 数据生成工具")
    print(f"{'='*60}")
    print(f"\n  Provider: {type(provider).__name__}")
    print(f"  任务:     {args.task}")
    print(f"  Stub:     {'是' if args.stub else '否'}")
    print()

    # ========== 执行 ==========
    pipeline = DataPipeline(provider=provider)

    task_results = {}
    if args.task == "all":
        task_results["highlights"] = pipeline.run_highlights()
        task_results["constraints"] = pipeline.run_constraints()
        task_results["experiences"] = pipeline.run_experiences()
        task_results["supplement"] = pipeline.run_supplement()
    else:
        method_name = TASKS[args.task]
        result = getattr(pipeline, method_name)()
        task_results[args.task] = result

    # ========== 汇总报告 ==========
    print(f"\n{'='*60}")
    print("📊 汇总报告")
    print(f"{'='*60}")

    all_ok = True
    for task_name, result in task_results.items():
        status = "✅" if result.fail_count == 0 else "⚠️"
        if result.fail_count > 0:
            all_ok = False
        print(f"\n  {status} {task_name}")
        print(f"     成功: {result.success_count}")
        print(f"     失败: {result.fail_count}")
        print(f"     输出: {result.output_path}")
        if result.errors:
            print(f"     错误:")
            for err in result.errors[:5]:
                print(f"       - {err}")
                if len(result.errors) > 5:
                    print(f"       ... 还有 {len(result.errors)-5} 条错误")
                    break

    if all_ok:
        print(f"\n  🎉 所有任务完成！")
    else:
        print(f"\n  ⚠️ 部分任务有错误，请检查上方日志。")


if __name__ == "__main__":
    main()
