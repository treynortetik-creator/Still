"""Authentication service - JWT token management and password hashing."""
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
import jwt
from jwt.exceptions import PyJWTError

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchval

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def _hash_token(token: str) -> str:
    """Hash a token for storage (don't store raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token (sync version - doesn't check blacklist)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        return None


async def decode_access_token_async(token: str) -> Optional[dict]:
    """Decode and validate a JWT token with blacklist check."""
    try:
        # Check if token is blacklisted
        if await is_token_blacklisted(token):
            return None

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        return None


async def blacklist_token(token: str):
    """Add a token to the database blacklist (for logout)."""
    token_hash = _hash_token(token)

    # Get token expiration from the token itself
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        expires_at = datetime.utcfromtimestamp(payload.get("exp", 0))
    except PyJWTError:
        # If we can't decode, set expiration to 7 days from now
        expires_at = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO revoked_tokens (token_hash, expires_at)
            VALUES ($1, $2)
            ON CONFLICT (token_hash) DO UPDATE SET expires_at = $2
            """,
            token_hash, expires_at
        )


async def is_token_blacklisted(token: str) -> bool:
    """Check if a token is blacklisted in the database."""
    token_hash = _hash_token(token)

    async with get_db() as db:
        result = await fetchval(db, "SELECT 1 FROM revoked_tokens WHERE token_hash = ?", (token_hash,))
        return result is not None


async def cleanup_expired_tokens():
    """Remove expired tokens from the blacklist."""
    async with get_db() as db:
        await db.execute("DELETE FROM revoked_tokens WHERE expires_at < NOW()")


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password meets requirements.
    Returns (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"

    return True, ""
