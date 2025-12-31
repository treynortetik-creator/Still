"""File upload API endpoints."""
import uuid
import json
import asyncio
import aiofiles
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Request
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchval
from app.models.job import JobResponse, JobStatus
from app.api.auth import get_current_user_id
from app.utils.security import sanitize_filename
from app.utils.validation import (
    validate_text_length,
    validate_json_field,
    validate_asset_types,
    validate_asset_quantities,
    validate_processing_mode,
)

router = APIRouter()
settings = get_settings()

# Rate limiter (uses app state limiter)
limiter = Limiter(key_func=get_remote_address)

# Allowed file types
ALLOWED_EXTENSIONS = {
    "video": [".mp4", ".mov", ".avi", ".webm", ".mkv"],
    "audio": [".mp3", ".wav", ".m4a", ".ogg", ".flac"],
    "document": [".pdf", ".txt", ".md", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp"],
}

ALLOWED_MIME_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/webm",
    "audio/mpeg", "audio/wav", "audio/x-m4a", "audio/ogg", "audio/flac",
    "application/pdf", "text/plain", "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png", "image/jpeg", "image/gif", "image/webp",
}


def get_file_type(filename: str, content_type: str) -> Optional[str]:
    """Determine file type category from filename and content type."""
    ext = Path(filename).suffix.lower()

    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return file_type

    return None


def generate_campaign_from_filename(filename: str) -> str:
    """Generate a campaign name from the filename.

    Examples:
        'marketing_strategy_2024.pdf' -> 'Marketing Strategy 2024'
        'podcast-episode-15.mp3' -> 'Podcast Episode 15'
        'Q4 Sales Training Video.mp4' -> 'Q4 Sales Training Video'
    """
    from pathlib import Path
    # Remove extension
    name = Path(filename).stem
    # Replace underscores and hyphens with spaces
    name = name.replace('_', ' ').replace('-', ' ')
    # Title case
    name = name.title()
    # Limit length
    return name[:200] if len(name) > 200 else name


