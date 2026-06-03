"""CityFlow 高效 JSON 序列化工具。

使用 orjson 实现高性能序列化，可选 gzip 压缩。
"""

from __future__ import annotations

import gzip
import json
from typing import Any

import orjson


class FastJSONSerializer:
    """基于 orjson 的高性能 JSON 序列化器。

    orjson 比标准库 json 快 5-10 倍，
    且原生支持 numpy 类型和非字符串 key。
    """

    _OPTIONS: int = orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY

    @staticmethod
    def dumps(obj: Any, compress: bool = False) -> bytes:
        """序列化为 bytes，可选 gzip 压缩。

        Args:
            obj: 任意可序列化对象。
            compress: 是否启用 gzip 压缩。

        Returns:
            序列化后的 bytes 数据。
        """
        data = orjson.dumps(obj, option=FastJSONSerializer._OPTIONS)
        if compress:
            return gzip.compress(data, compresslevel=6)
        return data

    @staticmethod
    def loads(data: bytes, compressed: bool = False) -> Any:
        """从 bytes 反序列化，可选 gzip 解压。

        Args:
            data: 序列化的 bytes 数据。
            compressed: 是否需要 gzip 解压。

        Returns:
            反序列化后的 Python 对象。
        """
        if compressed:
            data = gzip.decompress(data)
        return orjson.loads(data)

    @staticmethod
    def dumps_str(obj: Any) -> str:
        """序列化为 UTF-8 字符串。"""
        return orjson.dumps(obj, option=FastJSONSerializer._OPTIONS).decode("utf-8")

    @staticmethod
    def loads_str(data: str) -> Any:
        """从 UTF-8 字符串反序列化。"""
        return orjson.loads(data.encode("utf-8"))


class CompressedJSONSerializer:
    """基于标准库 json + gzip 的压缩序列化器。

    用于不依赖 orjson 的场景（如脚本、迁移工具）。
    """

    @staticmethod
    def dumps(obj: Any) -> bytes:
        """序列化并压缩。"""
        json_bytes = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return gzip.compress(json_bytes, compresslevel=6)

    @staticmethod
    def loads(data: bytes) -> Any:
        """解压并反序列化。"""
        json_bytes = gzip.decompress(data).decode("utf-8")
        return json.loads(json_bytes)


# 模块级单例，避免重复创建
serializer = FastJSONSerializer()


def serialize_response(data: Any, compress: bool = False) -> bytes:
    """序列化 API 响应数据。"""
    return serializer.dumps(data, compress)


def deserialize_request(data: bytes, compressed: bool = False) -> Any:
    """反序列化 API 请求数据。"""
    return serializer.loads(data, compressed)
