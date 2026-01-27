"""Pipeline step functions - extracted steps for the content generation pipeline."""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone
from app.models.job import JobStatus
from app.services.distillation import distill_content, distill_content_pass2
from app.services.summarization import generate_source_summary
from app.services.drafting import (
    draft_linkedin_posts,
    draft_blog_post,
    draft_email,
    draft_email_sequence,
)
from app.services.hook_generator import batch_generate_hooks
from app.services.editing import batch_edit_content
from app.services.factcheck import batch_factcheck_content
from app.services.library_manager import add_stills_to_library, save_stills_to_db, save_outputs_to_db
from app.services.scoring import batch_score_content
from app.services.persona_manager import get_persona
from app.services.image_prompts import batch_generate_image_prompts
from app.services.webhook_manager import (
    trigger_webhook_event,
    get_job_webhook_payload,
    get_content_webhook_payload,
)
from app.services.stream_manager import get_or_create_stream, get_stream

logger = logging.getLogger(__name__)
settings = get_settings()


async def emit_stream_step(job_id: str, step_name: str, description: str = ""):
    """Emit a step marker to the job's stream if it exists."""
    stream = get_stream(job_id)
    if stream:
        await stream.emit_step(step_name, description)


@dataclass
class PipelineContext:
    """Shared state passed between pipeline steps."""

    job_id: str
    user_id: int
    target_persona: str
    asset_types: list[str]
    asset_quantities: dict
    original_filename: str
    campaign_name: Optional[str]
    cleaned_transcript: str
    source_id: Optional[str] = None
    generate_image_prompts: bool = False

    # Accumulated during pipeline
    total_cost: float = 0.0
    stills: list[dict] = field(default_factory=list)
    drafts: list[dict] = field(default_factory=list)


@dataclass
class StepResult:
    """Result from a pipeline step."""

    success: bool
    cost: float = 0.0
    data: dict = field(default_factory=dict)
    error: Optional[str] = None


def enrich_outputs_with_topics(outputs: list[dict], stills: list[dict]) -> list[dict]:
    """
    Enrich outputs with topics gathered from the stills they use.

    Each output has a 'stills_used' field that lists still IDs.
    We gather all unique topics from those stills and add them to the output.
    """
    still_topics_map = {}
    for still in stills:
        still_id = still.get("id")
        topics = still.get("topics", [])
        if still_id and topics:
            still_topics_map[still_id] = topics

    enriched_outputs = []
    for output in outputs:
        stills_used = output.get("stills_used", output.get("atoms_used", []))
        output_topics = set()
        for still_id in stills_used:
            if still_id in still_topics_map:
                output_topics.update(still_topics_map[still_id])

        output_copy = output.copy()
        output_copy["topics"] = sorted(list(output_topics))
        enriched_outputs.append(output_copy)

    return enriched_outputs


async def update_job_status(
    job_id: str,
    status: JobStatus,
    current_step: str,
    progress: int,
    cost_to_add: float = 0.0,
    error_message: str = None,
):
    """Update job status in database and track user costs."""
    async with get_db() as db:
        if error_message:
            await execute(
                db,
                """
                UPDATE jobs SET
                    status = ?, current_step = ?, progress = ?,
                    cost_incurred = cost_incurred + ?, error_message = ?
                WHERE id = ?
                """,
                (status.value, current_step, progress, cost_to_add, error_message, job_id),
            )
        else:
            await execute(
                db,
                """
                UPDATE jobs SET
                    status = ?, current_step = ?, progress = ?,
                    cost_incurred = cost_incurred + ?
                WHERE id = ?
                """,
                (status.value, current_step, progress, cost_to_add, job_id),
            )

        if cost_to_add > 0:
            await execute(
                db,
                """
                UPDATE users SET total_cost_incurred = total_cost_incurred + ?
                WHERE id = (SELECT user_id FROM jobs WHERE id = ?)
                """,
                (cost_to_add, job_id),
            )

        if not settings.use_postgres:
            await db.commit()


# ============================================================================
# STEP FUNCTIONS
# ============================================================================


