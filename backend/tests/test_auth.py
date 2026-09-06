# -*- coding: utf-8 -*-
"""认证核心单元测试：密码哈希、用户查库、登录锁定策略、JWT 签发/校验。"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from app import models
from app.core.auth import (
    ALGORITHM,
    LOCKOUT_MINUTES,
    MAX_FAILED_LOGINS,
    SECRET_KEY,
    authenticate_user,
    create_access_token,
    get_current_user,
    get_user,
    hash_password,
    require_any,
    require_applicant,
    require_dept_approver,
    verify_password,
)
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPAuthorizationCredentials

pytestmark = pytest.mark.unit


class TestPasswordVerification:
    """密码哈希与校验（bcrypt，$2b$ 格式）。"""

    def test_hash_and_verify_roundtrip(self):
        hashed = hash_password("secret123")
        assert hashed.startswith("$2")
        assert verify_password("secret123", hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_seed_user_passwords_valid(self, db):
        """种子用户的密码必须与 seed_users 定义一致。"""
        from app.core.seed_users import SEED_USERS

        for spec in SEED_USERS:
            user = get_user(db, spec["id"])
            assert user is not None, f"种子用户 {spec['id']} 不存在"
            assert verify_password(spec["password"], user.password_hash), (
                f"{spec['id']} 密码校验失败"
            )


class TestUserLookup:
    """get_user 从数据库查询（MOCK_USERS 硬编码已移除）。"""

    def test_get_existing_user(self, db):
        user = get_user(db, "admin001")
        assert user is not None
        assert user.role == models.UserRole.ADMIN
        assert user.status == models.UserStatus.ACTIVE

    def test_get_missing_user(self, db):
        assert get_user(db, "nonexistent") is None


class TestAuthentication:
    """authenticate_user：凭据校验 + 失败锁定策略。"""

    def test_success_updates_last_login(self, db):
        user, error = authenticate_user(db, "user001", "password001")
        assert error is None
        assert user is not None
        assert user.last_login_at is not None
        assert user.failed_login_count == 0

    def test_wrong_password_fails(self, db):
        user, error = authenticate_user(db, "user001", "wrong-password")
        assert user is None
        assert error
        db.refresh(get_user(db, "user001"))
        assert get_user(db, "user001").failed_login_count == 1

    def test_unknown_user_generic_error(self, db):
        user, error = authenticate_user(db, "ghost", "whatever")
        assert user is None
        assert error == "用户名或密码错误"

    def test_lockout_after_max_failures(self, db):
        for _ in range(MAX_FAILED_LOGINS):
            user, error = authenticate_user(db, "user002", "bad-password")
            assert user is None
        locked = get_user(db, "user002")
        assert locked.locked_until is not None
        assert locked.failed_login_count == 0
        remaining = locked.locked_until - datetime.now(timezone.utc).replace(tzinfo=None)
        assert timedelta(minutes=LOCKOUT_MINUTES - 1) <= remaining <= timedelta(minutes=LOCKOUT_MINUTES)

    def test_locked_account_rejects_even_correct_password(self, db):
        for _ in range(MAX_FAILED_LOGINS):
            authenticate_user(db, "user002", "bad-password")
        user, error = authenticate_user(db, "user002", "password002")
        assert user is None
        assert "锁定" in error

    def test_lockout_expires(self, db):
        for _ in range(MAX_FAILED_LOGINS):
            authenticate_user(db, "user002", "bad-password")
        locked = get_user(db, "user002")
        locked.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
        user, error = authenticate_user(db, "user002", "password002")
        assert error is None
        assert user is not None

    def test_success_resets_failure_count(self, db):
        authenticate_user(db, "user002", "bad-password")
        authenticate_user(db, "user002", "bad-password")
        user, error = authenticate_user(db, "user002", "password002")
        assert error is None
        assert get_user(db, "user002").failed_login_count == 0

    def test_disabled_account_rejected(self, db):
        user = get_user(db, "user002")
        user.status = models.UserStatus.DISABLED
        db.commit()
        result, error = authenticate_user(db, "user002", "password002")
        assert result is None
        assert "停用" in error


def _creds(token: str) -> HTTPAuthorizationCredentials:
    """模拟 HTTPBearer 注入的凭据对象。"""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestJWTToken:
    """JWT 签发与过期校验。"""

    def test_token_contains_version(self, db):
        user = get_user(db, "admin001")
        token = create_access_token(
            {"sub": user.id, "role": user.role.value, "ver": user.token_version}
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "admin001"
        assert payload["ver"] == 0

    def test_expired_token_rejected_by_get_current_user(self, db):
        token = create_access_token({"sub": "admin001"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(HTTPException) as exc:
            get_current_user(_creds(token), db)
        assert exc.value.status_code == 401

    def test_token_version_mismatch_rejected(self, db):
        user = get_user(db, "admin001")
        token = create_access_token(
            {"sub": user.id, "role": user.role.value, "ver": user.token_version}
        )
        user.token_version += 1
        db.commit()
        with pytest.raises(HTTPException) as exc:
            get_current_user(_creds(token), db)
        assert exc.value.status_code == 401

    def test_disabled_user_token_rejected(self, db):
        user = get_user(db, "user001")
        token = create_access_token(
            {"sub": user.id, "role": user.role.value, "ver": user.token_version}
        )
        user.status = models.UserStatus.DISABLED
        db.commit()
        with pytest.raises(HTTPException) as exc:
            get_current_user(_creds(token), db)
        assert exc.value.status_code == 401


class TestRoleRequirements:
    """角色依赖工厂。"""

    def test_predefined_requirements_exist(self):
        assert require_applicant is not None
        assert require_any is not None
        assert require_dept_approver is not None
