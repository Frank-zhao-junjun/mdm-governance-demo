"""Authentication and authorization middleware (database-backed users)."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
import bcrypt

from app.core.config import settings
from app.core.database import get_db
from app import models

# JWT configuration
# Production (ENV=production) must provide MDM_SECRET_KEY; other environments
# (development/test/CI) fall back to a fixed local-only key.
SECRET_KEY = settings.SECRET_KEY
if not SECRET_KEY:
    if settings.ENV == "production":
        raise RuntimeError(
            "MDM_SECRET_KEY environment variable must be set in production"
        )
    SECRET_KEY = "dev-only-insecure-mdm-key-not-for-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# 登录失败锁定策略
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15

# Password hashing (bcrypt directly, passlib is deprecated on Python 3.13+)
def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# Security scheme
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        return False


def _is_locked(user: models.User, now: Optional[datetime] = None) -> bool:
    if user.locked_until is None:
        return False
    now = now or datetime.now(timezone.utc)
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return now < locked_until


def get_user(db: Session, user_id: str) -> Optional[models.User]:
    return db.get(models.User, user_id)


def authenticate_user(
    db: Session, user_id: str, password: str
) -> Tuple[Optional[models.User], Optional[str]]:
    """校验凭据并执行失败锁定策略。

    返回 (user, error)：user 非 None 表示认证成功；error 为中文失败原因。
    失败原因统一不区分"用户不存在/密码错误/已锁定"，但锁定原因单独提示，
    便于合法用户理解等待时间。
    """
    user = get_user(db, user_id)
    if user is None:
        return None, "用户名或密码错误"
    if user.status != models.UserStatus.ACTIVE:
        return None, "账号已停用，请联系管理员"
    now = datetime.now(timezone.utc)
    if _is_locked(user, now):
        remaining = (user.locked_until.replace(tzinfo=timezone.utc) - now).seconds // 60 + 1
        return None, f"登录失败次数过多，账号已锁定，请约 {remaining} 分钟后重试"
    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.failed_login_count = 0
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
        db.commit()
        return None, "用户名或密码错误"
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    return user, None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """Extract and validate current user from JWT token (with session revocation)."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if user.status != models.UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="账号已停用")
    token_version = payload.get("ver")
    if token_version is None or int(token_version) != int(user.token_version):
        raise HTTPException(
            status_code=401,
            detail="登录状态已失效（密码已修改或会话被撤销），请重新登录",
        )
    if _is_locked(user):
        raise HTTPException(status_code=401, detail="账号已锁定")

    return {
        "id": user.id,
        "name": user.name,
        "department": user.department,
        "role": user.role.value if isinstance(user.role, models.UserRole) else user.role,
    }


def require_role(allowed_roles: List[str]):
    """Dependency factory to enforce role-based access."""
    def role_checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker


# Predefined role requirements
require_applicant = require_role(["applicant", "admin", "data_admin"])
require_admin = require_role(["admin", "data_admin"])
require_dept_approver = require_role(["dept_approver", "admin", "data_admin"])
require_any = require_role(["applicant", "admin", "data_admin", "dept_approver"])
