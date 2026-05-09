"""CityFlow 覆盖率工具测试。

覆盖以下新增模块：
- backend/tools/coverage_analyzer.py
- backend/tools/test_supplement.py
"""

from __future__ import annotations

from pathlib import Path

from backend.tools.coverage_analyzer import CoverageAnalyzer, FileCoverage
from backend.tools.test_supplement import TestSupplement, UntestedFunction

# ===========================================================================
# FileCoverage
# ===========================================================================


class TestFileCoverage:
    """FileCoverage 数据类测试。"""

    def test_basic_properties(self) -> None:
        fc = FileCoverage(
            file_path="backend/test.py",
            total_lines=100,
            covered_lines=60,
            missing_lines=[1, 2, 3, 4],
            coverage_percent=60.0,
        )
        assert fc.file_path == "backend/test.py"
        assert fc.total_lines == 100
        assert fc.covered_lines == 60
        assert fc.uncovered_count == 40
        assert fc.missing_lines == [1, 2, 3, 4]

    def test_defaults(self) -> None:
        fc = FileCoverage(
            file_path="test.py",
            total_lines=10,
            covered_lines=10,
        )
        assert fc.missing_lines == []
        assert fc.coverage_percent == 0.0


# ===========================================================================
# CoverageAnalyzer
# ===========================================================================


class TestCoverageAnalyzer:
    """CoverageAnalyzer 测试。"""

    def test_init_defaults(self) -> None:
        analyzer = CoverageAnalyzer()
        assert analyzer._source == "backend"
        assert analyzer._report_format == "json"
        assert analyzer.files == {}

    def test_load_xml(self, tmp_path: Path) -> None:
        xml_content = """<?xml version="1.0" ?>
<coverage version="7.0" lines-valid="100" lines-covered="60" line-rate="0.6"
          branches-covered="0" branches-valid="0" branch-rate="0" complexity="0">
    <sources>
        <source>/app</source>
    </sources>
    <packages>
        <package name="." line-rate="0.5" branch-rate="0" complexity="0">
            <classes>
                <class name="main.py" filename="main.py" complexity="0"
                       line-rate="0.5" branch-rate="0">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="0"/>
                        <line number="4" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        xml_file = tmp_path / "coverage.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        analyzer = CoverageAnalyzer()
        result = analyzer.load_xml(xml_file)

        assert result["success"] is True
        assert result["total_lines"] == 100
        assert result["covered_lines"] == 60
        assert result["coverage_percent"] == 60.0
        assert result["file_count"] == 1

    def test_load_xml_file_not_found(self) -> None:
        analyzer = CoverageAnalyzer()
        result = analyzer.load_xml("/nonexistent/coverage.xml")
        assert result["success"] is False
        assert "不存在" in result["error"]

    def test_get_uncovered_lines_from_xml(self, tmp_path: Path) -> None:
        xml_content = """<?xml version="1.0" ?>
<coverage version="7.0" lines-valid="4" lines-covered="2" line-rate="0.5"
          branches-covered="0" branches-valid="0" branch-rate="0" complexity="0">
    <sources><source>/app</source></sources>
    <packages>
        <package name="." line-rate="0.5" branch-rate="0" complexity="0">
            <classes>
                <class name="a.py" filename="a.py" line-rate="0.5" branch-rate="0">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                    </lines>
                </class>
                <class name="b.py" filename="b.py" line-rate="1.0" branch-rate="0">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        xml_file = tmp_path / "coverage.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        analyzer = CoverageAnalyzer()
        analyzer.load_xml(xml_file)

        uncovered = analyzer.get_uncovered_lines()
        assert "a.py" in uncovered
        assert uncovered["a.py"] == [2]
        assert "b.py" not in uncovered

    def test_get_uncovered_files_sorted(self, tmp_path: Path) -> None:
        xml_content = """<?xml version="1.0" ?>
<coverage version="7.0" lines-valid="6" lines-covered="3" line-rate="0.5"
          branches-covered="0" branches-valid="0" branch-rate="0" complexity="0">
    <sources><source>/app</source></sources>
    <packages>
        <package name="." line-rate="0.5" branch-rate="0" complexity="0">
            <classes>
                <class name="good.py" filename="good.py" line-rate="1.0" branch-rate="0">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                    </lines>
                </class>
                <class name="bad.py" filename="bad.py" line-rate="0.25" branch-rate="0">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                        <line number="3" hits="0"/>
                        <line number="4" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        xml_file = tmp_path / "coverage.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        analyzer = CoverageAnalyzer()
        analyzer.load_xml(xml_file)

        files = analyzer.get_uncovered_files()
        assert len(files) == 1
        assert files[0].file_path == "bad.py"

    def test_get_summary_from_xml(self, tmp_path: Path) -> None:
        xml_content = """<?xml version="1.0" ?>
