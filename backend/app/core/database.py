"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Use PostgreSQL in production, SQLite for demo
# Reads from SQLALCHEMY_DATABASE_URL env var
database_url = settings.DATABASE_URL

connect_args = {}
engine_kwargs = {"pool_pre_ping": True}
if "sqlite" in database_url.lower():
    connect_args["check_same_thread"] = False
else:
    engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 3600,
    })

engine = create_engine(
    database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
