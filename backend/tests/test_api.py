"""Integration tests for API endpoints using TestClient."""
import pytest
from app import models


class TestAuthEndpoints:
    """Test authentication API endpoints."""

    def test_login_success(self, client):
        """TC-API-001: Successful login returns token."""
        response = client.post("/api/auth/login", json={
            "user_id": "admin001",
            "password": "adminpass001"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["id"] == "admin001"
        assert data["user"]["role"] == "admin"

    def test_login_wrong_password(self, client):
        """TC-API-002: Wrong password returns 401."""
        response = client.post("/api/auth/login", json={
            "user_id": "admin001",
            "password": "wrongpassword"
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """TC-API-003: Non-existent user returns 401."""
        response = client.post("/api/auth/login", json={
            "user_id": "nobody",
            "password": "password"
        })
        assert response.status_code == 401

    def test_get_me_with_token(self, client):
        """TC-API-004: /api/auth/me with valid token returns user."""
        response = client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "user001"
        assert data["role"] == "applicant"


class TestClassificationEndpoints:
    """Test classification API endpoints."""

    def test_list_classifications(self, client):
        """TC-API-010: List classifications returns tree structure."""
        response = client.get("/api/classifications/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have pre-seeded data
        assert len(data) > 0

    def test_get_classification(self, client, seeded_db):
        """TC-API-011: Get specific classification."""
        response = client.get("/api/classifications/cls-child-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "cls-child-001"
        assert data["code"] == "0101"

    def test_get_nonexistent_classification(self, client):
        """TC-API-012: Non-existent classification returns 404."""
        response = client.get("/api/classifications/non-existent")
        assert response.status_code == 404

    def test_create_classification(self, admin_client):
        """TC-API-013: Create new classification."""
        response = admin_client.post("/api/classifications/", json={
            "code": "TEST",
            "name": "测试分类",
            "level": 1,
            "description": "用于测试"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "TEST"
        assert data["name"] == "测试分类"

    def test_create_level_three_classification(self, admin_client, seeded_db):
        """TC-API-013B: Create and filter a level-3 classification."""
        response = admin_client.post("/api/classifications/", json={
            "code": "010101",
            "name": "不锈钢板",
            "level": 3,
            "parent_id": "cls-child-001",
            "description": "三级小类"
        })
        assert response.status_code == 200

        response = admin_client.get("/api/classifications/?level=3&parent_id=cls-child-001")
        assert response.status_code == 200
        data = response.json()
        assert any(item["code"] == "010101" for item in data)

    def test_get_templates(self, client, seeded_db):
        """TC-API-014: Get attribute templates for classification."""
        response = client.get("/api/classifications/cls-child-001/templates")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # material_grade and thickness


class TestApplicationEndpoints:
    """Test application lifecycle API endpoints."""

    def test_create_application(self, client, seeded_db):
        """TC-API-020: Create new application draft."""
        response = client.post("/api/applications/", json={
            "material_name": "测试不锈钢板材",
            "material_desc": "304不锈钢板",
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {"material_grade": "304不锈钢", "thickness": "2.0"}
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"
        assert data["app_no"].startswith("SQ-")
        assert data["created_by"] == "user001"

    def test_list_applications(self, client):
        """TC-API-021: List applications."""
        response = client.get("/api/applications/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_application(self, client, sample_application):
        """TC-API-022: Get specific application."""
        response = client.get(f"/api/applications/{sample_application.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_application.id
        assert data["material_name"] == sample_application.material_name

    def test_save_draft(self, client, sample_application):
        """TC-API-023: Save draft updates fields."""
        response = client.put(
            f"/api/applications/{sample_application.id}/draft",
            json={"material_name": "更新后的名称"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Response structure depends on serialization; verify basic fields
        assert "application" in data or "message" in data

    def test_save_draft_non_draft_fails(self, client, seeded_db, sample_application):
        """TC-API-024: Saving non-draft application should fail."""
        # Update status to non-draft
        from app import crud
        crud.update_application(seeded_db, sample_application.id, {
            "status": models.ApplicationStatus.PENDING_ADMIN
        })
        
        response = client.put(
            f"/api/applications/{sample_application.id}/draft",
            json={"material_name": "不应该更新"}
        )
        assert response.status_code == 400

    def test_submit_application(self, client, sample_application):
        """TC-API-025: Submit draft application."""
        response = client.post(f"/api/applications/{sample_application.id}/submit")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "material_code" in data
        assert data["material_code"] is not None

    def test_submit_non_draft_fails(self, client, seeded_db, sample_application):
        """TC-API-026: Submit non-draft should fail."""
        from app import crud
        crud.update_application(seeded_db, sample_application.id, {
            "status": models.ApplicationStatus.PENDING_ADMIN
        })
        
        response = client.post(f"/api/applications/{sample_application.id}/submit")
        assert response.status_code == 400

    def test_submit_without_auth(self, client, seeded_db, sample_application):
        """TC-API-027: Submit without auth header should use fallback (dev mode)."""
        # Remove auth header to test dev fallback
        client.headers.pop("Authorization", None)
        response = client.post(f"/api/applications/{sample_application.id}/submit")
        # In dev mode, falls back to mock user
        assert response.status_code in [200, 401]

    def test_pagination_params_validation(self, client):
        """TC-API-028: Invalid pagination params should return 400."""
        response = client.get("/api/applications/?skip=-1")
        assert response.status_code == 400
        
        response = client.get("/api/applications/?limit=0")
        assert response.status_code == 400
        
        response = client.get("/api/applications/?limit=501")
        assert response.status_code == 400

    def test_upload_application_attachment(self, client, sample_application):
        """TC-API-029: Upload and download an application attachment."""
        response = client.post(
            f"/api/applications/{sample_application.id}/attachments",
            files={"file": ("drawing.txt", b"drawing-content", "text/plain")}
        )
        assert response.status_code == 200
        attachment = response.json()
        assert attachment["original_name"] == "drawing.txt"
        assert attachment["size"] == len(b"drawing-content")

        response = client.get(f"/api/applications/{sample_application.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["attachments"][0]["id"] == attachment["id"]

        response = client.get(attachment["download_url"])
        assert response.status_code == 200
        assert response.content == b"drawing-content"


class TestApprovalEndpoints:
    """Test approval workflow endpoints."""

    def test_admin_approve(self, admin_client, seeded_db, sample_application):
        """TC-API-030: Admin approves application."""
        # First submit
        from app import crud
        crud.update_application(seeded_db, sample_application.id, {
            "status": models.ApplicationStatus.PENDING_ADMIN
        })
        
        response = admin_client.post(
            f"/api/applications/{sample_application.id}/admin-approve",
            json={"approved": True, "comment": "审批通过"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "审批通过" in data["message"]

    def test_admin_reject(self, admin_client, seeded_db, sample_application):
        """TC-API-031: Admin rejects application."""
        from app import crud
        crud.update_application(seeded_db, sample_application.id, {
            "status": models.ApplicationStatus.PENDING_ADMIN
        })
        
        response = admin_client.post(
            f"/api/applications/{sample_application.id}/admin-approve",
            json={"approved": False, "comment": "驳回测试"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "驳回" in data["message"]

    def test_dept_approve(self, dept_client, admin_client, seeded_db, sample_application):
        """TC-API-032: Department approves application."""
        # First admin approve
        from app import crud
        crud.update_application(seeded_db, sample_application.id, {
            "status": models.ApplicationStatus.PENDING_DEPT
        })
        
        response = dept_client.post(
            f"/api/applications/{sample_application.id}/dept-approve",
            json={"approved": True, "comment": "部门审批通过"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "部门审批通过" in data["message"]

    def test_approve_wrong_status_fails(self, admin_client, sample_application):
        """TC-API-033: Approve application in wrong status should fail."""
        response = admin_client.post(
            f"/api/applications/{sample_application.id}/admin-approve",
            json={"approved": True, "comment": "测试"}
        )
        # Application is still in DRAFT, not PENDING_ADMIN
        assert response.status_code == 400


class TestPublishEndpoints:
    """Test publish workflow endpoints."""

    def test_publish_application(self, admin_client, seeded_db, sample_application):
        """TC-API-040: Publish approved application."""
        # Set to approved with material_code
        from app import crud
        crud.update_application(seeded_db, sample_application.id, {
            "status": models.ApplicationStatus.APPROVED,
            "material_code": "M01-0101-00001"
        })
        
        response = admin_client.post(f"/api/applications/{sample_application.id}/publish")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "golden_record_id" in data
        assert "material_code" in data

    def test_publish_unapproved_fails(self, admin_client, sample_application):
        """TC-API-041: Publish unapproved application should fail."""
        response = admin_client.post(f"/api/applications/{sample_application.id}/publish")
        assert response.status_code == 400

    def test_publish_nonexistent_fails(self, admin_client):
        """TC-API-042: Publish nonexistent application should 404."""
        response = admin_client.post("/api/applications/non-existent/publish")
        assert response.status_code == 404


class TestAuditEndpoints:
    """Test audit trace endpoints."""

    def test_get_audit_trace(self, client, seeded_db, sample_application):
        """TC-API-050: Get audit trace for application."""
        # Create some audit logs
        from app.services.audit_service import AuditService
        audit = AuditService(seeded_db)
        audit.log(sample_application.id, "submit", "user001", "张三", "success")
        audit.log(sample_application.id, "validate", "system", "系统自动", "success")
        
        response = client.get(f"/api/applications/{sample_application.id}/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == sample_application.id
        assert "trace" in data
        assert len(data["trace"]) == 2

    def test_audit_trace_step_ids_unique(self, client, seeded_db, sample_application):
        """TC-API-051: Audit step IDs should be unique."""
        from app.services.audit_service import AuditService
        audit = AuditService(seeded_db)
        audit.log(sample_application.id, "submit", "user001", "张三", "success")
        audit.log(sample_application.id, "validate", "system", "系统自动", "success")
        
        response = client.get(f"/api/applications/{sample_application.id}/audit")
        data = response.json()
        step_ids = [log["step_id"] for log in data["trace"]]
        assert len(step_ids) == len(set(step_ids))


class TestGoldenRecordEndpoints:
    """Test Golden Record endpoints."""

    def test_list_golden_records(self, client):
        """TC-API-060: List golden records."""
        response = client.get("/api/golden-records/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_golden_record(self, client, seeded_db):
        """TC-API-061: Get specific golden record."""
        # Create a golden record
        from app import models, crud, schemas
        data = schemas.GoldenRecordBase(
            material_code="M01-0101-99999",
            material_name="测试GR",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW
        )
        gr = crud.create_golden_record(seeded_db, data, "app-001", "user001")
        
        response = client.get(f"/api/golden-records/{gr.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == gr.id
        assert data["material_code"] == "M01-0101-99999"


class TestDashboardEndpoints:
    """Test dashboard and health endpoints."""

    def test_dashboard_stats(self, client):
        """TC-API-070: Dashboard returns statistics."""
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "recent_applications" in data
        assert "recent_audit_logs" in data

    def test_health_check(self, client):
        """TC-API-071: Health check returns system status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data

    def test_btp_mock_health(self, client):
        """TC-API-072: BTP mock health endpoint."""
        response = client.get("/api/btp-mock/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestMetadataGovernanceEndpoints:
    """Test metadata governance overview endpoints."""

    def test_metadata_governance_overview_empty(self, client):
        """TC-API-073: Metadata governance overview returns all sections."""
        response = client.get("/api/metadata-governance/overview")
        assert response.status_code == 200
        data = response.json()
        assert "openmetadata" in data
        assert "summary" in data
        assert "catalog" in data
        assert "lineage" in data
        assert "quality_tests" in data
        assert "traces" in data

    def test_metadata_governance_overview_with_record(self, client, seeded_db, sample_application):
        """TC-API-074: Overview includes catalog, lineage, and trace data."""
        from app import crud, schemas
        from app.services.audit_service import AuditService

        crud.update_application(seeded_db, sample_application.id, {
            "status": models.ApplicationStatus.PUBLISHED,
            "material_code": "M01-0101-00002",
            "validation_result": {"passed": True, "errors": []}
        })
        gr = crud.create_golden_record(
            seeded_db,
            schemas.GoldenRecordBase(
                material_code="M01-0101-00002",
                material_name=sample_application.material_name,
                material_desc=sample_application.material_desc,
                classification_id=sample_application.classification_id,
                attribute_values=sample_application.attribute_values,
                material_type=sample_application.material_type,
            ),
            sample_application.id,
            "user001"
        )
        crud.update_golden_record(seeded_db, gr.id, {
            "btp_published": True,
            "om_synced": True,
            "om_entity_fqn": "RalphLoop.Material.M01-0101-00002"
        })
        audit = AuditService(seeded_db)
        audit.log(sample_application.id, "validate", "system", "系统自动", "success", {"passed": True, "errors": []})
        audit.log(sample_application.id, "om_test", "system", "系统自动", "success", {
            "results": [{"test_name": "material_code_not_null", "passed": True, "message": "物料编码非空"}]
        })

        response = client.get("/api/metadata-governance/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["metadata_assets"] >= 1
        assert any(item["material_code"] == "M01-0101-00002" for item in data["catalog"])
        assert any(edge["to"] == "openmetadata" for edge in data["lineage"]["edges"])
        assert any(test["source"] == "OpenMetadata" for test in data["quality_tests"])
        assert any(trace["application_id"] == sample_application.id for trace in data["traces"])


class TestAuthorization:
    """Test authorization - role-based access control."""

    def test_applicant_cannot_admin_approve(self, client, seeded_db, sample_application):
        """TC-API-080: Applicant cannot access admin approval."""
        from app import crud
        crud.update_application(seeded_db, sample_application.id, {
            "status": models.ApplicationStatus.PENDING_ADMIN
        })
        
        response = client.post(
            f"/api/applications/{sample_application.id}/admin-approve",
            json={"approved": True}
        )
        # Should get 403 forbidden since client has applicant role
        assert response.status_code == 403

    def test_applicant_cannot_publish(self, client, seeded_db, sample_application):
        """TC-API-081: Applicant cannot publish."""
        from app import crud
        crud.update_application(seeded_db, sample_application.id, {
            "status": models.ApplicationStatus.APPROVED
        })
        
        response = client.post(f"/api/applications/{sample_application.id}/publish")
        assert response.status_code == 403

    def test_admin_can_access_all(self, admin_client):
        """TC-API-082: Admin can access applicant endpoints."""
        response = admin_client.get("/api/applications/")
        assert response.status_code == 200

    def test_unauthorized_request(self, client):
        """TC-API-083: Request without token in non-DEV mode behavior."""
        # Remove auth header to test dev fallback
        original_auth = client.headers.pop("Authorization", None)
        try:
            response = client.get("/api/applications/")
            # In dev mode: falls back to mock user (200), in production: 401
            assert response.status_code in [200, 401]
        finally:
            if original_auth:
                client.headers.update({"Authorization": original_auth})
