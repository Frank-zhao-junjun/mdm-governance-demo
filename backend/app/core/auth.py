"""Authentication and authorization middleware."""
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt

from app.core.config import settings

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

# Password hashing (bcrypt directly, passlib is deprecated on Python 3.13+)
def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# Security scheme
security = HTTPBearer(auto_error=False)

# Mock user database (replace with real DB in production)
MOCK_USERS = {
    "user001": {
        "id": "user001",
        "name": "张三",
        "department": "研发部",
        "role": "applicant",
        "password": hash_password("password001"),
    },
    "user002": {
        "id": "user002",
        "name": "李四",
        "department": "采购部",
        "role": "applicant",
        "password": hash_password("password002"),
    },
    "admin001": {
        "id": "admin001",
        "name": "王管理员",
        "department": "IT部",
        "role": "admin",
        "password": hash_password("adminpass001"),
    },
    "dept001": {
        "id": "dept001",
        "name": "赵部长",
        "department": "生产部",
        "role": "dept_approver",
        "password": hash_password("deptpass001"),
    },
    "data001": {
        "id": "data001",
        "name": "钱数据",
        "department": "数据治理部",
        "role": "data_admin",
        "password": hash_password("datapass001"),
    },
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        return False


def get_user(user_id: str) -> Optional[dict]:
    return MOCK_USERS.get(user_id)


def authenticate_user(user_id: str, password: str) -> Optional[dict]:
    user = get_user(user_id)
    if not user:
        return None
    if not verify_password(password, user["password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """Extract and validate current user from JWT token."""
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
    
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    return {
        "id": user["id"],
        "name": user["name"],
        "department": user["department"],
        "role": user["role"],
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
