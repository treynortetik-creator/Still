"""Main FastAPI application for ContentMultiplier."""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from fastapi.responses import FileResponse

from app.config import get_settings
from app.database import init_db
from app.api import upload, jobs, library, admin
from app.api import admin_views

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("Starting ContentMultiplier...")

    # Ensure directories exist
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.prompts_dir.mkdir(parents=True, exist_ok=True)
    settings.clients_dir.mkdir(parents=True, exist_ok=True)
    settings.database_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database
    await init_db()
    print("Database initialized")

    # Initialize prompt templates from files
    from app.services.prompt_manager import init_prompts_from_files
    await init_prompts_from_files()
    print("Prompt templates loaded")

    yield

    # Shutdown
    print("Shutting down ContentMultiplier...")


app = FastAPI(
    title="ContentMultiplier",
    description="AI-powered content repurposing platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(library.router, prefix="/api", tags=["library"])
app.include_router(admin.router, prefix="/admin", tags=["admin-api"])
app.include_router(admin_views.router, prefix="/admin", tags=["admin-views"])

# Frontend path
frontend_path = Path(__file__).parent.parent / "frontend"

# Mount static files for frontend
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=frontend_path / "static"), name="static")


# Serve frontend HTML files
@app.get("/upload.html")
async def serve_upload():
    """Serve upload page."""
    return FileResponse(frontend_path / "upload.html")


@app.get("/status.html")
async def serve_status():
    """Serve status page."""
    return FileResponse(frontend_path / "status.html")


@app.get("/results.html")
async def serve_results():
    """Serve results page."""
    return FileResponse(frontend_path / "results.html")


@app.get("/library.html")
async def serve_library():
    """Serve library page."""
    return FileResponse(frontend_path / "library.html")


@app.get("/")
async def root():
    """Serve homepage."""
    return FileResponse(frontend_path / "index.html")


@app.get("/api")
async def api_info():
    """API info endpoint."""
    return {
        "name": "ContentMultiplier API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