async def step_distill(ctx: PipelineContext) -> StepResult:
    """Step 1: Distillation (Pass 1 + Pass 2) with parallel summarization."""
    total_cost = 0.0

    # Emit stream step marker
    await emit_stream_step(ctx.job_id, "distill", "Extracting key insights and stills from content")

    # Start summarization in parallel with distillation
    summary_task = asyncio.create_task(
        generate_source_summary(ctx.cleaned_transcript, ctx.job_id, ctx.user_id)
    )

    # Pass 1: Initial distillation
    await update_job_status(
        ctx.job_id,
        JobStatus.DISTILLING,
        "Step 1a: Distilling content stills (Pass 1)",
        25,
        ctx.total_cost,
    )
    ctx.total_cost = 0

    stills, still_cost = await distill_content(
        ctx.cleaned_transcript, ctx.target_persona, ctx.job_id, ctx.user_id
    )
    total_cost += still_cost
    logger.info(f"Job {ctx.job_id}: Pass 1 extracted {len(stills)} stills")

    # Pass 2: Deep extraction
    await update_job_status(
        ctx.job_id, JobStatus.DISTILLING, "Step 1b: Deep extraction (Pass 2)", 35, total_cost
    )
    total_cost = 0

    pass2_stills, pass2_cost = await distill_content_pass2(
        ctx.cleaned_transcript, stills, ctx.target_persona, ctx.job_id, ctx.user_id
    )
    total_cost += pass2_cost
    logger.info(f"Job {ctx.job_id}: Pass 2 extracted {len(pass2_stills)} additional stills")

    # Merge stills
    stills.extend(pass2_stills)
    logger.info(f"Job {ctx.job_id}: Total stills after both passes: {len(stills)}")

    # Await summarization result
    try:
        source_summary, summary_cost = await summary_task
        total_cost += summary_cost
        if source_summary:
            async with get_db() as db:
                await execute(
                    db,
                    "UPDATE jobs SET source_summary = ? WHERE id = ?",
                    (source_summary, ctx.job_id),
                )
                if not settings.use_postgres:
                    await db.commit()
            logger.info(f"Job {ctx.job_id}: Source summary saved ({len(source_summary)} chars)")
    except Exception as summary_err:
        logger.warning(f"Job {ctx.job_id}: Summary step failed (non-fatal): {summary_err}")

    # Save stills to database and the Reserve
    save_result = await save_stills_to_db(
        stills, campaign_name=ctx.campaign_name, source_id=ctx.source_id
    )
    if save_result["skipped_duplicates"] > 0:
        logger.info(
            f"Job {ctx.job_id}: {save_result['skipped_duplicates']} duplicate stills skipped, "
            f"{save_result['saved']} new stills saved"
        )
    await add_stills_to_library(
        stills,
        ctx.user_id,
        ctx.original_filename,
        campaign_name=ctx.campaign_name,
        job_id=ctx.job_id,
    )

    ctx.stills = stills
    return StepResult(success=True, cost=total_cost)


async def step_draft(ctx: PipelineContext) -> StepResult:
    """Step 2: Draft content for all requested asset types."""
    total_cost = 0.0

    # Emit stream step marker
    await emit_stream_step(ctx.job_id, "draft", "Creating initial content drafts")

    await update_job_status(
        ctx.job_id, JobStatus.DRAFTING, "Step 2: Drafting content", 50, ctx.total_cost
    )
    ctx.total_cost = 0

    all_drafts = []

    # LinkedIn posts
    if "linkedin" in ctx.asset_types:
        count = ctx.asset_quantities.get("linkedin", 3)
        linkedin_drafts, li_cost = await draft_linkedin_posts(
            ctx.stills, ctx.target_persona, count, ctx.job_id, ctx.user_id
        )
        total_cost += li_cost

        for i, draft in enumerate(linkedin_drafts):
            all_drafts.append(
                {
                    "content_type": "linkedin",
                    "variation_number": i + 1,
                    "content": draft.get("content", ""),
                    "stills_used": draft.get("stills_used", draft.get("atoms_used", [])),
                }
            )

    # Blog post
    if "blog" in ctx.asset_types:
        blog_draft, blog_cost = await draft_blog_post(
            ctx.stills, ctx.target_persona, ctx.job_id, ctx.user_id
        )
        total_cost += blog_cost

        all_drafts.append(
            {
                "content_type": "blog",
                "variation_number": 1,
                "content": blog_draft.get("content", ""),
                "title": blog_draft.get("title", ""),
                "stills_used": blog_draft.get("stills_used", blog_draft.get("atoms_used", [])),
            }
        )

    # Email
    if "email" in ctx.asset_types:
        email_draft, email_cost = await draft_email(
            ctx.stills, ctx.target_persona, ctx.job_id, ctx.user_id
        )
        total_cost += email_cost

        all_drafts.append(
            {
                "content_type": "email",
                "variation_number": 1,
                "content": email_draft.get("body", ""),
                "subject": email_draft.get("subject", ""),
                "stills_used": email_draft.get("stills_used", email_draft.get("atoms_used", [])),
            }
        )

    # Email sequence
    if "email_sequence" in ctx.asset_types:
        email_sequence, seq_cost = await draft_email_sequence(
            ctx.stills, ctx.target_persona, ctx.job_id, ctx.user_id
        )
        total_cost += seq_cost

        for i, email in enumerate(email_sequence):
            all_drafts.append(
                {
                    "content_type": "email_sequence",
                    "variation_number": i + 1,
                    "content": email.get("body", ""),
                    "subject": email.get("subject", ""),
                    "preview_text": email.get("preview_text", ""),
                    "email_day": email.get("day"),
                    "email_purpose": email.get("purpose", ""),
                    "sequence_name": email.get("sequence_name", ""),
                    "cta": email.get("cta", ""),
                    "stills_used": email.get("stills_used", email.get("atoms_used", [])),
                }
            )

    ctx.drafts = all_drafts
    return StepResult(success=True, cost=total_cost)


