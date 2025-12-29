"""Webhook management service for sending payloads to external services."""
import asyncio
import hmac
import hashlib
import json
import logging
import secrets
from datetime import datetime
from typing import Optional

import httpx

from app.database import get_db
from app.config import get_settings
from app.db_utils import execute, fetchone, fetchall
from app.utils.background_tasks import create_background_task

logger = logging.getLogger(__name__)
settings = get_settings()


def generate_secret_key() -> str:
    """Generate a random secret key for webhook signing."""
    return secrets.token_hex(32)


def create_signature(payload: dict, secret_key: str) -> str:
    """Create HMAC-SHA256 signature for webhook payload."""
    payload_str = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret_key.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature


async def trigger_webhook_event(event_type: str, user_id: int, data: dict):
    """
    Trigger webhooks for a specific event.

    Args:
        event_type: The type of event (job_completed, content_generated, batch_finished)
        user_id: The user ID to find webhooks for
        data: The event data payload
    """
    async with get_db() as db:
        # Get all active webhooks for this user that subscribe to this event
        webhooks = await fetchall(
            db,
            """
            SELECT id, url, secret_key, trigger_events
            FROM webhooks
            WHERE user_id = ? AND is_active = 1
            """,
            (user_id,)
        )

        for webhook in webhooks:
            trigger_events = json.loads(webhook["trigger_events"])
            if event_type not in trigger_events:
                continue

            # Build the full payload
            payload = {
                "event": event_type,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "webhook_id": webhook["id"],
                "data": data
            }

            # Create delivery record and get ID
            if settings.use_postgres:
                row = await db.fetchrow(
                    """
                    INSERT INTO webhook_deliveries (webhook_id, event_type, payload, attempts)
                    VALUES ($1, $2, $3, 0)
                    RETURNING id
                    """,
                    webhook["id"], event_type, json.dumps(payload)
                )
                delivery_id = row["id"]
            else:
                await execute(
                    db,
                    """
                    INSERT INTO webhook_deliveries (webhook_id, event_type, payload, attempts)
                    VALUES (?, ?, ?, 0)
                    """,
                    (webhook["id"], event_type, json.dumps(payload))
                )
                await db.commit()

                # Get the delivery ID
                cursor = await db.execute("SELECT last_insert_rowid()")
                delivery_id = (await cursor.fetchone())[0]

            # Trigger async delivery (fire and forget)
            create_background_task(
                deliver_webhook(
                    webhook["id"],
                    webhook["url"],
                    webhook["secret_key"],
                    payload,
                    delivery_id
                ),
                name=f"webhook_delivery_{delivery_id}"
            )


async def deliver_webhook(
    webhook_id: int,
    url: str,
    secret_key: str,
    payload: dict,
    delivery_id: int
) -> bool:
    """
    Deliver webhook with retries.

    Returns True if delivery was successful.
    """
    signature = create_signature(payload, secret_key)

    for attempt in range(settings.webhook_max_retries):
        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Attempt": str(attempt + 1),
                        "X-Webhook-Event": payload["event"],
                        "Content-Type": "application/json",
                        "User-Agent": "ContentMultiplier-Webhook/1.0"
                    }
                )

                # Update delivery record
                async with get_db() as db:
                    await execute(
                        db,
                        """
                        UPDATE webhook_deliveries
                        SET response_status = ?, response_body = ?, attempts = ?
                        WHERE id = ?
                        """,
                        (response.status_code, response.text[:1000], attempt + 1, delivery_id)
                    )
                    if not settings.use_postgres:
                        await db.commit()

                # Success if 2xx status
                if 200 <= response.status_code < 300:
                    return True

        except httpx.RequestError as e:
            # Log the error with full context
            logger.warning(
                f"Webhook delivery {delivery_id} to {url} failed (attempt {attempt + 1}): "
                f"{type(e).__name__}: {e}",
                exc_info=True
            )
            async with get_db() as db:
                await execute(
                    db,
                    """
                    UPDATE webhook_deliveries
                    SET response_body = ?, attempts = ?
                    WHERE id = ?
                    """,
                    (f"Request error: {type(e).__name__}: {str(e)}", attempt + 1, delivery_id)
                )
                if not settings.use_postgres:
                    await db.commit()

        # Wait before retry (with exponential backoff)
        if attempt < settings.webhook_max_retries - 1:
            delay = settings.webhook_retry_delay_seconds * (2 ** attempt)
            await asyncio.sleep(delay)

    return False


