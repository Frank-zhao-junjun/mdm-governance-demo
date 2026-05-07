"""pytest configuration and shared fixtures."""
import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure backend/app is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.pool import StaticPool

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


@pytest.fixture(scope="function")
def client(seeded_db):
    """TestClient with authenticated default user and seeded data."""
    from app.core.auth import create_access_token
    token = create_access_token({"sub": "user001", "role": "applicant"})
    
    # Create mock user in DB for auth checks
    # We need to patch get_current_user to not require DEBUG mode
    original_debug = os.environ.get("ENV", "")
    os.environ["ENV"] = "test"
    
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c
    
    os.environ["ENV"] = original_debug


@pytest.fixture(scope="function")
def seeded_db(db):
    """Database seeded with base classification data."""
    # Level-1 classification
    parent = models.MaterialClassification(
        id="cls-parent-001",
        code="M01",
        name="原材料",
        level=1,
        is_active=True
    )
    db.add(parent)
    
    # Level-2 classification
    child = models.MaterialClassification(
        id="cls-child-001",
        code="0101",
        name="金属材料",
        level=2,
        parent_id="cls-parent-001",
        is_active=True
    )
    db.add(child)
    
    # Attribute templates
    db.add(models.AttributeTemplate(
        id="tpl-001",
        classification_id="cls-child-001",
        field_name="material_grade",
        field_label="材质等级",
        field_type="select",
        is_required=True,
        options=["Q235", "304不锈钢", "316不锈钢"]
    ))
    db.add(models.AttributeTemplate(
        id="tpl-002",
        classification_id="cls-child-001",
        field_name="thickness",
        field_label="厚度(mm)",
        field_type="number",
        is_required=True
    ))
    db.add(models.AttributeTemplate(
        id="tpl-003",
        classification_id="cls-child-001",
        field_name="width",
        field_label="宽度(mm)",
        field_type="number",
        is_required=False
    ))
    
    # Code rule
    db.add(models.CodeRule(
        id="rule-001",
        name="金属材料编码规则",
        pattern="{大类}-{小类}-{流水}",
        prefix="M",
        current_seq=0,
        seq_length=5,
        classification_id="cls-child-001",
        is_active=True
    ))
    
    db.commit()
    yield db


@pytest.fixture
def admin_client(seeded_db):
    """TestClient authenticated as admin."""
    from app.core.auth import create_access_token
    token = create_access_token({"sub": "admin001", "role": "admin"})
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


@pytest.fixture
def dept_client(seeded_db):
    """TestClient authenticated as department approver."""
    from app.core.auth import create_access_token
    token = create_access_token({"sub": "dept001", "role": "dept_approver"})
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


@pytest.fixture
def sample_application(seeded_db):
    """Create a sample material application in draft state."""
    from app import crud, schemas
    data = schemas.ApplicationCreate(
        material_name="测试不锈钢板材304",
        material_desc="2mm厚304不锈钢板",
        classification_id="cls-child-001",
        material_type=models.MaterialType.RAW,
        attribute_values={"material_grade": "304不锈钢", "thickness": "2.0", "width": "1000"}
    )
    app = crud.create_application(seeded_db, data, "user001", "张三")
    yield app
