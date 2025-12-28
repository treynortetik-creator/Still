"""Webhooks API endpoints for Zapier/external integrations."""
import json
from fastapi import APIRouter, HTTPException, Depends

from app.database import get_db
from app.api.auth import get_current_user_id
from app.models.webhook import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookCreateResponse,
    WebhookListResponse,
    WebhookTestResponse,
)


from app.services.webhook_manager import generate_secret_key, test_webhook


def mask_secret_key(secret_key: str) -> str:
    """Mask a secret key, showing only first 4 and last 4 characters."""
    if not secret_key or len(secret_key) < 12:
        return "****"
    return f"{secret_key[:4]}****{secret_key[-4:]}"

router = APIRouter()


@router.post("/webhooks", response_model=WebhookCreateResponse)
async def create_webhook(
    data: WebhookCreate,
    user_id: int = Depends(get_current_user_id),
):
    """Create a new webhook."""
    # Validate URL (basic check)
    if not data.url.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Webhook URL must use HTTPS"
        )

    # Validate trigger events
    valid_events = {"job_completed", "content_generated", "batch_finished"}
    for event in data.trigger_events:
        if event not in valid_events:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid trigger event: {event}"
            )

    # Generate secret key
    secret_key = generate_secret_key()

    async with get_db() as db:
        # Check if URL already exists for user
        cursor = await db.execute(
            "SELECT id FROM webhooks WHERE user_id = ? AND url = ?",
            (user_id, data.url)
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="A webhook with this URL already exists"
            )

        # Create webhook
        await db.execute(
            """
            INSERT INTO webhooks (user_id, name, url, secret_key, trigger_events)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                data.name,
                data.url,
                secret_key,
                json.dumps(data.trigger_events)
            )
        )
        await db.commit()

        # Get the created webhook
        cursor = await db.execute("SELECT last_insert_rowid()")
        webhook_id = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT * FROM webhooks WHERE id = ?",
            (webhook_id,)
        )
        webhook = await cursor.fetchone()

        if not webhook:
            raise HTTPException(
                status_code=500,
                detail="Failed to create webhook"
            )

    # Return full secret key only on creation
    return WebhookCreateResponse(
        id=webhook["id"],
        name=webhook["name"],
        url=webhook["url"],
        secret_key=webhook["secret_key"],
        trigger_events=json.loads(webhook["trigger_events"]),
        is_active=bool(webhook["is_active"]),
        created_at=webhook["created_at"]
    )


@router.get("/webhooks", response_model=WebhookListResponse)
async def list_webhooks(user_id: int = Depends(get_current_user_id)):
    """List all webhooks for the current user."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM webhooks
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        rows = await cursor.fetchall()

    webhooks = [
        WebhookResponse(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            secret_key_preview=mask_secret_key(row["secret_key"]),
            trigger_events=json.loads(row["trigger_events"]),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"]
        )
        for row in rows
    ]

    return WebhookListResponse(webhooks=webhooks, total=len(webhooks))


@router.get("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get a specific webhook."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM webhooks WHERE id = ? AND user_id = ?",
            (webhook_id, user_id)
        )
        webhook = await cursor.fetchone()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse(
        id=webhook["id"],
        name=webhook["name"],
        url=webhook["url"],
        secret_key_preview=mask_secret_key(webhook["secret_key"]),
        trigger_events=json.loads(webhook["trigger_events"]),
        is_active=bool(webhook["is_active"]),
        created_at=webhook["created_at"]
    )


@router.put("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: int,
    data: WebhookUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update a webhook."""
    async with get_db() as db:
        # Check ownership
        cursor = await db.execute(
            "SELECT * FROM webhooks WHERE id = ? AND user_id = ?",
            (webhook_id, user_id)
        )
        webhook = await cursor.fetchone()

        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        # Build update query dynamically
        updates = []
        values = []

        if data.name is not None:
            updates.append("name = ?")
            values.append(data.name)

        if data.url is not None:
            if not data.url.startswith("https://"):
                raise HTTPException(
                    status_code=400,
                    detail="Webhook URL must use HTTPS"
                )
            updates.append("url = ?")
            values.append(data.url)

        if data.trigger_events is not None:
            valid_events = {"job_completed", "content_generated", "batch_finished"}
            for event in data.trigger_events:
                if event not in valid_events:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid trigger event: {event}"
                    )
            updates.append("trigger_events = ?")
            values.append(json.dumps(data.trigger_events))

        if data.is_active is not None:
            updates.append("is_active = ?")
            values.append(1 if data.is_active else 0)

        if updates:
            values.append(webhook_id)
            await db.execute(
                f"UPDATE webhooks SET {', '.join(updates)} WHERE id = ?",
                values
            )
            await db.commit()

        # Fetch updated webhook
        cursor = await db.execute(
            "SELECT * FROM webhooks WHERE id = ?",
            (webhook_id,)
        )
        webhook = await cursor.fetchone()

    return WebhookResponse(
        id=webhook["id"],
        name=webhook["name"],
        url=webhook["url"],
        secret_key_preview=mask_secret_key(webhook["secret_key"]),
        trigger_events=json.loads(webhook["trigger_events"]),
        is_active=bool(webhook["is_active"]),
        created_at=webhook["created_at"]
    )


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Delete a webhook."""
    async with get_db() as db:
        # Check ownership
        cursor = await db.execute(
            "SELECT id FROM webhooks WHERE id = ? AND user_id = ?",
            (webhook_id, user_id)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Webhook not found")

        # Delete delivery records first
        await db.execute(
            "DELETE FROM webhook_deliveries WHERE webhook_id = ?",
            (webhook_id,)
        )

        # Delete webhook
        await db.execute(
            "DELETE FROM webhooks WHERE id = ?",
            (webhook_id,)
        )
        await db.commit()

    return {"message": "Webhook deleted"}


@router.post("/webhooks/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook_endpoint(
    webhook_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Send a test payload to a webhook."""
    result = await test_webhook(webhook_id, user_id)
    return WebhookTestResponse(**result)


@router.post("/webhooks/{webhook_id}/regenerate-secret")
async def regenerate_secret(
    webhook_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Regenerate the secret key for a webhook."""
    new_secret = generate_secret_key()

    async with get_db() as db:
        # Check ownership
        cursor = await db.execute(
            "SELECT id FROM webhooks WHERE id = ? AND user_id = ?",
            (webhook_id, user_id)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Webhook not found")

        # Update secret
        await db.execute(
            "UPDATE webhooks SET secret_key = ? WHERE id = ?",
            (new_secret, webhook_id)
        )
        await db.commit()

    return {"secret_key": new_secret}
