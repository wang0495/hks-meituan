"""访问控制服务。

提供用户注册、权限校验，以及 FastAPI 依赖注入和装饰器两种接入方式。
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from fastapi import HTTPException, Request

from backend.auth.models import Permission, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 访问控制核心
# ---------------------------------------------------------------------------


class AccessControl:
    """访问控制服务（进程内单例）。"""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    # -- 用户管理 ----------------------------------------------------------

    def add_user(self, user: User) -> None:
        """注册 / 更新用户。"""
        self._users[user.user_id] = user

    def remove_user(self, user_id: str) -> bool:
        """移除用户，返回是否成功。"""
        return self._users.pop(user_id, None) is not None

    def get_user(self, user_id: str) -> User | None:
        """根据 user_id 获取用户。"""
        return self._users.get(user_id)

    def list_users(self) -> list[User]:
        """列出所有用户。"""
        return list(self._users.values())

    # -- 权限校验 ----------------------------------------------------------

    def check_permission(
        self,
        user_id: str,
        permission: Permission,
        resource_id: str | None = None,
    ) -> bool:
        """检查用户是否拥有指定权限。

        Args:
            user_id: 用户 ID。
            permission: 需要的权限。
            resource_id: 可选的资源 ID（预留，用于未来细粒度资源控制）。

        Returns:
            True 表示放行，False 表示拒绝。
        """
        user = self.get_user(user_id)
        if user is None:
            logger.warning("权限拒绝: 用户不存在 user_id=%s", user_id)
            return False

        has_perm = user.has_permission(permission)

        if not has_perm:
            logger.warning(
                "权限拒绝: user_id=%s permission=%s resource=%s",
                user_id,
                permission.value,
                resource_id,
            )

        return has_perm

    # -- FastAPI 集成 ------------------------------------------------------

    def require(self, permission: Permission) -> Callable[..., Any]:
        """返回一个 FastAPI Depends 可用的权限校验函数。

        用法::

            @router.get("/admin/users")
            async def list_users(
                _perm: None = Depends(acl.require(Permission.VIEW_USERS)),
            ):
                ...
        """

        async def _check(request: Request) -> None:
            user_id = self._extract_user_id(request)
            if user_id is None or not self.check_permission(user_id, permission):
                raise HTTPException(status_code=403, detail="权限不足")

        return _check

    def require_permission(self, permission: Permission) -> Callable[..., Any]:
        """装饰器版本的权限校验（用于非 FastAPI 场景）。

        用法::

            @acl.require_permission(Permission.MANAGE_SYSTEM)
            async def do_admin_work(user_id: str):
                ...
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                user_id = kwargs.get("user_id") or (args[0] if args else None)
                if not user_id or not self.check_permission(str(user_id), permission):
                    raise HTTPException(status_code=403, detail="权限不足")
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    # -- 内部工具 ----------------------------------------------------------

    @staticmethod
    def _extract_user_id(request: Request) -> str | None:
        """从请求中提取 user_id。

        优先级：
        1. 请求头 X-User-Id
        2. 查询参数 user_id
        3. 请求状态 state.user_id（中间件注入）
        """
        # 请求头
        header_val = request.headers.get("X-User-Id")
        if header_val:
            return header_val

        # 查询参数
        query_val = request.query_params.get("user_id")
        if query_val:
            return query_val

        # 中间件注入
        state_val = getattr(request.state, "user_id", None)
        if state_val:
            return str(state_val)

        return None


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_acl: AccessControl | None = None


def get_access_control() -> AccessControl:
    """获取全局 AccessControl 实例（懒初始化）。"""
    global _acl
    if _acl is None:
        _acl = AccessControl()
    return _acl


def reset_access_control() -> None:
    """重置全局实例（仅供测试使用）。"""
    global _acl
    _acl = None
