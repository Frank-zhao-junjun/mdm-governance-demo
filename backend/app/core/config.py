"""Core configuration for the MDM Governance platform."""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "RalphLoop MDM Governance"
    VERSION: str = "1.0.0"
    
    # Database — SQLite for dev, override with PostgreSQL in production
    DATABASE_URL: str = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite:///./mdm_governance.db")
    
    # OpenMetadata — disabled by default for dev
    OM_HOST: str = os.getenv("OPENMETADATA_HOST", "http://localhost:8585/api")
    OM_TOKEN: str = os.getenv("OPENMETADATA_TOKEN", "")
    OM_ENABLED: bool = os.getenv("OM_ENABLED", "false").lower() == "true"
    
    # BTP Mock — disabled by default for dev
    BTP_MOCK_URL: str = os.getenv("BTP_MOCK_URL", "http://localhost:8888")
    BTP_ENABLED: bool = os.getenv("BTP_ENABLED", "false").lower() == "true"
    
    # Environment
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = ENV == "development"

settings = Settings()
