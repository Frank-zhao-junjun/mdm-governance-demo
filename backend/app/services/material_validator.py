"""Material validation service."""
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app import crud


class MaterialValidator:
    """Validate material application data."""
    
    REQUIRED_FIELDS = ["material_name", "classification_id", "material_type"]
    DEFAULT_RULES: Dict[str, Dict[str, Any]] = {
        "required_material_name": {"severity": "blocking", "category": "completeness", "penalty": 20},
        "required_classification_id": {"severity": "blocking", "category": "completeness", "penalty": 20},
        "required_material_type": {"severity": "blocking", "category": "completeness", "penalty": 20},
        "name_length": {"severity": "blocking", "category": "consistency", "penalty": 20},
        "material_desc_completeness": {"severity": "warning", "category": "completeness", "penalty": 5},
        "classification_exists": {"severity": "blocking", "category": "governance", "penalty": 20},
        "material_type": {"severity": "blocking", "category": "governance", "penalty": 20},
        "required_attr_coverage": {"severity": "warning", "category": "completeness", "penalty": 5},
    }
    
    def __init__(self, db: Session):
        self.db = db

    def _get_rule_config(self, rule_key: str) -> Dict[str, Any]:
        defaults = self.DEFAULT_RULES.get(rule_key, {"severity": "blocking", "category": "data_quality", "penalty": 20})
        configured = crud.get_governance_rule(self.db, rule_key)

        if configured and not configured.is_active:
            return {
                "enabled": False,
                "severity": defaults["severity"],
                "category": defaults["category"],
                "penalty": defaults["penalty"],
            }

        if configured:
            return {
                "enabled": True,
                "severity": configured.severity.value,
                "category": configured.category,
                "penalty": configured.score_penalty,
            }

        return {
            "enabled": True,
            "severity": defaults["severity"],
            "category": defaults["category"],
            "penalty": defaults["penalty"],
        }
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run all validation checks."""
        checks: List[Dict[str, Any]] = []
        blocking_errors: List[str] = []
        warnings: List[str] = []
        total_penalty = 0

        def add_check(
            rule_key: str,
            check: str,
            passed: bool,
            message: str,
        ):
            nonlocal total_penalty
            config = self._get_rule_config(rule_key)
            if not config["enabled"]:
                return

            severity = config["severity"]
            category = config["category"]
            checks.append({
                "check": check,
                "passed": passed,
                "message": message,
                "severity": severity,
                "category": category,
                "rule_key": rule_key,
            })
            if passed:
                return
            total_penalty += config["penalty"]
            if severity == "blocking":
                blocking_errors.append(message)
            else:
                warnings.append(message)
        
        # Check 1: Required fields
        for field in self.REQUIRED_FIELDS:
            if not data.get(field):
                add_check(
                    rule_key=f"required_{field}",
                    check=f"required_{field}",
                    passed=False,
                    message=f"必填字段缺失: {field}",
                )
            else:
                add_check(
                    rule_key=f"required_{field}",
                    check=f"required_{field}",
                    passed=True,
                    message=f"{field} 已填写",
                )
        
        # Check 2: Material name length
        name = data.get("material_name", "")
        if name and len(name) < 5:
            add_check(
                rule_key="name_length",
                check="name_length",
                passed=False,
                message="物料名称太短（至少5个字符）",
            )
        elif name and len(name) > 200:
            add_check(
                rule_key="name_length",
                check="name_length",
                passed=False,
                message="物料名称太长（最多200个字符）",
            )
        else:
            add_check(
                rule_key="name_length",
                check="name_length",
                passed=True,
                message="名称长度合规",
            )

        # Check 2.1: Description completeness (warning only)
        material_desc = (data.get("material_desc") or "").strip()
        if not material_desc:
            add_check(
                rule_key="material_desc_completeness",
                check="material_desc_completeness",
                passed=False,
                message="物料描述未填写，建议补充业务描述",
            )
        elif len(material_desc) < 10:
            add_check(
                rule_key="material_desc_completeness",
                check="material_desc_completeness",
                passed=False,
                message="物料描述过短，建议至少10个字符",
            )
        else:
            add_check(
                rule_key="material_desc_completeness",
                check="material_desc_completeness",
                passed=True,
                message="物料描述完整",
            )
        
        # Check 3: Classification exists
        classification_id = data.get("classification_id")
        if classification_id:
            classification = crud.get_classification(self.db, classification_id)
            if not classification:
                add_check(
                    rule_key="classification_exists",
                    check="classification_exists",
                    passed=False,
                    message="所选分类不存在",
                )
            else:
                add_check(
                    rule_key="classification_exists",
                    check="classification_exists",
                    passed=True,
                    message=f"分类: {classification.name}",
                )
        
        # Check 4: Material type valid
        material_type = data.get("material_type")
        valid_types = ["raw", "semi", "finished", "auxiliary", "spare"]
        if material_type and material_type not in valid_types:
            add_check(
                rule_key="material_type",
                check="material_type",
                passed=False,
                message=f"无效的物料类型: {material_type}",
            )
        else:
            add_check(
                rule_key="material_type",
                check="material_type",
                passed=True,
                message=f"类型: {material_type}",
            )
        
        # Check 5: Attribute values validation
        attribute_values = data.get("attribute_values", {})
        if classification_id:
            templates = crud.get_attribute_templates(self.db, classification_id)
            required_templates = [template for template in templates if template.is_required]
            filled_required = 0
            for template in templates:
                if template.is_required:
                    value = attribute_values.get(template.field_name)
                    if not value:
                        add_check(
                            rule_key=f"attr_{template.field_name}",
                            check=f"attr_{template.field_name}",
                            passed=False,
                            message=f"必填属性缺失: {template.field_label}",
                        )
                    else:
                        filled_required += 1
                        add_check(
                            rule_key=f"attr_{template.field_name}",
                            check=f"attr_{template.field_name}",
                            passed=True,
                            message=f"{template.field_label}: {value}",
                        )

            # Check 6: Required attribute coverage warning
            if required_templates:
                coverage_ratio = filled_required / len(required_templates)
                if coverage_ratio < 1:
                    add_check(
                        rule_key="required_attr_coverage",
                        check="required_attr_coverage",
                        passed=False,
                        message=f"必填属性完整率 {int(coverage_ratio * 100)}%，请补齐后提交",
                    )
                else:
                    add_check(
                        rule_key="required_attr_coverage",
                        check="required_attr_coverage",
                        passed=True,
                        message="必填属性完整率 100%",
                    )

        blocking_failed = sum(1 for check in checks if (not check["passed"]) and check["severity"] == "blocking")
        warning_failed = sum(1 for check in checks if (not check["passed"]) and check["severity"] == "warning")
        quality_score = max(0, 100 - total_penalty)
        
        return {
            "passed": len(blocking_errors) == 0,
            "checks": checks,
            "errors": blocking_errors,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
            "quality_score": quality_score,
            "rule_version": "mdg-p0-v1",
            "summary": {
                "total_checks": len(checks),
                "blocking_failed": blocking_failed,
                "warning_failed": warning_failed,
                "total_penalty": total_penalty,
            },
        }
