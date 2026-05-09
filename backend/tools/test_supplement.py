"""CityFlow 测试补充器。

根据覆盖率分析结果，自动识别未测试的函数/方法，
并生成测试模板代码，辅助开发者快速补充测试。

使用方式::

    supplement = TestSupplement()
    untested = supplement.identify_untested_functions(coverage_data)
    for item in untested:
        print(supplement.generate_test_template(item["function"], item["module"]))
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TestSupplement", "UntestedFunction"]


@dataclass
class UntestedFunction:
    """未测试函数信息。"""

    name: str
    module: str
    file_path: str
    line_number: int
    is_async: bool = False
    is_method: bool = False
    class_name: str | None = None
    parameters: list[str] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        if self.class_name:
            return f"{self.class_name}.{self.name}"
        return self.name


class TestSupplement:
    """测试补充器。

    提供两大能力：
    1. 从覆盖率数据中识别未测试的函数
    2. 生成符合项目规范的测试模板
    """

    def __init__(
        self,
        source_root: str = "backend",
        test_root: str = "tests",
    ) -> None:
        self._source_root = Path(source_root)
        self._test_root = Path(test_root)

    # ------------------------------------------------------------------
    # 识别未测试函数
    # ------------------------------------------------------------------

    def identify_untested_functions(
        self,
        coverage_data: dict[str, Any],
    ) -> list[UntestedFunction]:
        """从覆盖率数据中识别未测试的函数。

        Args:
            coverage_data: pytest-cov 输出的 JSON 数据或文件覆盖率字典。

        Returns:
            未测试函数列表。
        """
        untested: list[UntestedFunction] = []

        files_data = coverage_data.get("files", coverage_data)

        for file_path, data in files_data.items():
            missing: list[int] = []
            if isinstance(data, dict):
                missing = data.get("missing_lines", [])
            elif hasattr(data, "missing_lines"):
                missing = data.missing_lines

            if not missing:
                continue

            # 尝试解析源文件，找出未覆盖行对应的函数
            try:
                funcs = self._parse_functions(file_path, set(missing))
                if funcs:
                    untested.extend(funcs)
                else:
                    # 文件无法解析或未找到函数定义，生成文件级占位
                    untested.append(
                        UntestedFunction(
                            name=Path(file_path).stem,
                            module=self._path_to_module(file_path),
                            file_path=file_path,
                            line_number=missing[0] if missing else 0,
                        )
                    )
            except (OSError, SyntaxError) as exc:
                logger.debug("跳过文件 %s: %s", file_path, exc)
                # 文件无法解析时，生成文件级别的占位
                untested.append(
                    UntestedFunction(
                        name=Path(file_path).stem,
                        module=self._path_to_module(file_path),
                        file_path=file_path,
                        line_number=missing[0] if missing else 0,
                    )
                )

        return untested

    # ------------------------------------------------------------------
    # 生成测试模板
    # ------------------------------------------------------------------

    def generate_test_template(
        self,
        function_name: str,
        module: str,
        *,
        is_async: bool = False,
        class_name: str | None = None,
    ) -> str:
        """生成测试模板代码。

        Args:
            function_name: 函数名。
            module: 模块导入路径。
            is_async: 是否为异步函数。
            class_name: 所属类名（方法时提供）。

        Returns:
            完整的测试代码字符串。
        """
        import_line = f"from {module} import {function_name}"
        if class_name:
            import_line = f"from {module} import {class_name}"

        qual_name = f"{class_name}.{function_name}" if class_name else function_name
        prefix = (
            f"test_{class_name}_{function_name}"
            if class_name
            else f"test_{function_name}"
        )
        await_kw = "await " if is_async else ""
        async_kw = "async " if is_async else ""
        marker = "@pytest.mark.asyncio\n" if is_async else ""

        return f'''"""{qual_name} 的测试。"""

from __future__ import annotations

import pytest
{import_line}


{marker}{async_kw}def {prefix}_basic() -> None:
    """测试 {qual_name} 基本功能。"""
    # TODO: 准备测试数据
    # result = {await_kw}{qual_name}()
    # assert result is not None
    pass


{marker}{async_kw}def {prefix}_edge_cases() -> None:
    """测试 {qual_name} 边界情况。"""
    # TODO: 测试边界值、空输入等
    pass


{marker}{async_kw}def {prefix}_error_handling() -> None:
    """测试 {qual_name} 错误处理。"""
    # TODO: 测试异常场景
    # with pytest.raises(SomeException):
    #     {await_kw}{qual_name}(invalid_input)
    pass
'''

    def generate_test_file(
        self,
        untested_funcs: list[UntestedFunction],
    ) -> str:
        """为一批未测试函数生成完整的测试文件。

        Args:
            untested_funcs: 同一模块的未测试函数列表。

        Returns:
            完整的测试文件内容。
        """
        if not untested_funcs:
            return ""

        # 按模块分组
        modules: dict[str, list[UntestedFunction]] = {}
        for func in untested_funcs:
            modules.setdefault(func.module, []).append(func)

        parts: list[str] = []
        parts.append('"""自动生成的测试文件。"""')
        parts.append("")
        parts.append("from __future__ import annotations")
        parts.append("")
        parts.append("import pytest")
        parts.append("")

        # 生成导入
        imports: set[str] = set()
        for func in untested_funcs:
            if func.class_name:
                imports.add(f"from {func.module} import {func.class_name}")
            else:
                imports.add(f"from {func.module} import {func.name}")

        parts.extend(sorted(imports))
        parts.append("")
        parts.append("")

        # 生成测试函数
        for func in untested_funcs:
            template = self.generate_test_template(
                func.name,
                func.module,
                is_async=func.is_async,
                class_name=func.class_name,
            )
            # 去掉模板的 import 行（已在文件头统一导入）
            lines = template.split("\n")
            body_lines = [
                line
                for line in lines
                if not line.startswith("from ")
                and not line.startswith("import ")
                and not line.startswith('"""')
                and line.strip() != ""
            ]
            parts.extend(body_lines)
            parts.append("")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 源码解析
    # ------------------------------------------------------------------

    def _parse_functions(
        self,
        file_path: str,
        missing_lines: set[int],
    ) -> list[UntestedFunction]:
        """解析源文件，找出定义在未覆盖行范围内的函数。"""
        path = Path(file_path)
        if not path.exists():
            # 尝试相对于 source_root
            path = self._source_root / file_path
        if not path.exists():
            return []

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=file_path)

        functions: list[UntestedFunction] = []
        module = self._path_to_module(file_path)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_end = getattr(node, "end_lineno", node.lineno + 10)
                # 函数体中是否全部未覆盖？
                func_lines = set(range(node.lineno, func_end + 1))
                if func_lines & missing_lines:
                    # 提取参数名
                    params = [arg.arg for arg in node.args.args if arg.arg != "self"]

                    # 检查是否是方法
                    class_name = None
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.ClassDef):
                            if node in ast.walk(parent):
                                class_name = parent.name
                                break

                    functions.append(
                        UntestedFunction(
                            name=node.name,
                            module=module,
                            file_path=file_path,
                            line_number=node.lineno,
                            is_async=isinstance(node, ast.AsyncFunctionDef),
                            is_method=class_name is not None,
                            class_name=class_name,
                            parameters=params,
                        )
                    )

        return functions

    def _path_to_module(self, file_path: str) -> str:
        """将文件路径转换为 Python 模块导入路径。"""
        path = Path(file_path)
        # 移除 .py 后缀
        parts = path.with_suffix("").parts
        # 将路径分隔符替换为点号
        return ".".join(parts)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_coverage_gaps(
        self,
        coverage_data: dict[str, Any],
    ) -> dict[str, Any]:
        """获取覆盖率缺口摘要。

        Returns:
            ``{"total_untested": int, "by_module": {...}, "priority_files": [...]}``
        """
        untested = self.identify_untested_functions(coverage_data)

        by_module: dict[str, int] = {}
        for func in untested:
            by_module[func.module] = by_module.get(func.module, 0) + 1

        # 按未测试函数数量排序
        priority = sorted(by_module.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_untested": len(untested),
            "by_module": by_module,
            "priority_files": [
                {"module": mod, "untested_count": count} for mod, count in priority[:10]
            ],
        }
