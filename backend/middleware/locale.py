"""CityFlow 本地化中间件。

从请求的 Accept-Language 头解析语言偏好，设置当前请求的语言上下文，
并在响应中添加 Content-Language 头。
"""

from __future__ import annotations

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.i18n import get_i18n


class LocaleMiddleware(BaseHTTPMiddleware):
    """本地化中间件。

    处理流程：
    1. 从 Accept-Language 请求头解析语言偏好
    2. 将语言设置到 i18n 上下文（contextvars，异步安全）
    3. 将语言注入 request.state.locale 供路由使用
    4. 在响应头中添加 Content-Language
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 从请求头获取语言
        accept_language = request.headers.get("Accept-Language", "")

        # 解析语言
        locale = self._parse_locale(accept_language)

        # 设置语言到 i18n 上下文（容错：不受支持的语言回退到默认）
        i18n = get_i18n()
        try:
            i18n.set_locale(locale)
        except ValueError:
            locale = "zh_CN"
            i18n.set_locale(locale)

        # 使用 i18n 实际生效的语言（set_locale 内部可能归一化）
        effective_locale = i18n.get_locale()

        # 注入到请求状态
        request.state.locale = effective_locale

        response = await call_next(request)

        # 响应头添加语言信息
        response.headers["Content-Language"] = effective_locale

        return response

    @staticmethod
    def _parse_locale(accept_language: str) -> str:
        """解析 Accept-Language 头，返回最佳语言代码。

        解析逻辑：
        - 按 q 值排序（未指定 q 时默认 q=1.0）
        - 优先匹配完整语言代码（如 zh-CN -> zh_CN）
        - 再匹配语言前缀（如 en -> en_US）

        Args:
            accept_language: Accept-Language 头的原始值。

        Returns:
            解析后的语言代码，如 "zh_CN" 或 "en_US"。
        """
        if not accept_language:
            return "zh_CN"

        # 解析 q 值并排序
        candidates: list[tuple[str, float]] = []
        for part in accept_language.split(","):
            part = part.strip()
            if not part:
                continue
            segments = part.split(";")
            lang = segments[0].strip()
            q = 1.0
            for seg in segments[1:]:
                seg = seg.strip()
                if seg.startswith("q="):
                    try:
                        q = float(seg[2:])
                    except ValueError:
                        q = 0.0
            candidates.append((lang, q))

        # 按 q 值降序排列
        candidates.sort(key=lambda x: x[1], reverse=True)

        # 映射表
        _LOCALE_MAP: dict[str, str] = {
            "zh": "zh_CN",
            "zh-cn": "zh_CN",
            "zh_cn": "zh_CN",
            "zh-tw": "zh_TW",
            "zh_tw": "zh_TW",
            "zh-hk": "zh_HK",
            "zh_hk": "zh_HK",
            "en": "en_US",
            "en-us": "en_US",
            "en_us": "en_US",
            "en-gb": "en_GB",
            "en_gb": "en_GB",
        }

        for lang, _q in candidates:
            normalized = lang.lower().replace("-", "_")
            # 精确匹配
            if normalized in _LOCALE_MAP:
                return _LOCALE_MAP[normalized]
            # 前缀匹配（如 "en-US;q=0.9,en;q=0.8" 中取 en）
            prefix = normalized.split("_")[0]
            if prefix in _LOCALE_MAP:
                return _LOCALE_MAP[prefix]

        return "zh_CN"
