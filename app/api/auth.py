"""Authentication API endpoints."""
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, EmailStr
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.db_utils import execute, fetchone, execute_insert_returning_id
from app.services.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
    decode_access_token_async,
    blacklist_token,
    validate_email,
    validate_password,
)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class UserRegister(BaseModel):
    """User registration request."""
    email: str
    password: str
    confirm_password: str


class UserLogin(BaseModel):
    """User login request."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    """User response."""
    id: int
    email: str
    subscription_tier: str
    created_at: str


@router.post("/register", response_model=TokenResponse)
@limiter.limit("500/hour")  # 500 registrations per hour per IP (high limit for E2E testing)
async def register(request: Request, user_data: UserRegister):
    """
    Register a new user.

    - Validates email format
    - Validates password strength (8+ chars, upper, lower, number)
    - Checks password confirmation matches
    - Creates user in database
    - Returns JWT token
    """
    # Validate email
    if not validate_email(user_data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Validate password
    is_valid, error_msg = validate_password(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Check passwords match
    if user_data.password != user_data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    async with get_db() as db:
        # Check if email already exists
        existing = await fetchone(db, "SELECT id FROM users WHERE email = ?", (user_data.email.lower(),))
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create user
        hashed_password = get_password_hash(user_data.password)
        user_id = await execute_insert_returning_id(
            db,
            """
            INSERT INTO users (email, password_hash, subscription_tier, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_data.email.lower(), hashed_password, "free", datetime.utcnow())
        )

        # Create token
        token = create_access_token({"sub": str(user_id), "email": user_data.email.lower()})

        return TokenResponse(
            access_token=token,
            user={
                "id": user_id,
                "email": user_data.email.lower(),
                "subscription_tier": "free",
            }
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")  # 10 login attempts per minute per IP
async def login(request: Request, user_data: UserLogin):
    """
    Login with email and password.

    Returns JWT token on success.
    """
    async with get_db() as db:
        user = await fetchone(
            db,
            "SELECT id, email, password_hash, subscription_tier FROM users WHERE email = ?",
            (user_data.email.lower(),)
        )

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not verify_password(user_data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Create token
        token = create_access_token({"sub": str(user["id"]), "email": user["email"]})

        return TokenResponse(
            access_token=token,
            user={
                "id": user["id"],
                "email": user["email"],
                "subscription_tier": user["subscription_tier"],
            }
        )


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """
    Logout user by blacklisting their token.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    await blacklist_token(token)

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Get current authenticated user info.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    # Use async version that checks blacklist
    payload = await decode_access_token_async(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")

    async with get_db() as db:
        user = await fetchone(
            db,
            "SELECT id, email, subscription_tier, created_at FROM users WHERE id = ?",
            (user_id,)
        )

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return UserResponse(
            id=user["id"],
            email=user["email"],
            subscription_tier=user["subscription_tier"],
            created_at=str(user["created_at"]) if user["created_at"] else "",
        )


# Dependency for protected routes
async def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """
    Dependency to get current user ID from token.
    Use in route functions: user_id: int = Depends(get_current_user_id)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    return int(user_id)


# Admin authentication dependency
from app.config import get_settings

async def verify_admin(authorization: Optional[str] = Header(None)) -> bool:
    """
    Dependency to verify admin credentials via Basic Auth or Bearer token with admin role.
    Use in route functions: _: bool = Depends(verify_admin)

    Supports two authentication methods:
    1. Basic Auth: Authorization: Basic base64(username:password)
    2. Bearer token with admin claim
    """
    settings = get_settings()

    # Check if admin credentials are configured
    if not settings.admin_username or not settings.admin_password:
        raise HTTPException(
            status_code=503,
            detail="Admin panel is not configured. Set ADMIN_USERNAME and ADMIN_PASSWORD environment variables."
        )

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": "Basic realm='Admin Panel'"}
        )

    parts = authorization.split()
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    auth_type = parts[0].lower()
    credentials = parts[1]

    # Handle Basic Auth
    if auth_type == "basic":
        import base64
        try:
            decoded = base64.b64decode(credentials).decode("utf-8")
            username, password = decoded.split(":", 1)

            # Use constant-time comparison to prevent timing attacks
            import hmac
            username_match = hmac.compare_digest(username, settings.admin_username)
            password_match = hmac.compare_digest(password, settings.admin_password)

            if username_match and password_match:
                return True
            else:
                raise HTTPException(status_code=403, detail="Invalid admin credentials")
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(status_code=401, detail="Invalid Basic Auth credentials")

    # Handle Bearer token (check for admin role in token)
    elif auth_type == "bearer":
        payload = decode_access_token(credentials)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # Check if user has admin role (you can extend this to check database)
        if payload.get("role") == "admin" or payload.get("is_admin") == True:
            return True
        else:
            raise HTTPException(status_code=403, detail="Admin access required")

    else:
        raise HTTPException(status_code=401, detail="Unsupported authentication type")