@router.post("/upload", response_model=JobResponse)
@limiter.limit("10/hour")  # 10 uploads per hour per user
async def upload_content(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_persona: Optional[str] = Form(default=None),
    asset_types: str = Form(default='["linkedin", "blog"]'),
    asset_quantities: str = Form(default='{"linkedin": 3, "blog": 1}'),
    processing_mode: str = Form(default="autopilot"),
    campaign_name: Optional[str] = Form(default=None),
    magic_words: Optional[str] = Form(default=None),
    generate_image_prompts: str = Form(default="false"),
    user_id: int = Depends(get_current_user_id),
):
    """
    Upload content for processing.

    Accepts video, audio, PDF, or text files.
    Returns a job ID that can be used to track progress.
    """
    # Validate file type
    file_type = get_file_type(file.filename, file.content_type)
    if not file_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {list(ALLOWED_EXTENSIONS.keys())}"
        )

    # Check file size
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    max_size = settings.upload_max_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.upload_max_size_mb}MB"
        )

    # Validate optional text fields
    campaign_name = validate_text_length(
        campaign_name, "campaign_name", settings.max_campaign_name_chars
    )
    magic_words = validate_text_length(
        magic_words, "magic_words", settings.max_magic_words_chars
    )

    # Validate processing mode
    processing_mode = validate_processing_mode(processing_mode)

    # Parse and validate JSON fields
    # Allow empty asset types for quick_distill mode (stills-only extraction)
    is_quick_distill = processing_mode == "quick_distill"
    asset_types_list = validate_json_field(asset_types, "asset_types", list)
    asset_types_list = validate_asset_types(asset_types_list, allow_empty=is_quick_distill)

    asset_quantities_dict = validate_json_field(asset_quantities, "asset_quantities", dict)
    asset_quantities_dict = validate_asset_quantities(asset_quantities_dict, asset_types_list)

    # Auto-generate campaign name from filename for quick_distill if not provided
    if is_quick_distill and not campaign_name:
        campaign_name = generate_campaign_from_filename(file.filename)

    # Parse generate_image_prompts boolean from string
    gen_img_prompts = generate_image_prompts.lower() in ("true", "1", "yes")

    # Create job ID
    job_id = str(uuid.uuid4())

    # Create job directory (scoped by user_id)
    job_dir = settings.upload_dir / str(user_id) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file (sanitize filename to prevent path traversal)
    safe_filename = sanitize_filename(file.filename)
    file_path = job_dir / safe_filename
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Create job in database
    async with get_db() as db:
        await execute(
            db,
            """
            INSERT INTO jobs (
                id, user_id, status, original_filename, file_type, file_size,
                target_persona, asset_types, asset_quantities, processing_mode,
                campaign_name, magic_words, generate_image_prompts, current_step, progress
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                user_id,
                JobStatus.UPLOADING.value,
                file.filename,
                file_type,
                file_size,
                target_persona,
                json.dumps(asset_types_list),
                json.dumps(asset_quantities_dict),
                processing_mode,
                campaign_name,
                magic_words,
                gen_img_prompts,
                "Uploading file" if not is_quick_distill else "Uploading file for Quick Distill",
                5,
            )
        )
        if not settings.use_postgres:
            await db.commit()

    # Start background processing
    from app.services.pipeline import process_job
    background_tasks.add_task(process_job, job_id)

    return JobResponse(
        job_id=job_id,
        status=JobStatus.UPLOADING,
        message="File uploaded successfully. Processing started."
    )


@router.post("/upload-text", response_model=JobResponse)
@limiter.limit("10/hour")  # 10 uploads per hour per user
async def upload_text(
    request: Request,
    background_tasks: BackgroundTasks,
    content: str = Form(...),
    target_persona: Optional[str] = Form(default=None),
    asset_types: str = Form(default='["linkedin", "blog"]'),
    asset_quantities: str = Form(default='{"linkedin": 3, "blog": 1}'),
    processing_mode: str = Form(default="autopilot"),
    campaign_name: Optional[str] = Form(default=None),
    content_name: Optional[str] = Form(default="pasted_content.txt"),
    magic_words: Optional[str] = Form(default=None),
    generate_image_prompts: str = Form(default="false"),
    user_id: int = Depends(get_current_user_id),
):
    """
    Upload text content directly (paste text instead of file).
    """
    # Validate text content length
    if not content or not content.strip():
        raise HTTPException(
            status_code=400,
            detail="Content is required"
        )

    if len(content) > settings.max_text_content_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Content exceeds maximum length of {settings.max_text_content_chars} characters"
        )

    # Validate optional text fields
    campaign_name = validate_text_length(
        campaign_name, "campaign_name", settings.max_campaign_name_chars
    )
    magic_words = validate_text_length(
        magic_words, "magic_words", settings.max_magic_words_chars
    )
    content_name = validate_text_length(
        content_name, "content_name", settings.max_content_name_chars
    ) or "pasted_content.txt"

    # Validate processing mode
    processing_mode = validate_processing_mode(processing_mode)

    # Parse and validate JSON fields
    # Allow empty asset types for quick_distill mode (stills-only extraction)
    is_quick_distill = processing_mode == "quick_distill"
    asset_types_list = validate_json_field(asset_types, "asset_types", list)
    asset_types_list = validate_asset_types(asset_types_list, allow_empty=is_quick_distill)

    asset_quantities_dict = validate_json_field(asset_quantities, "asset_quantities", dict)
    asset_quantities_dict = validate_asset_quantities(asset_quantities_dict, asset_types_list)

    # Auto-generate campaign name from content_name for quick_distill if not provided
    if is_quick_distill and not campaign_name and content_name:
        campaign_name = generate_campaign_from_filename(content_name)

    # Parse generate_image_prompts boolean from string
    gen_img_prompts = generate_image_prompts.lower() in ("true", "1", "yes")

    # Create job ID
    job_id = str(uuid.uuid4())

    # Create job directory (scoped by user_id)
    job_dir = settings.upload_dir / str(user_id) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save text content (sanitize filename to prevent path traversal)
    safe_content_name = sanitize_filename(content_name)
    file_path = job_dir / safe_content_name
    async with aiofiles.open(file_path, "w") as f:
        await f.write(content)

    # Create job in database
    async with get_db() as db:
        await execute(
            db,
            """
            INSERT INTO jobs (
                id, user_id, status, original_filename, file_type, file_size,
                target_persona, asset_types, asset_quantities, processing_mode,
                campaign_name, magic_words, generate_image_prompts, current_step, progress, transcript
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                user_id,
                JobStatus.UPLOADING.value,
                content_name,
                "text",
                len(content.encode("utf-8")),
                target_persona,
                json.dumps(asset_types_list),
                json.dumps(asset_quantities_dict),
                processing_mode,
                campaign_name,
                magic_words,
                gen_img_prompts,
                "Processing text content" if not is_quick_distill else "Processing text for Quick Distill",
                10,
                content,  # Text content is already the transcript
            )
        )
        if not settings.use_postgres:
            await db.commit()

    # Start background processing
    from app.services.pipeline import process_job
    background_tasks.add_task(process_job, job_id)

    return JobResponse(
        job_id=job_id,
        status=JobStatus.UPLOADING,
        message="Text content uploaded successfully. Processing started."
    )


