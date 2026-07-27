"""登录鉴权与 RBAC 服务。"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt as pyjwt

from app.config import JWT_ACCESS_TOKEN_EXPIRES, JWT_SECRET
from app.models.database import get_db_session
from app.models.user import User, UserRole

logger = logging.getLogger("zhinong.auth_service")

ALGORITHM = "HS256"


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def create_user(
    username: str,
    email: str,
    password: str,
    role: UserRole = UserRole.ASSESSOR,
) -> Optional[User]:
    """创建新用户。"""
    try:
        with get_db_session() as session:
            existing = session.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            if existing:
                logger.warning("User already exists: %s / %s", username, email)
                return None
            user = User(username=username, email=email, role=role)
            user.set_password(password)
            session.add(user)
            session.flush()
            logger.info("User created: %s (role=%s)", username, role.value)
            return user
    except Exception as exc:
        logger.error("Failed to create user: %s", exc)
        return None


def authenticate_user(username: str, password: str) -> Optional[User]:
    """验证用户名密码，成功返回 User 对象。"""
    try:
        with get_db_session() as session:
            user = session.query(User).filter(
                (User.username == username) | (User.email == username),
                User.is_active.is_(True),
            ).first()
            if user and user.check_password(password):
                return user
        return None
    except Exception as exc:
        logger.error("Authentication error: %s", exc)
        return None


def create_access_token(user: User) -> str:
    """生成 JWT access token。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRES),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """解码 JWT token，失败返回 None。"""
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except pyjwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except pyjwt.InvalidTokenError as exc:
        logger.warning("Invalid token: %s", exc)
        return None


def get_user_by_id(user_id: int) -> Optional[User]:
    """按 ID 获取用户。"""
    try:
        with get_db_session() as session:
            return session.query(User).filter(User.id == user_id).first()
    except Exception:
        return None


def check_permission(user_role: UserRole, required_role: UserRole) -> bool:
    """检查角色权限。"""
    role_hierarchy = {
        UserRole.ADMIN: 3,
        UserRole.ASSESSOR: 2,
        UserRole.READONLY: 1,
    }
    return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_role, 0)


def init_admin_user() -> None:
    """初始化管理员账号（首次启动时调用）。"""
    from app.config import ADMIN_EMAIL, ADMIN_PASSWORD

    try:
        with get_db_session() as session:
            existing = session.query(User).filter(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            ).first()
            if existing:
                logger.info("Admin user already exists: %s", existing.username)
                return

        admin = create_user(
            username="admin",
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            role=UserRole.ADMIN,
        )
        if admin:
            logger.info(
                "✅ Admin user created: %s / %s",
                ADMIN_EMAIL,
                "（使用 .env ADMIN_PASSWORD）",
            )
    except Exception as exc:
        logger.warning("Failed to init admin user: %s", exc)
