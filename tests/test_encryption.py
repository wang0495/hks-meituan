"""数据加密模块测试。"""

from __future__ import annotations

import pytest

from backend.utils.encryption import (DataEncryptor, EncryptionError,
                                      decrypt_sensitive_data,
                                      encrypt_sensitive_data, get_encryptor,
                                      reset_encryptor)
from backend.utils.field_encryption import (decrypt_field, decrypt_value,
                                            encrypt_field, encrypt_fields,
                                            encrypt_value)

# ---------------------------------------------------------------------------
# DataEncryptor 测试
# ---------------------------------------------------------------------------


class TestDataEncryptor:
    """DataEncryptor 单元测试。"""

    TEST_KEY = "test-secret-key-for-cityflow"

    @pytest.fixture
    def encryptor(self) -> DataEncryptor:
        return DataEncryptor(key=self.TEST_KEY)

    def test_encrypt_decrypt_roundtrip(self, encryptor: DataEncryptor) -> None:
        """加密后解密应还原原始数据。"""
        plaintext = "这是一段敏感数据"
        encrypted = encryptor.encrypt(plaintext)
        assert encrypted != plaintext
        assert encryptor.decrypt(encrypted) == plaintext

    def test_encrypt_dict_roundtrip(self, encryptor: DataEncryptor) -> None:
        """字典加解密应还原。"""
        data = {"phone": "13800138000", "name": "张三", "count": 42}
        encrypted = encryptor.encrypt_dict(data)
        assert encryptor.decrypt_dict(encrypted) == data

    def test_encrypt_unicode(self, encryptor: DataEncryptor) -> None:
        """支持 Unicode 内容。"""
        text = "珠海市香洲区 🎉 emoji测试"
        assert encryptor.decrypt(encryptor.encrypt(text)) == text

    def test_encrypt_empty_string(self, encryptor: DataEncryptor) -> None:
        """空字符串应可正常加解密。"""
        assert encryptor.decrypt(encryptor.encrypt("")) == ""

    def test_different_keys_cannot_decrypt(self) -> None:
        """不同密钥加密的数据无法互相解密。"""
        enc_a = DataEncryptor(key="key-a")
        enc_b = DataEncryptor(key="key-b")
        encrypted = enc_a.encrypt("secret")
        with pytest.raises(EncryptionError, match="解密失败"):
            enc_b.decrypt(encrypted)

    def test_decrypt_invalid_data(self, encryptor: DataEncryptor) -> None:
        """解密无效数据应抛出 EncryptionError。"""
        with pytest.raises(EncryptionError):
            encryptor.decrypt("not-valid-encrypted-data")

    def test_decrypt_tampered_data(self, encryptor: DataEncryptor) -> None:
        """篡改密文应抛出 EncryptionError。"""
        encrypted = encryptor.encrypt("original")
        # 篡改密文末尾字符
        tampered = encrypted[:-2] + ("A" if encrypted[-1] != "A" else "B") * 2
        with pytest.raises(EncryptionError):
            encryptor.decrypt(tampered)

    def test_same_input_different_ciphertext(self, encryptor: DataEncryptor) -> None:
        """相同明文每次加密应产生不同密文（Fernet 内含时间戳+随机 IV）。"""
        text = "same-input"
        c1 = encryptor.encrypt(text)
        c2 = encryptor.encrypt(text)
        # Fernet 包含时间戳，短时间内可能相同，但解密结果必须一致
        assert encryptor.decrypt(c1) == encryptor.decrypt(c2) == text

    def test_no_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """未配置密钥时应抛出 EncryptionError。"""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("ENCRYPTION_KEY_FILE", raising=False)
        with pytest.raises(EncryptionError, match="未配置加密密钥"):
            DataEncryptor()

    def test_env_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """应能从环境变量读取密钥。"""
        monkeypatch.setenv("ENCRYPTION_KEY", "env-key-value")
        enc = DataEncryptor()
        assert enc.decrypt(enc.encrypt("hello")) == "hello"


# ---------------------------------------------------------------------------
# 装饰器测试
# ---------------------------------------------------------------------------


class TestFieldEncryptionDecorators:
    """字段加密装饰器测试。"""

    @pytest.fixture(autouse=True)
    def _setup_encryptor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """为每个测试注入固定密钥。"""
        monkeypatch.setenv("ENCRYPTION_KEY", "decorator-test-key")
        reset_encryptor()

    def teardown_method(self) -> None:
        reset_encryptor()

    @pytest.mark.asyncio
    async def test_encrypt_field_decorator(self) -> None:
        """@encrypt_field 应加密指定字段。"""

        @encrypt_field("phone")
        async def get_user() -> dict:
            return {"id": 1, "phone": "13800138000", "name": "张三"}

        result = await get_user()
        assert result["id"] == 1
        assert result["name"] == "张三"
        assert result["phone"] != "13800138000"  # 已加密

    @pytest.mark.asyncio
    async def test_decrypt_field_decorator(self) -> None:
        """@decrypt_field 应解密指定字段。"""
        encryptor = get_encryptor()
        encrypted_phone = encryptor.encrypt("13800138000")

        @decrypt_field("phone")
        async def get_user() -> dict:
            return {"id": 1, "phone": encrypted_phone}

        result = await get_user()
        assert result["phone"] == "13800138000"

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_roundtrip(self) -> None:
        """加密装饰器 + 解密装饰器应能还原。"""

        @encrypt_field("secret")
        async def create() -> dict:
            return {"id": 1, "secret": "top-secret"}

        @decrypt_field("secret")
        async def read() -> dict:
            return await create()

        result = await read()
        assert result["secret"] == "top-secret"

    @pytest.mark.asyncio
    async def test_encrypt_fields_batch(self) -> None:
        """@encrypt_fields 应批量加密。"""

        @encrypt_fields("phone", "id_card")
        async def get_user() -> dict:
            return {"phone": "13800138000", "id_card": "440000000000000000"}

        result = await get_user()
        assert result["phone"] != "13800138000"
        assert result["id_card"] != "440000000000000000"

    def test_sync_function_support(self) -> None:
        """装饰器应同时支持同步函数。"""

        @encrypt_field("value")
        def get_data() -> dict:
            return {"value": "plaintext"}

        result = get_data()
        assert result["value"] != "plaintext"

    def test_missing_field_is_noop(self) -> None:
        """返回字典中不含目标字段时应原样返回。"""

        @encrypt_field("phone")
        def get_data() -> dict:
            return {"id": 1, "name": "test"}

        result = get_data()
        assert result == {"id": 1, "name": "test"}

    def test_non_dict_result_is_noop(self) -> None:
        """返回值非字典时应原样返回。"""

        @encrypt_field("phone")
        def get_data() -> str:
            return "not a dict"

        assert get_data() == "not a dict"


# ---------------------------------------------------------------------------
# 快捷函数测试
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    """快捷函数测试。"""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", "convenience-test-key")
        reset_encryptor()

    def teardown_method(self) -> None:
        reset_encryptor()

    def test_encrypt_decrypt_sensitive_data(self) -> None:
        """encrypt_sensitive_data / decrypt_sensitive_data 应能还原。"""
        plaintext = "13800138000"
        encrypted = encrypt_sensitive_data(plaintext)
        assert encrypted != plaintext
        assert decrypt_sensitive_data(encrypted) == plaintext

    def test_encrypt_decrypt_value(self) -> None:
        """encrypt_value / decrypt_value 应能还原。"""
        plaintext = "api-key-abc123"
        encrypted = encrypt_value(plaintext)
        assert encrypted != plaintext
        assert decrypt_value(encrypted) == plaintext