<coverage version="7.0" lines-valid="10" lines-covered="7" line-rate="0.7"
          branches-covered="0" branches-valid="0" branch-rate="0" complexity="0">
    <sources><source>/app</source></sources>
    <packages>
        <package name="." line-rate="0.7" branch-rate="0" complexity="0">
            <classes>
                <class name="x.py" filename="x.py" line-rate="0.7" branch-rate="0">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        xml_file = tmp_path / "coverage.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        analyzer = CoverageAnalyzer()
        analyzer.load_xml(xml_file)

        summary = analyzer.get_summary()
        assert summary["total_lines"] == 3
        assert summary["covered_lines"] == 2
        assert summary["missing_lines"] == 1
        assert summary["file_count"] == 1

    def test_get_file_coverage(self, tmp_path: Path) -> None:
        xml_content = """<?xml version="1.0" ?>
<coverage version="7.0" lines-valid="2" lines-covered="1" line-rate="0.5"
          branches-covered="0" branches-valid="0" branch-rate="0" complexity="0">
    <sources><source>/app</source></sources>
    <packages>
        <package name="." line-rate="0.5" branch-rate="0" complexity="0">
            <classes>
                <class name="test.py" filename="test.py" line-rate="0.5" branch-rate="0">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        xml_file = tmp_path / "coverage.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        analyzer = CoverageAnalyzer()
        analyzer.load_xml(xml_file)

        fc = analyzer.get_file_coverage("test.py")
        assert fc is not None
        assert fc.coverage_percent == 50.0

        assert analyzer.get_file_coverage("missing.py") is None

    def test_get_low_coverage_files(self, tmp_path: Path) -> None:
        xml_content = """<?xml version="1.0" ?>
<coverage version="7.0" lines-valid="4" lines-covered="3" line-rate="0.75"
          branches-covered="0" branches-valid="0" branch-rate="0" complexity="0">
    <sources><source>/app</source></sources>
    <packages>
        <package name="." line-rate="0.75" branch-rate="0" complexity="0">
            <classes>
                <class name="high.py" filename="high.py" line-rate="1.0" branch-rate="0">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                    </lines>
                </class>
                <class name="low.py" filename="low.py" line-rate="0.5" branch-rate="0">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                        <line number="3" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        xml_file = tmp_path / "coverage.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        analyzer = CoverageAnalyzer()
        analyzer.load_xml(xml_file)

        low = analyzer.get_low_coverage_files(threshold=80.0)
        assert len(low) == 1
        assert low[0].file_path == "low.py"


# ===========================================================================
# TestSupplement
# ===========================================================================


