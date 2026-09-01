"""Core configuration for the stock-data governance service."""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "Stock Data Governance"
    VERSION: str = "2.0.0"

    # Database — SQLite for dev, override with PostgreSQL in production
    DATABASE_URL: str = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite:///./mdm_governance.db")

    # Environment
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = ENV == "development"

    # JWT signing key — required in production, optional in development
    SECRET_KEY: str = os.getenv("MDM_SECRET_KEY", "")


settings = Settings()
