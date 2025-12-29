"""Pipeline orchestrator - coordinates the 4-step content generation process."""
import json
import logging
import os
import traceback
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone
from app.models.job import JobStatus
from app.services.transcription import transcribe_file, cleanup_transcript, extract_document_content
from app.services.distillation import distill_content
from app.services.drafting import draft_linkedin_posts, draft_blog_post, draft_email, draft_email_sequence
from app.services.hook_generator import batch_generate_hooks
from app.services.editing import batch_edit_content
from app.services.factcheck import batch_factcheck_content
from app.services.library_manager import (
    add_stills_to_library,
    save_stills_to_db,
    save_outputs_to_db,
)
from app.services.scoring import batch_score_content
from app.utils.error_messages import format_pipeline_error, detect_error_type, get_error_message

settings = get_settings()


def enrich_outputs_with_topics(outputs: list[dict], stills: list[dict]) -> list[dict]:
    """
    Enrich outputs with topics gathered from the stills they use.

    Each output has a 'stills_used' field that lists still IDs.
    We gather all unique topics from those stills and add them to the output.
    """
    # Create a mapping of still ID to topics
    still_topics_map = {}
    for still in stills:
        still_id = still.get("id")
        topics = still.get("topics", [])
        if still_id and topics:
            still_topics_map[still_id] = topics

    # Enrich each output
    enriched_outputs = []
    for output in outputs:
        # Get stills used by this output
        stills_used = output.get("stills_used", output.get("atoms_used", []))

        # Gather all unique topics from the stills
        output_topics = set()
        for still_id in stills_used:
            if still_id in still_topics_map:
                output_topics.update(still_topics_map[still_id])

        # Add topics to output
        output_copy = output.copy()
        output_copy["topics"] = sorted(list(output_topics))
        enriched_outputs.append(output_copy)

    return enriched_outputs


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
                (status.value, current_step, progress, cost_to_add, error_message, job_id)
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
                (status.value, current_step, progress, cost_to_add, job_id)
            )

        # Update user's total cost if cost was added
        if cost_to_add > 0:
            await execute(
                db,
                """
                UPDATE users SET total_cost_incurred = total_cost_incurred + ?
                WHERE id = (SELECT user_id FROM jobs WHERE id = ?)
                """,
                (cost_to_add, job_id)
            )

        if not settings.use_postgres:
            await db.commit()


