"""OpenMetadata synchronization service."""
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import requests

from app import schemas
from app.core.config import settings


class OpenMetadataSync:
    """Sync Golden Records to OpenMetadata."""
    
    def __init__(self, enabled: Optional[bool] = None):
        self.enabled = settings.OM_ENABLED if enabled is None else enabled
        self.host = settings.OM_HOST
        self.token = settings.OM_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def _api_call(self, method: str, endpoint: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
        """Make API call to OpenMetadata."""
        if not self.enabled:
            return {"success": False, "error": "OpenMetadata disabled"}
        
        url = f"{self.host}{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=self.headers, timeout=10)
            elif method == "POST":
                resp = requests.post(url, headers=self.headers, json=payload, timeout=10)
            elif method == "PUT":
                resp = requests.put(url, headers=self.headers, json=payload, timeout=10)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}
            
            resp.raise_for_status()
            return {"success": True, "data": resp.json()}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    
    def sync_material(self, material: schemas.GoldenRecordResponse) -> Dict[str, Any]:
        """Sync a material to OpenMetadata."""
        if not self.enabled:
            return {
                "success": True,
                "message": "OpenMetadata sync skipped (disabled)",
                "entity_fqn": None
            }
        
        # Check health
        health = self._api_call("GET", "/v1/health-check")
        if not health.get("success"):
            return {
                "success": False,
                "error": f"OpenMetadata unavailable: {health.get('error')}"
            }
        
        # Simulate sync delay
        time.sleep(0.3)
        
        # Mock success (in production, would call actual OM API)
        entity_fqn = f"RalphLoop.Material.{material.material_code}"
        
        return {
            "success": True,
            "entity_fqn": entity_fqn,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "message": f"Material {material.material_code} synced to OpenMetadata"
        }
    
    def run_quality_tests(self, material: schemas.GoldenRecordResponse) -> Dict[str, Any]:
        """Run data quality tests via OpenMetadata."""
        if not self.enabled:
            return {
                "success": True,
                "all_passed": True,
                "message": "Quality tests skipped (disabled)",
                "results": []
            }
        
        # Mock quality test results
        tests = [
            {
                "test_name": "material_code_not_null",
                "passed": bool(material.material_code),
                "message": "物料编码非空" if material.material_code else "物料编码为空"
            },
            {
                "test_name": "material_name_length",
                "passed": 5 <= len(material.material_name) <= 200,
                "message": f"名称长度: {len(material.material_name)}"
            },
            {
                "test_name": "classification_valid",
                "passed": bool(material.classification_id),
                "message": "分类有效" if material.classification_id else "分类无效"
            }
        ]
        
        all_passed = all(t["passed"] for t in tests)
        
        return {
            "success": True,
            "all_passed": all_passed,
            "results": tests,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check OpenMetadata connection."""
        if not self.enabled:
            return {"status": "disabled", "message": "OpenMetadata sync is disabled"}
        
        result = self._api_call("GET", "/v1/health-check")
        if result.get("success"):
            return {"status": "connected", "version": result["data"].get("version", "unknown")}
        return {"status": "disconnected", "error": result.get("error")}
