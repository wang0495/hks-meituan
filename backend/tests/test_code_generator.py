"""CityFlow 代码生成器测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.tools.code_generator import (CodeGenerator, _capitalize,
                                          _resolve_type)

# ---------------------------------------------------------------------------
# 辅助函数测试
# ---------------------------------------------------------------------------


class TestHelpers:
    """内部辅助函数测试。"""

    def test_capitalize_snake_case(self) -> None:
        """snake_case 转 PascalCase。"""
        assert _capitalize("user_profile") == "UserProfile"

    def test_capitalize_kebab_case(self) -> None:
        """kebab-case 转 PascalCase。"""
        assert _capitalize("user-profile") == "UserProfile"

    def test_capitalize_single_word(self) -> None:
        """单个单词。"""
        assert _capitalize("order") == "Order"

    def test_resolve_type_known(self) -> None:
        """已知类型映射。"""
        assert _resolve_type("str") == "str"
        assert _resolve_type("int") == "int"
        assert _resolve_type("float") == "float"
        assert _resolve_type("bool") == "bool"

    def test_resolve_type_unknown(self) -> None:
        """未知类型原样返回。"""
        assert _resolve_type("CustomModel") == "CustomModel"


# ---------------------------------------------------------------------------
# 端点生成测试
# ---------------------------------------------------------------------------


class TestGenerateApiEndpoint:
    """API 端点生成测试。"""

    @pytest.fixture
    def generator(self) -> CodeGenerator:
        return CodeGenerator()

    @pytest.fixture
    def sample_fields(self) -> list[dict]:
        return [
            {"name": "title", "type": "str", "description": "标题"},
            {"name": "price", "type": "float", "optional": True, "description": "价格"},
        ]

    def test_contains_router_definition(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """生成的代码包含 router 定义。"""
        code = generator.generate_api_endpoint("product", sample_fields)
        assert 'router = APIRouter(prefix="/api/product"' in code

    def test_contains_crud_endpoints(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """生成的代码包含完整 CRUD 端点。"""
        code = generator.generate_api_endpoint("product", sample_fields)
        assert "async def create_product" in code
        assert "async def list_product" in code
        assert "async def get_product" in code
        assert "async def update_product" in code
        assert "async def delete_product" in code

    def test_contains_request_models(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """生成的代码包含请求模型。"""
        code = generator.generate_api_endpoint("product", sample_fields)
        assert "class CreateProductRequest(BaseModel):" in code
        assert "class UpdateProductRequest(BaseModel):" in code

    def test_optional_field_handling(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """可选字段使用 Optional 类型。"""
        code = generator.generate_api_endpoint("product", sample_fields)
        assert "Optional[float]" in code

    def test_custom_prefix(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """支持自定义前缀。"""
        code = generator.generate_api_endpoint(
            "product", sample_fields, prefix="/v2/products"
        )
        assert 'prefix="/v2/products"' in code

    def test_custom_tag(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """支持自定义标签。"""
        code = generator.generate_api_endpoint("product", sample_fields, tag="商品管理")
        assert 'tags=["商品管理"]' in code


# ---------------------------------------------------------------------------
# 模型生成测试
# ---------------------------------------------------------------------------


class TestGenerateModel:
    """数据模型生成测试。"""

    @pytest.fixture
    def generator(self) -> CodeGenerator:
        return CodeGenerator()

    @pytest.fixture
    def sample_fields(self) -> list[dict]:
        return [
            {"name": "title", "type": "str", "description": "标题"},
            {"name": "count", "type": "int", "description": "数量"},
        ]

    def test_contains_model_class(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """生成的代码包含模型类。"""
        code = generator.generate_model("product", sample_fields)
        assert "class Product(BaseModel):" in code

    def test_contains_id_field(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """生成的代码包含 id 字段。"""
        code = generator.generate_model("product", sample_fields)
        assert "id: str" in code

    def test_contains_timestamps_by_default(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """默认包含时间戳字段。"""
        code = generator.generate_model("product", sample_fields)
        assert "created_at: datetime" in code
        assert "updated_at: datetime" in code

    def test_exclude_timestamps(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """可选排除时间戳字段。"""
        code = generator.generate_model(
            "product", sample_fields, include_timestamps=False
        )
        assert "created_at" not in code
        assert "updated_at" not in code

    def test_custom_description(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """支持自定义描述。"""
        code = generator.generate_model(
            "product", sample_fields, description="商品数据模型"
        )
        assert "商品数据模型" in code


# ---------------------------------------------------------------------------
# 服务生成测试
# ---------------------------------------------------------------------------


class TestGenerateService:
    """服务类生成测试。"""

    @pytest.fixture
    def generator(self) -> CodeGenerator:
        return CodeGenerator()

    def test_contains_service_class(self, generator: CodeGenerator) -> None:
        """生成的代码包含服务类。"""
        code = generator.generate_service("product")
        assert "class ProductService:" in code

    def test_contains_crud_methods(self, generator: CodeGenerator) -> None:
        """生成的代码包含 CRUD 方法。"""
        code = generator.generate_service("product")
        assert "async def create(" in code
        assert "async def get(" in code
        assert "async def list(" in code
        assert "async def update(" in code
        assert "async def delete(" in code

    def test_contains_singleton_getter(self, generator: CodeGenerator) -> None:
        """生成的代码包含单例获取函数。"""
        code = generator.generate_service("product")
        assert "def get_product_service() -> ProductService:" in code

    def test_database_mode(self, generator: CodeGenerator) -> None:
        """数据库模式包含 AsyncSession 注入。"""
        code = generator.generate_service("product", use_database=True)
        assert "session: AsyncSession" in code
        assert "from sqlalchemy.ext.asyncio import AsyncSession" in code

    def test_non_database_mode(self, generator: CodeGenerator) -> None:
        """非数据库模式不包含数据库相关导入。"""
        code = generator.generate_service("product", use_database=False)
        assert "AsyncSession" not in code


# ---------------------------------------------------------------------------
# 测试文件生成
# ---------------------------------------------------------------------------


class TestGenerateTest:
    """测试文件生成测试。"""

    @pytest.fixture
    def generator(self) -> CodeGenerator:
        return CodeGenerator()

    @pytest.fixture
    def sample_fields(self) -> list[dict]:
        return [
            {"name": "title", "type": "str", "description": "标题"},
            {"name": "price", "type": "float", "description": "价格"},
        ]

    def test_contains_test_class(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """生成的代码包含测试类。"""
        code = generator.generate_test("product", sample_fields)
        assert "class TestProductCRUD:" in code

    def test_contains_crud_tests(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """生成的代码包含 CRUD 测试方法。"""
        code = generator.generate_test("product", sample_fields)
        assert "def test_create(" in code
        assert "def test_list(" in code
        assert "def test_get_not_found(" in code
        assert "def test_update(" in code
        assert "def test_delete(" in code


# ---------------------------------------------------------------------------
# 文件保存测试
# ---------------------------------------------------------------------------


class TestSaveFile:
    """文件保存测试。"""

    def test_save_creates_file(self, tmp_path: Path) -> None:
        """保存文件会创建目标文件。"""
        generator = CodeGenerator(output_dir=str(tmp_path))
        result = generator.save_file("test_dir/test.py", "print('hello')")
        assert result.exists()
        assert result.read_text(encoding="utf-8") == "print('hello')"

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        """保存文件会自动创建父目录。"""
        generator = CodeGenerator(output_dir=str(tmp_path))
        result = generator.save_file("a/b/c/test.py", "# content")
        assert result.exists()

    def test_save_returns_absolute_path(self, tmp_path: Path) -> None:
        """返回绝对路径。"""
        generator = CodeGenerator(output_dir=str(tmp_path))
        result = generator.save_file("test.py", "# content")
        assert result.is_absolute()


# ---------------------------------------------------------------------------
# 完整生成测试
# ---------------------------------------------------------------------------


class TestGenerateFull:
    """一次性生成全部文件测试。"""

    @pytest.fixture
    def generator(self) -> CodeGenerator:
        return CodeGenerator()

    @pytest.fixture
    def sample_fields(self) -> list[dict]:
        return [
            {"name": "name", "type": "str", "description": "名称"},
            {"name": "value", "type": "float", "optional": True, "description": "值"},
        ]

    def test_returns_four_keys(
        self, generator: CodeGenerator, sample_fields: list[dict]
    ) -> None:
        """返回四个键。"""
        result = generator.generate_full("item", sample_fields)
        assert set(result.keys()) == {"router", "model", "service", "test"}

    def test_save_creates_all_files(
        self, tmp_path: Path, sample_fields: list[dict]
    ) -> None:
        """save=True 会创建全部文件。"""
        generator = CodeGenerator(output_dir=str(tmp_path))
        generator.generate_full("item", sample_fields, save=True)

        assert (tmp_path / "routers" / "item.py").exists()
        assert (tmp_path / "models" / "item.py").exists()
        assert (tmp_path / "services" / "item_service.py").exists()
        assert (tmp_path / "tests" / "test_item.py").exists()


# ---------------------------------------------------------------------------
# CLI 测试
# ---------------------------------------------------------------------------


class TestCLI:
    """CLI 入口测试。"""

    def test_main_with_save(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI --save 模式写入文件。"""
        from backend.tools.code_generator import main

        fields_json = json.dumps(
            [{"name": "title", "type": "str"}, {"name": "price", "type": "float"}]
        )
        monkeypatch.setattr(
            "sys.argv",
            [
                "code_generator",
                "product",
                "--fields",
                fields_json,
                "--save",
                "--output-dir",
                str(tmp_path),
            ],
        )

        main()
        assert (tmp_path / "routers" / "product.py").exists()
