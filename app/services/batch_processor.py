"""Batch processing service with concurrency control."""
import asyncio
import json
import logging
from datetime import datetime

from app.database import get_db
from app.config import get_settings
from app.db_utils import execute, fetchone, fetchall, safe_json

logger = logging.getLogger(__name__)
from app.services.pipeline import process_job

settings = get_settings()


async def process_batch(batch_id: str):
    """
    Process all jobs in a batch with concurrency limit.

    Jobs are processed in parallel but limited to CONCURRENCY_LIMIT at a time.
    Individual job failures do not stop the batch - processing continues with remaining jobs.
    """
    # Get job IDs from batch
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT job_ids, user_id FROM batches WHERE id = ?",
            (batch_id,)
        )
        if not row:
            return

        job_ids = safe_json(row["job_ids"], [])
        user_id = row["user_id"]

    # Update batch status to processing
    await update_batch_status(batch_id, "processing")

    # Process jobs with concurrency limit using semaphore
    semaphore = asyncio.Semaphore(settings.batch_concurrency_limit)

    async def process_with_limit(job_id: str):
        """Process a single job with semaphore-controlled concurrency."""
        async with semaphore:
            try:
                await process_job(job_id)
            except Exception as e:
                # Log error with full context but continue with other jobs
                logger.error(
                    f"Batch job {job_id} in batch {batch_id} failed: {type(e).__name__}: {e}",
                    exc_info=True
                )
                # Mark job as failed if not already
                async with get_db() as db:
                    await execute(
                        db,
                        """
                        UPDATE jobs SET status = 'failed', error_message = ?
                        WHERE id = ? AND status != 'complete' AND status != 'failed'
                        """,
                        (str(e), job_id)
                    )
            finally:
                # Update batch progress after each job completes
                await update_batch_progress(batch_id)

    # Create tasks for all jobs
    tasks = [process_with_limit(job_id) for job_id in job_ids]

    # Wait for all jobs to complete (regardless of individual success/failure)
    await asyncio.gather(*tasks, return_exceptions=True)

    # Finalize batch
    await finalize_batch(batch_id)


async def update_batch_status(batch_id: str, status: str):
    """Update the batch status."""
    async with get_db() as db:
        await execute(
            db,
            "UPDATE batches SET status = ? WHERE id = ?",
            (status, batch_id)
        )


async def update_batch_progress(batch_id: str):
    """Update batch completion counts based on job statuses."""
    async with get_db() as db:
        # Get batch info
        row = await fetchone(
            db,
            "SELECT job_ids FROM batches WHERE id = ?",
            (batch_id,)
        )
        if not row:
            return

        job_ids = safe_json(row["job_ids"], [])

        # Count completed and failed jobs
        stats = await fetchone(
            db,
            f"""
            SELECT
                SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(COALESCE(cost_incurred, 0)) as total_cost
            FROM jobs
            WHERE id IN ({','.join('?' * len(job_ids))})
            """,
            tuple(job_ids)
        )

        # Update batch
        await execute(
            db,
            """
            UPDATE batches
            SET completed_jobs = ?, failed_jobs = ?, total_cost = ?
            WHERE id = ?
            """,
            (
                stats["completed"] or 0,
                stats["failed"] or 0,
                stats["total_cost"] or 0.0,
                batch_id
            )
        )


async def finalize_batch(batch_id: str):
    """Mark batch as complete or partial based on job outcomes."""
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT total_jobs, completed_jobs, failed_jobs FROM batches WHERE id = ?",
            (batch_id,)
        )
        if not row:
            return

        total = row["total_jobs"]
        completed = row["completed_jobs"] or 0
        failed = row["failed_jobs"] or 0

        # Determine final status
        if failed == total:
            status = "failed"
        elif failed > 0:
            status = "partial"
        else:
            status = "complete"

        # Update batch with final status and completion time
        await execute(
            db,
            """
            UPDATE batches
            SET status = ?, completed_at = ?
            WHERE id = ?
            """,
            (status, datetime.utcnow(), batch_id)
        )

        # Get user_id for webhook
        batch_row = await fetchone(
            db,
            "SELECT user_id FROM batches WHERE id = ?",
            (batch_id,)
        )

    # Trigger webhook for batch completion
    if batch_row:
        try:
            from app.services.webhook_manager import (
                trigger_webhook_event,
                get_batch_webhook_payload
            )
            batch_payload = await get_batch_webhook_payload(batch_id)
            await trigger_webhook_event("batch_finished", batch_row["user_id"], batch_payload)
        except Exception as webhook_error:
            logger.warning(
                f"Webhook trigger failed for batch {batch_id}: {type(webhook_error).__name__}: {webhook_error}",
                exc_info=True
            )
