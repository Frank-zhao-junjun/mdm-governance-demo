#!/usr/bin/env python3
"""Initialize database with seed data for testing."""
import sys
sys.path.insert(0, "/mnt/agents/output/app/backend")

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app import models


def init_db():
    """Create tables and seed data."""
    # Drop and recreate
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Seed Classifications (Level 1 - 大类)
        raw = models.MaterialClassification(
            id="cls-raw-001", code="01", name="原材料", level=1,
            description="直接用于产品生产加工的物料"
        )
        semi = models.MaterialClassification(
            id="cls-semi-001", code="02", name="半成品", level=1,
            description="经过部分加工的中间产品"
        )
        finished = models.MaterialClassification(
            id="cls-fin-001", code="03", name="成品", level=1,
            description="已完成全部工序的产品"
        )
        aux = models.MaterialClassification(
            id="cls-aux-001", code="04", name="辅助材料", level=1,
            description="辅助生产的物料"
        )
        spare = models.MaterialClassification(
            id="cls-spa-001", code="05", name="备品备件", level=1,
            description="设备维修替换件"
        )
        
        db.add_all([raw, semi, finished, aux, spare])
        db.commit()
        
        # Seed Classifications (Level 2 - 中类)
        metal = models.MaterialClassification(
            id="cls-metal-001", code="0101", name="金属材料", level=2,
            parent_id="cls-raw-001"
        )
        plastic = models.MaterialClassification(
            id="cls-plastic-001", code="0102", name="塑料", level=2,
            parent_id="cls-raw-001"
        )
        elec = models.MaterialClassification(
            id="cls-elec-001", code="0103", name="电子元器件", level=2,
            parent_id="cls-raw-001"
        )
        
        db.add_all([metal, plastic, elec])
        db.commit()
        
        # Seed Classifications (Level 3 - 小类)
        steel_plate = models.MaterialClassification(
            id="cls-steel-plate-001", code="010101", name="钢板", level=3,
            parent_id="cls-metal-001"
        )
        stainless = models.MaterialClassification(
            id="cls-stainless-001", code="010102", name="不锈钢", level=3,
            parent_id="cls-metal-001"
        )
        engineering_plastic = models.MaterialClassification(
            id="cls-engineering-plastic-001", code="010201", name="工程塑料", level=3,
            parent_id="cls-plastic-001"
        )
        db.add_all([steel_plate, stainless, engineering_plastic])
        db.commit()
        
        # Seed Attribute Templates
        templates = [
            models.AttributeTemplate(
                id="tpl-001", classification_id="cls-stainless-001",
                field_name="material_grade", field_label="材质等级",
                field_type="select", is_required=True,
                options=["Q235", "Q345", "304不锈钢", "316不锈钢", "45#钢"]
            ),
            models.AttributeTemplate(
                id="tpl-002", classification_id="cls-stainless-001",
                field_name="thickness", field_label="厚度(mm)",
                field_type="number", is_required=True
            ),
            models.AttributeTemplate(
                id="tpl-003", classification_id="cls-stainless-001",
                field_name="width", field_label="宽度(mm)",
                field_type="number", is_required=False
            ),
            models.AttributeTemplate(
                id="tpl-004", classification_id="cls-engineering-plastic-001",
                field_name="plastic_type", field_label="塑料类型",
                field_type="select", is_required=True,
                options=["ABS", "PP", "PE", "PVC", "PA66"]
            ),
            models.AttributeTemplate(
                id="tpl-005", classification_id="cls-engineering-plastic-001",
                field_name="color", field_label="颜色",
                field_type="text", is_required=False
            ),
        ]
        db.add_all(templates)
        db.commit()
        
        # Seed Code Rules
        rules = [
            models.CodeRule(
                id="rule-001", name="金属材料编码规则",
                pattern="{大类}-{小类}-{流水}",
                prefix="M", seq_length=5,
                classification_id="cls-stainless-001"
            ),
            models.CodeRule(
                id="rule-002", name="塑料编码规则",
                pattern="{大类}-{小类}-{流水}",
                prefix="P", seq_length=5,
                classification_id="cls-engineering-plastic-001"
            ),
        ]
        db.add_all(rules)
        db.commit()
        
        print("✅ Database initialized with seed data")
        
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
