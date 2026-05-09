"""CityFlow 国际化（i18n）框架。

使用方式：
    from backend.i18n import t, get_i18n, set_locale

    # 翻译
    msg = t("route.planning")

    # 带参数
    msg = t("route.distance", km=5.2)

    # 切换语言（通过模块级快捷函数）
    set_locale("en_US")

    # 或通过实例
    get_i18n().set_locale("en_US")
"""

from __future__ import annotations

import contextvars
import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 默认翻译文件目录（相对于项目根目录）
_DEFAULT_LOCALE_DIR = Path(__file__).resolve().parent.parent.parent / "locales"

# contextvars 用于异步安全的语言状态
_current_locale_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "cityflow_locale", default="zh_CN"
)


class I18n:
    """国际化管理器。

    从 JSON 翻译文件加载多语言文本，支持点分键路径和字符串格式化参数。
    使用 contextvars 管理当前语言，天然兼容 async 并发场景。
    """

    def __init__(self, locale_dir: str | Path | None = None) -> None:
        self._locale_dir = Path(locale_dir) if locale_dir else _DEFAULT_LOCALE_DIR
        self._translations: dict[str, dict[str, Any]] = {}
        self._available_locales: set[str] = set()
        self._lock = threading.Lock()
        self._load_translations()

    def _load_translations(self) -> None:
        """从 locale_dir 加载所有 JSON 翻译文件。"""
        if not self._locale_dir.is_dir():
            logger.warning("翻译目录不存在: %s", self._locale_dir)
            return

        for locale_file in sorted(self._locale_dir.glob("*.json")):
            locale = locale_file.stem
            try:
                with open(locale_file, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._translations[locale] = data
                    self._available_locales.add(locale)
                    logger.debug("已加载翻译: %s (%d 个顶层键)", locale, len(data))
                else:
                    logger.warning("翻译文件格式错误（非 dict）: %s", locale_file)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("加载翻译文件失败: %s — %s", locale_file, exc)

    def reload(self) -> None:
        """重新加载所有翻译文件（热更新用）。"""
        with self._lock:
            self._translations.clear()
            self._available_locales.clear()
            self._load_translations()

    def set_locale(self, locale: str) -> None:
        """设置当前语言。

        Args:
            locale: 语言代码，如 "zh_CN"、"en_US"。

        Raises:
            ValueError: 如果 locale 不在已加载的翻译中且无法归一化。
        """
        normalized = self._normalize_locale(locale)
        if normalized not in self._available_locales and self._available_locales:
            available = ", ".join(sorted(self._available_locales)) or "(无)"
            raise ValueError(f"不支持的语言 '{locale}'，可用: {available}")
        _current_locale_var.set(normalized)
        logger.info("语言已切换: %s", normalized)

    def get_locale(self) -> str:
        """获取当前语言代码。"""
        return _current_locale_var.get("zh_CN")

    def get_available_locales(self) -> list[str]:
        """获取所有已加载的语言代码列表。"""
        return sorted(self._available_locales)

    def translate(self, key: str, **kwargs: Any) -> str:
        """翻译指定 key。

        使用点分路径访问嵌套字典，如 "route.planning"。
        支持 str.format() 参数插值。

        Args:
            key: 点分翻译键，如 "common.success"。
            **kwargs: 格式化参数。

        Returns:
            翻译后的字符串；如果找不到则返回 key 本身。
        """
        current_locale = self.get_locale()
        keys = key.split(".")
        value: Any = self._translations.get(current_locale, {})

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return key
            else:
                return key

        if not isinstance(value, str):
            return key

        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                logger.debug("翻译格式化失败: key=%s, kwargs=%s", key, kwargs)
                return value

        return value

    def _normalize_locale(self, locale: str) -> str:
        """规范化语言代码。

        将简写（如 "en"、"zh"）映射为标准代码。
        """
        if locale in self._available_locales:
            return locale

        short_map: dict[str, str] = {
            "zh": "zh_CN",
            "en": "en_US",
        }
        short = locale.split("-")[0].split("_")[0].lower()
        return short_map.get(short, locale)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_i18n: I18n | None = None
_i18n_lock = threading.Lock()


def get_i18n() -> I18n:
    """获取全局 I18n 单例。"""
    global _i18n
    if _i18n is None:
        with _i18n_lock:
            if _i18n is None:
                _i18n = I18n()
    return _i18n


def t(key: str, **kwargs: Any) -> str:
    """翻译快捷函数。

    等价于 ``get_i18n().translate(key, **kwargs)``。
    """
    return get_i18n().translate(key, **kwargs)


def set_locale(locale: str) -> None:
    """设置语言快捷函数。

    等价于 ``get_i18n().set_locale(locale)``。
    """
    get_i18n().set_locale(locale)


def get_locale() -> str:
    """获取当前语言快捷函数。"""
    return get_i18n().get_locale()