@router.post("/quick-distill", response_model=JobResponse)
@limiter.limit("10/hour")
async def quick_distill(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_persona: Optional[str] = Form(default=None),
    campaign_name: Optional[str] = Form(default=None),
    magic_words: Optional[str] = Form(default=None),
    user_id: int = Depends(get_current_user_id),
):
    """
    Quick Distill: Extract stills from content without generating content.

    Uploads a file, transcribes/extracts it, distills stills, and saves them
    directly to the Reserve. Skips drafting, editing, and other content generation steps.
    """
    # Validate file type
    file_type = get_file_type(file.filename, file.content_type)
    if not file_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {list(ALLOWED_EXTENSIONS.keys())}"
        )

    # Check file size
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    max_size = settings.upload_max_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.upload_max_size_mb}MB"
        )

    # Validate optional text fields
    campaign_name = validate_text_length(
        campaign_name, "campaign_name", settings.max_campaign_name_chars
    )
    magic_words = validate_text_length(
        magic_words, "magic_words", settings.max_magic_words_chars
    )

    # Auto-generate campaign_name from filename if not provided
    if not campaign_name:
        campaign_name = generate_campaign_from_filename(file.filename)

    # Create job ID
    job_id = str(uuid.uuid4())

    # Create job directory (scoped by user_id)
    job_dir = settings.upload_dir / str(user_id) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file (sanitize filename to prevent path traversal)
    safe_filename = sanitize_filename(file.filename)
    file_path = job_dir / safe_filename
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Use default persona if not provided
    if not target_persona:
        # Get the first available persona for the user
        async with get_db() as db:
            persona_id = await fetchval(
                db,
                "SELECT id FROM personas WHERE user_id = ? LIMIT 1",
                (user_id,)
            )
            if persona_id:
                target_persona = persona_id
            else:
                target_persona = "general"  # Fallback

    # Create job in database with quick_distill processing mode
    async with get_db() as db:
        await execute(
            db,
            """
            INSERT INTO jobs (
                id, user_id, status, original_filename, file_type, file_size,
                target_persona, asset_types, asset_quantities, processing_mode,
                campaign_name, magic_words, current_step, progress
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                user_id,
                JobStatus.UPLOADING.value,
                file.filename,
                file_type,
                file_size,
                target_persona,
                json.dumps([]),  # No asset types needed for Quick Distill
                json.dumps({}),  # No quantities needed
                "quick_distill",  # Special processing mode
                campaign_name,
                magic_words,
                "Uploading file for Quick Distill",
                5,
            )
        )
        if not settings.use_postgres:
            await db.commit()

    # Start background processing
    from app.services.pipeline import process_job
    background_tasks.add_task(process_job, job_id)

    return JobResponse(
        job_id=job_id,
        status=JobStatus.UPLOADING,
        message="Quick Distill started. Stills will be saved to your Reserve."
    )
