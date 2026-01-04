"""Pydantic models for authentication API endpoints."""
from pydantic import BaseModel


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
