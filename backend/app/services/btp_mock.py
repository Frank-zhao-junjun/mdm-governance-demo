"""Mock BTP publish service (Phase 2.2)."""
import random
import time
from datetime import datetime, timezone
from typing import Dict, Any

from app import schemas


class BTPMockService:
    """Mock SAP BTP publishing for development and testing."""
    
    MOCK_URL = "http://localhost:8888"
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
    
    def publish(self, material: schemas.GoldenRecordResponse) -> Dict[str, Any]:
        """Publish material to mock BTP."""
        if not self.enabled:
            return {
                "success": False,
                "sync_id": None,
                "error": "BTP service disabled",
                "details": None
            }
        
        # Simulate BTP processing
        time.sleep(0.5)
        
        # Mock response
        sync_id = f"BTP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
        
        return {
            "success": True,
            "sync_id": sync_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "target_systems": ["SAP-S4HANA", "SAP-Ariba"],
            "details": {
                "material_code": material.material_code,
                "material_name": material.material_name,
                "status": "published",
                "version": material.version,
                "revision": material.revision
            }
        }
    
    def rollback(self, sync_id: str) -> Dict[str, Any]:
        """Rollback a published material."""
        return {
            "success": True,
            "sync_id": sync_id,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            "message": "Material successfully rolled back from BTP"
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check mock BTP health."""
        return {
            "status": "healthy",
            "version": "2026.05",
            "services": {
                "s4hana": "connected",
                "ariba": "connected",
                "master_data_hub": "connected"
            }
        }
