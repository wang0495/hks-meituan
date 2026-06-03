"""i18n 模块测试。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

import backend.i18n as _i18n_mod
from backend.i18n import I18n, t

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_locale_contextvar() -> None:
    """每个测试前重置 contextvar，防止跨测试污染。"""
    _i18n_mod._current_locale_var.set("zh_CN")


@pytest.fixture()
def locale_dir(tmp_path: Path) -> Path:
    """创建临时翻译目录。"""
    zh = {
        "common": {"success": "成功", "error": "错误"},
        "route": {"planning": "正在规划路线...", "distance": "距离: {km} 公里"},
    }
    en = {
        "common": {"success": "Success", "error": "Error"},
        "route": {"planning": "Planning route...", "distance": "Distance: {km} km"},
    }
    (tmp_path / "zh_CN.json").write_text(json.dumps(zh, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "en_US.json").write_text(json.dumps(en, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def i18n(locale_dir: Path) -> I18n:
    """创建 I18n 实例。"""
    return I18n(locale_dir=locale_dir)


# ---------------------------------------------------------------------------
# 基础翻译
# ---------------------------------------------------------------------------


class TestTranslate:
    """翻译功能测试。"""

    def test_simple_key(self, i18n: I18n) -> None:
        assert i18n.translate("common.success") == "成功"

    def test_nested_key(self, i18n: I18n) -> None:
        assert i18n.translate("route.planning") == "正在规划路线..."

    def test_missing_key_returns_key(self, i18n: I18n) -> None:
        assert i18n.translate("nonexistent.key") == "nonexistent.key"

    def test_intermediate_key_returns_key(self, i18n: I18n) -> None:
        """中间节点不是字符串时应返回 key。"""
        assert i18n.translate("common") == "common"

    def test_format_params(self, i18n: I18n) -> None:
        assert i18n.translate("route.distance", km=5.2) == "距离: 5.2 公里"

    def test_format_missing_param_returns_template(self, i18n: I18n) -> None:
        """缺少参数时应返回原始模板。"""
        result = i18n.translate("route.distance")
        assert result == "距离: {km} 公里"


# ---------------------------------------------------------------------------
# 语言切换
# ---------------------------------------------------------------------------


class TestLocaleSwitching:
    """语言切换测试。"""

    def test_default_locale(self, i18n: I18n) -> None:
        assert i18n.get_locale() == "zh_CN"

    def test_switch_to_en(self, i18n: I18n) -> None:
        i18n.set_locale("en_US")
        assert i18n.get_locale() == "en_US"
        assert i18n.translate("common.success") == "Success"

    def test_switch_back(self, i18n: I18n) -> None:
        i18n.set_locale("en_US")
        i18n.set_locale("zh_CN")
        assert i18n.translate("common.success") == "成功"

    def test_invalid_locale_raises(self, i18n: I18n) -> None:
        with pytest.raises(ValueError, match="不支持的语言"):
            i18n.set_locale("fr_FR")

    def test_get_available_locales(self, i18n: I18n) -> None:
        locales = i18n.get_available_locales()
        assert "zh_CN" in locales
        assert "en_US" in locales


# ---------------------------------------------------------------------------
# 边界情况
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_locale_dir(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        i18n = I18n(locale_dir=empty_dir)
        assert i18n.translate("any.key") == "any.key"

    def test_nonexistent_locale_dir(self, tmp_path: Path) -> None:
        i18n = I18n(locale_dir=tmp_path / "nope")
        assert i18n.translate("any.key") == "any.key"

    def test_malformed_json_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "bad.json").write_text("{invalid json", encoding="utf-8")
        (tmp_path / "zh_CN.json").write_text(json.dumps({"ok": "yes"}), encoding="utf-8")
        i18n = I18n(locale_dir=tmp_path)
        assert i18n.translate("ok") == "yes"


# ---------------------------------------------------------------------------
# 全局快捷函数
# ---------------------------------------------------------------------------


class TestGlobalShortcut:
    """全局 t() 快捷函数测试。"""

    def test_t_function(self, locale_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """重置全局单例后测试 t()。"""
        import backend.i18n as mod

        mod._i18n = I18n(locale_dir=locale_dir)
        try:
            assert t("common.success") == "成功"
            mod._i18n.set_locale("en_US")
            assert t("common.success") == "Success"
        finally:
            mod._i18n = None