class TestTestSupplement:
    """TestSupplement 测试。"""

    def test_init_defaults(self) -> None:
        supplement = TestSupplement()
        assert supplement._source_root == Path("backend")
        assert supplement._test_root == Path("tests")

    def test_generate_test_template_basic(self) -> None:
        supplement = TestSupplement()
        code = supplement.generate_test_template("my_func", "backend.services.test")

        assert "from backend.services.test import my_func" in code
        assert "test_my_func_basic" in code
        assert "test_my_func_edge_cases" in code
        assert "test_my_func_error_handling" in code

    def test_generate_test_template_async(self) -> None:
        supplement = TestSupplement()
        code = supplement.generate_test_template(
            "my_func", "backend.svc", is_async=True
        )
        assert "async def test_my_func_basic" in code
        assert "@pytest.mark.asyncio" in code
        assert "await" in code

    def test_generate_test_template_with_class(self) -> None:
        supplement = TestSupplement()
        code = supplement.generate_test_template(
            "method", "backend.svc", class_name="MyClass"
        )
        assert "from backend.svc import MyClass" in code
        assert "test_MyClass_method" in code

    def test_path_to_module(self) -> None:
        supplement = TestSupplement()
        assert (
            supplement._path_to_module("backend/services/test.py")
            == "backend.services.test"
        )
        assert supplement._path_to_module("backend/main.py") == "backend.main"

    def test_identify_untested_functions(self) -> None:
        supplement = TestSupplement()

        coverage_data = {
            "files": {
                "backend/services/circuit_breaker.py": {
                    "missing_lines": [41, 42, 43, 44, 45],
                },
                "backend/services/retry.py": {
                    "missing_lines": [],
                },
            }
        }

        untested = supplement.identify_untested_functions(coverage_data)
        # circuit_breaker.py 有未覆盖行，retry.py 没有
        assert len(untested) >= 1
        # retry.py 不应出现
        retry_funcs = [f for f in untested if "retry" in f.module]
        assert len(retry_funcs) == 0

    def test_identify_untested_from_file_coverage(self) -> None:
        """测试从 FileCoverage 对象识别未测试函数。"""
        supplement = TestSupplement()

        # 使用 FileCoverage 对象（有 missing_lines 属性）
        fc = FileCoverage(
            file_path="test.py",
            total_lines=10,
            covered_lines=5,
            missing_lines=[6, 7, 8, 9, 10],
        )

        # identify_untested_functions 支持 dict 和对象
        data = {"test.py": fc}
        untested = supplement.identify_untested_functions(data)
        # 由于 test.py 不存在，会降级为文件级占位
        assert len(untested) >= 1

    def test_generate_test_file(self) -> None:
        supplement = TestSupplement()
        funcs = [
            UntestedFunction(
                name="func_a",
                module="backend.svc",
                file_path="backend/svc.py",
                line_number=10,
            ),
            UntestedFunction(
                name="func_b",
                module="backend.svc",
                file_path="backend/svc.py",
                line_number=20,
                is_async=True,
            ),
        ]
        code = supplement.generate_test_file(funcs)
        assert "from backend.svc import func_a" in code
        assert "from backend.svc import func_b" in code
        assert "test_func_a" in code
        assert "test_func_b" in code

    def test_generate_test_file_empty(self) -> None:
        supplement = TestSupplement()
        code = supplement.generate_test_file([])
        assert code == ""


class TestUntestedFunction:
    """UntestedFunction 数据类测试。"""

    def test_basic(self) -> None:
        f = UntestedFunction(
            name="my_func",
            module="backend.svc",
            file_path="backend/svc.py",
            line_number=10,
        )
        assert f.qualified_name == "my_func"
        assert f.is_async is False
        assert f.is_method is False

    def test_qualified_name_with_class(self) -> None:
        f = UntestedFunction(
            name="method",
            module="backend.svc",
            file_path="backend/svc.py",
            line_number=10,
            class_name="MyClass",
        )
        assert f.qualified_name == "MyClass.method"

    def test_defaults(self) -> None:
        f = UntestedFunction(
            name="f",
            module="m",
            file_path="p",
            line_number=1,
        )
        assert f.parameters == []
        assert f.class_name is None


class TestCoverageGaps:
    """get_coverage_gaps 测试。"""

    def test_get_coverage_gaps(self) -> None:
        supplement = TestSupplement()
        coverage_data = {
            "files": {
                "backend/a.py": {"missing_lines": [1, 2, 3]},
                "backend/b.py": {"missing_lines": []},
            }
        }
        gaps = supplement.get_coverage_gaps(coverage_data)
        assert "total_untested" in gaps
        assert "by_module" in gaps
        assert "priority_files" in gaps
