"""backend.auth 模块测试。"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from backend.auth import (AccessControl, Permission, Role, User,
                          get_access_control)
from backend.auth.access_control import reset_access_control

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_acl():
    """每个测试重置全局单例。"""
    reset_access_control()
    yield
    reset_access_control()


@pytest.fixture
def acl() -> AccessControl:
    return AccessControl()


@pytest.fixture
def admin_user() -> User:
    return User(user_id="admin1", username="admin", role=Role.ADMIN)


@pytest.fixture
def normal_user() -> User:
    return User(user_id="user1", username="alice", role=Role.USER)


@pytest.fixture
def guest_user() -> User:
    return User(user_id="guest1", username="guest", role=Role.GUEST)


# ---------------------------------------------------------------------------
# Role / Permission 基本测试
# ---------------------------------------------------------------------------


class TestRolePermission:
    def test_admin_has_all_permissions(self) -> None:
        user = User(user_id="a", username="a", role=Role.ADMIN)
        for perm in Permission:
            assert user.has_permission(perm), f"ADMIN missing {perm}"

    def test_user_permissions(self) -> None:
        user = User(user_id="u", username="u", role=Role.USER)
        expected = {
            Permission.PLAN_ROUTE,
            Permission.VIEW_ROUTE,
            Permission.EDIT_ROUTE,
            Permission.SEARCH_POI,
            Permission.VIEW_POI,
        }
        assert user.get_all_permissions() == expected

    def test_user_lacks_admin_permissions(self) -> None:
        user = User(user_id="u", username="u", role=Role.USER)
        assert not user.has_permission(Permission.MANAGE_USERS)
        assert not user.has_permission(Permission.MANAGE_SYSTEM)
        assert not user.has_permission(Permission.VIEW_LOGS)

    def test_guest_permissions(self) -> None:
        user = User(user_id="g", username="g", role=Role.GUEST)
        expected = {Permission.VIEW_ROUTE, Permission.SEARCH_POI, Permission.VIEW_POI}
        assert user.get_all_permissions() == expected

    def test_extra_permissions_grant_additional_access(self) -> None:
        user = User(
            user_id="u",
            username="u",
            role=Role.GUEST,
            extra_permissions={Permission.VIEW_LOGS},
        )
        assert user.has_permission(Permission.VIEW_LOGS)
        assert user.has_permission(Permission.VIEW_ROUTE)  # 角色默认


# ---------------------------------------------------------------------------
# AccessControl 用户管理
# ---------------------------------------------------------------------------


class TestAccessControlUserManagement:
    def test_add_and_get_user(self, acl: AccessControl, admin_user: User) -> None:
        acl.add_user(admin_user)
        assert acl.get_user("admin1") is admin_user

    def test_get_nonexistent_user(self, acl: AccessControl) -> None:
        assert acl.get_user("no_such_user") is None

    def test_remove_user(self, acl: AccessControl, normal_user: User) -> None:
        acl.add_user(normal_user)
        assert acl.remove_user("user1") is True
        assert acl.get_user("user1") is None

    def test_remove_nonexistent_user(self, acl: AccessControl) -> None:
        assert acl.remove_user("nope") is False

    def test_list_users(
        self, acl: AccessControl, admin_user: User, normal_user: User
    ) -> None:
        acl.add_user(admin_user)
        acl.add_user(normal_user)
        users = acl.list_users()
        assert len(users) == 2

    def test_add_user_overwrites(self, acl: AccessControl) -> None:
        u1 = User(user_id="x", username="v1", role=Role.GUEST)
        u2 = User(user_id="x", username="v2", role=Role.ADMIN)
        acl.add_user(u1)
        acl.add_user(u2)
        assert acl.get_user("x").username == "v2"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# AccessControl 权限校验
# ---------------------------------------------------------------------------


class TestAccessControlPermission:
    def test_check_permission_allowed(
        self, acl: AccessControl, admin_user: User
    ) -> None:
        acl.add_user(admin_user)
        assert acl.check_permission("admin1", Permission.MANAGE_SYSTEM) is True

    def test_check_permission_denied(
        self, acl: AccessControl, guest_user: User
    ) -> None:
        acl.add_user(guest_user)
        assert acl.check_permission("guest1", Permission.MANAGE_SYSTEM) is False

    def test_check_permission_unknown_user(self, acl: AccessControl) -> None:
        assert acl.check_permission("ghost", Permission.VIEW_ROUTE) is False

    def test_check_permission_with_resource_id(
        self, acl: AccessControl, normal_user: User
    ) -> None:
        acl.add_user(normal_user)
        # resource_id 不影响当前实现，但不应报错
        assert (
            acl.check_permission("user1", Permission.VIEW_ROUTE, resource_id="r1")
            is True
        )


# ---------------------------------------------------------------------------
# get_access_control 单例
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_returns_same_instance(self) -> None:
        a = get_access_control()
        b = get_access_control()
        assert a is b

    def test_reset_creates_new_instance(self) -> None:
        a = get_access_control()
        reset_access_control()
        b = get_access_control()
        assert a is not b


# ---------------------------------------------------------------------------
# FastAPI 集成：Depends 方式
# ---------------------------------------------------------------------------


@pytest.fixture
def fastapi_app(acl: AccessControl) -> FastAPI:
    """创建一个带权限校验的最小 FastAPI 应用。"""
    app = FastAPI()

    acl.add_user(User(user_id="admin1", username="admin", role=Role.ADMIN))
    acl.add_user(User(user_id="guest1", username="guest", role=Role.GUEST))

    @app.get("/admin/users")
    async def admin_endpoint(
        _perm: None = Depends(acl.require(Permission.VIEW_USERS)),
    ) -> dict:
        return {"users": ["admin1", "guest1"]}

    @app.get("/route")
    async def view_route(
        _perm: None = Depends(acl.require(Permission.VIEW_ROUTE)),
    ) -> dict:
        return {"route": []}

    return app


@pytest.fixture
async def app_client(fastapi_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestFastAPIIntegration:
    async def test_admin_accesses_admin_endpoint(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/admin/users", headers={"X-User-Id": "admin1"})
        assert resp.status_code == 200
        assert resp.json() == {"users": ["admin1", "guest1"]}

    async def test_guest_denied_admin_endpoint(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/admin/users", headers={"X-User-Id": "guest1"})
        assert resp.status_code == 403

    async def test_guest_accesses_view_route(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/route", headers={"X-User-Id": "guest1"})
        assert resp.status_code == 200

    async def test_no_user_header_denied(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/admin/users")
        assert resp.status_code == 403

    async def test_user_id_from_query_param(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/route?user_id=guest1")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 装饰器方式
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDecorator:
    async def test_decorator_allows(self, acl: AccessControl) -> None:
        acl.add_user(User(user_id="u1", username="u", role=Role.ADMIN))

        @acl.require_permission(Permission.MANAGE_SYSTEM)
        async def admin_action(user_id: str) -> str:
            return "done"

        result = await admin_action(user_id="u1")
        assert result == "done"

    async def test_decorator_denies(self, acl: AccessControl) -> None:
        from fastapi import HTTPException

        acl.add_user(User(user_id="g1", username="g", role=Role.GUEST))

        @acl.require_permission(Permission.MANAGE_SYSTEM)
        async def admin_action(user_id: str) -> str:
            return "done"

        with pytest.raises(HTTPException) as exc_info:
            await admin_action(user_id="g1")
        assert exc_info.value.status_code == 403