async def step_edit(ctx: PipelineContext) -> StepResult:
    """Step 3: Edit drafts for audience."""
    # Emit stream step marker
    await emit_stream_step(ctx.job_id, "edit", "Polishing content for target audience")

    await update_job_status(
        ctx.job_id, JobStatus.EDITING, "Step 3: Editing for audience", 70, ctx.total_cost
    )
    ctx.total_cost = 0

    edited_drafts, edit_cost = await batch_edit_content(
        ctx.drafts, ctx.target_persona, ctx.job_id, ctx.user_id
    )

    ctx.drafts = edited_drafts
    return StepResult(success=True, cost=edit_cost)


async def step_factcheck(ctx: PipelineContext) -> StepResult:
    """Step 4: Fact-check content against source."""
    # Emit stream step marker
    await emit_stream_step(ctx.job_id, "factcheck", "Verifying accuracy and claims")

    await update_job_status(
        ctx.job_id, JobStatus.FACTCHECKING, "Step 4: Fact-checking content", 85, ctx.total_cost
    )
    ctx.total_cost = 0

    factchecked_drafts, fc_cost = await batch_factcheck_content(
        ctx.drafts, ctx.cleaned_transcript, ctx.job_id, ctx.user_id, source_id=ctx.source_id
    )

    ctx.drafts = factchecked_drafts
    return StepResult(success=True, cost=fc_cost)


async def step_score(ctx: PipelineContext) -> StepResult:
    """Step 5: Score content quality."""
    await update_job_status(
        ctx.job_id, JobStatus.FACTCHECKING, "Step 5: Scoring content quality", 92, ctx.total_cost
    )
    ctx.total_cost = 0

    # Get persona title for context
    persona = await get_persona(ctx.target_persona, user_id=ctx.user_id)
    persona_title = persona.get("title", "") if persona else ""

    scored_drafts, score_cost = await batch_score_content(ctx.drafts, persona_title)

    ctx.drafts = scored_drafts
    return StepResult(success=True, cost=score_cost)


async def step_hooks(ctx: PipelineContext) -> StepResult:
    """Step 6: Generate hook variations for LinkedIn posts."""
    if "linkedin" not in ctx.asset_types:
        return StepResult(success=True, cost=0.0)

    await update_job_status(
        ctx.job_id,
        JobStatus.FACTCHECKING,
        "Step 6: Generating hook variations",
        96,
        ctx.total_cost,
    )
    ctx.total_cost = 0

    drafts_with_hooks, hook_cost = await batch_generate_hooks(
        ctx.drafts, ctx.target_persona, ctx.job_id, ctx.user_id
    )

    ctx.drafts = drafts_with_hooks
    return StepResult(success=True, cost=hook_cost)


