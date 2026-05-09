"""CityFlow 字段加密装饰器。

为 service 层函数提供透明的字段加解密，
支持对返回字典中的指定字段自动加密/解密。
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable

from backend.utils.encryption import EncryptionError, get_encryptor

logger = logging.getLogger(__name__)


def encrypt_field(field_name: str) -> Callable:
    """加密返回字典中的指定字段。

    用法::

        @encrypt_field("phone")
        async def create_user(data: dict) -> dict:
            return {"id": 1, "phone": "13800138000"}
            # 实际返回: {"id": 1, "phone": "<encrypted>"}
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            return _encrypt_result_field(result, field_name)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            return _encrypt_result_field(result, field_name)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def decrypt_field(field_name: str) -> Callable:
    """解密返回字典中的指定字段。

    用法::

        @decrypt_field("phone")
        async def get_user(user_id: int) -> dict:
            return {"id": 1, "phone": "<encrypted>"}
            # 实际返回: {"id": 1, "phone": "13800138000"}
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            return _decrypt_result_field(result, field_name)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            return _decrypt_result_field(result, field_name)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def encrypt_fields(*field_names: str) -> Callable:
    """批量加密返回字典中的多个字段。

    用法::

        @encrypt_fields("phone", "id_card")
        async def create_user(data: dict) -> dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            return _encrypt_result_fields(result, field_names)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            return _encrypt_result_fields(result, field_names)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def decrypt_fields(*field_names: str) -> Callable:
    """批量解密返回字典中的多个字段。

    用法::

        @decrypt_fields("phone", "id_card")
        async def get_user(user_id: int) -> dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            return _decrypt_result_fields(result, field_names)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            return _decrypt_result_fields(result, field_names)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _encrypt_result_field(result: Any, field_name: str) -> Any:
    """加密单个字段。"""
    if isinstance(result, dict) and field_name in result:
        encryptor = get_encryptor()
        result[field_name] = encryptor.encrypt(str(result[field_name]))
    return result


def _decrypt_result_field(result: Any, field_name: str) -> Any:
    """解密单个字段。"""
    if isinstance(result, dict) and field_name in result:
        try:
            encryptor = get_encryptor()
            result[field_name] = encryptor.decrypt(result[field_name])
        except EncryptionError:
            logger.warning("字段 '%s' 解密失败，可能未加密", field_name)
    return result


def _encrypt_result_fields(result: Any, field_names: tuple[str, ...]) -> Any:
    """批量加密字段。"""
    if isinstance(result, dict):
        encryptor = get_encryptor()
        for name in field_names:
            if name in result:
                result[name] = encryptor.encrypt(str(result[name]))
    return result


def _decrypt_result_fields(result: Any, field_names: tuple[str, ...]) -> Any:
    """批量解密字段。"""
    if isinstance(result, dict):
        encryptor = get_encryptor()
        for name in field_names:
            if name in result:
                try:
                    result[name] = encryptor.decrypt(result[name])
                except EncryptionError:
                    logger.warning("字段 '%s' 解密失败，可能未加密", name)
    return result


def encrypt_value(value: str) -> str:
    """直接加密单个值（不通过装饰器）。"""
    return get_encryptor().encrypt(value)


def decrypt_value(value: str) -> str:
    """直接解密单个值（不通过装饰器）。"""
    return get_encryptor().decrypt(value)