async def test_webhook(webhook_id: int, user_id: int) -> dict:
    """
    Send a test payload to a webhook.

    Returns dict with success status and details.
    """
    async with get_db() as db:
        # Get the webhook
        webhook = await fetchone(
            db,
            "SELECT url, secret_key FROM webhooks WHERE id = ? AND user_id = ?",
            (webhook_id, user_id)
        )

        if not webhook:
            return {"success": False, "message": "Webhook not found"}

        # Create test payload
        test_payload = {
            "event": "test",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "webhook_id": webhook_id,
            "data": {
                "message": "This is a test webhook from ContentMultiplier",
                "test": True
            }
        }

        signature = create_signature(test_payload, webhook["secret_key"])

        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                response = await client.post(
                    webhook["url"],
                    json=test_payload,
                    headers={
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Event": "test",
                        "Content-Type": "application/json",
                        "User-Agent": "ContentMultiplier-Webhook/1.0"
                    }
                )

                if 200 <= response.status_code < 300:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "message": "Webhook test successful"
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "message": f"Webhook returned status {response.status_code}"
                    }

        except httpx.RequestError as e:
            logger.warning(
                f"Webhook test for webhook {webhook_id} failed: {type(e).__name__}: {e}",
                exc_info=True
            )
            return {
                "success": False,
                "message": f"Request failed: {type(e).__name__}: {str(e)}"
            }


async def get_job_webhook_payload(job_id: str) -> dict:
    """Build webhook payload for job completion."""
    async with get_db() as db:
        # Get job details
        job = await fetchone(
            db,
            """
            SELECT id, user_id, status, original_filename, file_type,
                   target_persona, asset_types, cost_incurred,
                   created_at, completed_at
            FROM jobs WHERE id = ?
            """,
            (job_id,)
        )

        if not job:
            return {}

        return {
            "job_id": job["id"],
            "user_id": job["user_id"],
            "status": job["status"],
            "original_filename": job["original_filename"],
            "file_type": job["file_type"],
            "target_persona": job["target_persona"],
            "asset_types": json.loads(job["asset_types"]) if job["asset_types"] else [],
            "cost_incurred": job["cost_incurred"],
            "created_at": job["created_at"],
            "completed_at": job["completed_at"]
        }


async def get_content_webhook_payload(job_id: str) -> dict:
    """Build webhook payload for content generation with full output data."""
    async with get_db() as db:
        # Get job details
        job = await fetchone(
            db,
            "SELECT user_id, completed_at FROM jobs WHERE id = ?",
            (job_id,)
        )

        if not job:
            return {}

        # Get outputs
        outputs = await fetchall(
            db,
            """
            SELECT id, content_type, variation_number, step3_final,
                   quality_scores, hook_variations, subject, preview_text
            FROM outputs WHERE job_id = ?
            """,
            (job_id,)
        )

        output_list = []
        for output in outputs:
            output_list.append({
                "id": output["id"],
                "content_type": output["content_type"],
                "variation_number": output["variation_number"],
                "step3_final": output["step3_final"],
                "quality_scores": json.loads(output["quality_scores"]) if output["quality_scores"] else None,
                "hook_variations": json.loads(output["hook_variations"]) if output["hook_variations"] else None,
                "subject": output["subject"],
                "preview_text": output["preview_text"]
            })

        # Get still count
        still_row = await fetchone(
            db,
            "SELECT COUNT(*) as count FROM stills WHERE job_id = ?",
            (job_id,)
        )
        still_count = still_row["count"]

        return {
            "job_id": job_id,
            "user_id": job["user_id"],
            "completed_at": job["completed_at"],
            "outputs": output_list,
            "still_count": still_count
        }


async def get_batch_webhook_payload(batch_id: str) -> dict:
    """Build webhook payload for batch completion."""
    async with get_db() as db:
        batch = await fetchone(
            db,
            """
            SELECT id, user_id, status, total_jobs, completed_jobs,
                   failed_jobs, total_cost, created_at, completed_at
            FROM batches WHERE id = ?
            """,
            (batch_id,)
        )

        if not batch:
            return {}

        return {
            "batch_id": batch["id"],
            "user_id": batch["user_id"],
            "status": batch["status"],
            "total_jobs": batch["total_jobs"],
            "completed_jobs": batch["completed_jobs"],
            "failed_jobs": batch["failed_jobs"],
            "total_cost": batch["total_cost"],
            "created_at": batch["created_at"],
            "completed_at": batch["completed_at"]
        }
