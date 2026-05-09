"""CityFlow 代码生成工具。

根据字段定义自动生成符合项目规范的 API 端点、数据模型和服务类代码。
生成的代码遵循 CityFlow 项目的编码风格：
- 使用 `from __future__ import annotations`
- Pydantic v2 BaseModel + Field
- 统一的注释分隔线风格
- 类型注解完整
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 类型映射
# ---------------------------------------------------------------------------

_PYDANTIC_TYPE_MAP: dict[str, str] = {
    "str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "list": "list[Any]",
    "dict": "dict[str, Any]",
    "datetime": "datetime",
}


def _resolve_type(raw: str) -> str:
    """将简写类型映射为 Python 类型字符串。"""
    return _PYDANTIC_TYPE_MAP.get(raw, raw)


def _capitalize(name: str) -> str:
    """将资源名转为 PascalCase。

    支持 ``snake_case`` 和 ``kebab-case`` 输入。
    """
    parts = name.replace("-", "_").split("_")
    return "".join(p.capitalize() for p in parts)


_SEP = "# " + "-" * 70


# ---------------------------------------------------------------------------
# 代码生成器
# ---------------------------------------------------------------------------


class CodeGenerator:
    """代码生成器。

    根据字段定义生成 FastAPI 端点、Pydantic 模型、异步服务类的代码，
    并可选择直接写入文件。

    Parameters
    ----------
    output_dir : str
        输出根目录，默认 ``"backend"``。
    """

    def __init__(self, output_dir: str = "backend") -> None:
        self._output_dir = Path(output_dir)

    # ------------------------------------------------------------------
    # 字段行构建
    # ------------------------------------------------------------------

    @staticmethod
    def _build_field_lines(fields: list[dict[str, Any]]) -> list[str]:
        """为 Pydantic 模型构建字段行（带 4 空格缩进）。"""
        lines: list[str] = []
        for field in fields:
            ftype = _resolve_type(field.get("type", "str"))
            fname = field["name"]
            optional = field.get("optional", False)
            desc = field.get("description", fname)

            if optional:
                lines.append(
                    f"    {fname}: Optional[{ftype}] = Field("
                    f'None, description="{desc}")'
                )
            else:
                lines.append(f'    {fname}: {ftype} = Field(..., description="{desc}")')
        return lines

    @staticmethod
    def _build_sample_payload(fields: list[dict[str, Any]]) -> list[str]:
        """为测试构建示例 payload 行。"""
        lines: list[str] = []
        for field in fields:
            fname = field["name"]
            ftype = _resolve_type(field.get("type", "str"))
            if ftype == "str":
                lines.append(f'        "{fname}": "test-{fname}",')
            elif ftype == "int":
                lines.append(f'        "{fname}": 1,')
            elif ftype == "float":
                lines.append(f'        "{fname}": 1.0,')
            elif ftype == "bool":
                lines.append(f'        "{fname}": True,')
            else:
                lines.append(f'        "{fname}": None,')
        return lines

    # ------------------------------------------------------------------
    # API 端点生成
    # ------------------------------------------------------------------

    def generate_api_endpoint(
        self,
        name: str,
        fields: list[dict[str, Any]],
        *,
        tag: str | None = None,
        prefix: str | None = None,
    ) -> str:
        """生成 CRUD API 端点代码。

        Parameters
        ----------
        name : str
            资源名称（英文小写，如 ``"order"``）。
        fields : list[dict]
            字段列表，每项包含 ``name``、``type``、``optional`` 键。
        tag : str | None
            OpenAPI 标签，默认使用资源名称。
        prefix : str | None
            路由前缀，默认 ``/api/{name}``。

        Returns
        -------
        str
            完整的端点模块代码。
        """
        tag = tag or _capitalize(name)
        prefix = prefix or f"/api/{name}"
        cap = _capitalize(name)
        field_lines = self._build_field_lines(fields)
        fl = "\n".join(field_lines)

        lines: list[str] = [
            f'"""{tag} API 端点。',
            "",
            f"提供 {name} 的 CRUD 接口。",
            '"""',
            "",
            "from __future__ import annotations",
            "",
            "from typing import Any",
            "",
            "from fastapi import APIRouter, HTTPException, Query",
            "from pydantic import BaseModel, Field",
            "",
            f'router = APIRouter(prefix="{prefix}", tags=["{tag}"])',
            "",
            "",
            _SEP,
            "# 请求 / 响应模型",
            _SEP,
            "",
            "",
            f"class Create{cap}Request(BaseModel):",
            f'    """创建 {name} 请求。"""',
            "",
            fl,
            "",
            "",
            f"class Update{cap}Request(BaseModel):",
            f'    """更新 {name} 请求。"""',
            "",
            fl,
            "",
            "",
            f"class {cap}Response(BaseModel):",
            f'    """{name} 响应。"""',
            "",
            '    id: str = Field(..., description="资源 ID")',
            "",
            fl,
            "",
            "",
            _SEP,
            "# 路由",
            _SEP,
            "",
            "",
            f'@router.post("/", summary="创建{name}")',
            f"async def create_{name}(body: Create{cap}Request) -> dict[str, str]:",
            f'    """创建新的 {name}，返回资源 ID。"""',
            "    # TODO: 注入服务并实现创建逻辑",
            f'    return {{"id": "new-{name}-id"}}',
            "",
            "",
            f'@router.get("/", summary="获取{name}列表")',
            f"async def list_{name}(",
            '    page: int = Query(1, ge=1, description="页码"),',
            '    size: int = Query(20, ge=1, le=100, description="每页数量"),',
            ") -> dict[str, Any]:",
            f'    """分页获取 {name} 列表。"""',
            "    # TODO: 注入服务并实现列表查询",
            '    return {"items": [], "total": 0, "page": page, "size": size}',
            "",
            "",
            f'@router.get("/{{item_id}}", summary="获取单个{name}")',
            f"async def get_{name}(item_id: str) -> dict[str, Any]:",
            f'    """获取指定 {name} 的详细信息。"""',
            "    # TODO: 注入服务并实现获取逻辑",
            f'    raise HTTPException(status_code=404, detail="{name} 不存在")',
            "",
            "",
            f'@router.put("/{{item_id}}", summary="更新{name}")',
            f"async def update_{name}(",
            "    item_id: str,",
            f"    body: Update{cap}Request,",
            ") -> dict[str, str]:",
            f'    """更新指定 {name}。"""',
            "    # TODO: 注入服务并实现更新逻辑",
            '    return {"message": "更新成功"}',
            "",
            "",
            f'@router.delete("/{{item_id}}", summary="删除{name}")',
            f"async def delete_{name}(item_id: str) -> dict[str, str]:",
            f'    """删除指定 {name}。"""',
            "    # TODO: 注入服务并实现删除逻辑",
            '    return {"message": "删除成功"}',
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 数据模型生成
    # ------------------------------------------------------------------

    def generate_model(
        self,
        name: str,
        fields: list[dict[str, Any]],
        *,
        description: str | None = None,
        include_timestamps: bool = True,
    ) -> str:
        """生成 Pydantic 数据模型代码。

        Parameters
        ----------
        name : str
            模型名称（英文小写，如 ``"order"``）。
        fields : list[dict]
            字段列表，每项包含 ``name``、``type``、``optional``、``description`` 键。
        description : str | None
            模型描述，默认自动生成。
        include_timestamps : bool
            是否包含 ``created_at`` 和 ``updated_at`` 字段，默认 ``True``。

        Returns
        -------
        str
            完整的模型模块代码。
        """
        cap = _capitalize(name)
        description = description or f"{cap} 数据模型。"
        field_lines = self._build_field_lines(fields)

        parts: list[str] = [
            f'"""{description}"""',
            "",
            "from __future__ import annotations",
            "",
            "from datetime import datetime",
            "from typing import Any, Optional",
            "",
            "from pydantic import BaseModel, Field",
            "",
            "",
            f"class {cap}(BaseModel):",
            f'    """{description}"""',
            "",
            '    id: str = Field(..., description="资源唯一标识")',
        ]

        parts.extend(field_lines)

        if include_timestamps:
            parts.extend(
                [
                    "",
                    "    created_at: datetime = Field(",
                    '        default_factory=datetime.now, description="创建时间"',
                    "    )",
                    "    updated_at: datetime = Field(",
                    '        default_factory=datetime.now, description="更新时间"',
                    "    )",
                ]
            )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 服务类生成
    # ------------------------------------------------------------------

    def generate_service(
        self,
        name: str,
        *,
        description: str | None = None,
        use_database: bool = False,
    ) -> str:
        """生成异步服务类代码。

        Parameters
        ----------
        name : str
            服务名称（英文小写，如 ``"order"``）。
        description : str | None
            服务描述，默认自动生成。
        use_database : bool
            是否包含数据库会话注入，默认 ``False``。

        Returns
        -------
        str
            完整的服务模块代码。
        """
        cap = _capitalize(name)
        description = description or f"{cap} 服务。"

        if use_database:
            db_import = "from sqlalchemy.ext.asyncio import AsyncSession"
            db_param = "\n        session: AsyncSession,"
            init_lines = [
                "",
                "    def __init__(self, session: AsyncSession) -> None:",
                "        self._session = session",
            ]
        else:
            db_import = ""
            db_param = ""
            init_lines = [
                "",
                "    def __init__(self) -> None:",
                "        pass",
            ]

        parts: list[str] = [
            f'"""{description}',
            "",
            f"提供 {name} 的 CRUD 业务逻辑。",
            '"""',
            "",
            "from __future__ import annotations",
            "",
            "import logging",
            "from typing import Any, Optional",
        ]

        if db_import:
            parts.append("")
            parts.append(db_import)

        parts.extend(
            [
                "",
                "logger = logging.getLogger(__name__)",
                "",
                f'__all__ = ["{cap}Service", "get_{name}_service"]',
                "",
                "",
                f"class {cap}Service:",
                f'    """{description}"""',
            ]
        )

        parts.extend(init_lines)

        # create
        parts.extend(
            [
                "",
                f"    async def create(self,{db_param} data: dict[str, Any]) -> dict[str, Any]:",
                f'        """创建 {name}。',
                "",
                "        Parameters",
                "        ----------",
                "        data : dict",
                "            创建数据。",
                "",
                "        Returns",
                "        -------",
                "        dict",
                "            创建后的资源。",
                '        """',
                "        # TODO: 实现创建逻辑",
                f'        logger.info("创建 %s: %s", "{name}", data)',
                "        return data",
            ]
        )

        # get
        parts.extend(
            [
                "",
                f"    async def get(self,{db_param} item_id: str) -> Optional[dict[str, Any]]:",
                f'        """获取 {name}。',
                "",
                "        Parameters",
                "        ----------",
                "        item_id : str",
                "            资源 ID。",
                "",
                "        Returns",
                "        -------",
                "        dict | None",
                "            资源数据，不存在返回 ``None``。",
                '        """',
                "        # TODO: 实现获取逻辑",
                f'        logger.info("获取 %s: %s", "{name}", item_id)',
                "        return None",
            ]
        )

        # list
        parts.extend(
            [
                "",
                "    async def list(self,{db_param} page: int = 1, size: int = 20) -> list[dict[str, Any]]:",
                f'        """获取 {name} 列表。',
                "",
                "        Parameters",
                "        ----------",
                "        page : int",
                "            页码。",
                "        size : int",
                "            每页数量。",
                "",
                "        Returns",
                "        -------",
                "        list[dict]",
                "            资源列表。",
                '        """',
                "        # TODO: 实现列表查询",
                f'        logger.info("查询 %s 列表: page=%d, size=%d", "{name}", page, size)',
                "        return []",
            ]
        )

        # update
        parts.extend(
            [
                "",
                "    async def update(",
                f"        self,{db_param}",
                "        item_id: str,",
                "        data: dict[str, Any],",
                "    ) -> Optional[dict[str, Any]]:",
                f'        """更新 {name}。',
                "",
                "        Parameters",
                "        ----------",
                "        item_id : str",
                "            资源 ID。",
                "        data : dict",
                "            更新数据。",
                "",
                "        Returns",
                "        -------",
                "        dict | None",
                "            更新后的资源，不存在返回 ``None``。",
                '        """',
                "        # TODO: 实现更新逻辑",
                f'        logger.info("更新 %s %s: %s", "{name}", item_id, data)',
                "        return data",
            ]
        )

        # delete
        parts.extend(
            [
                "",
                f"    async def delete(self,{db_param} item_id: str) -> bool:",
                f'        """删除 {name}。',
                "",
                "        Parameters",
                "        ----------",
                "        item_id : str",
                "            资源 ID。",
                "",
                "        Returns",
                "        -------",
                "        bool",
                "            是否删除成功。",
                '        """',
                "        # TODO: 实现删除逻辑",
                f'        logger.info("删除 %s: %s", "{name}", item_id)',
                "        return True",
            ]
        )

        # singleton
        parts.extend(
            [
                "",
                "",
                f"_instance: {cap}Service | None = None",
                "",
                "",
                f"def get_{name}_service() -> {cap}Service:",
                f'    """获取 {cap}Service 单例。',
                "",
                "    Returns",
                "    -------",
                f"    {cap}Service",
                "        服务实例。",
                '    """',
                "    global _instance",
                "    if _instance is None:",
                f"        _instance = {cap}Service()",
                "    return _instance",
            ]
        )

        # 格式化 db_param 占位符
        code = "\n".join(parts)
        code = code.replace("{db_param}", db_param)
        return code

    # ------------------------------------------------------------------
    # 测试文件生成
    # ------------------------------------------------------------------

    def generate_test(self, name: str, fields: list[dict[str, Any]]) -> str:
        """生成测试文件代码。

        Parameters
        ----------
        name : str
            资源名称（英文小写）。
        fields : list[dict]
            字段列表。

        Returns
        -------
        str
            完整的测试模块代码。
        """
        cap = _capitalize(name)
        sample_lines = self._build_sample_payload(fields)
        sb = "\n".join(sample_lines)

        return "\n".join(
            [
                f'"""{cap} API 端点测试。"""',
                "",
                "from __future__ import annotations",
                "",
                "import pytest",
                "from fastapi import FastAPI",
                "from fastapi.testclient import TestClient",
                "",
                f"from backend.routers.{name} import router",
                "",
                "",
                "@pytest.fixture",
                "def client() -> TestClient:",
                '    """创建测试客户端。"""',
                "    app = FastAPI()",
                "    app.include_router(router)",
                "    return TestClient(app)",
                "",
                "",
                f"class Test{cap}CRUD:",
                f'    """{cap} CRUD 接口测试。"""',
                "",
                "    def test_create(self, client: TestClient) -> None:",
                '        """测试创建接口。"""',
                "        payload = {",
                sb,
                "        }",
                '        resp = client.post("/", json=payload)',
                "        assert resp.status_code == 200",
                '        assert "id" in resp.json()',
                "",
                "    def test_list(self, client: TestClient) -> None:",
                '        """测试列表接口。"""',
                '        resp = client.get("/")',
                "        assert resp.status_code == 200",
                "        data = resp.json()",
                '        assert "items" in data',
                '        assert "total" in data',
                "",
                "    def test_get_not_found(self, client: TestClient) -> None:",
                '        """测试获取不存在的资源返回 404。"""',
                '        resp = client.get("/nonexistent-id")',
                "        assert resp.status_code == 404",
                "",
                "    def test_update(self, client: TestClient) -> None:",
                '        """测试更新接口。"""',
                "        payload = {",
                sb,
                "        }",
                '        resp = client.put("/test-id", json=payload)',
                "        assert resp.status_code == 200",
                "",
                "    def test_delete(self, client: TestClient) -> None:",
                '        """测试删除接口。"""',
                '        resp = client.delete("/test-id")',
                "        assert resp.status_code == 200",
                '        assert resp.json()["message"] == "删除成功"',
            ]
        )

    # ------------------------------------------------------------------
    # 文件保存
    # ------------------------------------------------------------------

    def save_file(self, filename: str, content: str) -> Path:
        """将生成的代码保存到文件。

        Parameters
        ----------
        filename : str
            相对于输出目录的文件路径，如 ``"routers/order.py"``。
        content : str
            文件内容。

        Returns
        -------
        Path
            保存后的绝对路径。
        """
        filepath = self._output_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        return filepath.resolve()

    def generate_full(
        self,
        name: str,
        fields: list[dict[str, Any]],
        *,
        save: bool = False,
    ) -> dict[str, str]:
        """一次性生成端点、模型、服务、测试四个文件的代码。

        Parameters
        ----------
        name : str
            资源名称（英文小写）。
        fields : list[dict]
            字段列表。
        save : bool
            是否同时写入文件，默认 ``False``。

        Returns
        -------
        dict[str, str]
            键为 ``router``/``model``/``service``/``test``，值为生成的代码。
        """
        result = {
            "router": self.generate_api_endpoint(name, fields),
            "model": self.generate_model(name, fields),
            "service": self.generate_service(name),
            "test": self.generate_test(name, fields),
        }

        if save:
            self.save_file(f"routers/{name}.py", result["router"])
            self.save_file(f"models/{name}.py", result["model"])
            self.save_file(f"services/{name}_service.py", result["service"])
            self.save_file(f"tests/test_{name}.py", result["test"])

        return result


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def main() -> None:
    """命令行入口，用于快速生成代码。

    用法::

        python -m backend.tools.code_generator order \
            --fields '[{"name": "title", "type": "str"}, {"name": "price", "type": "float"}]' \
            --save
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="CityFlow 代码生成工具",
    )
    parser.add_argument("name", help="资源名称（英文小写）")
    parser.add_argument(
        "--fields",
        required=True,
        help="字段定义 JSON 字符串",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="同时写入文件",
    )
    parser.add_argument(
        "--output-dir",
        default="backend",
        help="输出目录，默认 backend",
    )

    args = parser.parse_args()
    fields: list[dict[str, Any]] = json.loads(args.fields)

    generator = CodeGenerator(output_dir=args.output_dir)
    result = generator.generate_full(args.name, fields, save=args.save)

    for key, code in result.items():
        print(f"\n{'=' * 60}")
        print(f"  {key.upper()}")
        print(f"{'=' * 60}")
        print(code)

    if args.save:
        print(f"\n文件已保存到 {args.output_dir}/")


if __name__ == "__main__":
    main()
