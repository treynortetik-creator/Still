# app/api/errors.py
"""Error logging API endpoint for frontend errors."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.auth import get_current_user_id_optional
from app.services.error_logger import log_error

router = APIRouter()

# Rate limiter for error logging endpoint
limiter = Limiter(key_func=get_remote_address)


class ErrorLogRequest(BaseModel):
    error_type: str
    error_message: str
    endpoint: Optional[str] = None
    stack_trace: Optional[str] = None
    additional_context: Optional[dict] = None


@router.post("/errors/log")
@limiter.limit("30/minute")
async def log_frontend_error(
    request: Request,
    error_data: ErrorLogRequest,
    user_id: Optional[int] = Depends(get_current_user_id_optional)
):
    """Log a frontend error to the database."""
    await log_error(
        error_type=error_data.error_type,
        error_message=error_data.error_message,
        source="frontend",
        user_id=user_id,
        endpoint=error_data.endpoint,
        stack_trace=error_data.stack_trace,
        additional_context=error_data.additional_context
    )
    return {"success": True}
