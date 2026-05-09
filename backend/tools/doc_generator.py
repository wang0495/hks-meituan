"""CityFlow 文档自动生成工具。

从 Python 源码中提取 API 文档、SDK 文档和使用指南。
支持解析 FastAPI 路由、Pydantic 模型、服务类等模块，
自动生成结构化的 Markdown 文档。

Features:
    - 基于 AST 解析，无需运行代码即可提取文档
    - 支持函数、类、方法的 docstring 提取
    - 自动生成参数表格和返回值说明
    - 支持 FastAPI 路由端点的 HTTP 方法和路径识别
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from backend.tools.markdown_generator import MarkdownGenerator

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


class DocType(Enum):
    """文档类型枚举。"""

    API = "api"
    SDK = "sdk"
    GUIDE = "guide"


@dataclass
class ParamInfo:
    """函数参数信息。"""

    name: str
    annotation: str = ""
    default: str = ""
    description: str = ""


@dataclass
class ReturnInfo:
    """函数返回值信息。"""

    annotation: str = ""
    description: str = ""


@dataclass
class FunctionDoc:
    """函数/方法文档信息。"""

    name: str
    docstring: str = ""
    params: list[ParamInfo] = field(default_factory=list)
    returns: ReturnInfo = field(default_factory=ReturnInfo)
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False
    lineno: int = 0


@dataclass
class ClassDoc:
    """类文档信息。"""

    name: str
    docstring: str = ""
    methods: list[FunctionDoc] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)
    lineno: int = 0


@dataclass
class ModuleDoc:
    """模块文档信息。"""

    name: str
    file_path: str
    docstring: str = ""
    functions: list[FunctionDoc] = field(default_factory=list)
    classes: list[ClassDoc] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


@dataclass
class RouteInfo:
    """FastAPI 路由信息。"""

    method: str
    path: str
    function_name: str
    summary: str = ""
    description: str = ""
    params: list[ParamInfo] = field(default_factory=list)
    returns: ReturnInfo = field(default_factory=ReturnInfo)
    tags: list[str] = field(default_factory=list)
    is_async: bool = False


# ---------------------------------------------------------------------------
# AST 解析器
# ---------------------------------------------------------------------------


class _AstParser:
    """AST 解析辅助类，从 Python 源码中提取文档信息。"""

    @staticmethod
    def parse_annotation(node: ast.expr | None) -> str:
        """将 AST 类型注解节点转换为可读字符串。

        Parameters
        ----------
        node : ast.expr | None
            AST 类型注解节点。

        Returns
        -------
        str
            可读的类型注解字符串。
        """
        if node is None:
            return ""

        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.Attribute):
            value = _AstParser.parse_annotation(node.value)
            return f"{value}.{node.attr}"
        if isinstance(node, ast.Subscript):
            base = _AstParser.parse_annotation(node.value)
            slice_val = _AstParser.parse_annotation(node.slice)
            return f"{base}[{slice_val}]"
        if isinstance(node, ast.Tuple):
            elts = [_AstParser.parse_annotation(e) for e in node.elts]
            return ", ".join(elts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left = _AstParser.parse_annotation(node.left)
            right = _AstParser.parse_annotation(node.right)
            return f"{left} | {right}"
        if isinstance(node, ast.Constant):
            return repr(node.value)

        return ast.dump(node)

    @staticmethod
    def parse_default(node: ast.expr | None) -> str:
        """将 AST 默认值节点转换为可读字符串。

        Parameters
        ----------
        node : ast.expr | None
            AST 默认值节点。

        Returns
        -------
        str
            可读的默认值字符串。
        """
        if node is None:
            return ""
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            value = _AstParser.parse_default(node.value)
            return f"{value}.{node.attr}"
        if isinstance(node, ast.Call):
            func = _AstParser.parse_default(node.func)
            return f"{func}(...)"
        return "..."

    @staticmethod
    def extract_params(
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[ParamInfo]:
        """从函数定义中提取参数信息。

        Parameters
        ----------
        func_node : ast.FunctionDef | ast.AsyncFunctionDef
            函数定义节点。

        Returns
        -------
        list[ParamInfo]
            参数信息列表。
        """
        params: list[ParamInfo] = []
        args = func_node.args

        # 计算默认值偏移量
        num_defaults = len(args.defaults)
        num_args = len(args.args)
        default_offset = num_args - num_defaults

        for i, arg in enumerate(args.args):
            if arg.arg == "self" or arg.arg == "cls":
                continue

            annotation = _AstParser.parse_annotation(arg.annotation)
            default = ""
            if i >= default_offset:
                default = _AstParser.parse_default(args.defaults[i - default_offset])

            params.append(
                ParamInfo(
                    name=arg.arg,
                    annotation=annotation,
                    default=default,
                )
            )

        return params

    @staticmethod
    def extract_return(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> ReturnInfo:
        """从函数定义中提取返回值信息。

        Parameters
        ----------
        func_node : ast.FunctionDef | ast.AsyncFunctionDef
            函数定义节点。

        Returns
        -------
        ReturnInfo
            返回值信息。
        """
        annotation = _AstParser.parse_annotation(func_node.returns)
        return ReturnInfo(annotation=annotation)

    @staticmethod
    def extract_decorators(
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> list[str]:
        """提取装饰器名称列表。

        Parameters
        ----------
        node : ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            AST 节点。

        Returns
        -------
        list[str]
            装饰器名称列表。
        """
        decorators: list[str] = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(_AstParser.parse_annotation(dec))
            elif isinstance(dec, ast.Call):
                decorators.append(_AstParser.parse_annotation(dec.func))
        return decorators

    @staticmethod
    def extract_route_info(decorators: list[str]) -> tuple[str, str] | None:
        """从装饰器中提取 FastAPI 路由信息。

        Parameters
        ----------
        decorators : list[str]
            装饰器名称列表。

        Returns
        -------
        tuple[str, str] | None
            (HTTP方法, 路径) 元组，未找到返回 None。
        """
        route_methods = {"get", "post", "put", "delete", "patch", "head", "options"}
        for dec in decorators:
            parts = dec.split(".")
            for part in parts:
                if part.lower() in route_methods:
                    return part.lower(), dec
        return None


# ---------------------------------------------------------------------------
# 文档生成器
# ---------------------------------------------------------------------------


class DocGenerator:
    """文档生成器。

    从 Python 源码目录中提取文档信息，生成 API 文档、SDK 文档和使用指南。

    Parameters
    ----------
    source_dir : str
        源码目录路径，默认 ``"backend"``。
    project_name : str
        项目名称，默认 ``"CityFlow"``。
    """

    def __init__(
        self,
        source_dir: str = "backend",
        project_name: str = "CityFlow",
    ) -> None:
        self._source_dir = Path(source_dir)
        self._project_name = project_name
        self._md = MarkdownGenerator()
        self._modules: list[ModuleDoc] = []
        self._routes: list[RouteInfo] = []

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def parse(self) -> None:
        """解析源码目录，提取所有文档信息。

        遍历源码目录中的所有 Python 文件，提取模块、类、函数的文档信息，
        以及 FastAPI 路由端点信息。
        """
        self._modules.clear()
        self._routes.clear()

        for py_file in self._source_dir.rglob("*.py"):
            if py_file.name == "__pycache__":
                continue
            if "_pycache_" in str(py_file):
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            module_doc = self._parse_module(tree, py_file)
            self._modules.append(module_doc)
            self._extract_routes(tree, py_file)

    def _parse_module(self, tree: ast.Module, file_path: Path) -> ModuleDoc:
        """解析单个模块。

        Parameters
        ----------
        tree : ast.Module
            模块 AST 树。
        file_path : Path
            文件路径。

        Returns
        -------
        ModuleDoc
            模块文档信息。
        """
        # 计算模块名称
        try:
            relative = file_path.relative_to(self._source_dir.parent)
            module_name = (
                str(relative.with_suffix("")).replace("/", ".").replace("\\", ".")
            )
        except ValueError:
            module_name = file_path.stem

        module_doc = ModuleDoc(
            name=module_name,
            file_path=str(file_path),
            docstring=ast.get_docstring(tree) or "",
        )

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                func_doc = self._parse_function(node)
                module_doc.functions.append(func_doc)
            elif isinstance(node, ast.ClassDef):
                class_doc = self._parse_class(node)
                module_doc.classes.append(class_doc)

        return module_doc

    def _parse_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> FunctionDoc:
        """解析函数/方法定义。

        Parameters
        ----------
        node : ast.FunctionDef | ast.AsyncFunctionDef
            函数定义节点。

        Returns
        -------
        FunctionDoc
            函数文档信息。
        """
        return FunctionDoc(
            name=node.name,
            docstring=ast.get_docstring(node) or "",
            params=_AstParser.extract_params(node),
            returns=_AstParser.extract_return(node),
            decorators=_AstParser.extract_decorators(node),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            lineno=node.lineno,
        )

    def _parse_class(self, node: ast.ClassDef) -> ClassDoc:
        """解析类定义。

        Parameters
        ----------
        node : ast.ClassDef
            类定义节点。

        Returns
        -------
        ClassDoc
            类文档信息。
        """
        base_classes = [_AstParser.parse_annotation(base) for base in node.bases]
        methods: list[FunctionDoc] = []

        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                methods.append(self._parse_function(child))

        return ClassDoc(
            name=node.name,
            docstring=ast.get_docstring(node) or "",
            methods=methods,
            base_classes=base_classes,
            lineno=node.lineno,
        )

    def _extract_routes(self, tree: ast.Module, file_path: Path) -> None:
        """从模块中提取 FastAPI 路由信息。

        Parameters
        ----------
        tree : ast.Module
            模块 AST 树。
        file_path : Path
            文件路径。
        """
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue

            decorators = _AstParser.extract_decorators(node)
            route_info = _AstParser.extract_route_info(decorators)
            if route_info is None:
                continue

            method, _ = route_info

            # 尝试从装饰器调用中提取路径和参数
            path = ""
            summary = ""
            tags: list[str] = []

            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if dec.func.attr.lower() in {
                        "get",
                        "post",
                        "put",
                        "delete",
                        "patch",
                    }:
                        # 提取路径参数
                        if dec.args and isinstance(dec.args[0], ast.Constant):
                            path = dec.args[0].value
                        # 提取关键字参数
                        for kw in dec.keywords:
                            if kw.arg == "summary" and isinstance(
                                kw.value, ast.Constant
                            ):
                                summary = kw.value.value
                            elif kw.arg == "tags" and isinstance(kw.value, ast.List):
                                tags = [
                                    elt.value
                                    for elt in kw.value.elts
                                    if isinstance(elt, ast.Constant)
                                ]

            route = RouteInfo(
                method=method.upper(),
                path=path,
                function_name=node.name,
                summary=summary,
                description=ast.get_docstring(node) or "",
                params=_AstParser.extract_params(node),
                returns=_AstParser.extract_return(node),
                tags=tags,
                is_async=isinstance(node, ast.AsyncFunctionDef),
            )
            self._routes.append(route)

    # ------------------------------------------------------------------
    # 文档生成
    # ------------------------------------------------------------------

    def generate_api_docs(self) -> dict[str, Any]:
        """生成 API 文档数据结构。

        Returns
        -------
        dict[str, Any]
            包含模块、路由、统计信息的文档数据。
        """
        if not self._modules:
            self.parse()

        modules_data: list[dict[str, Any]] = []
        for mod in self._modules:
            mod_dict: dict[str, Any] = {
                "name": mod.name,
                "file": mod.file_path,
                "docstring": mod.docstring,
                "functions": [],
                "classes": [],
            }

            for func in mod.functions:
                mod_dict["functions"].append(
                    {
                        "name": func.name,
                        "docstring": func.docstring,
                        "params": [
                            {"name": p.name, "type": p.annotation, "default": p.default}
                            for p in func.params
                        ],
                        "returns": func.returns.annotation,
                        "is_async": func.is_async,
                    }
                )

            for cls in mod.classes:
                cls_dict: dict[str, Any] = {
                    "name": cls.name,
                    "docstring": cls.docstring,
                    "base_classes": cls.base_classes,
                    "methods": [],
                }
                for method in cls.methods:
                    cls_dict["methods"].append(
                        {
                            "name": method.name,
                            "docstring": method.docstring,
                            "params": [
                                {
                                    "name": p.name,
                                    "type": p.annotation,
                                    "default": p.default,
                                }
                                for p in method.params
                            ],
                            "returns": method.returns.annotation,
                            "is_async": method.is_async,
                        }
                    )
                mod_dict["classes"].append(cls_dict)

            modules_data.append(mod_dict)

        routes_data: list[dict[str, Any]] = []
        for route in self._routes:
            routes_data.append(
                {
                    "method": route.method,
                    "path": route.path,
                    "function": route.function_name,
                    "summary": route.summary,
                    "description": route.description,
                    "params": [
                        {"name": p.name, "type": p.annotation, "default": p.default}
                        for p in route.params
                    ],
                    "returns": route.returns.annotation,
                    "tags": route.tags,
                }
            )

        return {
            "project": self._project_name,
            "modules": modules_data,
            "routes": routes_data,
            "stats": {
                "total_modules": len(modules_data),
                "total_functions": sum(len(m["functions"]) for m in modules_data),
                "total_classes": sum(len(m["classes"]) for m in modules_data),
                "total_routes": len(routes_data),
            },
        }

    def generate_api_docs_markdown(self) -> str:
        """生成 API 文档的 Markdown 格式。

        Returns
        -------
        str
            API 文档 Markdown 内容。
        """
        data = self.generate_api_docs()
        stats = data["stats"]

        lines: list[str] = []
        lines.append(f"# {self._project_name} API 文档\n")
        lines.append("**自动生成于源码解析**\n")
        lines.append("## 概览\n")
        lines.append(
            self._md.generate_table(
                headers=["指标", "数量"],
                rows=[
                    ["模块数", str(stats["total_modules"])],
                    ["函数数", str(stats["total_functions"])],
                    ["类数", str(stats["total_classes"])],
                    ["API 路由数", str(stats["total_routes"])],
                ],
            )
        )
        lines.append("")

        # 路由文档
        if data["routes"]:
            lines.append("## API 路由\n")
            lines.append(
                self._md.generate_table(
                    headers=["方法", "路径", "函数", "说明"],
                    rows=[
                        [r["method"], r["path"], r["function"], r["summary"]]
                        for r in data["routes"]
                    ],
                )
            )
            lines.append("")

            for route in data["routes"]:
                lines.append(f"### {route['method']} {route['path']}\n")
                if route["summary"]:
                    lines.append(f"**{route['summary']}**\n")
                if route["description"]:
                    lines.append(f"{route['description']}\n")
                if route["params"]:
                    lines.append("**参数:**\n")
                    lines.append(
                        self._md.generate_table(
                            headers=["参数名", "类型", "默认值"],
                            rows=[
                                [p["name"], p["type"] or "-", p["default"] or "-"]
                                for p in route["params"]
                            ],
                        )
                    )
                    lines.append("")
                if route["returns"]:
                    lines.append(f"**返回值**: `{route['returns']}`\n")
                lines.append("---\n")

        # 模块文档
        if data["modules"]:
            lines.append("## 模块详情\n")
            for mod in data["modules"]:
                lines.append(f"### {mod['name']}\n")
                if mod["docstring"]:
                    lines.append(f"{mod['docstring']}\n")

                if mod["classes"]:
                    for cls in mod["classes"]:
                        lines.append(f"#### class `{cls['name']}`\n")
                        if cls["base_classes"]:
                            lines.append(
                                f"**继承**: {', '.join(f'`{b}`' for b in cls['base_classes'])}\n"
                            )
                        if cls["docstring"]:
                            lines.append(f"{cls['docstring']}\n")
                        if cls["methods"]:
                            lines.append(
                                self._md.generate_table(
                                    headers=["方法", "参数", "返回值"],
                                    rows=[
                                        [
                                            method["name"],
                                            ", ".join(
                                                p["name"] for p in method["params"]
                                            )
                                            or "-",
                                            method["returns"] or "-",
                                        ]
                                        for method in cls["methods"]
                                    ],
                                )
                            )
                            lines.append("")

                if mod["functions"]:
                    lines.append("#### 函数\n")
                    lines.append(
                        self._md.generate_table(
                            headers=["函数", "参数", "返回值", "异步"],
                            rows=[
                                [
                                    func["name"],
                                    ", ".join(p["name"] for p in func["params"]) or "-",
                                    func["returns"] or "-",
                                    "是" if func["is_async"] else "否",
                                ]
                                for func in mod["functions"]
                            ],
                        )
                    )
                    lines.append("")

                lines.append("---\n")

        return "\n".join(lines)

    def generate_sdk_docs(self) -> str:
        """生成 SDK 文档的 Markdown 格式。

        SDK 文档面向开发者使用 CityFlow 的服务类和工具，
        侧重于类和方法的使用说明。

        Returns
        -------
        str
            SDK 文档 Markdown 内容。
        """
        if not self._modules:
            self.parse()

        lines: list[str] = []
        lines.append(f"# {self._project_name} SDK 文档\n")
        lines.append("本文档自动生成，涵盖所有可公开使用的服务类、工具类和辅助函数。\n")

        # 目录
        toc_entries: list[dict[str, Any]] = []
        for mod in self._modules:
            if mod.classes or mod.functions:
                toc_entries.append({"level": 2, "title": mod.name})

        if toc_entries:
            lines.append("## 目录\n")
            lines.append(self._md.generate_toc(toc_entries))
            lines.append("")

        # 按模块组织
        for mod in self._modules:
            if not mod.classes and not mod.functions:
                continue

            lines.append(f"## {mod.name}\n")
            lines.append(f"**文件**: `{mod.file_path}`\n")
            if mod.docstring:
                lines.append(f"{mod.docstring}\n")

            # 类文档
            for cls in mod.classes:
                lines.append(f"### class `{cls.name}`\n")
                if cls.base_classes:
                    lines.append(
                        f"**继承**: {', '.join(f'`{b}`' for b in cls.base_classes)}\n"
                    )
                if cls.docstring:
                    lines.append(f"{cls.docstring}\n")

                for method in cls.methods:
                    if method.name.startswith("_") and method.name != "__init__":
                        continue

                    prefix = "async " if method.is_async else ""
                    param_str = ", ".join(self._format_param(p) for p in method.params)
                    lines.append(
                        f"#### `{prefix}{cls.name}.{method.name}({param_str})`\n"
                    )
                    if method.docstring:
                        lines.append(f"{method.docstring}\n")
                    if method.returns.annotation:
                        lines.append(f"**Returns**: `{method.returns.annotation}`\n")
                    lines.append("")

            # 函数文档
            for func in mod.functions:
                if func.name.startswith("_"):
                    continue

                prefix = "async " if func.is_async else ""
                param_str = ", ".join(self._format_param(p) for p in func.params)
                lines.append(f"### `{prefix}{func.name}({param_str})`\n")
                if func.docstring:
                    lines.append(f"{func.docstring}\n")
                if func.params:
                    lines.append(
                        self._md.generate_table(
                            headers=["参数", "类型", "默认值", "说明"],
                            rows=[
                                [
                                    p.name,
                                    p.annotation or "-",
                                    p.default or "-",
                                    p.description or "-",
                                ]
                                for p in func.params
                            ],
                        )
                    )
                    lines.append("")
                if func.returns.annotation:
                    lines.append(f"**Returns**: `{func.returns.annotation}`\n")
                lines.append("---\n")

        return "\n".join(lines)

    def generate_usage_guide(self) -> str:
        """生成使用指南的 Markdown 格式。

        使用指南面向最终用户和新开发者，包含快速开始、
        常见用例和最佳实践。

        Returns
        -------
        str
            使用指南 Markdown 内容。
        """
        if not self._modules:
            self.parse()

        data = self.generate_api_docs()
        stats = data["stats"]

        lines: list[str] = []
        lines.append(f"# {self._project_name} 使用指南\n")

        # 快速开始
        lines.append("## 快速开始\n")
        lines.append("### 环境要求\n")
        lines.append("- Python 3.12+")
        lines.append("- 依赖包见 `requirements.txt`\n")

        lines.append("### 安装\n")
        lines.append(
            self._md.generate_code_block(
                "# 克隆项目\n"
                "git clone <repo-url>\n"
                "cd cityflow\n\n"
                "# 安装依赖\n"
                "pip install -r requirements.txt\n\n"
                "# 配置环境变量\n"
                "cp .env.example .env",
                language="bash",
            )
        )
        lines.append("")

        lines.append("### 启动服务\n")
        lines.append(
            self._md.generate_code_block(
                "# 开发模式\n"
                "python -m backend.main\n\n"
                "# 或使用 uvicorn\n"
                "uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000",
                language="bash",
            )
        )
        lines.append("")

        # API 概览
        lines.append("## API 概览\n")
        lines.append(f"项目包含 **{stats['total_routes']}** 个 API 端点，")
        lines.append(f"分布在 **{stats['total_modules']}** 个模块中。\n")

        if data["routes"]:
            lines.append("### 主要接口\n")
            lines.append(
                self._md.generate_table(
                    headers=["方法", "路径", "说明"],
                    rows=[
                        [r["method"], r["path"], r["summary"]] for r in data["routes"]
                    ],
                )
            )
            lines.append("")

        # 使用示例
        lines.append("## 使用示例\n")

        # 查找 plan 相关路由
        plan_routes = [r for r in self._routes if "plan" in r.function_name.lower()]
        if plan_routes:
            route = plan_routes[0]
            lines.append("### 路线规划\n")
            lines.append(f"使用 `{route.function_name}` 接口进行路线规划：\n")
            lines.append(
                self._md.generate_code_block(
                    "import httpx\n\n"
                    "async def plan_route():\n"
                    "    async with httpx.AsyncClient() as client:\n"
                    "        response = await client.post(\n"
                    '            "http://localhost:8000/api/v1/plan",\n'
                    "            json={\n"
                    '                "user_input": "周末想一个人安静走走"\n'
                    "            },\n"
                    "        )\n"
                    "        result = response.json()\n"
                    "        print(result)",
                    language="python",
                )
            )
            lines.append("")

        # 查找 POI 相关路由
        poi_routes = [r for r in self._routes if "poi" in r.function_name.lower()]
        if poi_routes:
            route = poi_routes[0]
            lines.append("### POI 查询\n")
            lines.append(f"使用 `{route.function_name}` 接口查询兴趣点：\n")
            lines.append(
                self._md.generate_code_block(
                    "import httpx\n\n"
                    "async def search_pois():\n"
                    "    async with httpx.AsyncClient() as client:\n"
                    "        response = await client.get(\n"
                    '            "http://localhost:8000/api/poi/search",\n'
                    "            params={\n"
                    '                "region": "珠海",\n'
                    '                "categories": ["文化", "美食"],\n'
                    "            },\n"
                    "        )\n"
                    "        pois = response.json()\n"
                    "        for poi in pois:\n"
                    "            print(f\"{poi['name']} - {poi['category']}\")",
                    language="python",
                )
            )
            lines.append("")

        # 项目结构
        lines.append("## 项目结构\n")
        lines.append(
            self._md.generate_code_block(
                "backend/\n"
                "├── main.py          # 应用入口\n"
                "├── config.py        # 配置管理\n"
                "├── errors.py        # 异常体系\n"
                "├── docs.py          # OpenAPI 文档\n"
                "├── routers/         # API 路由\n"
                "│   ├── v1/          # API v1\n"
                "│   └── v2/          # API v2\n"
                "├── services/        # 业务服务\n"
                "├── models/          # 数据模型\n"
                "├── middleware/      # 中间件\n"
                "├── database/        # 数据库\n"
                "├── tools/           # 开发工具\n"
                "└── utils/           # 工具函数",
            )
        )
        lines.append("")

        # 最佳实践
        lines.append("## 最佳实践\n")
        lines.append(
            "1. **错误处理**: 使用 `CityFlowException` 及其子类，统一错误码体系"
        )
        lines.append("2. **类型注解**: 所有函数必须有完整的类型注解")
        lines.append("3. **异步优先**: I/O 操作使用 `async/await`")
        lines.append("4. **日志记录**: 使用 `logging` 模块，关键操作记录日志")
        lines.append("5. **配置管理**: 敏感信息通过环境变量配置，不硬编码\n")

        # 故障排查
        lines.append("## 故障排查\n")
        lines.append(
            self._md.generate_table(
                headers=["问题", "可能原因", "解决方案"],
                rows=[
                    ["服务启动失败", "端口被占用", "修改 .env 中的 PORT 配置"],
                    ["数据库连接失败", "数据库未启动", "检查数据库服务状态"],
                    ["API 返回 500", "内部服务异常", "查看日志文件定位错误"],
                    ["API 返回 429", "请求频率超限", "降低请求频率或联系管理员"],
                ],
            )
        )
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 文件保存
    # ------------------------------------------------------------------

    def save_docs(self, output_dir: str = "docs") -> dict[str, Path]:
        """生成并保存所有文档文件。

        Parameters
        ----------
        output_dir : str
            输出目录，默认 ``"docs"``。

        Returns
        -------
        dict[str, Path]
            键为文档类型，值为保存路径。
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results: dict[str, Path] = {}

        # API 文档
        api_content = self.generate_api_docs_markdown()
        api_file = output_path / "api_reference.md"
        api_file.write_text(api_content, encoding="utf-8")
        results["api"] = api_file.resolve()

        # SDK 文档
        sdk_content = self.generate_sdk_docs()
        sdk_file = output_path / "sdk_reference.md"
        sdk_file.write_text(sdk_content, encoding="utf-8")
        results["sdk"] = sdk_file.resolve()

        # 使用指南
        guide_content = self.generate_usage_guide()
        guide_file = output_path / "usage_guide.md"
        guide_file.write_text(guide_content, encoding="utf-8")
        results["guide"] = guide_file.resolve()

        return results

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _format_param(param: ParamInfo) -> str:
        """格式化参数为函数签名格式。

        Parameters
        ----------
        param : ParamInfo
            参数信息。

        Returns
        -------
        str
            格式化后的参数字符串。
        """
        parts = [param.name]
        if param.annotation:
            parts.append(f": {param.annotation}")
        if param.default:
            parts.append(f" = {param.default}")
        return "".join(parts)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def main() -> None:
    """命令行入口，用于生成文档。

    用法::

        python -m backend.tools.doc_generator --source backend --output docs
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="CityFlow 文档生成工具",
    )
    parser.add_argument(
        "--source",
        default="backend",
        help="源码目录，默认 backend",
    )
    parser.add_argument(
        "--output",
        default="docs",
        help="输出目录，默认 docs",
    )
    parser.add_argument(
        "--project-name",
        default="CityFlow",
        help="项目名称，默认 CityFlow",
    )
    parser.add_argument(
        "--type",
        choices=["api", "sdk", "guide", "all"],
        default="all",
        help="生成文档类型，默认 all",
    )

    args = parser.parse_args()

    generator = DocGenerator(
        source_dir=args.source,
        project_name=args.project_name,
    )
    generator.parse()

    doc_type = args.type
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    if doc_type in ("api", "all"):
        content = generator.generate_api_docs_markdown()
        file_path = output_path / "api_reference.md"
        file_path.write_text(content, encoding="utf-8")
        print(f"API 文档已生成: {file_path}")

    if doc_type in ("sdk", "all"):
        content = generator.generate_sdk_docs()
        file_path = output_path / "sdk_reference.md"
        file_path.write_text(content, encoding="utf-8")
        print(f"SDK 文档已生成: {file_path}")

    if doc_type in ("guide", "all"):
        content = generator.generate_usage_guide()
        file_path = output_path / "usage_guide.md"
        file_path.write_text(content, encoding="utf-8")
        print(f"使用指南已生成: {file_path}")

    print("文档生成完成！")


if __name__ == "__main__":
    main()
