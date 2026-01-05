# app/rate_limiter.py
"""Shared rate limiter instance for all API endpoints."""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_user_id_or_ip(request: Request) -> str:
    """Get user ID from auth header or fall back to IP address."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # Use token hash as identifier (not the full token for security)
        token = auth_header[7:]
        return f"user:{hash(token) % 1000000}"
    return get_remote_address(request)


# Single shared limiter instance - MUST be attached to app.state.limiter in main.py
limiter = Limiter(key_func=get_user_id_or_ip)
