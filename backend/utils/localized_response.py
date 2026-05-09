"""CityFlow 本地化响应工具。

提供统一的 API 响应格式，所有消息通过 i18n 翻译后返回。
"""

from __future__ import annotations

from typing import Any

from backend.i18n import t


class LocalizedResponse:
    """本地化 API 响应构建器。

    所有方法返回字典，可直接由 FastAPI 序列化为 JSON。
    消息键默认使用 "common.*" 下的翻译。
    """

    @staticmethod
    def success(
        message_key: str = "common.success",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """构造成功响应。

        Args:
            message_key: 翻译键。
            **kwargs: 翻译插值参数。

        Returns:
            {"success": True, "message": "..."}
        """
        return {
            "success": True,
            "message": t(message_key, **kwargs),
        }

    @staticmethod
    def error(
        message_key: str = "common.error",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """构造错误响应。

        Args:
            message_key: 翻译键。
            **kwargs: 翻译插值参数。

        Returns:
            {"success": False, "message": "..."}
        """
        return {
            "success": False,
            "message": t(message_key, **kwargs),
        }

    @staticmethod
    def data(
        data: Any,
        message_key: str = "common.success",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """构造带数据的成功响应。

        Args:
            data: 要返回的数据。
            message_key: 翻译键。
            **kwargs: 翻译插值参数。

        Returns:
            {"success": True, "message": "...", "data": ...}
        """
        return {
            "success": True,
            "message": t(message_key, **kwargs),
            "data": data,
        }

    @staticmethod
    def paginated(
        data: list[Any],
        total: int,
        page: int = 1,
        page_size: int = 20,
        message_key: str = "common.success",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """构造分页响应。

        Args:
            data: 当前页数据列表。
            total: 总记录数。
            page: 当前页码（从 1 开始）。
            page_size: 每页条数。
            message_key: 翻译键。
            **kwargs: 翻译插值参数。

        Returns:
            包含分页信息的响应字典。
        """
        return {
            "success": True,
            "message": t(message_key, **kwargs),
            "data": data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (
                    (total + page_size - 1) // page_size if page_size > 0 else 0
                ),
            },
        }
