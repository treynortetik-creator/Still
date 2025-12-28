"""Brand Voice API endpoints for voice analysis and management."""
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from app.api.auth import get_current_user_id
from app.database import get_db
from app.services.brand_voice_analyzer import (
    analyze_brand_voice,
    get_brand_voice_profile,
    get_voice_samples,
    add_voice_sample,
    delete_voice_sample,
)

router = APIRouter()


class SampleCreate(BaseModel):
    """Request to add a voice sample."""
    content: str
    content_type: Optional[str] = "general"


class BrandVoiceConfig(BaseModel):
    """Extended brand voice configuration."""
    company_name: Optional[str] = None
    industry: Optional[str] = None
    tone_linkedin: Optional[str] = None
    tone_blog: Optional[str] = None
    tone_email: Optional[str] = None
    tone_twitter: Optional[str] = None
    core_principles: Optional[List[str]] = None
    phrases_to_use: Optional[List[str]] = None
    phrases_to_avoid: Optional[List[str]] = None
    vocabulary_level: Optional[str] = "professional"


@router.get("/brand-voice/profile")
async def get_profile(
    user_id: int = Depends(get_current_user_id),
):
    """Get the user's brand voice profile and samples."""
    profile = await get_brand_voice_profile(user_id)
    samples = await get_voice_samples(user_id)

    return {
        "profile": profile,
        "samples": samples,
    }


@router.post("/brand-voice/samples")
async def create_sample(
    data: SampleCreate,
    user_id: int = Depends(get_current_user_id),
):
    """Add a writing sample for voice analysis."""
    if not data.content or len(data.content.strip()) < 50:
        raise HTTPException(status_code=400, detail="Sample must be at least 50 characters")

    if len(data.content) > 10000:
        raise HTTPException(status_code=400, detail="Sample must be less than 10,000 characters")

    sample_id = await add_voice_sample(
        user_id=user_id,
        content=data.content,
        content_type=data.content_type or "general",
    )

    return {
        "id": sample_id,
        "message": "Sample added successfully",
    }


@router.delete("/brand-voice/samples/{sample_id}")
async def remove_sample(
    sample_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Delete a voice sample."""
    success = await delete_voice_sample(user_id, sample_id)

    if not success:
        raise HTTPException(status_code=404, detail="Sample not found")

    return {"message": "Sample deleted"}


@router.post("/brand-voice/analyze")
async def run_analysis(
    user_id: int = Depends(get_current_user_id),
):
    """
    Analyze voice samples to create/update brand voice profile.

    Requires at least 3 samples.
    """
    try:
        result, cost = await analyze_brand_voice(user_id)

        return {
            "profile": result,
            "cost": cost,
            "message": "Brand voice analysis complete",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ========== Extended Brand Voice Configuration ==========

@router.get("/brand-voice/config")
async def get_brand_voice_config(
    user_id: int = Depends(get_current_user_id),
):
    """Get the user's extended brand voice configuration."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT company_name, industry, tone_linkedin, tone_blog,
                   tone_email, tone_twitter, core_principles,
                   phrases_to_use, phrases_to_avoid, vocabulary_level,
                   created_at, updated_at
            FROM brand_voice_config
            WHERE user_id = ?
            """,
            (user_id,)
        )
        row = await cursor.fetchone()

        if not row:
            # Return defaults
            return {
                "company_name": "",
                "industry": "",
                "tone_linkedin": "Professional and insightful",
                "tone_blog": "Educational and engaging",
                "tone_email": "Friendly and direct",
                "tone_twitter": "Conversational and punchy",
                "core_principles": [],
                "phrases_to_use": [],
                "phrases_to_avoid": [],
                "vocabulary_level": "professional",
                "is_configured": False,
            }

        return {
            "company_name": row["company_name"] or "",
            "industry": row["industry"] or "",
            "tone_linkedin": row["tone_linkedin"] or "",
            "tone_blog": row["tone_blog"] or "",
            "tone_email": row["tone_email"] or "",
            "tone_twitter": row["tone_twitter"] or "",
            "core_principles": json.loads(row["core_principles"]) if row["core_principles"] else [],
            "phrases_to_use": json.loads(row["phrases_to_use"]) if row["phrases_to_use"] else [],
            "phrases_to_avoid": json.loads(row["phrases_to_avoid"]) if row["phrases_to_avoid"] else [],
            "vocabulary_level": row["vocabulary_level"] or "professional",
            "is_configured": True,
            "updated_at": row["updated_at"],
        }


@router.put("/brand-voice/config")
async def update_brand_voice_config(
    config: BrandVoiceConfig,
    user_id: int = Depends(get_current_user_id),
):
    """Update the user's extended brand voice configuration."""
    async with get_db() as db:
        # Check if exists
        cursor = await db.execute(
            "SELECT id FROM brand_voice_config WHERE user_id = ?",
            (user_id,)
        )
        exists = await cursor.fetchone()

        core_principles_json = json.dumps(config.core_principles) if config.core_principles else None
        phrases_to_use_json = json.dumps(config.phrases_to_use) if config.phrases_to_use else None
        phrases_to_avoid_json = json.dumps(config.phrases_to_avoid) if config.phrases_to_avoid else None

        if exists:
            # Update
            await db.execute(
                """
                UPDATE brand_voice_config
                SET company_name = ?, industry = ?, tone_linkedin = ?,
                    tone_blog = ?, tone_email = ?, tone_twitter = ?,
                    core_principles = ?, phrases_to_use = ?, phrases_to_avoid = ?,
                    vocabulary_level = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (
                    config.company_name,
                    config.industry,
                    config.tone_linkedin,
                    config.tone_blog,
                    config.tone_email,
                    config.tone_twitter,
                    core_principles_json,
                    phrases_to_use_json,
                    phrases_to_avoid_json,
                    config.vocabulary_level,
                    user_id,
                )
            )
        else:
            # Insert
            await db.execute(
                """
                INSERT INTO brand_voice_config
                (user_id, company_name, industry, tone_linkedin, tone_blog,
                 tone_email, tone_twitter, core_principles, phrases_to_use,
                 phrases_to_avoid, vocabulary_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    config.company_name,
                    config.industry,
                    config.tone_linkedin,
                    config.tone_blog,
                    config.tone_email,
                    config.tone_twitter,
                    core_principles_json,
                    phrases_to_use_json,
                    phrases_to_avoid_json,
                    config.vocabulary_level,
                )
            )

        await db.commit()

    return {"message": "Brand voice configuration saved", "config": config.model_dump()}


@router.delete("/brand-voice/config")
async def delete_brand_voice_config(
    user_id: int = Depends(get_current_user_id),
):
    """Delete the user's brand voice configuration (reset to defaults)."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM brand_voice_config WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

    return {"message": "Brand voice configuration reset to defaults"}
