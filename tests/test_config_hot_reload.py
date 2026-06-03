"""ConfigHotReloader 和 ConfigManager 测试。

覆盖：
- 配置文件加载（YAML / JSON）
- 文件监听启动/停止
- 变更回调通知
- 防抖行为
- 版本历史与回滚
- ConfigManager 的 CRUD + 持久化
- 两者集成
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from backend.config.hot_reload import (
    ConfigHotReloader,
    ConfigReloadError,
    ConfigRollbackError,
    ConfigSnapshot,
)
from backend.config.manager import ConfigManager, ConfigManagerError

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """创建临时配置目录并写入初始配置。"""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()

    # YAML 配置
    app_config = {
        "app": {"name": "CityFlow", "port": 8000},
        "database": {"host": "localhost", "port": 5432},
    }
    (cfg_dir / "app.yaml").write_text(yaml.dump(app_config, allow_unicode=True), encoding="utf-8")

    # JSON 配置
    feature_flags = {"enable_cache": True, "max_retries": 3}
    (cfg_dir / "features.json").write_text(
        json.dumps(feature_flags, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return cfg_dir


@pytest.fixture
def reloader(config_dir: Path) -> ConfigHotReloader:
    """创建 ConfigHotReloader 实例（不自动启动）。"""
    return ConfigHotReloader(config_dir=config_dir, max_history=5, debounce_seconds=0.1)


@pytest.fixture
def manager(config_dir: Path) -> ConfigManager:
    """创建 ConfigManager 实例。"""
    return ConfigManager(config_dir=config_dir)


# ---------------------------------------------------------------------------
# ConfigHotReloader 测试
# ---------------------------------------------------------------------------


class TestConfigHotReloader:
    """ConfigHotReloader 单元测试。"""

    def test_load_yaml_config(self, config_dir: Path) -> None:
        """应能加载 YAML 配置。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.reload("app")
        assert r.get("app", "app.name") == "CityFlow"
        assert r.get("app", "database.port") == 5432

    def test_load_json_config(self, config_dir: Path) -> None:
        """应能加载 JSON 配置。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.reload("features")
        assert r.get("features", "enable_cache") is True
        assert r.get("features", "max_retries") == 3

    def test_get_entire_config(self, config_dir: Path) -> None:
        """key=None 时返回整个配置。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.reload("app")
        config = r.get("app")
        assert isinstance(config, dict)
        assert "app" in config

    def test_get_missing_config_returns_none(self, config_dir: Path) -> None:
        """不存在的配置返回 None。"""
        r = ConfigHotReloader(config_dir=config_dir)
        assert r.get("nonexistent") is None

    def test_get_missing_key_returns_none(self, config_dir: Path) -> None:
        """不存在的键返回 None。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.reload("app")
        assert r.get("app", "nonexistent.key") is None

    def test_reload_nonexistent_raises(self, config_dir: Path) -> None:
        """重载不存在的配置应抛出 ConfigReloadError。"""
        r = ConfigHotReloader(config_dir=config_dir)
        with pytest.raises(ConfigReloadError, match="找不到配置文件"):
            r.reload("nonexistent")

    def test_get_all(self, config_dir: Path) -> None:
        """get_all 返回所有已加载配置的拷贝。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.reload("app")
        r.reload("features")
        all_configs = r.get_all()
        assert "app" in all_configs
        assert "features" in all_configs
        # 修改拷贝不影响原始
        all_configs["app"]["app"]["name"] = "modified"
        assert r.get("app", "app.name") == "CityFlow"

    def test_start_stop(self, config_dir: Path) -> None:
        """启动和停止监听不应抛异常。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.start()
        assert r.is_running
        r.stop()
        assert not r.is_running

    def test_start_nonexistent_dir_raises(self, tmp_path: Path) -> None:
        """目录不存在时启动应抛出 RuntimeError。"""
        r = ConfigHotReloader(config_dir=tmp_path / "nope")
        with pytest.raises(RuntimeError, match="配置目录不存在"):
            r.start()

    def test_stop_when_not_running(self, config_dir: Path) -> None:
        """未运行时调用 stop 不应抛异常。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.stop()  # no-op

    def test_double_start(self, config_dir: Path) -> None:
        """重复 start 不应抛异常。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.start()
        r.start()  # 应被忽略
        assert r.is_running
        r.stop()

    def test_watcher_notification(self, config_dir: Path) -> None:
        """配置变更时应通知观察者。"""
        r = ConfigHotReloader(config_dir=config_dir)
        received: list[dict[str, Any]] = []

        def on_change(config: dict[str, Any]) -> None:
            received.append(config)

        r.watch("app", on_change)
        r.reload("app")

        assert len(received) == 1
        assert received[0]["app"]["name"] == "CityFlow"

    def test_multiple_watchers(self, config_dir: Path) -> None:
        """多个观察者都应被通知。"""
        r = ConfigHotReloader(config_dir=config_dir)
        calls_a: list[bool] = []
        calls_b: list[bool] = []

        r.watch("app", lambda c: calls_a.append(True))
        r.watch("app", lambda c: calls_b.append(True))
        r.reload("app")

        assert len(calls_a) == 1
        assert len(calls_b) == 1

    def test_unwatch(self, config_dir: Path) -> None:
        """移除观察者后不再收到通知。"""
        r = ConfigHotReloader(config_dir=config_dir)
        calls: list[bool] = []

        def cb(config: dict[str, Any]) -> None:
            calls.append(True)

        r.watch("app", cb)
        r.reload("app")
        assert len(calls) == 1

        r.unwatch("app", cb)
        r.reload("app")
        assert len(calls) == 1  # 不再增加

    def test_unwatch_nonexistent(self, config_dir: Path) -> None:
        """移除未注册的回调不应抛异常。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.unwatch("app", lambda c: None)  # no-op

    @pytest.mark.asyncio
    async def test_async_watcher(self, config_dir: Path) -> None:
        """异步观察者应被正确调度。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r._loop = asyncio.get_running_loop()
        received: list[dict[str, Any]] = []

        async def on_change(config: dict[str, Any]) -> None:
            received.append(config)

        r.watch("app", on_change)
        r.reload("app")

        # 等待异步调度
        await asyncio.sleep(0.1)
        assert len(received) == 1

    # ---- 版本历史与回滚 ----

    def test_history_recorded(self, config_dir: Path) -> None:
        """每次重载应产生历史快照。"""
        r = ConfigHotReloader(config_dir=config_dir, max_history=5)
        r.reload("app")

        # 写入新配置
        new_config = {"app": {"name": "CityFlow-v2", "port": 9000}}
        (config_dir / "app.yaml").write_text(
            yaml.dump(new_config, allow_unicode=True), encoding="utf-8"
        )
        r.reload("app")

        history = r.get_history("app")
        assert len(history) == 1
        assert history[0].config["app"]["name"] == "CityFlow"

    def test_rollback(self, config_dir: Path) -> None:
        """回滚应恢复到上一版本。"""
        r = ConfigHotReloader(config_dir=config_dir, max_history=5)
        r.reload("app")

        # 写入新版本
        new_config = {"app": {"name": "CityFlow-v2", "port": 9000}}
        (config_dir / "app.yaml").write_text(
            yaml.dump(new_config, allow_unicode=True), encoding="utf-8"
        )
        r.reload("app")
        assert r.get("app", "app.name") == "CityFlow-v2"

        # 回滚
        rolled = r.rollback("app")
        assert rolled["app"]["name"] == "CityFlow"
        assert r.get("app", "app.name") == "CityFlow"

    def test_rollback_multiple_steps(self, config_dir: Path) -> None:
        """多步回滚。"""
        r = ConfigHotReloader(config_dir=config_dir, max_history=10)

        # v1
        r.reload("app")

        # v2
        v2 = {"app": {"name": "v2", "port": 9001}}
        (config_dir / "app.yaml").write_text(yaml.dump(v2), encoding="utf-8")
        r.reload("app")

        # v3
        v3 = {"app": {"name": "v3", "port": 9002}}
        (config_dir / "app.yaml").write_text(yaml.dump(v3), encoding="utf-8")
        r.reload("app")

        assert r.get("app", "app.name") == "v3"

        # 回滚 2 步
        r.rollback("app", steps=2)
        assert r.get("app", "app.name") == "CityFlow"

    def test_rollback_no_history_raises(self, config_dir: Path) -> None:
        """无历史版本时回滚应抛出 ConfigRollbackError。"""
        r = ConfigHotReloader(config_dir=config_dir)
        r.reload("app")

        with pytest.raises(ConfigRollbackError, match="没有足够的历史版本"):
            r.rollback("app")

    def test_rollback_too_many_steps_raises(self, config_dir: Path) -> None:
        """回滚步数超出历史时应抛出 ConfigRollbackError。"""
        r = ConfigHotReloader(config_dir=config_dir, max_history=5)
        r.reload("app")

        new_config = {"app": {"name": "v2", "port": 9001}}
        (config_dir / "app.yaml").write_text(yaml.dump(new_config), encoding="utf-8")
        r.reload("app")

        with pytest.raises(ConfigRollbackError, match="没有足够的历史版本"):
            r.rollback("app", steps=5)

    def test_rollback_notifies_watchers(self, config_dir: Path) -> None:
        """回滚时应通知观察者。"""
        r = ConfigHotReloader(config_dir=config_dir, max_history=5)
        received: list[str] = []

        def on_change(config: dict[str, Any]) -> None:
            received.append(config["app"]["name"])

        r.watch("app", on_change)
        r.reload("app")

        new_config = {"app": {"name": "v2", "port": 9001}}
        (config_dir / "app.yaml").write_text(yaml.dump(new_config), encoding="utf-8")
        r.reload("app")

        r.rollback("app")
        assert "CityFlow" in received

    def test_max_history_limit(self, config_dir: Path) -> None:
        """历史版本数不应超过 max_history。"""
        r = ConfigHotReloader(config_dir=config_dir, max_history=3)

        for i in range(5):
            cfg = {"app": {"name": f"v{i}", "port": 8000 + i}}
            (config_dir / "app.yaml").write_text(yaml.dump(cfg), encoding="utf-8")
            r.reload("app")

        history = r.get_history("app")
        assert len(history) <= 3

    def test_snapshot_to_dict(self) -> None:
        """ConfigSnapshot.to_dict 应返回正确结构。"""
        snap = ConfigSnapshot(
            config={"key": "value"},
            timestamp=1234567890.0,
            source="/path/to/config.yaml",
        )
        d = snap.to_dict()
        assert d["config"] == {"key": "value"}
        assert d["timestamp"] == 1234567890.0
        assert d["source"] == "/path/to/config.yaml"

    # ---- reload_all ----

    def test_reload_all(self, config_dir: Path) -> None:
        """reload_all 应加载目录下所有配置。"""
        r = ConfigHotReloader(config_dir=config_dir)
        results = r.reload_all()
        assert "app" in results
        assert "features" in results

    # ---- 文件监听集成 ----

    def test_file_change_triggers_reload(self, config_dir: Path) -> None:
        """修改文件后应自动重载。"""
        r = ConfigHotReloader(config_dir=config_dir, debounce_seconds=0.1)
        received: list[str] = []
        r.watch("app", lambda c: received.append(c["app"]["name"]))
        r.start()

        try:
            # 修改文件
            new_config = {"app": {"name": "auto-reloaded", "port": 8000}}
            (config_dir / "app.yaml").write_text(yaml.dump(new_config), encoding="utf-8")

            # 等待 watchdog 检测
            time.sleep(1.5)
            assert "auto-reloaded" in received
        finally:
            r.stop()

    def test_new_file_triggers_reload(self, config_dir: Path) -> None:
        """新增配置文件应被检测。"""
        r = ConfigHotReloader(config_dir=config_dir, debounce_seconds=0.1)
        received: list[str] = []
        r.watch("new_cfg", lambda c: received.append("loaded"))
        r.start()

        try:
            new_config = {"option": True}
            (config_dir / "new_cfg.yaml").write_text(yaml.dump(new_config), encoding="utf-8")
            time.sleep(1.5)
            assert "loaded" in received
        finally:
            r.stop()

    # ---- 错误处理 ----

    def test_invalid_yaml_continues(self, config_dir: Path) -> None:
        """无效 YAML 文件应抛出 ConfigReloadError。"""
        r = ConfigHotReloader(config_dir=config_dir)
        (config_dir / "bad.yaml").write_text("{{invalid yaml::", encoding="utf-8")
        with pytest.raises(ConfigReloadError):
            r.reload("bad")

    def test_non_dict_yaml_raises(self, config_dir: Path) -> None:
        """顶层不是 dict 的 YAML 应抛出 ConfigReloadError。"""
        r = ConfigHotReloader(config_dir=config_dir)
        (config_dir / "list_cfg.yaml").write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ConfigReloadError, match="顶层必须是对象"):
            r.reload("list_cfg")


# ---------------------------------------------------------------------------
# ConfigManager 测试
# ---------------------------------------------------------------------------


class TestConfigManager:
    """ConfigManager 单元测试。"""

    def test_load_all(self, config_dir: Path) -> None:
        """应加载目录下所有配置。"""
        m = ConfigManager(config_dir=config_dir)
        results = m.load_all()
        assert "app" in results
        assert "features" in results

    def test_load_single(self, config_dir: Path) -> None:
        """应能加载单个配置。"""
        m = ConfigManager(config_dir=config_dir)
        config = m.load("app")
        assert config["app"]["name"] == "CityFlow"

    def test_load_nonexistent_raises(self, config_dir: Path) -> None:
        """加载不存在的配置应抛出 ConfigManagerError。"""
        m = ConfigManager(config_dir=config_dir)
        with pytest.raises(ConfigManagerError, match="找不到配置文件"):
            m.load("nonexistent")

    def test_load_nonexistent_dir_raises(self, tmp_path: Path) -> None:
        """目录不存在时 load_all 应抛出 ConfigManagerError。"""
        m = ConfigManager(config_dir=tmp_path / "nope")
        with pytest.raises(ConfigManagerError, match="配置目录不存在"):
            m.load_all()

    def test_get_simple(self, config_dir: Path) -> None:
        """简单键值读取。"""
        m = ConfigManager(config_dir=config_dir)
        m.load_all()
        assert m.get("app", "app.name") == "CityFlow"

    def test_get_nested(self, config_dir: Path) -> None:
        """嵌套键读取。"""
        m = ConfigManager(config_dir=config_dir)
        m.load_all()
        assert m.get("app", "database.host") == "localhost"

    def test_get_entire_config(self, config_dir: Path) -> None:
        """key=None 返回整个配置。"""
        m = ConfigManager(config_dir=config_dir)
        m.load_all()
        config = m.get("app")
        assert isinstance(config, dict)

    def test_get_default(self, config_dir: Path) -> None:
        """不存在时返回默认值。"""
        m = ConfigManager(config_dir=config_dir)
        m.load_all()
        assert m.get("app", "missing.key", default="fallback") == "fallback"
        assert m.get("nonexistent", default={}) == {}

    def test_set_simple(self, config_dir: Path) -> None:
        """简单键值设置。"""
        m = ConfigManager(config_dir=config_dir)
        m.load("app")
        m.set("app", "app.port", 9999)
        assert m.get("app", "app.port") == 9999

    def test_set_creates_config(self, config_dir: Path) -> None:
        """设置不存在的配置名时应自动创建。"""
        m = ConfigManager(config_dir=config_dir)
        m.set("new", "key", "value")
        assert m.get("new", "key") == "value"

    def test_set_nested_path(self, config_dir: Path) -> None:
        """嵌套路径设置。"""
        m = ConfigManager(config_dir=config_dir)
        m.load("app")
        m.set("app", "new.nested.key", 42)
        assert m.get("app", "new.nested.key") == 42

    def test_set_persist(self, config_dir: Path) -> None:
        """persist=True 应写入文件。"""
        m = ConfigManager(config_dir=config_dir)
        m.load("app")
        m.set("app", "app.port", 7777, persist=True)

        # 重新加载验证
        text = (config_dir / "app.yaml").read_text(encoding="utf-8")
        reloaded = yaml.safe_load(text)
        assert reloaded["app"]["port"] == 7777

    def test_update_deep_merge(self, config_dir: Path) -> None:
        """update 深度合并。"""
        m = ConfigManager(config_dir=config_dir)
        m.load("app")
        m.update("app", {"app": {"port": 5555}})

        # name 应保留
        assert m.get("app", "app.name") == "CityFlow"
        # port 应更新
        assert m.get("app", "app.port") == 5555

    def test_update_shallow(self, config_dir: Path) -> None:
        """update 浅合并（直接覆盖）。"""
        m = ConfigManager(config_dir=config_dir)
        m.load("app")
        m.update("app", {"app": {"port": 5555}}, deep=False)

        # 浅合并会覆盖整个 "app" 子键
        assert m.get("app", "app.port") == 5555
        assert m.get("app", "app.name") is None  # 被覆盖了

    def test_update_persist(self, config_dir: Path) -> None:
        """update + persist 应写入文件。"""
        m = ConfigManager(config_dir=config_dir)
        m.load("app")
        m.update("app", {"app": {"version": 2}}, persist=True)

        text = (config_dir / "app.yaml").read_text(encoding="utf-8")
        reloaded = yaml.safe_load(text)
        assert reloaded["app"]["version"] == 2

    def test_persist_new_config(self, config_dir: Path) -> None:
        """持久化新配置应创建 YAML 文件。"""
        m = ConfigManager(config_dir=config_dir)
        m.set("brand_new", "hello", "world")
        m.persist("brand_new")

        assert (config_dir / "brand_new.yaml").is_file()

    def test_persist_json_format(self, config_dir: Path) -> None:
        """JSON 格式的配置应以 JSON 格式持久化。"""
        m = ConfigManager(config_dir=config_dir)
        m.load("features")
        m.set("features", "new_flag", True, persist=True)

        text = (config_dir / "features.json").read_text(encoding="utf-8")
        reloaded = json.loads(text)
        assert reloaded["new_flag"] is True

    def test_persist_nonexistent_raises(self, config_dir: Path) -> None:
        """持久化不存在的配置应抛出 ConfigManagerError。"""
        m = ConfigManager(config_dir=config_dir)
        with pytest.raises(ConfigManagerError, match="配置不存在"):
            m.persist("ghost")

    def test_get_all_returns_copy(self, config_dir: Path) -> None:
        """get_all 返回深拷贝。"""
        m = ConfigManager(config_dir=config_dir)
        m.load_all()
        all_cfg = m.get_all()
        all_cfg["app"]["app"]["name"] = "hacked"
        assert m.get("app", "app.name") == "CityFlow"

    # ---- 集成测试 ----

    def test_bind_reloader_syncs(self, config_dir: Path) -> None:
        """绑定 reloader 后，reloader 重载应同步到 manager。"""
        m = ConfigManager(config_dir=config_dir)
        m.load_all()

        r = ConfigHotReloader(config_dir=config_dir, debounce_seconds=0.1)
        m.bind_reloader(r)

        # reloader 重载
        new_config = {"app": {"name": "synced", "port": 8000}}
        (config_dir / "app.yaml").write_text(yaml.dump(new_config), encoding="utf-8")
        r.reload("app")

        # manager 应同步
        assert m.get("app", "app.name") == "synced"

    def test_load_invalid_yaml_raises(self, config_dir: Path) -> None:
        """无效 YAML 应抛出 ConfigManagerError。"""
        (config_dir / "bad.yaml").write_text("{{invalid::", encoding="utf-8")
        m = ConfigManager(config_dir=config_dir)
        with pytest.raises(ConfigManagerError, match="加载失败"):
            m.load("bad")

    def test_load_list_yaml_raises(self, config_dir: Path) -> None:
        """顶层为 list 的 YAML 应抛出 ConfigManagerError。"""
        (config_dir / "list.yaml").write_text("- a\n- b\n", encoding="utf-8")
        m = ConfigManager(config_dir=config_dir)
        with pytest.raises(ConfigManagerError, match="顶层必须是对象"):
            m.load("list")


# ---------------------------------------------------------------------------
# ConfigReloadError / ConfigRollbackError 测试
# ---------------------------------------------------------------------------


class TestExceptions:
    """自定义异常测试。"""

    def test_config_reload_error_inherits(self) -> None:
        """ConfigReloadError 应继承 CityFlowException。"""
        from backend.errors import CityFlowException

        err = ConfigReloadError(message="test")
        assert isinstance(err, CityFlowException)
        assert err.message == "test"
        assert err.status_code == 500

    def test_config_rollback_error_inherits(self) -> None:
        """ConfigRollbackError 应继承 CityFlowException。"""
        from backend.errors import CityFlowException

        err = ConfigRollbackError(
            message="rollback failed",
            details={"config": "app"},
        )
        assert isinstance(err, CityFlowException)
        assert err.details == {"config": "app"}

    def test_config_manager_error_inherits(self) -> None:
        """ConfigManagerError 应继承 CityFlowException。"""
        from backend.errors import CityFlowException

        err = ConfigManagerError(message="manager error")
        assert isinstance(err, CityFlowException)
