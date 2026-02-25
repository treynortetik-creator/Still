"""Admin HTML view routes using Jinja2 templates."""
import json
import base64
import hmac
import secrets
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Cookie, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.config import get_settings
from app.utils.security import is_safe_redirect_url

router = APIRouter()


def generate_csrf_token() -> str:
    """Generate a CSRF token with timestamp."""
    settings = get_settings()
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    data = f"{timestamp}:{nonce}"
    signature = hmac.new(
        settings.secret_key.encode(),
        data.encode(),
        digestmod="sha256"
    ).hexdigest()[:16]
    return f"{data}:{signature}"


def verify_csrf_token(token: str, max_age: int = 3600) -> bool:
    """Verify a CSRF token is valid and not expired."""
    settings = get_settings()
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        timestamp, nonce, signature = parts
        # Check timestamp (token expires after max_age seconds)
        if int(time.time()) - int(timestamp) > max_age:
            return False
        # Verify signature
        data = f"{timestamp}:{nonce}"
        expected_signature = hmac.new(
            settings.secret_key.encode(),
            data.encode(),
            digestmod="sha256"
        ).hexdigest()[:16]
        return hmac.compare_digest(signature, expected_signature)
    except (ValueError, TypeError):
        return False


# Set up templates directory
templates_dir = Path(__file__).parent.parent / "templates" / "admin"
templates_dir.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))


def verify_admin_session(request: Request) -> bool:
    """
    Verify admin authentication from request.
    Checks for Basic Auth header or admin session cookie.
    Returns True if authenticated, False otherwise.
    """
    settings = get_settings()

    # Check if admin credentials are configured
    if not settings.admin_username or not settings.admin_password:
        return False

    # Check Authorization header (Basic Auth)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        try:
            credentials = auth_header[6:]
            decoded = base64.b64decode(credentials).decode("utf-8")
            username, password = decoded.split(":", 1)

            username_match = hmac.compare_digest(username, settings.admin_username)
            password_match = hmac.compare_digest(password, settings.admin_password)

            if username_match and password_match:
                return True
        except (ValueError, UnicodeDecodeError):
            pass

    # Check for admin session cookie (set after successful Basic Auth)
    admin_session = request.cookies.get("admin_session")
    if admin_session:
        # Validate session token (simple HMAC-based validation)
        try:
            expected_token = hmac.new(
                settings.secret_key.encode(),
                f"{settings.admin_username}:admin".encode(),
                digestmod="sha256"
            ).hexdigest()
            if hmac.compare_digest(admin_session, expected_token):
                return True
        except (TypeError, AttributeError, UnicodeDecodeError):
            # Invalid token format or encoding - treat as invalid session
            pass

    return False


