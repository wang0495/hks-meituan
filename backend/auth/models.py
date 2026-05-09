"""角色、权限与用户模型。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 角色
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """系统角色。"""

    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


# ---------------------------------------------------------------------------
# 权限
# ---------------------------------------------------------------------------


class Permission(str, Enum):
    """细粒度权限枚举。"""

    # 路线规划
    PLAN_ROUTE = "plan_route"
    VIEW_ROUTE = "view_route"
    EDIT_ROUTE = "edit_route"
    DELETE_ROUTE = "delete_route"

    # POI
    SEARCH_POI = "search_poi"
    VIEW_POI = "view_poi"

    # 用户管理
    MANAGE_USERS = "manage_users"
    VIEW_USERS = "view_users"

    # 系统管理
    MANAGE_SYSTEM = "manage_system"
    VIEW_LOGS = "view_logs"


# ---------------------------------------------------------------------------
# 角色 -> 默认权限映射
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),  # 管理员拥有全部权限
    Role.USER: {
        Permission.PLAN_ROUTE,
        Permission.VIEW_ROUTE,
        Permission.EDIT_ROUTE,
        Permission.SEARCH_POI,
        Permission.VIEW_POI,
    },
    Role.GUEST: {
        Permission.VIEW_ROUTE,
        Permission.SEARCH_POI,
        Permission.VIEW_POI,
    },
}


# ---------------------------------------------------------------------------
# 用户模型
# ---------------------------------------------------------------------------


class User(BaseModel):
    """系统用户。"""

    user_id: str = Field(..., description="用户唯一标识")
    username: str = Field(..., description="用户名")
    role: Role = Field(default=Role.GUEST, description="用户角色")
    extra_permissions: set[Permission] = Field(
        default_factory=set,
        description="额外授予的权限（叠加在角色默认权限之上）",
    )

    def has_permission(self, permission: Permission) -> bool:
        """检查用户是否拥有指定权限。

        权限来源（任一满足即为拥有）：
        1. 角色默认权限
        2. 额外授予的权限
        """
        role_perms = ROLE_PERMISSIONS.get(self.role, set())
        return permission in role_perms or permission in self.extra_permissions

    def get_all_permissions(self) -> set[Permission]:
        """获取用户的有效权限集合。"""
        return ROLE_PERMISSIONS.get(self.role, set()) | self.extra_permissions
