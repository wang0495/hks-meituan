"""CityFlow 文档维护脚本。

命令行入口，提供文档生成、版本管理和搜索功能。

用法::

    # 生成所有文档
    python -m backend.tools.maintain_docs generate

    # 生成指定类型文档
    python -m backend.tools.maintain_docs generate --type api

    # 搜索文档
    python -m backend.tools.maintain_docs search 路线规划

    # 查看版本历史
    python -m backend.tools.maintain_docs versions

    # 创建新版本
    python -m backend.tools.maintain_docs version 1.2.0

    # 查看文档统计
    python -m backend.tools.maintain_docs stats
"""

from __future__ import annotations

import argparse
import sys

from backend.tools.doc_maintainer import DocMaintainer

# ---------------------------------------------------------------------------
# 输出格式化
# ---------------------------------------------------------------------------


def _print_separator(title: str) -> None:
    """打印分隔线标题。"""
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}\n")


def _print_success(message: str) -> None:
    """打印成功信息。"""
    print(f"  [OK] {message}")


def _print_info(message: str) -> None:
    """打印信息。"""
    print(f"  [INFO] {message}")


def _print_error(message: str) -> None:
    """打印错误信息。"""
    print(f"  [ERROR] {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 命令处理
# ---------------------------------------------------------------------------


def cmd_generate(maintainer: DocMaintainer, args: argparse.Namespace) -> int:
    """处理文档生成命令。

    Parameters
    ----------
    maintainer : DocMaintainer
        文档维护器实例。
    args : argparse.Namespace
        命令行参数。

    Returns
    -------
    int
        退出码，0 表示成功。
    """
    _print_separator("文档生成")

    doc_type = args.type

    try:
        if doc_type == "all":
            results = maintainer.generate_all_docs()
            for doc_type, path in results.items():
                _print_success(f"{doc_type} 文档已生成: {path}")
        elif doc_type == "api":
            content = maintainer.generate_api_doc()
            path = maintainer.save_doc("api_reference.md", content)
            _print_success(f"API 文档已生成: {path}")
        elif doc_type == "sdk":
            content = maintainer.generate_sdk_doc()
            path = maintainer.save_doc("sdk_reference.md", content)
            _print_success(f"SDK 文档已生成: {path}")
        elif doc_type == "guide":
            content = maintainer.generate_guide_doc()
            path = maintainer.save_doc("usage_guide.md", content)
            _print_success(f"使用指南已生成: {path}")
        else:
            _print_error(f"未知文档类型: {doc_type}")
            return 1
    except Exception as exc:
        _print_error(f"生成失败: {exc}")
        return 1

    return 0


def cmd_search(maintainer: DocMaintainer, args: argparse.Namespace) -> int:
    """处理文档搜索命令。

    Parameters
    ----------
    maintainer : DocMaintainer
        文档维护器实例。
    args : argparse.Namespace
        命令行参数。

    Returns
    -------
    int
        退出码，0 表示成功。
    """
    _print_separator(f"搜索: {args.keyword}")

    results = maintainer.search_docs(
        args.keyword,
        case_sensitive=args.case_sensitive,
        max_snippets=args.snippets,
    )

    if not results:
        _print_info("未找到匹配结果")
        return 0

    _print_info(f"找到 {len(results)} 个相关文档\n")

    for i, result in enumerate(results, 1):
        print(f"  {i}. {result.file}")
        print(f"     匹配次数: {result.matches}")

        if result.snippets and args.verbose:
            print("     匹配片段:")
            for snippet in result.snippets:
                for line in snippet.splitlines():
                    print(f"       {line}")
                print()

    return 0


def cmd_versions(maintainer: DocMaintainer, args: argparse.Namespace) -> int:
    """处理版本历史命令。

    Parameters
    ----------
    maintainer : DocMaintainer
        文档维护器实例。
    args : argparse.Namespace
        命令行参数。

    Returns
    -------
    int
        退出码，0 表示成功。
    """
    _print_separator("文档版本历史")

    versions = maintainer.get_version_history()

    if not versions:
        _print_info("暂无版本记录")
        return 0

    for i, version in enumerate(versions, 1):
        print(f"  {i}. {version.version}")
        print(f"     日期: {version.date}")
        if version.commit_hash:
            print(f"     提交: {version.commit_hash}")
        if version.files:
            print(f"     文件: {', '.join(version.files)}")
        print()

    return 0


def cmd_create_version(maintainer: DocMaintainer, args: argparse.Namespace) -> int:
    """处理创建版本命令。

    Parameters
    ----------
    maintainer : DocMaintainer
        文档维护器实例。
    args : argparse.Namespace
        命令行参数。

    Returns
    -------
    int
        退出码，0 表示成功。
    """
    _print_separator(f"创建版本: {args.version}")

    try:
        doc_version = maintainer.create_version(args.version)
        _print_success(f"版本 {doc_version.version} 已创建")
        _print_info(f"日期: {doc_version.date}")
        if doc_version.commit_hash:
            _print_info(f"提交: {doc_version.commit_hash}")
        if doc_version.files:
            _print_info(f"文件: {', '.join(doc_version.files)}")
    except Exception as exc:
        _print_error(f"创建版本失败: {exc}")
        return 1

    return 0


def cmd_stats(maintainer: DocMaintainer, args: argparse.Namespace) -> int:
    """处理文档统计命令。

    Parameters
    ----------
    maintainer : DocMaintainer
        文档维护器实例。
    args : argparse.Namespace
        命令行参数。

    Returns
    -------
    int
        退出码，0 表示成功。
    """
    _print_separator("文档统计")

    stats = maintainer.get_stats()

    print(f"  文件数量: {stats.total_files}")
    print(f"  总词数:   {stats.total_words}")
    print(f"  总行数:   {stats.total_lines}")
    print(f"  最后更新: {stats.last_updated or '无'}")
    print(f"  版本数量: {len(stats.versions)}")

    return 0


def cmd_diff(maintainer: DocMaintainer, args: argparse.Namespace) -> int:
    """处理版本差异命令。

    Parameters
    ----------
    maintainer : DocMaintainer
        文档维护器实例。
    args : argparse.Namespace
        命令行参数。

    Returns
    -------
    int
        退出码，0 表示成功。
    """
    _print_separator(f"版本差异: {args.from_version} -> {args.to_version}")

    result = maintainer.diff_versions(args.from_version, args.to_version)

    if result is None:
        _print_error("无法获取版本差异，请确认版本号正确且在 Git 仓库中")
        return 1

    if not result["changed_files"]:
        _print_info("两个版本之间没有文档变更")
        return 0

    _print_info(f"变更文件 ({len(result['changed_files'])}):\n")
    for file in result["changed_files"]:
        print(f"    - {file}")

    if args.verbose and result["diff"]:
        print("\n  差异详情:\n")
        print(result["diff"])

    return 0


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """主函数，返回退出码。

    Parameters
    ----------
    argv : list[str] | None
        命令行参数，为 None 时使用 sys.argv。

    Returns
    -------
    int
        退出码，0 表示成功。
    """
    parser = argparse.ArgumentParser(
        description="CityFlow 文档维护工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # 全局参数
    parser.add_argument(
        "--docs-dir",
        default="docs",
        help="文档目录 (默认: docs)",
    )
    parser.add_argument(
        "--source-dir",
        default="backend",
        help="源码目录 (默认: backend)",
    )
    parser.add_argument(
        "--project-name",
        default="CityFlow",
        help="项目名称 (默认: CityFlow)",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # generate 命令
    generate_parser = subparsers.add_parser(
        "generate",
        help="生成文档",
    )
    generate_parser.add_argument(
        "--type",
        choices=["api", "sdk", "guide", "all"],
        default="all",
        help="文档类型 (默认: all)",
    )

    # search 命令
    search_parser = subparsers.add_parser(
        "search",
        help="搜索文档",
    )
    search_parser.add_argument(
        "keyword",
        help="搜索关键词",
    )
    search_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="显示匹配片段",
    )
    search_parser.add_argument(
        "-c",
        "--case-sensitive",
        action="store_true",
        help="区分大小写",
    )
    search_parser.add_argument(
        "--snippets",
        type=int,
        default=3,
        help="每个文件最多显示的片段数 (默认: 3)",
    )

    # versions 命令
    subparsers.add_parser(
        "versions",
        help="查看版本历史",
    )

    # version 命令
    version_parser = subparsers.add_parser(
        "version",
        help="创建新版本",
    )
    version_parser.add_argument(
        "version",
        help="版本号",
    )

    # stats 命令
    subparsers.add_parser(
        "stats",
        help="查看文档统计",
    )

    # diff 命令
    diff_parser = subparsers.add_parser(
        "diff",
        help="比较版本差异",
    )
    diff_parser.add_argument(
        "from_version",
        help="起始版本",
    )
    diff_parser.add_argument(
        "to_version",
        help="结束版本",
    )
    diff_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="显示差异详情",
    )

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # 初始化维护器
    maintainer = DocMaintainer(
        docs_dir=args.docs_dir,
        source_dir=args.source_dir,
        project_name=args.project_name,
    )

    # 分发命令
    command_map = {
        "generate": cmd_generate,
        "search": cmd_search,
        "versions": cmd_versions,
        "version": cmd_create_version,
        "stats": cmd_stats,
        "diff": cmd_diff,
    }

    handler = command_map.get(args.command)
    if handler:
        return handler(maintainer, args)

    _print_error(f"未知命令: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
