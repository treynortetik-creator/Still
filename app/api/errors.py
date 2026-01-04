# app/api/errors.py
"""Error logging API endpoint for frontend errors."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.auth import get_current_user_id_optional
from app.services.error_logger import log_error

router = APIRouter()


class ErrorLogRequest(BaseModel):
    error_type: str
    error_message: str
    endpoint: Optional[str] = None
    stack_trace: Optional[str] = None
    additional_context: Optional[dict] = None


@router.post("/errors/log")
async def log_frontend_error(
    request: ErrorLogRequest,
    user_id: Optional[int] = Depends(get_current_user_id_optional)
):
    """Log a frontend error to the database."""
    await log_error(
        error_type=request.error_type,
        error_message=request.error_message,
        source="frontend",
        user_id=user_id,
        endpoint=request.endpoint,
        stack_trace=request.stack_trace,
        additional_context=request.additional_context
    )
    return {"success": True}
