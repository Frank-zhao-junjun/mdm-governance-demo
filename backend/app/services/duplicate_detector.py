"""Duplicate detection service - optimized with database-level similarity."""
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app import crud, models


class DuplicateDetector:
    """Detect duplicate materials using database-level similarity queries."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def check(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for duplicate materials.
        
        Uses database ILIKE query instead of loading all records into memory.
        """
        material_name = data.get("material_name", "").lower().strip()
        
        if not material_name or len(material_name) < 3:
            return {
                "is_duplicate": False,
                "confidence": 0.0,
                "similar_materials": []
            }
        
        similar_materials = []
        
        # Strategy 1: Exact name match (highest confidence)
        exact_matches = self.db.query(models.GoldenRecord).filter(
            models.GoldenRecord.status == models.GoldenRecordStatus.ACTIVE,
            models.GoldenRecord.material_name.ilike(material_name)
        ).limit(3).all()
        
        for gr in exact_matches:
            similar_materials.append({
                "material_code": gr.material_code,
                "material_name": gr.material_name,
                "similarity": 1.0,
                "reason": "名称完全相同"
            })
        
        # Strategy 2: Partial match using first 4 chars (prefix similarity)
        if len(material_name) >= 4:
            prefix = material_name[:4]
            partial_matches = self.db.query(models.GoldenRecord).filter(
                models.GoldenRecord.status == models.GoldenRecordStatus.ACTIVE,
                models.GoldenRecord.material_name.ilike(f"%{prefix}%"),
                models.GoldenRecord.material_name != material_name  # exclude exact matches
            ).limit(5).all()
            
            for gr in partial_matches:
                # Calculate simple similarity score
                gr_name_lower = gr.material_name.lower()
                if material_name == gr_name_lower:
                    continue  # Already counted
                
                # Word overlap similarity
                words1 = set(material_name.split())
                words2 = set(gr_name_lower.split())
                if words1 and words2:
                    overlap = len(words1 & words2) / max(len(words1), len(words2))
                    if overlap >= 0.5:
                        similar_materials.append({
                            "material_code": gr.material_code,
                            "material_name": gr.material_name,
                            "similarity": round(overlap, 2),
                            "reason": f"关键词重叠 {int(overlap*100)}%"
                        })
        
        # Sort by similarity descending
        similar_materials.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Deduplicate by material_code
        seen_codes = set()
        unique_materials = []
        for m in similar_materials:
            if m["material_code"] not in seen_codes:
                seen_codes.add(m["material_code"])
                unique_materials.append(m)
        
        # Flag as duplicate if high similarity found
        top_3 = unique_materials[:3]
        is_duplicate = any(s["similarity"] >= 0.8 for s in top_3)
        
        return {
            "is_duplicate": is_duplicate,
            "confidence": top_3[0]["similarity"] if top_3 else 0.0,
            "similar_materials": unique_materials[:5]  # Top 5
        }
