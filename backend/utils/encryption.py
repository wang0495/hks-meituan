"""CityFlow 数据加密工具。

基于 Fernet 对称加密，使用 PBKDF2 派生密钥。
用于加密数据库中的敏感字段（如用户手机号、API Key 等）。
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# 默认盐值 -- 生产环境建议通过环境变量覆盖
_DEFAULT_SALT = b"cityflow-salt-v1"
_PBKDF2_ITERATIONS = 480_000  # OWASP 2023 推荐最低值


class EncryptionError(Exception):
    """加密/解密操作失败。"""


class DataEncryptor:
    """Fernet 对称加密器。

    Parameters
    ----------
    key:
        用户提供的原始密钥字符串。如果为 ``None``，
        则依次尝试 ``ENCRYPTION_KEY`` 环境变量、
        ``ENCRYPTION_KEY_FILE`` 指向的文件。
        三者均不可用时抛出 ``EncryptionError``。
    salt:
        PBKDF2 盐值，默认 ``b"cityflow-salt-v1"``。
    iterations:
        PBKDF2 迭代次数，默认 480 000。
    """

    def __init__(
        self,
        key: str | None = None,
        salt: bytes = _DEFAULT_SALT,
        iterations: int = _PBKDF2_ITERATIONS,
    ) -> None:
        raw_key = self._resolve_key(key)
        self._fernet = self._build_fernet(raw_key, salt, iterations)

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def encrypt(self, data: str) -> str:
        """加密字符串，返回 base64 编码的密文。"""
        try:
            return self._fernet.encrypt(data.encode("utf-8")).decode("ascii")
        except Exception as exc:
            raise EncryptionError(f"加密失败: {exc}") from exc

    def decrypt(self, encrypted_data: str) -> str:
        """解密 base64 编码的密文，返回明文。"""
        try:
            return self._fernet.decrypt(encrypted_data.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise EncryptionError("解密失败: 密钥不匹配或数据已损坏") from exc
        except Exception as exc:
            raise EncryptionError(f"解密失败: {exc}") from exc

    def encrypt_dict(self, data: dict[str, Any]) -> str:
        """将字典序列化为 JSON 后加密。"""
        json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return self.encrypt(json_str)

    def decrypt_dict(self, encrypted_data: str) -> dict[str, Any]:
        """解密后反序列化为字典。"""
        json_str = self.decrypt(encrypted_data)
        return json.loads(json_str)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_key(key: str | None) -> str:
        """按优先级解析密钥：参数 > Settings > ENCRYPTION_KEY 环境变量 > 密钥文件。"""
        if key:
            return key

        # 从 Pydantic settings 读取（覆盖了 SECURITY_ENCRYPTION_KEY 和 ENCRYPTION_KEY）
        from backend.config import settings

        settings_key = settings.security.encryption_key
        if settings_key:
            return settings_key

        # 兜底：直接读环境变量（ENCRYPTION_KEY / ENCRYPTION_KEY_FILE）
        import os

        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            return env_key

        key_file = os.getenv("ENCRYPTION_KEY_FILE")
        if key_file:
            path = Path(key_file).resolve()
            if path.is_file():
                return path.read_text(encoding="utf-8").strip()

        raise EncryptionError(
            "未配置加密密钥。请设置 SECURITY_ENCRYPTION_KEY 环境变量，"
            "或在 Settings.security.encryption_key 中提供。"
        )

    @staticmethod
    def _build_fernet(raw_key: str, salt: bytes, iterations: int) -> Fernet:
        """从原始密钥派生 Fernet 实例。"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        derived = base64.urlsafe_b64encode(kdf.derive(raw_key.encode("utf-8")))
        return Fernet(derived)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_encryptor: DataEncryptor | None = None


def get_encryptor() -> DataEncryptor:
    """获取全局加密器实例（懒加载单例）。"""
    global _encryptor
    if _encryptor is None:
        from backend.config import settings

        _encryptor = DataEncryptor(
            key=settings.security.encryption_key or None,
        )
    return _encryptor


def reset_encryptor() -> None:
    """重置全局加密器（测试用）。"""
    global _encryptor
    _encryptor = None


def encrypt_sensitive_data(data: str) -> str:
    """快捷函数：加密敏感数据。"""
    return get_encryptor().encrypt(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """快捷函数：解密敏感数据。"""
    return get_encryptor().decrypt(encrypted_data)
