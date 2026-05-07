"""FastAPI main application entry point."""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.core.config import settings
from app.core.auth import authenticate_user, create_access_token, require_any
from app.api import classifications, applications, golden_records, dashboard, metadata_governance
from app.core.database import engine, Base
from app.core.schema_compat import ensure_schema_compatibility

# Create tables
Base.metadata.create_all(bind=engine)
ensure_schema_compatibility()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="RalphLoop Material Master Data Governance Platform",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS - restrict in production
if settings.DEBUG:
    # Development: allow localhost origins
    origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
else:
    # Production: restrict to specific origins
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"]
)

# Static files (frontend)
static_dir = os.path.join(os.path.dirname(__file__), "../../dist")
if os.path.exists(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

# Include routers
app.include_router(classifications.router)
app.include_router(applications.router)
app.include_router(golden_records.router)
app.include_router(dashboard.router)
app.include_router(metadata_governance.router)


@app.post("/api/auth/login")
def login(credentials: dict):
    """Authenticate user and return JWT token.
    
    Request body: {"user_id": "user001", "password": "password001"}
    """
    user = authenticate_user(credentials.get("user_id"), credentials.get("password"))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user["id"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "role": user["role"],
            "department": user["department"],
        }
    }


@app.get("/api/auth/me")
def get_me(user: dict = Depends(require_any)):
    """Get current authenticated user info."""
    return user


@app.get("/")
def root():
    return {
        "message": "RalphLoop MDM Governance API",
        "version": settings.VERSION,
        "docs": "/docs"
    }


# Serve index.html for all non-API routes (SPA fallback)
@app.get("/{path:path}")
def serve_spa(path: str):
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path) and not path.startswith("api") and not path.startswith("docs"):
        return FileResponse(index_path)
    return {"message": "RalphLoop MDM Governance API", "version": settings.VERSION}
