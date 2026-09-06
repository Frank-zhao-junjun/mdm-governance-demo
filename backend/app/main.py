"""FastAPI main application entry point.

Governance-only service: data standards + stock records + quality checks.
Application/approval/golden-record/publish flows were removed (SPEC §1.4).
"""
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api import copilot, data_import, data_standards, evidence, governance, metadata, owners, quality_checks, records, suspected_errors, users
from app.core.auth import authenticate_user, create_access_token, get_current_user, hash_password, verify_password
from app.core.config import settings
from app.core.database import Base, engine, get_db
from app import crud, schemas
from app.models import StepName
from app.services.audit_service import AuditService

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Stock-data governance service: standards + quality management",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS - restrict in production
if settings.DEBUG:
    # Development: allow localhost origins
    origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
else:
    # Production: restrict to specific origins
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Static files (frontend)
static_dir = os.path.join(os.path.dirname(__file__), "../../dist")
if os.path.exists(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

# Include routers
app.include_router(data_standards.router)
app.include_router(quality_checks.router)
app.include_router(suspected_errors.router)
app.include_router(data_import.router)
app.include_router(copilot.router)
app.include_router(governance.router)
app.include_router(owners.router)
app.include_router(metadata.router)
app.include_router(evidence.router)
app.include_router(records.router)
app.include_router(users.router)


@app.post(
    "/api/auth/login",
    summary="用户登录（获取 JWT 令牌）",
    responses={
        401: {"description": "用户名或密码错误 / 账号被锁定或禁用"},
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "admin": {
                            "summary": "管理员登录",
                            "value": {"user_id": "admin001", "password": "adminpass001"},
                        },
                        "user": {
                            "summary": "普通用户登录",
                            "value": {"user_id": "user001", "password": "password001"},
                        },
                    }
                }
            }
        }
    },
)
def login(credentials: dict, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token.

    Request body: {"user_id": "user001", "password": "password001"}
    连续失败达到上限（默认 5 次）将锁定账号 15 分钟；成功/失败均落审计。
    """
    user_id = (credentials.get("user_id") or "").strip()
    password = credentials.get("password") or ""
    user, reason = authenticate_user(db, user_id, password)
    audit = AuditService(db)
    if not user:
        try:
            audit.log(
                step_name=StepName.USER_LOGIN_FAILED,
                executed_by=user_id or "unknown",
                executed_by_name=user_id or "unknown",
                status="failed",
                details={"reason": reason or "invalid_credentials"},
            )
        except Exception:
            pass
        raise HTTPException(status_code=401, detail=reason or "用户名或密码错误")

    try:
        audit.log(
            step_name=StepName.USER_LOGIN,
            executed_by=user.id,
            executed_by_name=user.name,
            status="success",
            details={"role": user.role.value},
        )
    except Exception:
        pass

    token = create_access_token({"sub": user.id, "role": user.role.value, "ver": user.token_version})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "role": user.role.value,
            "department": user.department,
        },
    }


@app.get(
    "/api/auth/me",
    summary="获取当前登录用户信息",
    responses={401: {"description": "未认证 / 令牌无效或过期"}},
)
def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user info."""
    return user


@app.post(
    "/api/me/password",
    summary="本人修改密码（验证旧密码，成功后所有会话失效需重新登录）",
    responses={
        400: {"description": "旧密码错误或新密码不合规"},
        401: {"description": "未认证 / 令牌无效或过期"},
    },
)
def change_my_password(
    body: schemas.PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    me = crud.get_user(db, user["id"])
    if me is None:
        raise HTTPException(status_code=401, detail="用户不存在或已删除")
    if not verify_password(body.old_password, me.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")
    crud.change_user_password(db, me, hash_password(body.new_password))
    try:
        AuditService(db).log(
            step_name=StepName.USER_PASSWORD_CHANGE,
            executed_by=me.id,
            executed_by_name=me.name,
            status="success",
            details={"mode": "self_change"},
        )
    except Exception:
        pass
    return {"message": "密码已修改，请使用新密码重新登录"}


@app.get("/", summary="健康检查 / API 欢迎信息")
def root():
    return {
        "message": "Stock Data Governance API",
        "version": settings.VERSION,
        "docs": "/docs",
    }


# Serve index.html for all non-API routes (SPA fallback)
@app.get("/{path:path}", summary="SPA 前端兜底路由（dist/ 存在时返回 index.html）")
def serve_spa(path: str):
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path) and not path.startswith("api") and not path.startswith("docs"):
        return FileResponse(index_path)
    return {"message": "Stock Data Governance API", "version": settings.VERSION}
