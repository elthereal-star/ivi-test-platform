import uuid
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.config import settings
from app.core.db import get_session
from app.core.security import decode_access_token
from app.models import Role, User

bearer = HTTPBearer(auto_error=False)

# 角色能力表：读全员（含只读访客），写操作收敛到 lead 及以上
READ_ROLES = {Role.ADMIN, Role.LEAD, Role.EXECUTOR, Role.VIEWER}
EXEC_ROLES = {Role.ADMIN, Role.LEAD, Role.EXECUTOR}
WRITE_ROLES = {Role.ADMIN, Role.LEAD}


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(cred.credentials)
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录状态已失效，请重新登录") from None

    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不存在或已停用")
    return user


def require(roles: set[Role]) -> Callable[..., User]:
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "当前角色无此操作权限")
        return user

    return _dep


require_read = require(READ_ROLES)
require_exec = require(EXEC_ROLES)
require_write = require(WRITE_ROLES)
require_admin = require({Role.ADMIN})


def verify_automation_token(
    x_automation_token: str = Header(default="", alias="X-Automation-Token"),
) -> None:
    """自动化脚本用静态令牌，不用 JWT —— CI 里不该保存人的账号。"""
    if not settings.AUTOMATION_TOKEN or x_automation_token != settings.AUTOMATION_TOKEN:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "自动化令牌无效")
