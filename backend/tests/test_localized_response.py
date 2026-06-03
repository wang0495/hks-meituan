"""CityFlow 本地化响应测试。"""

from __future__ import annotations

import pytest

import backend.i18n as _i18n_mod
from backend.i18n import set_locale
from backend.utils.localized_response import LocalizedResponse as LocalizedResp


@pytest.fixture(autouse=True)
def _reset_locale() -> None:
    """每个测试前重置 contextvar 为 zh_CN。"""
    _i18n_mod._current_locale_var.set("zh_CN")


# ---------------------------------------------------------------------------
# success
# ---------------------------------------------------------------------------


class TestSuccess:
    def test_default_message(self) -> None:
        result = LocalizedResp.success()
        assert result == {"success": True, "message": "成功"}

    def test_custom_key(self) -> None:
        result = LocalizedResp.success("auth.login_success")
        assert result == {"success": True, "message": "登录成功"}

    def test_en_locale(self) -> None:
        set_locale("en_US")
        result = LocalizedResp.success()
        assert result == {"success": True, "message": "Success"}


# ---------------------------------------------------------------------------
# error
# ---------------------------------------------------------------------------


class TestError:
    def test_default_message(self) -> None:
        result = LocalizedResp.error()
        assert result == {"success": False, "message": "错误"}

    def test_custom_key(self) -> None:
        result = LocalizedResp.error("common.rate_limited")
        assert result["success"] is False
        assert "频繁" in result["message"]

    def test_en_locale(self) -> None:
        set_locale("en_US")
        result = LocalizedResp.error()
        assert result == {"success": False, "message": "Error"}


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------


class TestData:
    def test_basic_data(self) -> None:
        result = LocalizedResp.data({"id": 1})
        assert result == {
            "success": True,
            "message": "成功",
            "data": {"id": 1},
        }

    def test_list_data(self) -> None:
        result = LocalizedResp.data([1, 2, 3])
        assert result["data"] == [1, 2, 3]

    def test_none_data(self) -> None:
        result = LocalizedResp.data(None)
        assert result["data"] is None

    def test_en_locale(self) -> None:
        set_locale("en_US")
        result = LocalizedResp.data("test")
        assert result["message"] == "Success"


# ---------------------------------------------------------------------------
# paginated
# ---------------------------------------------------------------------------


class TestPaginated:
    def test_basic_paginated(self) -> None:
        result = LocalizedResp.paginated(data=[1, 2, 3], total=10, page=1, page_size=3)
        assert result["success"] is True
        assert result["data"] == [1, 2, 3]
        assert result["pagination"] == {
            "total": 10,
            "page": 1,
            "page_size": 3,
            "total_pages": 4,
        }

    def test_exact_page_count(self) -> None:
        result = LocalizedResp.paginated(data=[], total=20, page=1, page_size=10)
        assert result["pagination"]["total_pages"] == 2

    def test_single_page(self) -> None:
        result = LocalizedResp.paginated(data=[1], total=1, page=1, page_size=10)
        assert result["pagination"]["total_pages"] == 1

    def test_zero_total(self) -> None:
        result = LocalizedResp.paginated(data=[], total=0, page=1, page_size=10)
        assert result["pagination"]["total_pages"] == 0

    def test_en_locale(self) -> None:
        set_locale("en_US")
        result = LocalizedResp.paginated(data=[], total=0)
        assert result["message"] == "Success"
