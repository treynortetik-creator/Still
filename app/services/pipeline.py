"""Pipeline orchestrator - coordinates the 4-step content generation process."""
import json
import logging
import os
import traceback
from pathlib import Path

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone
from app.models.job import JobStatus
from app.services.transcription import transcribe_file, cleanup_transcript, extract_document_content
from app.services.source_of_truth import (
    generate_source_of_truth,
    save_source_of_truth,
    approve_source_of_truth,
)
from app.services.editing import batch_edit_content
from app.services.factcheck import batch_factcheck_content
from app.services.drafting import draft_linkedin_posts, draft_blog_post
from app.services.library_manager import save_outputs_to_db
from app.services.pipeline_steps import (
    PipelineContext,
    run_pipeline_steps,
    update_job_status,
    enrich_outputs_with_topics,
)
from app.utils.error_messages import format_pipeline_error

logger = logging.getLogger(__name__)
settings = get_settings()


async def log_error_to_db(job_id: str, user_id: int, error_type: str, error_message: str, stack_trace: str):
    """Log error details to database for debugging."""
    try:
        async with get_db() as db:
            await execute(
                db,
                """
                INSERT INTO error_logs (job_id, user_id, error_type, error_message, stack_trace)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, user_id, error_type, error_message, stack_trace)
            )
            if not settings.use_postgres:
                await db.commit()
    except Exception as log_err:
        logger.warning(f"Failed to log error to database: {log_err}")


def validate_api_keys(file_type: str) -> tuple[bool, str]:
    """
    Validate that required API keys are configured for the given file type.

    All AI calls now go through OpenRouter, so only OPENROUTER_API_KEY is required.

    Returns (is_valid, error_message)
    """
    openrouter_key = settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")

    if not openrouter_key:
        return False, (
            "OPENROUTER_API_KEY is not configured. "
            "Please set it in Admin > Settings or your .env file. "
            "Get your API key at https://openrouter.ai/keys"
        )

    return True, ""


async def get_job_data(job_id: str) -> dict:
    """Get job data from database."""
    async with get_db() as db:
        row = await fetchone(db, "SELECT * FROM jobs WHERE id = ?", (job_id,))
        if row:
            return dict(row)
        return None


def _determine_step_context(current_step: str) -> str:
    """Determine the step context from current_step for error messages."""
    if not current_step:
        return "unknown"
    current = current_step.lower()
    if "transcrib" in current or "extract" in current:
        return "transcription"
    elif "distill" in current or "still" in current:
        return "distillation"
    elif "draft" in current:
        return "drafting"
    elif "edit" in current:
        return "editing"
    elif "fact" in current:
        return "factchecking"
    return "unknown"


async def _handle_pipeline_error(
    e: Exception, job_id: str, user_id: int, total_cost: float
):
    """Common error handling for pipeline failures."""
    error_type = type(e).__name__
    error_message = str(e)
    stack_trace = traceback.format_exc()
    error_detail = f"{error_type}: {error_message}\n{stack_trace}"
    logger.error(f"Job {job_id} failed: {error_detail}")

    # Determine which step failed for context
    job_data_check = await get_job_data(job_id)
    step_context = "unknown"
    if job_data_check:
        step_context = _determine_step_context(job_data_check.get("current_step", ""))

    # Log error to database
    await log_error_to_db(
        job_id,
        user_id if user_id else 0,
        f"{step_context.upper()}_{error_type}",
        error_message,
        stack_trace
    )

    # Get user-friendly error message
    user_error = format_pipeline_error(e, step_context, job_id)

    await update_job_status(
        job_id, JobStatus.FAILED,
        "Failed", 0, total_cost, user_error
    )


async def process_job(job_id: str):
    """
    Main pipeline orchestrator.

    Steps:
    0. Transcribe (if needed) + Clean
    1. Distill content (extract stills)
    2. Draft content
    3. Edit for audience
    4. Fact-check
    5. Save results
    """
    total_cost = 0.0
    user_id = None

    try:
        # Get job data
        job_data = await get_job_data(job_id)
        if not job_data:
            logger.error(f"Job {job_id} not found in database")
            return

        user_id = job_data["user_id"]
        target_persona = job_data["target_persona"]
        asset_types = json.loads(job_data["asset_types"]) if job_data["asset_types"] else ["linkedin"]
        asset_quantities = json.loads(job_data["asset_quantities"]) if job_data["asset_quantities"] else {}
        original_filename = job_data["original_filename"]
        file_type = job_data["file_type"]
        magic_words = job_data.get("magic_words")
        campaign_name = job_data.get("campaign_name")

        # === VALIDATE API KEYS BEFORE STARTING ===
        is_valid, api_error = validate_api_keys(file_type)
        if not is_valid:
            error_msg = f"API Configuration Error: {api_error}"
            logger.error(f"Job {job_id} failed: {error_msg}")
            await log_error_to_db(job_id, user_id, "API_KEY_MISSING", api_error, "")
            await update_job_status(
                job_id, JobStatus.FAILED,
                "Configuration Error", 0, 0,
                f"API Configuration Error: {api_error} Please configure the required API keys in Admin > Settings."
            )
            return

        # Check if we already have transcript (text upload)
        transcript = job_data.get("transcript")
        cleaned_transcript = job_data.get("cleaned_transcript")

        file_path = settings.upload_dir / str(user_id) / job_id / original_filename

        # Determine processing path based on file type
        is_document = file_type == "document"
        is_audio_video = file_type in ["audio", "video"]

        if is_document:
            # ======== DOCUMENT PATH: Extract content directly ========
            if not cleaned_transcript:
                if not file_path.exists():
                    raise FileNotFoundError(f"Upload file not found: {file_path}")

                ext = file_path.suffix.lower()
                is_plain_text = ext in [".txt", ".md", ".docx", ".doc"]

                if is_plain_text:
                    await update_job_status(
                        job_id, JobStatus.TRANSCRIBING,
                        "Reading text file...", 15
                    )
                else:
                    await update_job_status(
                        job_id, JobStatus.TRANSCRIBING,
                        "Extracting document content...", 15
                    )

                extracted_content, extract_cost = await extract_document_content(
                    file_path, job_id, user_id
                )
                total_cost += extract_cost

                cleaned_transcript = extracted_content
                transcript = extracted_content

                async with get_db() as db:
                    await execute(
                        db,
                        "UPDATE jobs SET transcript = ?, cleaned_transcript = ? WHERE id = ?",
                        (transcript, cleaned_transcript, job_id)
                    )
                    if not settings.use_postgres:
                        await db.commit()

        elif is_audio_video:
            # ======== AUDIO/VIDEO PATH: Transcribe → Cleanup ========
            if not transcript:
                await update_job_status(
                    job_id, JobStatus.TRANSCRIBING,
                    "Step 0a: Transcribing content", 10
                )

                if not file_path.exists():
                    raise FileNotFoundError(f"Upload file not found: {file_path}")

                transcript, trans_cost = await transcribe_file(
                    file_path, file_type, job_id, user_id, magic_words
                )
                total_cost += trans_cost

                async with get_db() as db:
                    await execute(
                        db,
                        "UPDATE jobs SET transcript = ? WHERE id = ?",
                        (transcript, job_id)
                    )
                    if not settings.use_postgres:
                        await db.commit()

            if not cleaned_transcript:
                await update_job_status(
                    job_id, JobStatus.CLEANING,
                    "Step 0b: Cleaning transcript", 20, total_cost
                )
                total_cost = 0

                source_text = transcript or job_data.get("transcript", "")

                cleaned_transcript, clean_cost = await cleanup_transcript(source_text)
                total_cost += clean_cost

                async with get_db() as db:
                    await execute(
                        db,
                        "UPDATE jobs SET cleaned_transcript = ? WHERE id = ?",
                        (cleaned_transcript, job_id)
                    )
                    if not settings.use_postgres:
                        await db.commit()

        else:
            # ======== TEXT UPLOAD PATH (file_type == "text") ========
            if not cleaned_transcript:
                await update_job_status(
                    job_id, JobStatus.CLEANING,
                    "Processing text content", 20, total_cost
                )
                total_cost = 0

                source_text = transcript or job_data.get("transcript", "")

                cleaned_transcript, clean_cost = await cleanup_transcript(source_text)
                total_cost += clean_cost

                async with get_db() as db:
                    await execute(
                        db,
                        "UPDATE jobs SET cleaned_transcript = ? WHERE id = ?",
                        (cleaned_transcript, job_id)
                    )
                    if not settings.use_postgres:
                        await db.commit()

        # ======== STEP 0c: SOURCE OF TRUTH GENERATION ========
        await update_job_status(
            job_id, JobStatus.ANALYZING,
            "Step 0c: Generating Source of Truth", 22, total_cost
        )
        total_cost = 0

        source_data, sot_cost = await generate_source_of_truth(
            cleaned_transcript, job_id, user_id
        )
        total_cost += sot_cost
        logger.info(f"Job {job_id}: Generated Source of Truth with {len(source_data.get('statistics', []))} statistics")

        source_id = await save_source_of_truth(job_id, user_id, source_data)

        auto_approve = job_data.get("auto_approve_source", False)

        if auto_approve:
            await approve_source_of_truth(source_id)
            logger.info(f"Job {job_id}: Auto-approved Source of Truth")
        else:
            await update_job_status(
                job_id, JobStatus.AWAITING_APPROVAL,
                "Awaiting Source of Truth approval", 24, total_cost
            )
            logger.info(f"Job {job_id}: Paused for Source of Truth approval")
            return

        # ======== RUN SHARED PIPELINE STEPS ========
        ctx = PipelineContext(
            job_id=job_id,
            user_id=user_id,
            target_persona=target_persona,
            asset_types=asset_types,
            asset_quantities=asset_quantities,
            original_filename=original_filename,
            campaign_name=campaign_name,
            cleaned_transcript=cleaned_transcript,
            source_id=source_id,
            generate_image_prompts=job_data.get("generate_image_prompts", False),
            total_cost=total_cost,
        )

        await run_pipeline_steps(ctx)

    except Exception as e:
        await _handle_pipeline_error(e, job_id, user_id if user_id else 0, total_cost)


async def process_job_from_library(job_id: str, still_content: list[dict]):
    """
    Process a job generated from Reserve stills.

    Skips transcription and distillation steps.
    """
    total_cost = 0.0
    user_id = 0

    logger.debug(f"[RESERVE] Starting process_job_from_library for job {job_id}")
    logger.debug(f"[RESERVE] Received {len(still_content)} stills")

    try:
        logger.debug(f"[RESERVE] Fetching job data for {job_id}")
        job_data = await get_job_data(job_id)
        if not job_data:
            logger.error(f"[RESERVE] Job {job_id} not found in database!")
            return

        target_persona = job_data["target_persona"]
        user_id = job_data["user_id"]
        asset_types = json.loads(job_data["asset_types"]) if job_data["asset_types"] else ["linkedin"]
        asset_quantities = json.loads(job_data["asset_quantities"]) if job_data["asset_quantities"] else {}
        campaign_name = job_data.get("campaign_name")

        logger.debug(f"[RESERVE] Job config: persona={target_persona}, assets={asset_types}, quantities={asset_quantities}")

        # Convert library entries to still format
        stills = []
        for entry in still_content:
            stills.append({
                "id": str(entry.get("id")),
                "still_type": entry.get("type", "insight"),
                "content": entry.get("content", ""),
                "persona_relevance": entry.get("persona_relevance", {}),
            })

        logger.debug(f"[RESERVE] Converted {len(stills)} stills for processing")
        if stills:
            logger.debug(f"[RESERVE] First still preview: {stills[0].get('content', '')[:100]}...")

        # ======== STEP 2: DRAFTING ========
        logger.debug(f"[RESERVE] Starting DRAFTING step")
        await update_job_status(
            job_id, JobStatus.DRAFTING,
            "Drafting content from Reserve", 50, 0
        )

        all_drafts = []

        if "linkedin" in asset_types:
            count = asset_quantities.get("linkedin", 2)
            logger.debug(f"[RESERVE] Drafting {count} LinkedIn posts...")
            linkedin_drafts, li_cost = await draft_linkedin_posts(
                stills, target_persona, count, job_id, user_id
            )
            logger.debug(f"[RESERVE] LinkedIn drafts complete: {len(linkedin_drafts)} drafts, cost={li_cost}")
            total_cost += li_cost

            for i, draft in enumerate(linkedin_drafts):
                all_drafts.append({
                    "content_type": "linkedin",
                    "variation_number": i + 1,
                    "content": draft.get("content", ""),
                    "stills_used": draft.get("stills_used", draft.get("atoms_used", [])),
                })

        if "blog" in asset_types:
            blog_draft, blog_cost = await draft_blog_post(
                stills, target_persona, job_id, user_id
            )
            total_cost += blog_cost

            all_drafts.append({
                "content_type": "blog",
                "variation_number": 1,
                "content": blog_draft.get("content", ""),
                "title": blog_draft.get("title", ""),
                "stills_used": blog_draft.get("stills_used", blog_draft.get("atoms_used", [])),
            })

        # ======== STEP 3: EDITING ========
        await update_job_status(
            job_id, JobStatus.EDITING,
            "Editing for audience", 70, total_cost
        )
        total_cost = 0

        edited_drafts, edit_cost = await batch_edit_content(
            all_drafts, target_persona, job_id, user_id
        )
        total_cost += edit_cost

        # ======== STEP 4: FACT-CHECKING ========
        await update_job_status(
            job_id, JobStatus.FACTCHECKING,
            "Final review", 85, total_cost
        )

        still_text = "\n\n".join([s["content"] for s in stills])
        factchecked_drafts, fc_cost = await batch_factcheck_content(
            edited_drafts, still_text, job_id, user_id
        )
        total_cost += fc_cost

        # Save results
        enriched_outputs = enrich_outputs_with_topics(factchecked_drafts, stills)
        await save_outputs_to_db(enriched_outputs, job_id, campaign_name=campaign_name)

        # Mark complete
        await update_job_status(
            job_id, JobStatus.COMPLETE,
            "Complete", 100, total_cost
        )

        async with get_db() as db:
            if settings.use_postgres:
                await db.execute("UPDATE jobs SET completed_at = NOW() WHERE id = $1", job_id)
            else:
                await execute(db, "UPDATE jobs SET completed_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
                await db.commit()

    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        stack_trace = traceback.format_exc()
        error_detail = f"{error_type}: {error_message}\n{stack_trace}"
        logger.error(f"[RESERVE] Job {job_id} failed: {error_detail}")

        try:
            await log_error_to_db(
                job_id,
                user_id,
                f"RESERVE_{error_type}",
                error_message,
                stack_trace
            )
        except Exception as log_err:
            logger.error(f"[RESERVE] Failed to log error to DB: {log_err}")

        user_error = format_pipeline_error(e, "generation", job_id)

        await update_job_status(
            job_id, JobStatus.FAILED,
            "Failed", 0, total_cost, user_error
        )


async def resume_pipeline_from_distillation(job_id: str):
    """
    Resume pipeline from distillation step after Source of Truth approval.

    This is called when user approves the Source of Truth via API.
    The pipeline continues from distillation onwards (skipping transcription/cleanup/SOT generation).
    """
    total_cost = 0.0
    user_id = None

    try:
        job_data = await get_job_data(job_id)
        if not job_data:
            logger.error(f"Job {job_id} not found for resume")
            return

        user_id = job_data["user_id"]
        target_persona = job_data.get("target_persona")
        asset_types = json.loads(job_data["asset_types"]) if job_data.get("asset_types") else ["linkedin"]
        asset_quantities = json.loads(job_data["asset_quantities"]) if job_data.get("asset_quantities") else {}
        original_filename = job_data.get("original_filename", "unknown")
        campaign_name = job_data.get("campaign_name")
        cleaned_transcript = job_data.get("cleaned_transcript")
        generate_image_prompts = job_data.get("generate_image_prompts", False)

        if not cleaned_transcript:
            raise ValueError("No cleaned transcript found - cannot resume pipeline")

        # Get source_id from sources table
        async with get_db() as db:
            source_row = await fetchone(
                db,
                "SELECT id FROM sources WHERE job_id = ?",
                (job_id,)
            )
            source_id = source_row["id"] if source_row else None

        # ======== RUN SHARED PIPELINE STEPS ========
        ctx = PipelineContext(
            job_id=job_id,
            user_id=user_id,
            target_persona=target_persona,
            asset_types=asset_types,
            asset_quantities=asset_quantities,
            original_filename=original_filename,
            campaign_name=campaign_name,
            cleaned_transcript=cleaned_transcript,
            source_id=source_id,
            generate_image_prompts=generate_image_prompts,
            total_cost=total_cost,
        )

        await run_pipeline_steps(ctx)

    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        stack_trace = traceback.format_exc()
        error_detail = f"{error_type}: {error_message}\n{stack_trace}"
        logger.error(f"Job {job_id} failed during resume: {error_detail}")

        job_data_check = await get_job_data(job_id)
        step_context = "unknown"
        if job_data_check:
            step_context = _determine_step_context(job_data_check.get("current_step", ""))

        await log_error_to_db(
            job_id,
            user_id if user_id else 0,
            f"{step_context.upper()}_{error_type}",
            error_message,
            stack_trace
        )

        user_error = format_pipeline_error(e, step_context, job_id)

        await update_job_status(
            job_id, JobStatus.FAILED,
            "Failed", 0, total_cost, user_error
        )