async def step_image_prompts(ctx: PipelineContext) -> StepResult:
    """Step 7: Generate image prompts (optional)."""
    if not ctx.generate_image_prompts:
        logger.info(f"Job {ctx.job_id}: Skipping image prompt generation (disabled)")
        return StepResult(success=True, cost=0.0)

    await update_job_status(
        ctx.job_id, JobStatus.FACTCHECKING, "Step 7: Generating image prompts", 98, ctx.total_cost
    )
    ctx.total_cost = 0

    drafts_with_images, img_cost = await batch_generate_image_prompts(
        ctx.drafts, ctx.job_id, ctx.user_id
    )

    ctx.drafts = drafts_with_images
    return StepResult(success=True, cost=img_cost)


async def step_finalize(ctx: PipelineContext) -> StepResult:
    """Final step: Save results and trigger webhooks."""
    # Emit stream step marker
    await emit_stream_step(ctx.job_id, "complete", "Processing complete - saving results")

    # Enrich outputs with topics from their stills
    enriched_outputs = enrich_outputs_with_topics(ctx.drafts, ctx.stills)
    await save_outputs_to_db(enriched_outputs, ctx.job_id, campaign_name=ctx.campaign_name)

    # Mark job complete
    await update_job_status(ctx.job_id, JobStatus.COMPLETE, "Complete", 100, ctx.total_cost)

    # Emit completion to stream
    stream = get_stream(ctx.job_id)
    if stream:
        await stream.emit_complete("All content generated successfully")

    # Update completed_at timestamp
    async with get_db() as db:
        if settings.use_postgres:
            await db.execute("UPDATE jobs SET completed_at = NOW() WHERE id = $1", ctx.job_id)
        else:
            await execute(
                db, "UPDATE jobs SET completed_at = CURRENT_TIMESTAMP WHERE id = ?", (ctx.job_id,)
            )
            await db.commit()

    # Trigger webhooks
    try:
        job_payload = await get_job_webhook_payload(ctx.job_id)
        await trigger_webhook_event("job_completed", ctx.user_id, job_payload)

        content_payload = await get_content_webhook_payload(ctx.job_id)
        await trigger_webhook_event("content_generated", ctx.user_id, content_payload)
    except Exception as webhook_error:
        logger.warning(f"Webhook trigger failed for job {ctx.job_id}: {webhook_error}")

    return StepResult(success=True, cost=0.0)


async def run_pipeline_steps(ctx: PipelineContext) -> StepResult:
    """
    Run the shared pipeline steps from distillation through finalization.

    This is called by both process_job() (after transcription/SOT) and
    resume_pipeline_from_distillation() (after SOT approval).
    """
    # Step 1: Distillation
    result = await step_distill(ctx)
    if not result.success:
        return result
    ctx.total_cost += result.cost

    # Check if Quick Distill mode - stop after distillation
    async with get_db() as db:
        job_row = await fetchone(db, "SELECT processing_mode FROM jobs WHERE id = ?", (ctx.job_id,))
        processing_mode = job_row["processing_mode"] if job_row else "autopilot"

    if processing_mode == "quick_distill":
        await update_job_status(
            ctx.job_id, JobStatus.COMPLETE, "Stills saved to Reserve", 100, ctx.total_cost
        )
        async with get_db() as db:
            if settings.use_postgres:
                await db.execute("UPDATE jobs SET completed_at = NOW() WHERE id = $1", ctx.job_id)
            else:
                await execute(
                    db,
                    "UPDATE jobs SET completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (ctx.job_id,),
                )
                await db.commit()
        return StepResult(success=True, cost=ctx.total_cost)

    # Step 2: Drafting
    result = await step_draft(ctx)
    if not result.success:
        return result
    ctx.total_cost += result.cost

    # Step 3: Editing
    result = await step_edit(ctx)
    if not result.success:
        return result
    ctx.total_cost += result.cost

    # Step 4: Fact-checking
    result = await step_factcheck(ctx)
    if not result.success:
        return result
    ctx.total_cost += result.cost

    # Step 5: Scoring
    result = await step_score(ctx)
    if not result.success:
        return result
    ctx.total_cost += result.cost

    # Step 6: Hook variations
    result = await step_hooks(ctx)
    if not result.success:
        return result
    ctx.total_cost += result.cost

    # Step 7: Image prompts (optional)
    result = await step_image_prompts(ctx)
    if not result.success:
        return result
    ctx.total_cost += result.cost

    # Final: Save and complete
    result = await step_finalize(ctx)
    return result
