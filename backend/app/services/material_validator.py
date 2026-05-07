"""Material validation service."""
import re
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app import crud


class MaterialValidator:
    """Validate material application data."""
    
    REQUIRED_FIELDS = ["material_name", "classification_id", "material_type"]
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run all validation checks."""
        checks = []
        errors = []
        
        # Check 1: Required fields
        for field in self.REQUIRED_FIELDS:
            if not data.get(field):
                errors.append(f"必填字段缺失: {field}")
                checks.append({"check": f"required_{field}", "passed": False, "message": f"{field} 不能为空"})
            else:
                checks.append({"check": f"required_{field}", "passed": True, "message": f"{field} 已填写"})
        
        # Check 2: Material name length
        name = data.get("material_name", "")
        if name and len(name) < 5:
            errors.append("物料名称太短（至少5个字符）")
            checks.append({"check": "name_length", "passed": False, "message": f"名称长度 {len(name)} < 5"})
        elif name and len(name) > 200:
            errors.append("物料名称太长（最多200个字符）")
            checks.append({"check": "name_length", "passed": False, "message": f"名称长度 {len(name)} > 200"})
        else:
            checks.append({"check": "name_length", "passed": True, "message": "名称长度合规"})
        
        # Check 3: Classification exists
        classification_id = data.get("classification_id")
        if classification_id:
            classification = crud.get_classification(self.db, classification_id)
            if not classification:
                errors.append("所选分类不存在")
                checks.append({"check": "classification_exists", "passed": False, "message": "分类不存在"})
            else:
                checks.append({"check": "classification_exists", "passed": True, "message": f"分类: {classification.name}"})
        
        # Check 4: Material type valid
        material_type = data.get("material_type")
        valid_types = ["raw", "semi", "finished", "auxiliary", "spare"]
        if material_type and material_type not in valid_types:
            errors.append(f"无效的物料类型: {material_type}")
            checks.append({"check": "material_type", "passed": False, "message": f"无效类型: {material_type}"})
        else:
            checks.append({"check": "material_type", "passed": True, "message": f"类型: {material_type}"})
        
        # Check 5: Attribute values validation
        attribute_values = data.get("attribute_values", {})
        if classification_id:
            templates = crud.get_attribute_templates(self.db, classification_id)
            for template in templates:
                if template.is_required:
                    value = attribute_values.get(template.field_name)
                    if not value:
                        errors.append(f"必填属性缺失: {template.field_label}")
                        checks.append({"check": f"attr_{template.field_name}", "passed": False, "message": f"{template.field_label} 必填"})
                    else:
                        checks.append({"check": f"attr_{template.field_name}", "passed": True, "message": f"{template.field_label}: {value}"})
        
        return {
            "passed": len(errors) == 0,
            "checks": checks,
            "errors": errors
        }
