"""用户管理 API：管理员建号/更新/重置密码 + 本人改密。

安全约束：
- 全部端点要求有效 JWT；管理操作仅 admin/data_admin（require_admin）
- 创建/重置/改密均落审计（step_name=USER_CREATE/USER_UPDATE/USER_PASSWORD_CHANGE）
- 禁用、改角色、重置密码都会 bump token_version，使存量会话立即失效
- 不提供物理删除（治理平台审计不可变性），停用走 status=disabled
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core.auth import (
    hash_password,
    require_admin,
)
from app.core.database import get_db
from app.models import StepName
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/users", tags=["Users"])


def _user_to_response(user: models.User) -> schemas.UserResponse:
    return schemas.UserResponse(
        id=user.id,
        name=user.name,
        department=user.department,
        role=user.role.value if isinstance(user.role, models.UserRole) else user.role,
        status=user.status.value if isinstance(user.status, models.UserStatus) else user.status,
        token_version=user.token_version,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=schemas.UserListResponse, summary="用户列表（支持角色/状态过滤）")
def list_users(
    role: Optional[str] = Query(None, description="按角色过滤：applicant/admin/data_admin/dept_approver"),
    status: Optional[str] = Query(None, description="按状态过滤：active/disabled"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    users, total = crud.get_users(db, role=role, status=status, skip=skip, limit=limit)
    return schemas.UserListResponse(
        total=total, items=[_user_to_response(u) for u in users]
    )


@router.post("", response_model=schemas.UserResponse, status_code=201, summary="创建用户（管理员建号制）", responses={400: {"description": "请求参数不合法"}, 409: {"description": "用户 ID 已存在"}, 403: {"description": "权限不足，仅 admin/data_admin 可建号"}})
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    if crud.get_user(db, payload.user_id) is not None:
        raise HTTPException(status_code=409, detail=f"用户 {payload.user_id} 已存在")
    new_user = crud.create_user(
        db,
        user_id=payload.user_id,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        department=payload.department,
    )
    audit = AuditService(db)
    audit.log(
        step_name=models.StepName.USER_CREATE,
        executed_by=user["id"],
        executed_by_name=user["name"],
        status="success",
        details={"target_user": new_user.id, "role": new_user.role.value},
    )
    return _user_to_response(new_user)


@router.put("/{user_id}", response_model=schemas.UserResponse, summary="更新用户（角色/状态/基本信息）", responses={400: {"description": "请求参数不合法或自锁操作"}, 404: {"description": "用户不存在"}, 403: {"description": "权限不足"}})
def update_user(
    user_id: str,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    target = crud.get_user(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    # 防自锁护栏：不允许把自己的角色改掉或把自己停用
    if user_id == user["id"] and ("role" in changes or changes.get("status") == "disabled"):
        raise HTTPException(status_code=400, detail="不能修改自己的角色或停用自己")
    bump = "role" in changes or changes.get("status") == "disabled"
    updated = crud.update_user(db, target, changes, bump_token_version=bump)
    audit = AuditService(db)
    audit.log(
        step_name=models.StepName.USER_UPDATE,
        executed_by=user["id"],
        executed_by_name=user["name"],
        status="success",
        details={"target_user": user_id, "changes": changes, "token_version_bumped": bump},
    )
    return _user_to_response(updated)


@router.post("/{user_id}/reset-password", response_model=schemas.UserResponse, summary="管理员重置密码（存量会话全部失效）", responses={404: {"description": "用户不存在"}, 403: {"description": "权限不足"}})
def reset_password(
    user_id: str,
    body: schemas.PasswordResetRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(require_admin),
):
    target = crud.get_user(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
    updated = crud.reset_user_password(db, target, hash_password(body.new_password))
    AuditService(db).log(
        step_name=StepName.USER_PASSWORD_CHANGE,
        executed_by=actor["id"],
        executed_by_name=actor["name"],
        status="success",
        details={"mode": "admin_reset", "target_user": user_id},
    )
    return _user_to_response(updated)


@router.get("/{user_id}", response_model=schemas.UserResponse, summary="查询单个用户", responses={404: {"description": "用户不存在"}, 403: {"description": "权限不足，仅 admin/data_admin 可查"}})
def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    target = crud.get_user(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
    return _user_to_response(target)
