import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user, require_admin, require_read
from app.core.db import get_session
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Role, User
from app.schemas import LoginRequest, Message, Page, Token, UserCreate, UserRead, UserUpdate

router = APIRouter(tags=["认证与用户"])


@router.post("/auth/login", response_model=Token, summary="登录")
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> Token:
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    token = create_access_token(subject=str(user.id), role=user.role)
    return Token(access_token=token, user=UserRead.model_validate(user))


@router.get("/auth/me", response_model=UserRead, summary="当前登录用户")
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/users", response_model=Page[UserRead], summary="用户列表")
def list_users(
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> Page[UserRead]:
    users = session.exec(select(User).order_by(User.created_at)).all()
    return Page(total=len(users), items=[UserRead.model_validate(u) for u in users])


@router.post("/users", response_model=UserRead, status_code=201, summary="新建用户")
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> User:
    if session.exec(select(User).where(User.email == payload.email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已存在")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead, summary="修改用户")
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data and data["password"]:
        user.hashed_password = hash_password(data.pop("password"))
    data.pop("password", None)
    if user.id == admin.id and data.get("role") and data["role"] != Role.ADMIN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能降低自己的角色，请让其他管理员操作")
    for k, v in data.items():
        setattr(user, k, v)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/users/{user_id}", response_model=Message, summary="删除用户")
def delete_user(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> Message:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除自己")
    session.delete(user)
    session.commit()
    return Message(detail="已删除")
