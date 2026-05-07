"""Material code generation engine."""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app import crud, models


class CodeGenerator:
    """Generate material codes based on rules."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate(self, classification_id: str, material_type: str, rule_id: Optional[str] = None) -> str:
        """Generate a unique material code."""
        
        # Get classification
        classification = crud.get_classification(self.db, classification_id)
        if not classification:
            raise ValueError("分类不存在")
        
        # Get code rule
        if rule_id:
            rule = crud.get_code_rule(self.db, rule_id)
        else:
            # Find matching rule
            rules = crud.get_code_rules(self.db, classification_id)
            rule = rules[0] if rules else None
        
        if not rule:
            # Default rule: {大类码}-{小类码}-{流水}
            return self._generate_default(classification)
        
        # Increment sequence
        seq = crud.increment_seq(self.db, rule.id)
        
        # Build code
        code = rule.pattern
        
        # Replace placeholders
        replacements = {
            "{大类}": self._get_parent_code(classification) or "00",
            "{小类}": classification.code,
            "{流水}": f"{seq:0{rule.seq_length}d}",
            "{类型}": material_type[:3].upper(),
            "{年份}": str(datetime.now().year)[-2:],
        }
        
        for placeholder, value in replacements.items():
            code = code.replace(placeholder, value)
        
        # Add prefix/suffix
        if rule.prefix:
            code = f"{rule.prefix}{code}"
        if rule.suffix:
            code = f"{code}{rule.suffix}"
        
        return code
    
    def _generate_default(self, classification: models.MaterialClassification) -> str:
        """Generate default code when no rule matches."""
        parent_code = self._get_parent_code(classification) or "00"
        
        # Count existing golden records for this classification
        count = self.db.query(models.GoldenRecord).filter(
            models.GoldenRecord.classification_id == classification.id
        ).count()
        
        return f"{parent_code}-{classification.code}-{count + 1:05d}"
    
    def _get_parent_code(self, classification: models.MaterialClassification) -> Optional[str]:
        """Get parent classification code."""
        if classification.parent_id:
            parent = crud.get_classification(self.db, classification.parent_id)
            return parent.code if parent else None
        return classification.code if classification.level == 1 else None
