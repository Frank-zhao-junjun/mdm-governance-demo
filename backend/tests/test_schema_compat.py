"""Tests for upgrading local databases without losing compatibility."""
from sqlalchemy import create_engine, inspect, text

from app.core.schema_compat import ensure_schema_compatibility


def test_schema_compatibility_adds_new_columns_to_existing_application_table(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE material_applications (
                id VARCHAR(36) PRIMARY KEY,
                attachments JSON
            )
        """))

    import app.core.schema_compat as schema_compat

    monkeypatch.setattr(schema_compat, "engine", engine)
    monkeypatch.setattr(schema_compat, "SessionLocal", lambda: None)
    monkeypatch.setattr(schema_compat, "seed_demo_three_level_classifications", lambda: None)

    ensure_schema_compatibility()

    columns = {column["name"] for column in inspect(engine).get_columns("material_applications")}
    assert {"id", "attachments", "published_at"}.issubset(columns)