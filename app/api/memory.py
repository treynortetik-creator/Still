"""Memory Rules API - Persistent content preferences that apply to all drafting."""
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.api.auth import get_current_user_id

router = APIRouter()


# Rule types
RULE_TYPES = {
    "always": "Always do this",
    "never": "Never do this",
    "prefer": "Prefer this style/approach",
    "avoid": "Avoid this style/approach",
    "include": "Always include this element",
    "exclude": "Always exclude this element",
    "tone": "Tone/voice preference",
    "format": "Formatting preference",
    "custom": "Custom rule",
}


class MemoryRuleCreate(BaseModel):
    """Request to create a memory rule."""
    rule_type: str
    rule_text: str
    priority: Optional[int] = 0


class MemoryRuleUpdate(BaseModel):
    """Request to update a memory rule."""
    rule_text: Optional[str] = None
    rule_type: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


@router.get("/memory/rules")
async def list_rules(
    active_only: bool = False,
    user_id: int = Depends(get_current_user_id),
):
    """List all memory rules for the current user."""
    async with get_db() as db:
        query = "SELECT * FROM memory_rules WHERE user_id = ?"
        params = [user_id]

        if active_only:
            query += " AND is_active = ?"
            params.append(True)

        query += " ORDER BY priority DESC, created_at DESC"

        rows = await fetchall(db, query, tuple(params))

        rules = []
        for row in rows:
            rules.append({
                "id": row["id"],
                "rule_type": row["rule_type"],
                "rule_text": row["rule_text"],
                "is_active": bool(row["is_active"]),
                "priority": row["priority"],
                "created_at": row["created_at"],
            })

        return {
            "rules": rules,
            "rule_types": RULE_TYPES,
        }


@router.post("/memory/rules")
async def create_rule(
    data: MemoryRuleCreate,
    user_id: int = Depends(get_current_user_id),
):
    """Create a new memory rule."""
    if data.rule_type not in RULE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid rule type. Valid types: {list(RULE_TYPES.keys())}"
        )

    if not data.rule_text or len(data.rule_text.strip()) < 3:
        raise HTTPException(status_code=400, detail="Rule text must be at least 3 characters")

    async with get_db() as db:
        row = await db.fetchrow(
            """
            INSERT INTO memory_rules (user_id, rule_type, rule_text, priority)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            user_id, data.rule_type, data.rule_text.strip(), data.priority or 0
        )
        rule_id = row["id"]

        return {
            "id": rule_id,
            "message": "Memory rule created",
        }


@router.put("/memory/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    data: MemoryRuleUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update a memory rule."""
    async with get_db() as db:
        # Check ownership
        existing = await fetchone(
            db,
            "SELECT id FROM memory_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id)
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Rule not found")

        # Build update query
        updates = []
        params = []

        if data.rule_text is not None:
            updates.append("rule_text = ?")
            params.append(data.rule_text.strip())
        if data.rule_type is not None:
            if data.rule_type not in RULE_TYPES:
                raise HTTPException(status_code=400, detail="Invalid rule type")
            updates.append("rule_type = ?")
            params.append(data.rule_type)
        if data.is_active is not None:
            updates.append("is_active = ?")
            params.append(data.is_active)
        if data.priority is not None:
            updates.append("priority = ?")
            params.append(data.priority)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(rule_id)
        await execute(
            db,
            f"UPDATE memory_rules SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )

        return {"message": "Rule updated"}


@router.delete("/memory/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Delete a memory rule."""
    async with get_db() as db:
        result = await execute(
            db,
            "DELETE FROM memory_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id)
        )

        # Check if any rows were affected
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Rule not found")

        return {"message": "Rule deleted"}


@router.post("/memory/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Toggle a rule's active status."""
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT is_active FROM memory_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id)
        )

        if not row:
            raise HTTPException(status_code=404, detail="Rule not found")

        new_status = not row["is_active"]
        await execute(
            db,
            "UPDATE memory_rules SET is_active = ? WHERE id = ?",
            (new_status, rule_id)
        )

        return {
            "is_active": bool(new_status),
            "message": "Rule " + ("activated" if new_status else "deactivated")
        }


@router.get("/memory/context")
async def get_memory_context(
    user_id: int = Depends(get_current_user_id),
):
    """
    Get the formatted memory context for use in prompts.

    This is what gets injected into drafting prompts.
    """
    context = await get_memory_rules_context(user_id)

    return {
        "context": context,
        "has_rules": bool(context),
    }


async def get_memory_rules_context(user_id: int) -> str:
    """
    Get formatted memory rules for injection into prompts.

    Called by drafting service to get user's persistent preferences.
    """
    async with get_db() as db:
        rows = await fetchall(
            db,
            """
            SELECT rule_type, rule_text
            FROM memory_rules
            WHERE user_id = ? AND is_active = ?
            ORDER BY priority DESC
            """,
            (user_id, True)
        )

        if not rows:
            return ""

        # Group rules by type
        rules_by_type = {}
        for row in rows:
            rule_type = row["rule_type"]
            if rule_type not in rules_by_type:
                rules_by_type[rule_type] = []
            rules_by_type[rule_type].append(row["rule_text"])

        # Format for prompt
        context_parts = ["\n=== USER'S CONTENT RULES (must follow) ==="]

        type_labels = {
            "always": "ALWAYS DO",
            "never": "NEVER DO",
            "prefer": "PREFER",
            "avoid": "AVOID",
            "include": "ALWAYS INCLUDE",
            "exclude": "NEVER INCLUDE",
            "tone": "TONE",
            "format": "FORMAT",
            "custom": "RULES",
        }

        for rule_type, rules in rules_by_type.items():
            label = type_labels.get(rule_type, rule_type.upper())
            context_parts.append(f"\n{label}:")
            for rule in rules:
                context_parts.append(f"  - {rule}")

        context_parts.append("\n")

        return "\n".join(context_parts)
