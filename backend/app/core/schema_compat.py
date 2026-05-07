"""Small startup schema compatibility fixes for local demo databases."""
from sqlalchemy import inspect, text

from app import models
from app.core.database import SessionLocal, engine


def ensure_schema_compatibility() -> None:
    """Add columns that Base.metadata.create_all cannot add to existing tables."""
    inspector = inspect(engine)
    if "material_applications" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("material_applications")}
    if "attachments" in column_names:
        seed_demo_three_level_classifications()
        return

    column_type = "JSON" if engine.dialect.name != "sqlite" else "JSON"
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE material_applications ADD COLUMN attachments {column_type}"))

    seed_demo_three_level_classifications()


def seed_demo_three_level_classifications() -> None:
    """Backfill a few level-3 demo classes for existing two-level local data."""
    db = SessionLocal()
    try:
        if db.query(models.MaterialClassification).filter(models.MaterialClassification.level == 3).first():
            return

        demo_classes = [
            ("cls-steel-plate-001", "010101", "钢板", "cls-metal-001"),
            ("cls-stainless-001", "010102", "不锈钢", "cls-metal-001"),
            ("cls-engineering-plastic-001", "010201", "工程塑料", "cls-plastic-001"),
        ]

        for class_id, code, name, parent_id in demo_classes:
            if not db.query(models.MaterialClassification).filter(models.MaterialClassification.id == parent_id).first():
                continue
            db.add(models.MaterialClassification(
                id=class_id,
                code=code,
                name=name,
                level=3,
                parent_id=parent_id,
                is_active=True,
            ))

        db.commit()

        template_targets = {
            "cls-metal-001": "cls-stainless-001",
            "cls-plastic-001": "cls-engineering-plastic-001",
        }
        for source_id, target_id in template_targets.items():
            if db.query(models.AttributeTemplate).filter(models.AttributeTemplate.classification_id == target_id).first():
                continue
            for template in db.query(models.AttributeTemplate).filter(models.AttributeTemplate.classification_id == source_id).all():
                db.add(models.AttributeTemplate(
                    id=f"{template.id}-{target_id}",
                    classification_id=target_id,
                    field_name=template.field_name,
                    field_label=template.field_label,
                    field_type=template.field_type,
                    is_required=template.is_required,
                    default_value=template.default_value,
                    options=template.options,
                    sort_order=template.sort_order,
                    description=template.description,
                ))

        db.commit()
    finally:
        db.close()