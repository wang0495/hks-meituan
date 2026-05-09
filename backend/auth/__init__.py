"""CityFlow 访问控制模块。

提供基于角色的访问控制（RBAC），包括：
- 角色与权限定义
- 用户模型
- 访问控制服务（单例）

Usage:
    from backend.auth import get_access_control, Permission, Role, User

    acl = get_access_control()
    acl.add_user(User(user_id="u1", username="admin", role=Role.ADMIN))
    if acl.check_permission("u1", Permission.MANAGE_USERS):
        ...
"""

from __future__ import annotations

from backend.auth.access_control import AccessControl, get_access_control
from backend.auth.models import ROLE_PERMISSIONS, Permission, Role, User

__all__ = [
    "AccessControl",
    "Permission",
    "Role",
    "User",
    "ROLE_PERMISSIONS",
    "get_access_control",
]
