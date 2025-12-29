"""Batch processing API endpoints."""
import uuid
import json
import io
import zipfile
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.models.job import JobStatus
from app.models.batch import BatchResponse, BatchStatusResponse, BatchJobStatus, BatchListResponse, BatchListItem
from app.api.auth import get_current_user_id
from app.utils.security import sanitize_filename

router = APIRouter()
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

# Max files per batch
MAX_BATCH_FILES = 5

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    "video": [".mp4", ".mov", ".avi", ".webm", ".mkv"],
    "audio": [".mp3", ".wav", ".m4a", ".ogg", ".flac"],
    "document": [".pdf", ".txt", ".md", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp"],
}


def get_file_type(filename: str) -> Optional[str]:
    """Determine file type category from filename."""
    ext = Path(filename).suffix.lower()
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return file_type
    return None


@router.post("/batch/upload", response_model=BatchResponse)
@limiter.limit("5/hour")
async def upload_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    target_persona: Optional[str] = Form(default=None),
    asset_types: str = Form(default='["linkedin", "blog"]'),
    asset_quantities: str = Form(default='{"linkedin": 3, "blog": 1}'),
    campaign_name: Optional[str] = Form(default=None),
    magic_words: Optional[str] = Form(default=None),
    user_id: int = Depends(get_current_user_id),
):
    """
    Upload multiple files for batch processing (max 5).
    All files will be processed with the same settings.
    """
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_BATCH_FILES} files per batch"
        )

    if len(files) < 1:
        raise HTTPException(status_code=400, detail="At least 1 file required")

    # Parse JSON fields
    try:
        asset_types_list = json.loads(asset_types)
        asset_quantities_dict = json.loads(asset_quantities)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON in asset_types or asset_quantities"
        )

    # Validate all files first
    for file in files:
        file_type = get_file_type(file.filename)
        if not file_type:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type for {file.filename}"
            )

        # Check file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        max_size = settings.upload_max_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} too large. Maximum: {settings.upload_max_size_mb}MB"
            )

    # Create batch
    batch_id = str(uuid.uuid4())
    job_ids = []

    # Create job for each file
    async with get_db() as db:
        for file in files:
            job_id = str(uuid.uuid4())
            job_ids.append(job_id)

            file_type = get_file_type(file.filename)
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            # Create job directory
            job_dir = settings.upload_dir / str(user_id) / job_id
            job_dir.mkdir(parents=True, exist_ok=True)

            # Save file (sanitize filename to prevent path traversal)
            safe_filename = sanitize_filename(file.filename)
            file_path = job_dir / safe_filename
            content = await file.read()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)

            # Create job record
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
                    json.dumps(asset_types_list),
                    json.dumps(asset_quantities_dict),
                    "autopilot",
                    campaign_name,
                    magic_words,
                    "Queued for batch processing",
                    0,
                )
            )

        # Create batch record
        batch_settings = {
            "target_persona": target_persona,
            "asset_types": asset_types_list,
            "asset_quantities": asset_quantities_dict,
            "campaign_name": campaign_name,
            "magic_words": magic_words,
        }

        await execute(
            db,
            """
            INSERT INTO batches (id, user_id, status, job_ids, total_jobs, settings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                user_id,
                "pending",
                json.dumps(job_ids),
                len(job_ids),
                json.dumps(batch_settings),
                datetime.utcnow().isoformat(),
            )
        )
        if not settings.use_postgres:
            await db.commit()

    # Start batch processor
    from app.services.batch_processor import process_batch
    background_tasks.add_task(process_batch, batch_id)

    return BatchResponse(
        batch_id=batch_id,
        job_ids=job_ids,
        message=f"Batch created with {len(job_ids)} files. Processing started."
    )


@router.get("/batch/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """Get status of a batch with all job statuses."""
    async with get_db() as db:
        # Get batch
        batch = await fetchone(
            db,
            "SELECT * FROM batches WHERE id = ? AND user_id = ?",
            (batch_id, user_id)
        )

        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        job_ids = json.loads(batch["job_ids"])

        # Get all jobs in a single query (avoid N+1)
        if job_ids:
            job_rows = await fetchall(
                db,
                f"SELECT id, original_filename, status, progress, current_step, error_message FROM jobs WHERE id IN ({','.join('?' * len(job_ids))})",
                tuple(job_ids)
            )
            jobs = [
                BatchJobStatus(
                    job_id=job["id"],
                    filename=job["original_filename"],
                    status=job["status"],
                    progress=job["progress"] or 0,
                    current_step=job["current_step"],
                    error_message=job["error_message"],
                )
                for job in job_rows
            ]
        else:
            jobs = []

    return BatchStatusResponse(
        batch_id=batch_id,
        status=batch["status"],
        total_jobs=batch["total_jobs"],
        completed_jobs=batch["completed_jobs"] or 0,
        failed_jobs=batch["failed_jobs"] or 0,
        jobs=jobs,
        created_at=batch["created_at"],
        completed_at=batch["completed_at"],
        total_cost=batch["total_cost"] or 0.0,
    )


@router.get("/batch/{batch_id}/download")
async def download_batch_zip(
    batch_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """Download all completed outputs as a single ZIP file."""
    async with get_db() as db:
        batch = await fetchone(
            db,
            "SELECT job_ids, status FROM batches WHERE id = ? AND user_id = ?",
            (batch_id, user_id)
        )

        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        job_ids = json.loads(batch["job_ids"])

        # Batch fetch all completed jobs (avoid N+1)
        if not job_ids:
            raise HTTPException(status_code=404, detail="No jobs in batch")

        job_rows = await fetchall(
            db,
            f"SELECT id, original_filename, status FROM jobs WHERE id IN ({','.join('?' * len(job_ids))}) AND user_id = ? AND status = 'complete'",
            (*job_ids, user_id)
        )
        completed_jobs = {job["id"]: job for job in job_rows}

        # Batch fetch all outputs for completed jobs
        if completed_jobs:
            completed_job_ids = list(completed_jobs.keys())
            all_outputs = await fetchall(
                db,
                f"""
                SELECT job_id, content_type, variation_number, step3_final, step2_edited, step1_draft,
                       subject, hook_variations
                FROM outputs WHERE job_id IN ({','.join('?' * len(completed_job_ids))})
                """,
                tuple(completed_job_ids)
            )

            # Group outputs by job_id
            outputs_by_job = {}
            for output in all_outputs:
                job_id = output["job_id"]
                if job_id not in outputs_by_job:
                    outputs_by_job[job_id] = []
                outputs_by_job[job_id].append(output)
        else:
            outputs_by_job = {}

        # Create ZIP in memory
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for job_id, job in completed_jobs.items():
                try:
                    folder_name = Path(job["original_filename"]).stem
                    outputs = outputs_by_job.get(job_id, [])

                    # Build markdown export
                    md_content = f"# Content Export: {job['original_filename']}\n\n"
                    md_content += f"Generated: {datetime.utcnow().isoformat()}\n\n---\n\n"

                    for output in outputs:
                        content = output["step3_final"] or output["step2_edited"] or output["step1_draft"] or ""
                        content_type = output["content_type"]
                        variation = output["variation_number"] or 1

                        md_content += f"## {content_type.replace('_', ' ').title()} #{variation}\n\n"
                        if output["subject"]:
                            md_content += f"**Subject:** {output['subject']}\n\n"
                        md_content += f"{content}\n\n---\n\n"

                        # Also save individual files
                        if content:
                            filename = f"{folder_name}/{content_type}_{variation}.txt"
                            zf.writestr(filename, content)

                    # Save combined markdown
                    zf.writestr(f"{folder_name}/all_content.md", md_content)

                except Exception as e:
                    # Skip failed jobs
                    continue

        buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="batch_{batch_id[:8]}.zip"'
        }
    )


@router.get("/batches", response_model=BatchListResponse)
async def list_batches(
    user_id: int = Depends(get_current_user_id),
    limit: int = 20,
    offset: int = 0,
):
    """List all batches for the current user."""
    async with get_db() as db:
        rows = await fetchall(
            db,
            """
            SELECT id, status, total_jobs, completed_jobs, failed_jobs,
                   created_at, completed_at, total_cost
            FROM batches
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset)
        )

        # Get total count
        count_row = await fetchone(
            db,
            "SELECT COUNT(*) as cnt FROM batches WHERE user_id = ?",
            (user_id,)
        )
        total = count_row["cnt"] if count_row else 0

    batches = [
        BatchListItem(
            batch_id=row["id"],
            status=row["status"],
            total_jobs=row["total_jobs"],
            completed_jobs=row["completed_jobs"] or 0,
            failed_jobs=row["failed_jobs"] or 0,
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            total_cost=row["total_cost"] or 0.0,
        )
        for row in rows
    ]

    return BatchListResponse(batches=batches, total=total)
