"""Core configuration for the MDM Governance platform."""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "RalphLoop MDM Governance"
    VERSION: str = "1.0.0"
    
    # Database
    DATABASE_URL: str = os.getenv("SQLALCHEMY_DATABASE_URL", "postgresql://mdg_user:mdg_password@localhost:5432/mdm_governance")
    
    # OpenMetadata
    OM_HOST: str = os.getenv("OPENMETADATA_HOST", "http://localhost:8585/api")
    OM_TOKEN: str = os.getenv("OPENMETADATA_TOKEN", "")
    OM_ENABLED: bool = os.getenv("OM_ENABLED", "true").lower() == "true"
    
    # BTP Mock
    BTP_MOCK_URL: str = os.getenv("BTP_MOCK_URL", "http://localhost:8888")
    BTP_ENABLED: bool = os.getenv("BTP_ENABLED", "true").lower() == "true"
    
    # Environment
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = ENV == "development"

settings = Settings()
