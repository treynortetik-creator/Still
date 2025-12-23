"""Admin HTML view routes using Jinja2 templates."""
import json
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db

router = APIRouter()

# Set up templates directory
templates_dir = Path(__file__).parent.parent / "templates" / "admin"
templates_dir.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Render admin dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/prompts", response_class=HTMLResponse)
async def admin_prompts(request: Request):
    """Render prompt editor."""
    return templates.TemplateResponse("prompt_editor.html", {"request": request})


@router.get("/clients", response_class=HTMLResponse)
async def admin_clients(request: Request):
    """Render client management view."""
    return templates.TemplateResponse("client_view.html", {"request": request})


@router.get("/library", response_class=HTMLResponse)
async def admin_library(request: Request):
    """Render library browser."""
    return templates.TemplateResponse("library_browser.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    """Render settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})
