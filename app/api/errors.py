# app/api/errors.py
"""Error logging API endpoint for frontend errors."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional

from app.api.auth import get_current_user_id_optional
from app.services.error_logger import log_error
from app.rate_limiter import limiter

router = APIRouter()


class ErrorLogRequest(BaseModel):
    error_type: str = Field(..., max_length=200)
    error_message: str = Field(..., max_length=2000)
    endpoint: Optional[str] = Field(None, max_length=500)
    stack_trace: Optional[str] = Field(None, max_length=10000)
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