async def get_job_data(job_id: str) -> dict:
    """Get job data from database."""
    async with get_db() as db:
        row = await fetchone(db, "SELECT * FROM jobs WHERE id = ?", (job_id,))
        if row:
            return dict(row)
        return None


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
    user_id = None  # Initialize for error logging

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
        # Documents (PDF, DOCX, TXT, MD) go directly to extraction → atomization
        # Audio/Video go through transcription → cleanup → atomization
        is_document = file_type == "document"
        is_audio_video = file_type in ["audio", "video"]

        if is_document:
            # ======== DOCUMENT PATH: Extract content directly ========
            if not cleaned_transcript:
                await update_job_status(
                    job_id, JobStatus.TRANSCRIBING,
                    "Extracting document content", 15
                )

                if not file_path.exists():
                    raise FileNotFoundError(f"Upload file not found: {file_path}")

                # Extract document content with image/graph analysis
                # This goes directly to cleaned_transcript (no cleanup needed for documents)
                extracted_content, extract_cost = await extract_document_content(
                    file_path, job_id, user_id
                )
                total_cost += extract_cost

                # For documents, the extracted content IS the cleaned transcript
                # No cleanup step needed since it's not spoken content
                cleaned_transcript = extracted_content
                transcript = extracted_content

                # Save both transcript and cleaned_transcript
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
            # Step 0a: Transcription
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

                # Save transcript to database
                async with get_db() as db:
                    await execute(
                        db,
                        "UPDATE jobs SET transcript = ? WHERE id = ?",
                        (transcript, job_id)
                    )
                    if not settings.use_postgres:
                        await db.commit()

            # Step 0b: Cleanup (for spoken content with filler words, etc.)
            if not cleaned_transcript:
                await update_job_status(
                    job_id, JobStatus.CLEANING,
                    "Step 0b: Cleaning transcript", 20, total_cost
                )
                total_cost = 0  # Reset after update

                # Use transcript or the text that was uploaded
                source_text = transcript or job_data.get("transcript", "")

                cleaned_transcript, clean_cost = await cleanup_transcript(source_text)
                total_cost += clean_cost

                # Save cleaned transcript
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
            # Text was already saved to transcript, just need cleanup
            if not cleaned_transcript:
                await update_job_status(
                    job_id, JobStatus.CLEANING,
                    "Processing text content", 20, total_cost
                )
                total_cost = 0

                source_text = transcript or job_data.get("transcript", "")

                # For pasted text, do a light cleanup
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

        # ======== STEP 1: DISTILLATION ========
        await update_job_status(
            job_id, JobStatus.DISTILLING,
            "Step 1: Distilling content stills", 30, total_cost
        )
        total_cost = 0

        stills, still_cost = await distill_content(
            cleaned_transcript, target_persona, job_id, user_id
        )
        total_cost += still_cost

        # Save stills to database and the Reserve
        await save_stills_to_db(stills, campaign_name=campaign_name)
        await add_stills_to_library(stills, user_id, original_filename, campaign_name=campaign_name)

        # Check if this is a Quick Distill job - if so, complete now
        processing_mode = job_data.get("processing_mode", "autopilot")
        if processing_mode == "quick_distill":
            # Quick Distill: skip drafting/editing, just save stills to Reserve
            await update_job_status(
                job_id, JobStatus.COMPLETE,
                "Stills saved to Reserve", 100, total_cost
            )
            async with get_db() as db:
                if settings.use_postgres:
                    await db.execute("UPDATE jobs SET completed_at = NOW() WHERE id = $1", job_id)
                else:
                    await execute(db, "UPDATE jobs SET completed_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
                    await db.commit()
            return

        # ======== STEP 2: DRAFTING ========
        await update_job_status(
            job_id, JobStatus.DRAFTING,
            "Step 2: Drafting content", 50, total_cost
        )
        total_cost = 0

        all_drafts = []

        # Generate LinkedIn posts if requested
        if "linkedin" in asset_types:
            count = asset_quantities.get("linkedin", 3)
            linkedin_drafts, li_cost = await draft_linkedin_posts(
                stills, target_persona, count, job_id, user_id
            )
            total_cost += li_cost

            for i, draft in enumerate(linkedin_drafts):
                all_drafts.append({
                    "content_type": "linkedin",
                    "variation_number": i + 1,
                    "content": draft.get("content", ""),
                    "stills_used": draft.get("stills_used", draft.get("atoms_used", [])),
                })

        # Generate blog post if requested
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

        # Generate email if requested
        if "email" in asset_types:
            email_draft, email_cost = await draft_email(
                stills, target_persona, job_id, user_id
            )
            total_cost += email_cost

            all_drafts.append({
                "content_type": "email",
                "variation_number": 1,
                "content": email_draft.get("body", ""),
                "subject": email_draft.get("subject", ""),
                "stills_used": email_draft.get("stills_used", email_draft.get("atoms_used", [])),
            })

        # Generate email sequence if requested
        if "email_sequence" in asset_types:
            email_sequence, seq_cost = await draft_email_sequence(
                stills, target_persona, job_id, user_id
            )
            total_cost += seq_cost

            for i, email in enumerate(email_sequence):
                all_drafts.append({
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
                })

        # ======== STEP 3: EDITING ========
        await update_job_status(
            job_id, JobStatus.EDITING,
            "Step 3: Editing for audience", 70, total_cost
        )
        total_cost = 0

        edited_drafts, edit_cost = await batch_edit_content(
            all_drafts, target_persona, job_id, user_id
        )
        total_cost += edit_cost

        # ======== STEP 4: FACT-CHECKING ========
        await update_job_status(
            job_id, JobStatus.FACTCHECKING,
            "Step 4: Fact-checking content", 85, total_cost
        )
        total_cost = 0

        factchecked_drafts, fc_cost = await batch_factcheck_content(
            edited_drafts, cleaned_transcript, job_id, user_id
        )
        total_cost += fc_cost

        # ======== STEP 5: QUALITY SCORING ========
        await update_job_status(
            job_id, JobStatus.FACTCHECKING,
            "Step 5: Scoring content quality", 92, total_cost
        )
        total_cost = 0

        # Get persona title for context
        from app.services.persona_manager import get_persona
        persona = await get_persona(target_persona, user_id=user_id)
        persona_title = persona.get("title", "") if persona else ""

        scored_drafts, score_cost = await batch_score_content(
            factchecked_drafts, persona_title
        )
        total_cost += score_cost

        # ======== STEP 6: HOOK VARIATIONS (for LinkedIn posts) ========
        if "linkedin" in asset_types:
            await update_job_status(
                job_id, JobStatus.FACTCHECKING,
                "Step 6: Generating hook variations", 96, total_cost
            )
            total_cost = 0

            scored_drafts, hook_cost = await batch_generate_hooks(
                scored_drafts, target_persona, job_id, user_id
            )
            total_cost += hook_cost

        # ======== STEP 7: IMAGE PROMPT GENERATION ========
        await update_job_status(
            job_id, JobStatus.FACTCHECKING,
            "Step 7: Generating image prompts", 98, total_cost
        )
        total_cost = 0

        from app.services.image_prompts import batch_generate_image_prompts
        scored_drafts, img_cost = await batch_generate_image_prompts(
            scored_drafts, job_id, user_id
        )
        total_cost += img_cost

        # ======== SAVE RESULTS ========
        # Enrich outputs with topics from their stills
        enriched_outputs = enrich_outputs_with_topics(scored_drafts, stills)
        await save_outputs_to_db(enriched_outputs, job_id, campaign_name=campaign_name)

        # Mark job complete
        await update_job_status(
            job_id, JobStatus.COMPLETE,
            "Complete", 100, total_cost
        )

        # Update completed_at timestamp
        async with get_db() as db:
            if settings.use_postgres:
                await db.execute("UPDATE jobs SET completed_at = NOW() WHERE id = $1", job_id)
            else:
                await execute(db, "UPDATE jobs SET completed_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
                await db.commit()

        # Trigger webhooks for job completion and content generation
        try:
            from app.services.webhook_manager import (
                trigger_webhook_event,
                get_job_webhook_payload,
                get_content_webhook_payload
            )
            job_payload = await get_job_webhook_payload(job_id)
            await trigger_webhook_event("job_completed", user_id, job_payload)

            content_payload = await get_content_webhook_payload(job_id)
            await trigger_webhook_event("content_generated", user_id, content_payload)
        except Exception as webhook_error:
            # Don't fail the job if webhook fails
            logger.warning(f"Webhook trigger failed for job {job_id}: {webhook_error}")

    except Exception as e:
        # Log detailed error for debugging
        error_type = type(e).__name__
        error_message = str(e)
        stack_trace = traceback.format_exc()
        error_detail = f"{error_type}: {error_message}\n{stack_trace}"
        logger.error(f"Job {job_id} failed: {error_detail}")

        # Determine which step failed for context
        step_context = "unknown"
        job_data_check = await get_job_data(job_id)
        if job_data_check:
            current = job_data_check.get("current_step", "")
            if "transcrib" in current.lower() or "extract" in current.lower():
                step_context = "transcription"
            elif "distill" in current.lower() or "still" in current.lower():
                step_context = "distillation"
            elif "draft" in current.lower():
                step_context = "drafting"
            elif "edit" in current.lower():
                step_context = "editing"
            elif "fact" in current.lower():
                step_context = "factchecking"

        # Log error to database for admin debugging
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


async def process_job_from_library(job_id: str, still_content: list[dict]):
    """
    Process a job generated from Reserve stills.

    Skips transcription and distillation steps.
    """
    total_cost = 0.0

    try:
        # Get job data
        job_data = await get_job_data(job_id)
        if not job_data:
            return

        target_persona = job_data["target_persona"]
        user_id = job_data["user_id"]
        asset_types = json.loads(job_data["asset_types"]) if job_data["asset_types"] else ["linkedin"]
        asset_quantities = json.loads(job_data["asset_quantities"]) if job_data["asset_quantities"] else {}
        campaign_name = job_data.get("campaign_name")

        # Convert library entries to still format
        stills = []
        for entry in still_content:
            stills.append({
                "id": str(entry.get("id")),
                "still_type": entry.get("type", "insight"),
                "content": entry.get("content", ""),
                "persona_relevance": entry.get("persona_relevance", {}),
            })

        # ======== STEP 2: DRAFTING ========
        await update_job_status(
            job_id, JobStatus.DRAFTING,
            "Drafting content from Reserve", 50, 0
        )

        all_drafts = []

        if "linkedin" in asset_types:
            count = asset_quantities.get("linkedin", 2)
            linkedin_drafts, li_cost = await draft_linkedin_posts(
                stills, target_persona, count, job_id, user_id
            )
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
        # For Reserve generation, we do a lighter fact-check
        await update_job_status(
            job_id, JobStatus.FACTCHECKING,
            "Final review", 85, total_cost
        )

        # Use still content as "transcript" for fact-checking
        still_text = "\n\n".join([s["content"] for s in stills])
        factchecked_drafts, fc_cost = await batch_factcheck_content(
            edited_drafts, still_text, job_id, user_id
        )
        total_cost += fc_cost

        # Save results
        # Enrich outputs with topics from their stills
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
        error_detail = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Reserve job {job_id} failed: {error_detail}")

        # Get user-friendly error message
        user_error = format_pipeline_error(e, "generation", job_id)

        await update_job_status(
            job_id, JobStatus.FAILED,
            "Failed", 0, total_cost, user_error
        )
