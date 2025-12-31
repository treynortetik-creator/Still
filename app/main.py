"""Main FastAPI application for ContentMultiplier."""
import asyncio
import traceback
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathlib import Path

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime

from app.config import get_settings
from app.database import init_db, close_postgres_pool

logger = logging.getLogger(__name__)
from app.api import upload, jobs, library, admin, auth, personas, export, feedback, edit
from app.api import admin_views, swipes, memory, brand_voice, remix, custom_personas, batch
from app.api import webhooks, calendar, autopilot, sommelier, workshop

settings = get_settings()

# Configure rate limiter
def get_user_id_or_ip(request: Request) -> str:
    """Get user ID from auth header or fall back to IP address."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # Use token hash as identifier (not the full token for security)
        token = auth_header[7:]
        return f"user:{hash(token) % 1000000}"
    return get_remote_address(request)

limiter = Limiter(key_func=get_user_id_or_ip)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors with clear reset time."""
    # Parse the retry-after header if available
    retry_after = getattr(exc, 'retry_after', 60)

    # Calculate reset time
    reset_time = datetime.utcnow().timestamp() + retry_after

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded: {exc.detail}",
            "retry_after_seconds": retry_after,
            "reset_at": datetime.utcfromtimestamp(reset_time).isoformat() + "Z",
            "limits": {
                "uploads": "100 per hour",
                "api_calls": "1000 per hour"
            }
        },
        headers={"Retry-After": str(retry_after)}
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler - ensures all errors return JSON, not plain text."""
    # Log the full exception with traceback
    error_id = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception [{error_id}]: {exc}\n{tb}")

    # Try to log to database
    try:
        from app.database import get_db
        from app.db_utils import execute
        async with get_db() as db:
            await execute(
                db,
                """
                INSERT INTO error_logs (error_type, error_message, stack_trace, context)
                VALUES (?, ?, ?, ?)
                """,
                (
                    type(exc).__name__,
                    str(exc)[:1000],  # Limit message length
                    tb[:5000],  # Limit stack trace length
                    f"URL: {request.url}, Method: {request.method}",
                )
            )
            if not get_settings().use_postgres:
                await db.commit()
    except Exception as log_err:
        logger.error(f"Failed to log error to database: {log_err}")

    # Return JSON error response
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error. Please try again.",
            "error_id": error_id,
            "error_type": type(exc).__name__,
            # Include error message in development, hide in production
            "message": str(exc) if settings.debug else "An unexpected error occurred",
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions to ensure JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors with detailed JSON response."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors()
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("Starting ContentMultiplier...")

    # Ensure directories exist
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.prompts_dir.mkdir(parents=True, exist_ok=True)
    settings.clients_dir.mkdir(parents=True, exist_ok=True)
    if not settings.use_postgres:
        settings.database_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database
    await init_db()
    print("Database initialized")

    # Initialize prompt templates from files
    from app.services.prompt_manager import init_prompts_from_files
    await init_prompts_from_files()
    print("Prompt templates loaded")

    # Initialize settings from database (or create defaults)
    from app.services import settings_manager
    await settings_manager.init_default_settings()
    print("Settings initialized from database")

    # Start autopilot scheduler
    from app.services.scheduler import start_scheduler, stop_scheduler
    await start_scheduler()

    yield

    # Shutdown
    print("Shutting down ContentMultiplier...")

    # Stop autopilot scheduler
    await stop_scheduler()

    # Close PostgreSQL connection pool
    if settings.use_postgres:
        await close_postgres_pool()
        print("PostgreSQL pool closed")


app = FastAPI(
    title="ContentMultiplier",
    description="AI-powered content repurposing platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Add global exception handlers for JSON responses
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# CORS middleware - use allowed_origins from settings
# In production, set ALLOWED_ORIGINS env var to comma-separated list of domains
cors_origins = [origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(library.router, prefix="/api", tags=["library"])
app.include_router(personas.router, prefix="/api", tags=["personas"])
# Register admin views FIRST so HTML pages take priority over API responses
app.include_router(admin_views.router, prefix="/admin", tags=["admin-views"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin-api"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
app.include_router(edit.router, prefix="/api", tags=["edit"])
app.include_router(swipes.router, prefix="/api", tags=["swipes"])
app.include_router(memory.router, prefix="/api", tags=["memory"])
app.include_router(brand_voice.router, prefix="/api", tags=["brand-voice"])
app.include_router(remix.router, prefix="/api", tags=["remix"])
app.include_router(custom_personas.router, prefix="/api", tags=["custom-personas"])
app.include_router(batch.router, prefix="/api", tags=["batch"])
app.include_router(webhooks.router, prefix="/api", tags=["webhooks"])
app.include_router(calendar.router, prefix="/api", tags=["calendar"])
app.include_router(autopilot.router, prefix="/api", tags=["autopilot"])
app.include_router(sommelier.router, prefix="/api", tags=["sommelier"])
app.include_router(workshop.router, prefix="/api", tags=["workshop"])

# Frontend path
frontend_path = Path(__file__).parent.parent / "frontend"

# Mount static files for frontend
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=frontend_path / "static"), name="static")


# Serve frontend HTML files
@app.get("/login.html")
async def serve_login():
    """Serve login page."""
    return FileResponse(frontend_path / "login.html")


@app.get("/register.html")
async def serve_register():
    """Serve register page."""
    return FileResponse(frontend_path / "register.html")


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
    """Serve library page (legacy redirect to Reserve)."""
    return FileResponse(frontend_path / "reserve.html")


@app.get("/reserve.html")
async def serve_reserve():
    """Serve the Reserve page."""
    return FileResponse(frontend_path / "reserve.html")


@app.get("/settings.html")
async def serve_settings():
    """Serve settings page."""
    return FileResponse(frontend_path / "settings.html")


@app.get("/swipes.html")
async def serve_swipes():
    """Serve swipe files page."""
    return FileResponse(frontend_path / "swipes.html")


@app.get("/remix.html")
async def serve_remix():
    """Serve content remix page."""
    return FileResponse(frontend_path / "remix.html")


@app.get("/batch-status.html")
async def serve_batch_status():
    """Serve batch status page."""
    return FileResponse(frontend_path / "batch-status.html")


@app.get("/calendar.html")
async def serve_calendar():
    """Serve content calendar page."""
    return FileResponse(frontend_path / "calendar.html")


@app.get("/autopilot.html")
async def serve_autopilot():
    """Serve autopilot monitors page."""
    return FileResponse(frontend_path / "autopilot.html")


@app.get("/brand-voice.html")
async def serve_brand_voice():
    """Serve brand voice configuration page."""
    return FileResponse(frontend_path / "brand-voice.html")


@app.get("/workshop.html")
async def serve_workshop():
    """Serve the Workshop content editing page."""
    return FileResponse(frontend_path / "workshop.html")


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
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)