def require_admin(request: Request, error: str = "") -> RedirectResponse:
    """
    Redirect to login page for admin pages.
    """
    settings = get_settings()

    # If admin not configured, show error page
    if not settings.admin_username or not settings.admin_password:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Admin Not Configured</title></head>
            <body style="font-family: sans-serif; padding: 50px; text-align: center;">
                <h1>Admin Panel Not Configured</h1>
                <p>Set ADMIN_USERNAME and ADMIN_PASSWORD environment variables to enable the admin panel.</p>
            </body>
            </html>
            """,
            status_code=503
        )

    # Redirect to login page
    redirect_url = f"/admin/login?next={request.url.path}"
    if error:
        redirect_url += f"&error={error}"
    return RedirectResponse(url=redirect_url, status_code=302)


def create_admin_response(request: Request, template_name: str) -> HTMLResponse:
    """
    Create response for admin page with session cookie.
    """
    settings = get_settings()

    # Create session token
    session_token = hmac.new(
        settings.secret_key.encode(),
        f"{settings.admin_username}:admin".encode(),
        digestmod="sha256"
    ).hexdigest()

    response = templates.TemplateResponse(template_name, {"request": request})
    response.set_cookie(
        key="admin_session",
        value=session_token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        max_age=3600 * 8  # 8 hours
    )
    return response


@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Render admin login page."""
    settings = get_settings()

    # If admin not configured, show error
    if not settings.admin_username or not settings.admin_password:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Admin Not Configured</title></head>
            <body style="font-family: sans-serif; padding: 50px; text-align: center;">
                <h1>Admin Panel Not Configured</h1>
                <p>Set ADMIN_USERNAME and ADMIN_PASSWORD environment variables to enable the admin panel.</p>
            </body>
            </html>
            """,
            status_code=503
        )

    # If already logged in, redirect to dashboard
    if verify_admin_session(request):
        return RedirectResponse(url="/admin/dashboard", status_code=302)

    error = request.query_params.get("error", "")
    next_url = request.query_params.get("next", "/admin/dashboard")

    # Validate next_url to prevent open redirect
    if not is_safe_redirect_url(next_url, ['/admin/']):
        next_url = "/admin/dashboard"

    # Generate CSRF token for form protection
    csrf_token = generate_csrf_token()

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Login - ContentMultiplier</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-900 min-h-screen flex items-center justify-center">
            <div class="bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-md">
                <h1 class="text-2xl font-bold text-white mb-2 text-center">Admin Login</h1>
                <p class="text-gray-400 text-center mb-6">ContentMultiplier</p>

                {"<div class='bg-red-500/20 border border-red-500 text-red-400 px-4 py-2 rounded mb-4 text-center'>Invalid username or password</div>" if error else ""}

                <form method="POST" action="/admin/login">
                    <input type="hidden" name="csrf_token" value="{csrf_token}">
                    <input type="hidden" name="next" value="{next_url}">

                    <div class="mb-4">
                        <label class="block text-gray-300 text-sm font-medium mb-2" for="username">
                            Username
                        </label>
                        <input
                            type="text"
                            id="username"
                            name="username"
                            required
                            class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-indigo-500"
                            placeholder="Enter your username"
                        >
                    </div>

                    <div class="mb-6">
                        <label class="block text-gray-300 text-sm font-medium mb-2" for="password">
                            Password
                        </label>
                        <input
                            type="password"
                            id="password"
                            name="password"
                            required
                            class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-indigo-500"
                            placeholder="Enter your password"
                        >
                    </div>

                    <button
                        type="submit"
                        class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded transition"
                    >
                        Sign In
                    </button>
                </form>

                <div class="mt-6 text-center">
                    <a href="/" class="text-gray-400 hover:text-white text-sm">Back to App</a>
                </div>
            </div>
        </body>
        </html>
        """,
        status_code=200
    )


@router.post("/login")
async def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    next: str = Form("/admin/dashboard")
):
    """Handle admin login form submission."""
    settings = get_settings()

    # Verify CSRF token
    if not verify_csrf_token(csrf_token):
        return RedirectResponse(
            url="/admin/login?error=csrf",
            status_code=302
        )

    # Validate credentials
    username_match = hmac.compare_digest(username, settings.admin_username)
    password_match = hmac.compare_digest(password, settings.admin_password)

    if username_match and password_match:
        # Create session token
        session_token = hmac.new(
            settings.secret_key.encode(),
            f"{settings.admin_username}:admin".encode(),
            digestmod="sha256"
        ).hexdigest()

        # Validate redirect URL to prevent open redirect attacks
        safe_next = next if is_safe_redirect_url(next, ['/admin/']) else '/admin/dashboard'
        response = RedirectResponse(url=safe_next, status_code=302)
        response.set_cookie(
            key="admin_session",
            value=session_token,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
            max_age=3600 * 8  # 8 hours
        )
        return response
    else:
        # Invalid credentials - redirect back to login with error
        return RedirectResponse(
            url=f"/admin/login?error=1&next={next}",
            status_code=302
        )


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Render admin dashboard."""
    if not verify_admin_session(request):
        return require_admin(request)
    return create_admin_response(request, "dashboard.html")


@router.get("/prompts", response_class=HTMLResponse)
async def admin_prompts(request: Request):
    """Render prompt editor."""
    if not verify_admin_session(request):
        return require_admin(request)
    return create_admin_response(request, "prompt_editor.html")


@router.get("/clients", response_class=HTMLResponse)
async def admin_clients(request: Request):
    """Render client management view."""
    if not verify_admin_session(request):
        return require_admin(request)
    return create_admin_response(request, "client_view.html")


@router.get("/library", response_class=HTMLResponse)
async def admin_library(request: Request):
    """Render library browser."""
    if not verify_admin_session(request):
        return require_admin(request)
    return create_admin_response(request, "library_browser.html")


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    """Render settings page."""
    if not verify_admin_session(request):
        return require_admin(request)
    return create_admin_response(request, "settings.html")


@router.get("/error-logs", response_class=HTMLResponse)
async def admin_error_logs(request: Request):
    """Render error logs page."""
    if not verify_admin_session(request):
        return require_admin(request)
    return create_admin_response(request, "error_logs.html")


@router.get("/logout")
async def admin_logout(request: Request):
    """Logout from admin panel by clearing session cookie."""
    response = RedirectResponse(url="/admin/dashboard", status_code=302)
    response.delete_cookie("admin_session")
    return response
