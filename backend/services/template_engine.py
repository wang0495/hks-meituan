"""CityFlow Jinja2 模板引擎。

提供模板渲染、缓存、自定义过滤器/全局变量等功能。
模板编译结果缓存在内存中，避免重复编译开销。
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class TemplateRenderError(CityFlowException):
    """模板渲染失败。"""

    def __init__(
        self,
        message: str = "模板渲染失败",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.NARRATIVE_GENERATION_FAILED,
            message=message,
            details=details,
        )


# ---------------------------------------------------------------------------
# 模板缓存
# ---------------------------------------------------------------------------


class TemplateCache:
    """编译模板的 TTL + LRU 内存缓存。

    缓存键为模板内容的 SHA256 哈希，值为编译后的 Template 对象。
    文件模板以文件路径 + mtime 为键，字符串模板以内容哈希为键。
    """

    def __init__(self, max_size: int = 256, ttl_seconds: int = 600) -> None:
        self._cache: OrderedDict[str, tuple[Template, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def size(self) -> int:
        return len(self._cache)

    def get(self, key: str) -> Template | None:
        """获取缓存的编译模板，过期则删除并返回 None。"""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        template, write_ts = entry
        if time.monotonic() - write_ts >= self._ttl:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        # 移到末尾（最近使用）
        self._cache.move_to_end(key)
        return template

    def set(self, key: str, template: Template) -> None:
        """写入缓存，满时淘汰最旧条目。"""
        if len(self._cache) >= self._max_size:
            # 弹出最旧的（字典有序，第一个即最旧）
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = (template, time.monotonic())

    def invalidate(self, key: str) -> bool:
        """删除指定缓存条目。"""
        return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        """清空缓存。"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# ---------------------------------------------------------------------------
# 模板引擎
# ---------------------------------------------------------------------------


class TemplateEngine:
    """Jinja2 模板引擎，带编译缓存。

    Args:
        template_dir: 模板文件目录，默认 ``templates``。
        cache_max_size: 缓存最大条目数。
        cache_ttl: 缓存条目 TTL（秒）。
    """

    def __init__(
        self,
        template_dir: str = "templates",
        cache_max_size: int = 256,
        cache_ttl: int = 600,
    ) -> None:
        self._template_dir = Path(template_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._cache = TemplateCache(max_size=cache_max_size, ttl_seconds=cache_ttl)
        # 字符串模板缓存（内容哈希 -> Template）
        self._string_cache = TemplateCache(
            max_size=cache_max_size, ttl_seconds=cache_ttl
        )

    @property
    def cache(self) -> TemplateCache:
        """暴露缓存实例，便于监控和测试。"""
        return self._cache

    @property
    def string_cache(self) -> TemplateCache:
        """字符串模板缓存实例。"""
        return self._string_cache

    @property
    def template_dir(self) -> Path:
        return self._template_dir

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def render(self, template_name: str, context: dict[str, Any] | None = None) -> str:
        """渲染文件模板。

        Args:
            template_name: 模板文件名（相对于 template_dir）。
            context: 模板上下文变量。

        Returns:
            渲染后的字符串。

        Raises:
            TemplateRenderError: 模板加载或渲染失败。
        """
        try:
            template = self._get_file_template(template_name)
            return template.render(context or {})
        except TemplateRenderError:
            raise
        except Exception as exc:
            logger.error("模板渲染失败: %s, %s", template_name, exc)
            raise TemplateRenderError(
                message=f"模板渲染失败: {template_name}",
                details={"template": template_name, "error": str(exc)},
            ) from exc

    def render_string(
        self, template_string: str, context: dict[str, Any] | None = None
    ) -> str:
        """渲染模板字符串（带缓存）。

        Args:
            template_string: Jinja2 模板字符串。
            context: 模板上下文变量。

        Returns:
            渲染后的字符串。

        Raises:
            TemplateRenderError: 模板编译或渲染失败。
        """
        try:
            template = self._get_string_template(template_string)
            return template.render(context or {})
        except TemplateRenderError:
            raise
        except Exception as exc:
            logger.error("模板字符串渲染失败: %s", exc)
            raise TemplateRenderError(
                message="模板字符串渲染失败",
                details={"error": str(exc)},
            ) from exc

    # ------------------------------------------------------------------
    # 内部：带缓存的模板获取
    # ------------------------------------------------------------------

    def _get_file_template(self, template_name: str) -> Template:
        """获取文件模板，优先从缓存读取。

        缓存键 = "file:{template_name}:{mtime}"。
        """
        template_path = self._template_dir / template_name
        if not template_path.exists():
            raise TemplateRenderError(
                message=f"模板文件不存在: {template_name}",
                details={"path": str(template_path)},
            )

        mtime = template_path.stat().st_mtime
        cache_key = f"file:{template_name}:{mtime}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        template = self._env.get_template(template_name)
        self._cache.set(cache_key, template)
        return template

    def _get_string_template(self, template_string: str) -> Template:
        """获取字符串模板，优先从缓存读取。

        缓存键 = "str:{sha256}"。
        """
        content_hash = hashlib.sha256(template_string.encode("utf-8")).hexdigest()
        cache_key = f"str:{content_hash}"

        cached = self._string_cache.get(cache_key)
        if cached is not None:
            return cached

        template = self._env.from_string(template_string)
        self._string_cache.set(cache_key, template)
        return template

    # ------------------------------------------------------------------
    # 扩展
    # ------------------------------------------------------------------

    def add_filter(self, name: str, func: Any) -> None:
        """注册自定义 Jinja2 过滤器。"""
        self._env.filters[name] = func

    def add_global(self, name: str, value: Any) -> None:
        """注册全局模板变量。"""
        self._env.globals[name] = value

    def invalidate_cache(self) -> None:
        """清空所有缓存。"""
        self._cache.clear()
        self._string_cache.clear()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_engine: TemplateEngine | None = None


def get_template_engine() -> TemplateEngine:
    """获取全局模板引擎单例。"""
    global _engine
    if _engine is None:
        _engine = TemplateEngine()
    return _engine


def reset_template_engine() -> None:
    """重置全局单例（测试用）。"""
    global _engine
    _engine = None


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------


def render_template(template_name: str, context: dict[str, Any] | None = None) -> str:
    """渲染模板（使用全局引擎）。"""
    return get_template_engine().render(template_name, context)


def render_string(template_string: str, context: dict[str, Any] | None = None) -> str:
    """渲染模板字符串（使用全局引擎）。"""
    return get_template_engine().render_string(template_string, context)


def invalidate_template_cache() -> None:
    """清空全局模板缓存（使用全局引擎）。"""
    get_template_engine().invalidate_cache()
