# -*- coding: utf-8 -*-
"""用户管理 API 的 HTTP 级集成测试。

覆盖：登录全链路（含审计）、失败锁定、本人改密（token_version 撤销）、
管理员建号/更新/重置/禁用、权限门禁与防自锁护栏。
"""

import pytest

from app.core.auth import create_access_token


def _login(client, user_id, password):
    return client.post("/api/auth/login", json={"user_id": user_id, "password": password})


def _admin_headers(user_id="admin001"):
    token = create_access_token({"sub": user_id, "role": "admin", "ver": 0})
    return {"Authorization": f"Bearer {token}"}


def _user_headers(user_id, role="applicant"):
    token = create_access_token({"sub": user_id, "role": role, "ver": 0})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.usefixtures("seeded_db")
class TestLoginFlow:
    def test_login_success_returns_token_and_user(self, client):
        resp = _login(client, "user001", "password001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["user"]["id"] == "user001"
        assert body["user"]["role"] == "applicant"

    def test_login_failure_401(self, client):
        resp = _login(client, "user001", "wrong-password")
        assert resp.status_code == 401
        assert "detail" in resp.json()

    def test_login_success_audited(self, client, db):
        _login(client, "user001", "password001")
        from app.models import AuditLog, StepName

        row = (
            db.query(AuditLog)
            .filter(AuditLog.step_name == StepName.USER_LOGIN, AuditLog.executed_by == "user001")
            .first()
        )
        assert row is not None

    def test_login_failure_audited(self, client, db):
        _login(client, "user001", "wrong-password")
        from app.models import AuditLog, StepName

        row = (
            db.query(AuditLog)
            .filter(
                AuditLog.step_name == StepName.USER_LOGIN_FAILED,
                AuditLog.executed_by == "user001",
            )
            .first()
        )
        assert row is not None


@pytest.mark.usefixtures("seeded_db")
class TestLockout:
    def test_locked_after_max_failures(self, client):
        for _ in range(5):
            assert _login(client, "user002", "bad-pass").status_code == 401
        resp = _login(client, "user002", "password002")
        assert resp.status_code == 401
        assert "锁定" in resp.json()["detail"]

    def test_lockout_is_per_user(self, client):
        for _ in range(5):
            _login(client, "user002", "bad-pass")
        assert _login(client, "user001", "password001").status_code == 200

    def test_reset_clears_lockout(self, client, db):
        for _ in range(5):
            _login(client, "user002", "bad-pass")
        from app.core.auth import hash_password
        from app.models import User

        user = db.get(User, "user002")
        user.locked_until = None
        user.password_hash = hash_password("password002")
        db.commit()
        assert _login(client, "user002", "password002").status_code == 200


@pytest.mark.usefixtures("seeded_db")
class TestPasswordChange:
    def _change(self, client, headers, old, new):
        return client.post(
            "/api/me/password", json={"old_password": old, "new_password": new}, headers=headers
        )

    def test_change_password_invalidates_existing_token(self, client):
        login = _login(client, "user001", "password001").json()
        old_token = login["access_token"]
        headers = {"Authorization": f"Bearer {old_token}"}

        resp = self._change(client, headers, "password001", "NewPass12345")
        assert resp.status_code == 200

        me = client.get("/api/auth/me", headers=headers)
        assert me.status_code == 401

        relogin = _login(client, "user001", "NewPass12345")
        assert relogin.status_code == 200

    def test_change_password_requires_old_password(self, client):
        headers = _user_headers("user001")
        resp = self._change(client, headers, "totally-wrong", "NewPass12345")
        assert resp.status_code in (400, 401)

    def test_change_password_rejects_short_new(self, client):
        headers = _user_headers("user001")
        resp = self._change(client, headers, "password001", "short")
        assert resp.status_code == 422

    def test_change_password_requires_authentication(self, client):
        client.headers.pop("Authorization", None)
        resp = self._change(client, {}, "password001", "NewPass12345")
        assert resp.status_code in (401, 403)


@pytest.mark.usefixtures("seeded_db")
class TestAdminUserManagement:
    def test_create_user_by_admin(self, client):
        resp = client.post(
            "/api/users",
            json={
                "user_id": "user003",
                "name": "王五",
                "department": "质量部",
                "role": "applicant",
                "password": "InitPass123",
            },
            headers=_admin_headers(),
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == "user003"
        assert _login(client, "user003", "InitPass123").status_code == 200

    def test_create_user_duplicate_conflict(self, client):
        resp = client.post(
            "/api/users",
            json={
                "user_id": "user001",
                "name": "重复用户",
                "role": "applicant",
                "password": "InitPass123",
            },
            headers=_admin_headers(),
        )
        assert resp.status_code == 409

    def test_create_user_forbidden_for_applicant(self, client):
        resp = client.post(
            "/api/users",
            json={"user_id": "user003", "name": "x", "role": "applicant", "password": "InitPass123"},
            headers=_user_headers("user001"),
        )
        assert resp.status_code == 403

    def test_reset_password_invalidates_sessions(self, client):
        login = _login(client, "user001", "password001").json()
        old_token = login["access_token"]

        resp = client.post(
            "/api/users/user001/reset-password",
            json={"new_password": "AdminReset99"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
        assert me.status_code == 401
        assert _login(client, "user001", "password001").status_code == 401
        assert _login(client, "user001", "AdminReset99").status_code == 200

    def test_disable_user_revokes_access(self, client):
        login = _login(client, "user002", "password002").json()
        token = login["access_token"]

        resp = client.put(
            "/api/users/user002", json={"status": "disabled"}, headers=_admin_headers()
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 401
        assert _login(client, "user002", "password002").status_code == 401

    def test_reenable_user_restores_access(self, client):
        client.put("/api/users/user002", json={"status": "disabled"}, headers=_admin_headers())
        resp = client.put(
            "/api/users/user002", json={"status": "active"}, headers=_admin_headers()
        )
        assert resp.status_code == 200
        assert _login(client, "user002", "password002").status_code == 200

    def test_admin_cannot_disable_self(self, client):
        resp = client.put(
            "/api/users/admin001", json={"status": "disabled"}, headers=_admin_headers()
        )
        assert resp.status_code in (400, 403)

    def test_admin_cannot_demote_self(self, client):
        resp = client.put(
            "/api/users/admin001", json={"role": "applicant"}, headers=_admin_headers()
        )
        assert resp.status_code in (400, 403)

    def test_update_role_bumps_token_version(self, client):
        login = _login(client, "user001", "password001").json()
        token = login["access_token"]

        resp = client.put(
            "/api/users/user001", json={"role": "data_admin"}, headers=_admin_headers()
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "data_admin"

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 401

    def test_list_users_paginated(self, client):
        resp = client.get("/api/users", params={"limit": 2, "skip": 0}, headers=_admin_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 5
        assert len(body["items"]) == 2

    def test_list_users_filter_role(self, client):
        resp = client.get("/api/users", params={"role": "applicant"}, headers=_admin_headers())
        assert resp.status_code == 200
        assert all(item["role"] == "applicant" for item in resp.json()["items"])

    def test_list_users_forbidden_for_applicant(self, client):
        resp = client.get("/api/users", headers=_user_headers("user001"))
        assert resp.status_code == 403

    def test_get_single_user(self, client):
        resp = client.get("/api/users/data001", headers=_admin_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "data001"
        assert body["role"] == "data_admin"
        assert "password_hash" not in body

    def test_get_missing_user_404(self, client):
        resp = client.get("/api/users/no_such_user", headers=_admin_headers())
        assert resp.status_code == 404


@pytest.mark.usefixtures("seeded_db")
class TestTokenVersion:
    def test_stale_token_rejected_after_bump(self, client, db):
        login = _login(client, "user001", "password001").json()
        token = login["access_token"]

        from app.models import User

        user = db.get(User, "user001")
        user.token_version += 1
        db.commit()

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 401

    def test_token_without_ver_claim_rejected(self, client):
        from app.core.auth import create_access_token

        stale = create_access_token({"sub": "user001", "role": "applicant"})
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {stale}"})
        assert me.status_code == 401
