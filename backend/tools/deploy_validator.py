"""CityFlow 部署验证工具。

验证 Docker 配置、Docker Compose 配置、健康检查端点。
可独立运行，也可作为模块导入。
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class CheckStatus(StrEnum):
    """检查状态。"""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class CheckResult:
    """单项检查结果。"""

    name: str
    status: CheckStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.status == CheckStatus.PASS


@dataclass
class ValidationReport:
    """部署验证报告。"""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def overall_success(self) -> bool:
        """所有检查通过（跳过的不算失败）。"""
        return all(
            c.status in (CheckStatus.PASS, CheckStatus.SKIP) for c in self.checks
        )

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)

    @property
    def errors(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.ERROR)

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.SKIP)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_success": self.overall_success,
            "summary": {
                "passed": self.passed,
                "failed": self.failed,
                "errors": self.errors,
                "skipped": self.skipped,
                "total": len(self.checks),
            },
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "details": c.details,
                    "duration_ms": round(c.duration_ms, 1),
                }
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str] | None:
    """执行外部命令，返回结果。命令不存在时返回 None。"""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or PROJECT_ROOT,
            timeout=timeout,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def _timed(fn: Any, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    """执行函数并返回 (结果, 耗时毫秒)。"""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    return result, elapsed


# ---------------------------------------------------------------------------
# 部署验证器
# ---------------------------------------------------------------------------


class DeployValidator:
    """CityFlow 部署验证器。

    验证项目：
    1. Dockerfile 语法与构建
    2. Docker Compose 配置校验
    3. 健康检查端点可用性
    4. 环境变量完整性
    5. 关键文件存在性
    """

    def __init__(
        self,
        project_root: Path | None = None,
        health_url: str = "http://localhost:8000/health",
        compose_file: str = "docker-compose.yml",
    ) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self.health_url = health_url
        self.compose_file = compose_file

    # ------------------------------------------------------------------
    # 1. Dockerfile 验证
    # ------------------------------------------------------------------

    def validate_dockerfile(self) -> CheckResult:
        """验证 Dockerfile 是否存在且可构建。"""
        dockerfile = self.project_root / "Dockerfile"
        dockerfile_opt = self.project_root / "Dockerfile.optimized"

        # 检查文件存在
        if not dockerfile.exists() and not dockerfile_opt.exists():
            return CheckResult(
                name="Dockerfile 存在性",
                status=CheckStatus.FAIL,
                message="未找到 Dockerfile 或 Dockerfile.optimized",
            )

        # 尝试语法校验（docker build --check 仅在 BuildKit 支持时可用）
        # 退而求其次：用 --no-cache 构建测试镜像
        target = dockerfile if dockerfile.exists() else dockerfile_opt
        result, elapsed = _timed(
            _run_cmd,
            [
                "docker",
                "build",
                "-f",
                str(target),
                "-t",
                "cityflow-deploy-test",
                "--no-cache",
                ".",
            ],
        )

        if result is None:
            return CheckResult(
                name="Dockerfile 构建",
                status=CheckStatus.ERROR,
                message="docker 命令不可用，请确认已安装 Docker Desktop",
            )

        if result.returncode == 0:
            return CheckResult(
                name="Dockerfile 构建",
                status=CheckStatus.PASS,
                message=f"Docker 镜像构建成功 ({target.name})",
                duration_ms=elapsed,
            )

        return CheckResult(
            name="Dockerfile 构建",
            status=CheckStatus.FAIL,
            message="Docker 镜像构建失败",
            details={
                "stdout": result.stdout[-1000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
            },
            duration_ms=elapsed,
        )

    def validate_dockerfile_content(self) -> CheckResult:
        """静态检查 Dockerfile 内容是否包含关键指令。"""
        dockerfile = self.project_root / "Dockerfile.optimized"
        if not dockerfile.exists():
            dockerfile = self.project_root / "Dockerfile"
        if not dockerfile.exists():
            return CheckResult(
                name="Dockerfile 内容检查",
                status=CheckStatus.SKIP,
                message="未找到 Dockerfile",
            )

        content = dockerfile.read_text(encoding="utf-8")
        required = ["FROM", "WORKDIR", "COPY", "EXPOSE", "CMD"]
        missing = [kw for kw in required if kw not in content]

        if missing:
            return CheckResult(
                name="Dockerfile 内容检查",
                status=CheckStatus.FAIL,
                message=f"缺少关键指令: {', '.join(missing)}",
                details={"missing": missing},
            )

        # 检查 HEALTHCHECK
        has_healthcheck = "HEALTHCHECK" in content
        return CheckResult(
            name="Dockerfile 内容检查",
            status=CheckStatus.PASS,
            message="Dockerfile 包含所有关键指令"
            + (
                " (含 HEALTHCHECK)"
                if has_healthcheck
                else " (无 HEALTHCHECK，建议添加)"
            ),
            details={"has_healthcheck": has_healthcheck},
        )

    # ------------------------------------------------------------------
    # 2. Docker Compose 验证
    # ------------------------------------------------------------------

    def validate_compose_config(self) -> CheckResult:
        """验证 docker-compose.yml 配置语法。"""
        compose_path = self.project_root / self.compose_file
        if not compose_path.exists():
            return CheckResult(
                name="Docker Compose 配置",
                status=CheckStatus.FAIL,
                message=f"未找到 {self.compose_file}",
            )

        result, elapsed = _timed(
            _run_cmd,
            ["docker-compose", "-f", str(compose_path), "config"],
        )

        if result is None:
            return CheckResult(
                name="Docker Compose 配置",
                status=CheckStatus.ERROR,
                message="docker-compose 命令不可用，请确认已安装 Docker Desktop",
            )

        if result.returncode == 0:
            return CheckResult(
                name="Docker Compose 配置",
                status=CheckStatus.PASS,
                message="Docker Compose 配置语法正确",
                duration_ms=elapsed,
            )

        return CheckResult(
            name="Docker Compose 配置",
            status=CheckStatus.FAIL,
            message="Docker Compose 配置校验失败",
            details={"stderr": result.stderr[-500:] if result.stderr else ""},
            duration_ms=elapsed,
        )

    def validate_compose_services(self) -> CheckResult:
        """检查 compose 文件中是否定义了必要的服务。"""
        compose_path = self.project_root / self.compose_file
        if not compose_path.exists():
            return CheckResult(
                name="Compose 服务定义",
                status=CheckStatus.SKIP,
                message=f"未找到 {self.compose_file}",
            )

        result = _run_cmd(
            ["docker-compose", "-f", str(compose_path), "config", "--services"],
        )

        if result is None:
            return CheckResult(
                name="Compose 服务定义",
                status=CheckStatus.ERROR,
                message="docker-compose 命令不可用，请确认已安装 Docker Desktop",
            )

        if result.returncode != 0:
            return CheckResult(
                name="Compose 服务定义",
                status=CheckStatus.ERROR,
                message="无法解析 Compose 服务列表",
                details={"stderr": result.stderr[-300:]},
            )

        services = {s.strip() for s in result.stdout.strip().splitlines() if s.strip()}
        required_services = {"nginx", "backend1", "redis"}
        missing = required_services - services

        if missing:
            return CheckResult(
                name="Compose 服务定义",
                status=CheckStatus.FAIL,
                message=f"缺少必要服务: {', '.join(sorted(missing))}",
                details={"found": sorted(services), "missing": sorted(missing)},
            )

        return CheckResult(
            name="Compose 服务定义",
            status=CheckStatus.PASS,
            message=f"已定义 {len(services)} 个服务: {', '.join(sorted(services))}",
            details={"services": sorted(services)},
        )

    # ------------------------------------------------------------------
    # 3. 健康检查验证
    # ------------------------------------------------------------------

    def validate_health_endpoint(self) -> CheckResult:
        """验证健康检查端点是否可达。"""
        try:
            import urllib.error
            import urllib.request

            start = time.perf_counter()
            req = urllib.request.Request(self.health_url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                elapsed = (time.perf_counter() - start) * 1000
                data = json.loads(body)

            status_ok = data.get("status") == "healthy"
            return CheckResult(
                name="健康检查端点",
                status=CheckStatus.PASS if status_ok else CheckStatus.FAIL,
                message=f"健康检查返回 status={data.get('status', 'unknown')}",
                details={
                    "response": data,
                    "latency_ms": round(elapsed, 1),
                },
                duration_ms=elapsed,
            )

        except urllib.error.URLError as exc:
            return CheckResult(
                name="健康检查端点",
                status=CheckStatus.FAIL,
                message=f"无法连接健康检查端点: {self.health_url}",
                details={"error": str(exc.reason)},
            )
        except (json.JSONDecodeError, KeyError) as exc:
            return CheckResult(
                name="健康检查端点",
                status=CheckStatus.FAIL,
                message="健康检查响应格式异常",
                details={"error": str(exc)},
            )
        except Exception as exc:
            return CheckResult(
                name="健康检查端点",
                status=CheckStatus.ERROR,
                message=f"健康检查发生未知错误: {exc}",
            )

    def validate_compose_healthchecks(self) -> CheckResult:
        """检查 compose 文件中是否为服务定义了 healthcheck。"""
        compose_path = self.project_root / self.compose_file
        if not compose_path.exists():
            return CheckResult(
                name="Compose Healthcheck 定义",
                status=CheckStatus.SKIP,
                message=f"未找到 {self.compose_file}",
            )

        content = compose_path.read_text(encoding="utf-8")
        has_healthcheck = "healthcheck" in content.lower()

        if not has_healthcheck:
            return CheckResult(
                name="Compose Healthcheck 定义",
                status=CheckStatus.FAIL,
                message="docker-compose.yml 中未定义 healthcheck",
            )

        return CheckResult(
            name="Compose Healthcheck 定义",
            status=CheckStatus.PASS,
            message="docker-compose.yml 中已定义 healthcheck",
        )

    # ------------------------------------------------------------------
    # 4. 环境变量验证
    # ------------------------------------------------------------------

    def validate_env_files(self) -> CheckResult:
        """检查必要的环境变量文件是否存在。"""
        required_files = [".env.example"]
        optional_files = [".env.dev", ".env.prod", ".env.test"]
        missing_required = [
            f for f in required_files if not (self.project_root / f).exists()
        ]
        missing_optional = [
            f for f in optional_files if not (self.project_root / f).exists()
        ]

        if missing_required:
            return CheckResult(
                name="环境变量文件",
                status=CheckStatus.FAIL,
                message=f"缺少必要文件: {', '.join(missing_required)}",
                details={"missing_required": missing_required},
            )

        msg = (
            "环境变量文件齐全"
            if not missing_optional
            else f"缺少可选文件: {', '.join(missing_optional)}"
        )
        return CheckResult(
            name="环境变量文件",
            status=CheckStatus.PASS if not missing_optional else CheckStatus.PASS,
            message=msg,
            details={"missing_optional": missing_optional} if missing_optional else {},
        )

    # ------------------------------------------------------------------
    # 5. 关键文件验证
    # ------------------------------------------------------------------

    def validate_critical_files(self) -> CheckResult:
        """检查部署所需的关键文件是否存在。"""
        critical = [
            "requirements.txt",
            "backend/main.py",
            "docker-compose.yml",
        ]
        missing = [f for f in critical if not (self.project_root / f).exists()]

        if missing:
            return CheckResult(
                name="关键文件存在性",
                status=CheckStatus.FAIL,
                message=f"缺少关键文件: {', '.join(missing)}",
                details={"missing": missing},
            )

        return CheckResult(
            name="关键文件存在性",
            status=CheckStatus.PASS,
            message=f"所有 {len(critical)} 个关键文件均存在",
        )

    # ------------------------------------------------------------------
    # 6. Nginx 配置验证
    # ------------------------------------------------------------------

    def validate_nginx_config(self) -> CheckResult:
        """检查 Nginx 配置文件是否存在。"""
        nginx_conf = self.project_root / "nginx" / "nginx.conf"
        if not nginx_conf.exists():
            return CheckResult(
                name="Nginx 配置",
                status=CheckStatus.SKIP,
                message="未找到 nginx/nginx.conf，跳过",
            )

        content = nginx_conf.read_text(encoding="utf-8")
        has_upstream = "upstream" in content
        has_proxy = "proxy_pass" in content

        issues = []
        if not has_upstream:
            issues.append("缺少 upstream 定义")
        if not has_proxy:
            issues.append("缺少 proxy_pass 指令")

        if issues:
            return CheckResult(
                name="Nginx 配置",
                status=CheckStatus.WARNING if not issues else CheckStatus.FAIL,
                message=f"Nginx 配置问题: {'; '.join(issues)}",
                details={"issues": issues},
            )

        return CheckResult(
            name="Nginx 配置",
            status=CheckStatus.PASS,
            message="Nginx 配置包含 upstream 和 proxy_pass",
        )

    # ------------------------------------------------------------------
    # 汇总
    # ------------------------------------------------------------------

    def validate_all(
        self, skip_build: bool = False, skip_health: bool = False
    ) -> ValidationReport:
        """运行所有验证检查。

        Args:
            skip_build: 跳过 Docker 构建测试（耗时较长）。
            skip_health: 跳过健康检查端点测试（需要服务运行中）。
        """
        report = ValidationReport()

        # 文件级检查（快速）
        report.checks.append(self.validate_critical_files())
        report.checks.append(self.validate_env_files())
        report.checks.append(self.validate_dockerfile_content())
        report.checks.append(self.validate_compose_config())
        report.checks.append(self.validate_compose_services())
        report.checks.append(self.validate_compose_healthchecks())
        report.checks.append(self.validate_nginx_config())

        # 构建检查（可选，耗时）
        if skip_build:
            report.checks.append(
                CheckResult(
                    name="Dockerfile 构建",
                    status=CheckStatus.SKIP,
                    message="已跳过 (--skip-build)",
                )
            )
        else:
            report.checks.append(self.validate_dockerfile())

        # 健康检查（可选，需要服务运行）
        if skip_health:
            report.checks.append(
                CheckResult(
                    name="健康检查端点",
                    status=CheckStatus.SKIP,
                    message="已跳过 (--skip-health)",
                )
            )
        else:
            report.checks.append(self.validate_health_endpoint())

        return report
