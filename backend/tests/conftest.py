"""pytest configuration and shared fixtures."""
import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend/app is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import Base, get_db
from app.main import app
from app import models

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Single connection pool for shared in-memory DB
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override dependency to use test database."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Apply override
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def db():
    """Create fresh database tables and yield a session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _make_client(user_id: str, role: str) -> TestClient:
    """Build a TestClient carrying a JWT for the given mock user."""
    from app.core.auth import create_access_token
    token = create_access_token({"sub": user_id, "role": role})
    os.environ.setdefault("ENV", "test")
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture(scope="function")
def client(seeded_db):
    """Read-only applicant client (user001) + seeded standards."""
    return _make_client("user001", "applicant")


@pytest.fixture(scope="function")
def data_client(seeded_db):
    """Data-admin client (data001) — write permissions for standards."""
    return _make_client("data001", "data_admin")


@pytest.fixture(scope="function")
def dept_client(seeded_db):
    """Dept-approver client (dept001) — read-only for standards."""
    return _make_client("dept001", "dept_approver")


@pytest.fixture(scope="function")
def seeded_db(db):
    """Database seeded with data standards + stock records."""
    db.add(models.DataStandard(
        entity_type="material",
        sap_table="MARA",
        field_name="MATNR",
        field_label="物料编码",
        data_type="string",
        required=True,
        pattern=r"^M\d{5}$",
        unique=True,
        owner="钱数据",
        standard_source="sap",
        dept_scope=["采购部"],
        description="物料主编码",
    ))
    db.add(models.DataStandard(
        entity_type="supplier",
        sap_table="LFA1",
        field_name="LIFNR",
        field_label="供应商编号",
        data_type="string",
        required=True,
        pattern=r"^[0-9]{10}$",
        unique=True,
        owner="钱数据",
        standard_source="sap",
    ))
    db.add(models.MaterialRecord(
        material_code="M10001",
        material_name="六角螺栓 M8×30 镀锌",
        attributes={"MTART": "ROH", "MEINS": "PC"},
    ))
    db.add(models.PartnerRecord(
        entity_type="supplier",
        partner_code="1000000001",
        partner_name="华成精密机械有限公司",
        attributes={"CITY1": "上海", "ZTERM": "0010"},
    ))
    db.commit()
    yield db
