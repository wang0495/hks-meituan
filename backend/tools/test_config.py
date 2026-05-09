"""CityFlow 测试配置：集中管理测试路径、标记、超时等参数。

用法：
    from backend.tools.test_config import TEST_CONFIG, get_test_paths, collect_markers
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

# 项目根目录（向上两级到 backend/tools -> 项目根）
ROOT = Path(__file__).resolve().parent.parent.parent

# 插件可用性检测
_HAS_XDIST = importlib.util.find_spec("xdist") is not None  # type: ignore[attr-defined]
_HAS_TIMEOUT = importlib.util.find_spec("pytest_timeout") is not None  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# 输出文件路径
# ---------------------------------------------------------------------------
JUNIT_XML_PATH = ROOT / "test_results.xml"
COVERAGE_XML_PATH = ROOT / "coverage.xml"
REPORT_HTML_PATH = ROOT / "test_report.html"
COVERAGE_HTML_DIR = ROOT / "coverage_html"

# ---------------------------------------------------------------------------
# 测试目录
# ---------------------------------------------------------------------------
BACKEND_TESTS_DIR = ROOT / "backend" / "tests"
ROOT_TESTS_DIR = ROOT / "tests"


@dataclass(frozen=True)
class TestMarker:
    """pytest 标记定义。"""

    name: str
    description: str
    timeout: int = 0  # 该标记的超时秒数，0 表示使用全局配置


# ---------------------------------------------------------------------------
# 标记注册
# ---------------------------------------------------------------------------
TEST_MARKERS: dict[str, TestMarker] = {
    "slow": TestMarker(
        "slow", "慢速测试（deselect with '-m \"not slow\"'）", timeout=600
    ),
    "integration": TestMarker("integration", "集成测试", timeout=120),
    "e2e": TestMarker("e2e", "端到端测试", timeout=300),
    "unit": TestMarker("unit", "单元测试", timeout=30),
}


@dataclass
class TestConfig:
    """测试运行配置。"""

    # 测试路径（相对于项目根目录）
    test_paths: list[str] = field(default_factory=lambda: ["backend/tests/"])

    # 是否并行运行（需要 pytest-xdist）
    parallel: bool = True

    # 并行 worker 数量，"auto" 表示自动检测 CPU 核心数
    workers: str = "auto"

    # 是否收集覆盖率
    coverage: bool = True

    # 覆盖率目标模块
    coverage_source: str = "backend"

    # 单个测试超时秒数
    timeout: int = 300

    # 是否排除慢速测试
    exclude_slow: bool = True

    # pytest 附加参数
    extra_args: list[str] = field(default_factory=list)

    # 输出路径
    junit_xml: Path = field(default_factory=lambda: JUNIT_XML_PATH)
    coverage_xml: Path = field(default_factory=lambda: COVERAGE_XML_PATH)
    report_html: Path = field(default_factory=lambda: REPORT_HTML_PATH)
    coverage_html_dir: Path = field(default_factory=lambda: COVERAGE_HTML_DIR)


# ---------------------------------------------------------------------------
# 默认配置实例
# ---------------------------------------------------------------------------
TEST_CONFIG = TestConfig()


def discover_test_files(
    directory: Path | None = None,
    pattern: str = "test_*.py",
) -> list[Path]:
    """扫描测试目录，返回所有测试文件路径。

    Args:
        directory: 要扫描的目录，默认 backend/tests
        pattern: 文件名 glob 模式

    Returns:
        测试文件路径列表（绝对路径）
    """
    target = directory or BACKEND_TESTS_DIR
    if not target.exists():
        return []
    return sorted(target.glob(pattern))


def get_test_paths(
    config: TestConfig | None = None,
) -> list[str]:
    """获取配置中所有测试路径（已验证存在）。

    Args:
        config: 测试配置，默认使用 TEST_CONFIG

    Returns:
        存在的测试路径列表
    """
    cfg = config or TEST_CONFIG
    paths: list[str] = []
    for p in cfg.test_paths:
        full = ROOT / p
        if full.exists():
            paths.append(p)
    return paths


def collect_markers(directory: Path | None = None) -> dict[str, int]:
    """扫描测试文件，统计各标记出现次数。

    Args:
        directory: 要扫描的目录，默认 backend/tests

    Returns:
        {marker_name: count} 字典
    """
    import re

    marker_re = re.compile(r"@pytest\.mark\.(\w+)")
    counts: dict[str, int] = {}
    for f in discover_test_files(directory):
        content = f.read_text(encoding="utf-8", errors="ignore")
        for m in marker_re.finditer(content):
            name = m.group(1)
            counts[name] = counts.get(name, 0) + 1
    return counts


def build_pytest_args(
    config: TestConfig | None = None,
    *,
    module: str | None = None,
    markers: list[str] | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    """根据配置构建 pytest 命令行参数列表。

    Args:
        config: 测试配置，默认使用 TEST_CONFIG
        module: 指定单个测试模块/文件
        markers: 只运行指定标记的测试
        extra: 额外附加参数

    Returns:
        完整的 pytest 参数列表（不含 pytest 可执行文件本身）
    """
    cfg = config or TEST_CONFIG
    args: list[str] = []

    # 测试路径
    if module:
        args.append(module)
    else:
        args.extend(get_test_paths(cfg))

    # JUnit XML
    args.extend(["--junitxml", str(cfg.junit_xml)])

    # 覆盖率
    if cfg.coverage:
        args.extend(
            [
                f"--cov={cfg.coverage_source}",
                f"--cov-report=xml:{cfg.coverage_xml}",
                f"--cov-report=html:{cfg.coverage_html_dir}",
                "--cov-report=term-missing",
            ]
        )

    # 并行（需要 pytest-xdist）
    if cfg.parallel and _HAS_XDIST:
        args.extend(["-n", cfg.workers])

    # 超时（需要 pytest-timeout）
    if cfg.timeout > 0 and _HAS_TIMEOUT:
        args.extend(["--timeout", str(cfg.timeout)])

    # 标记过滤
    marker_exprs: list[str] = []
    if cfg.exclude_slow and not markers:
        marker_exprs.append("not slow")
    if markers:
        marker_exprs.extend(markers)
    if marker_exprs:
        args.extend(["-m", " and ".join(marker_exprs)])

    # 详细输出 + 短回溯
    args.extend(["-v", "--tb=short"])

    # 额外参数
    args.extend(cfg.extra_args)
    if extra:
        args.extend(extra)

    return args


def filter_test_files(
    pattern: str,
    directory: Path | None = None,
) -> list[Path]:
    """按名称模式过滤测试文件。

    Args:
        pattern: 名称匹配模式（子字符串匹配，不区分大小写）
        directory: 要扫描的目录，默认 backend/tests

    Returns:
        匹配的测试文件路径列表
    """
    all_files = discover_test_files(directory)
    if not pattern:
        return all_files
    lower_pattern = pattern.lower()
    return [f for f in all_files if lower_pattern in f.stem.lower()]


def get_marker_timeout(marker_name: str, default: int = 300) -> int:
    """获取指定标记的超时时间。

    Args:
        marker_name: 标记名称
        default: 默认超时秒数

    Returns:
        超时秒数
    """
    marker = TEST_MARKERS.get(marker_name)
    if marker and marker.timeout > 0:
        return marker.timeout
    return default
