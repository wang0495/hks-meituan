"""CityFlow 配置管理器。

集中管理 YAML / JSON 配置文件的加载、读取、更新和持久化。
可独立使用，也可与 ``ConfigHotReloader`` 集成实现热更新。

用法::

    from backend.config.manager import ConfigManager

    manager = ConfigManager(config_dir="config")
    manager.load_all()

    # 读取
    value = manager.get("app", "database.host")

    # 更新（内存 + 持久化）
    manager.set("app", "database.port", 5433, persist=True)

    # 集成热更新
    from backend.config.hot_reload import ConfigHotReloader
    reloader = ConfigHotReloader(config_dir="config")
    manager.bind_reloader(reloader)
    reloader.start()
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import yaml

from backend.config.hot_reload import ConfigHotReloader
from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

# 支持的后缀及对应的 loader / dumper
_LOADER_MAP: dict[str, Any] = {
    ".yaml": yaml.safe_load,
    ".yml": yaml.safe_load,
    ".json": json.loads,
}


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class ConfigManagerError(CityFlowException):
    """配置管理器错误。"""

    def __init__(
        self,
        message: str = "配置管理错误",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            details=details,
        )


# ---------------------------------------------------------------------------
# 配置管理器
# ---------------------------------------------------------------------------


class ConfigManager:
    """配置管理器。

    Args:
        config_dir: 配置文件目录。
    """

    def __init__(self, config_dir: str | Path = "config") -> None:
        self._config_dir = Path(config_dir)
        self._configs: dict[str, dict[str, Any]] = {}
        self._sources: dict[str, Path] = {}  # 配置名 -> 原始文件路径
        self._reloader: ConfigHotReloader | None = None

    # ---- 加载 ----

    def load_all(self) -> dict[str, dict[str, Any]]:
        """加载目录下所有配置文件。

        Returns:
            {配置名: 配置内容} 的字典。
        """
        if not self._config_dir.is_dir():
            raise ConfigManagerError(
                message=f"配置目录不存在: {self._config_dir}",
                details={"dir": str(self._config_dir)},
            )

        results: dict[str, dict[str, Any]] = {}
        for config_file in self._iter_config_files():
            name = config_file.stem
            results[name] = self._load_single(config_file)

        logger.info("已加载 %d 个配置文件", len(results))
        return results

    def load(self, config_name: str) -> dict[str, Any]:
        """加载单个配置文件。

        Args:
            config_name: 配置名（不含扩展名）。

        Returns:
            配置内容。

        Raises:
            ConfigManagerError: 文件不存在或解析失败时抛出。
        """
        file_path = self._find_config_file(config_name)
        if file_path is None:
            raise ConfigManagerError(
                message=f"找不到配置文件: {config_name}",
                details={"config_name": config_name, "dir": str(self._config_dir)},
            )
        return self._load_single(file_path)

    # ---- 读取 ----

    def get(self, config_name: str, key: str | None = None, default: Any = None) -> Any:
        """获取配置值。

        Args:
            config_name: 配置名。
            key: 点分隔的键路径（如 ``"database.host"``）。
                 为 None 时返回整个配置。
            default: 键不存在时的默认值。

        Returns:
            配置值。
        """
        config = self._configs.get(config_name)
        if config is None:
            return default
        if key is None:
            return copy.deepcopy(config)

        # 点分隔嵌套查找
        parts = key.split(".")
        current: Any = config
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return default
            if current is None:
                return default
        return current

    def get_all(self) -> dict[str, dict[str, Any]]:
        """获取所有配置的深拷贝。"""
        return copy.deepcopy(self._configs)

    # ---- 更新 ----

    def set(
        self,
        config_name: str,
        key: str,
        value: Any,
        *,
        persist: bool = False,
    ) -> None:
        """设置配置值。

        Args:
            config_name: 配置名。
            key: 点分隔的键路径。
            value: 要设置的值。
            persist: 是否同时写入文件。
        """
        config = self._configs.get(config_name)
        if config is None:
            config = {}
            self._configs[config_name] = config

        # 点分隔路径赋值
        parts = key.split(".")
        current = config
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

        logger.debug("配置已更新: %s.%s = %s", config_name, key, value)

        if persist:
            self.persist(config_name)

    def update(
        self,
        config_name: str,
        data: dict[str, Any],
        *,
        deep: bool = True,
        persist: bool = False,
    ) -> None:
        """批量更新配置。

        Args:
            config_name: 配置名。
            data: 要合并的数据。
            deep: 是否深度合并（True 递归合并 dict，False 直接覆盖）。
            persist: 是否同时写入文件。
        """
        config = self._configs.get(config_name, {})
        if deep:
            config = self._deep_merge(config, data)
        else:
            config.update(data)
        self._configs[config_name] = config

        if persist:
            self.persist(config_name)

    # ---- 持久化 ----

    def persist(self, config_name: str) -> None:
        """将内存中的配置写回文件。

        使用与原文件相同的格式（YAML / JSON）。
        若未知原始格式，默认 YAML。
        """
        config = self._configs.get(config_name)
        if config is None:
            raise ConfigManagerError(
                message=f"配置不存在: {config_name}",
                details={"config_name": config_name},
            )

        source = self._sources.get(config_name)
        if source is not None:
            target = source
        else:
            target = self._config_dir / f"{config_name}.yaml"

        target.parent.mkdir(parents=True, exist_ok=True)

        if target.suffix == ".json":
            text = json.dumps(config, ensure_ascii=False, indent=2)
        else:
            text = yaml.dump(
                config,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        target.write_text(text, encoding="utf-8")
        logger.info("配置已持久化: %s -> %s", config_name, target)

    # ---- 热更新集成 ----

    def bind_reloader(self, reloader: ConfigHotReloader) -> None:
        """绑定热更新器，自动同步配置变更。

        绑定后，reloader 监听到的配置变更会自动同步到 manager。
        """
        self._reloader = reloader

        # 为每个已加载的配置注册回调
        for config_name in self._configs:
            reloader.watch(config_name, self._make_sync_callback(config_name))

        logger.info("ConfigManager 已绑定 ConfigHotReloader")

    def _make_sync_callback(self, config_name: str) -> Any:
        """创建同步回调。"""

        def _sync(config: dict[str, Any]) -> None:
            self._configs[config_name] = copy.deepcopy(config)
            logger.debug("ConfigManager 已同步配置: %s", config_name)

        return _sync

    # ---- 内部方法 ----

    def _find_config_file(self, config_name: str) -> Path | None:
        """查找配置文件。"""
        for ext in _LOADER_MAP:
            candidate = self._config_dir / f"{config_name}{ext}"
            if candidate.is_file():
                return candidate
        return None

    def _iter_config_files(self) -> list[Path]:
        """列出所有配置文件。"""
        files: list[Path] = []
        for ext in _LOADER_MAP:
            files.extend(self._config_dir.glob(f"*{ext}"))
        return sorted(files)

    def _load_single(self, file_path: Path) -> dict[str, Any]:
        """加载并解析单个配置文件。"""
        suffix = file_path.suffix
        loader = _LOADER_MAP.get(suffix)
        if loader is None:
            raise ConfigManagerError(
                message=f"不支持的配置文件格式: {suffix}",
                details={"file": str(file_path)},
            )

        try:
            text = file_path.read_text(encoding="utf-8")
            result = loader(text)
        except (yaml.YAMLError, json.JSONDecodeError, OSError) as exc:
            raise ConfigManagerError(
                message=f"配置文件加载失败: {file_path.name}",
                details={"file": str(file_path), "error": str(exc)},
            ) from exc

        if not isinstance(result, dict):
            raise ConfigManagerError(
                message=f"配置文件顶层必须是对象: {file_path.name}",
                details={"file": str(file_path), "got_type": type(result).__name__},
            )

        name = file_path.stem
        self._configs[name] = result
        self._sources[name] = file_path
        logger.debug("已加载配置: %s (%s)", name, file_path)
        return result

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """深度合并两个字典（override 覆盖 base）。"""
        result = copy.deepcopy(base)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result
