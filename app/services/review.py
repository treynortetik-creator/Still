"""Combined review service - merges editing, fact-checking, and scoring into one LLM call per draft."""
import logging
from typing import Tuple

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.persona_manager import get_persona
from app.services.brand_voice_analyzer import get_brand_voice_template_vars
from app.services.source_of_truth import (
    get_source_of_truth_template_vars,
    get_statistics_for_factcheck,
)
from app.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)

# Fallback persona when none is selected
DEFAULT_PERSONA = {
    "title": "General Professional Audience",
    "priorities": ["actionable insights", "practical solutions", "valuable information"],
    "pain_points": ["common business challenges", "efficiency", "growth"],
    "language_level": "Professional",
    "content_preferences": {"tone": "Professional"},
}

TRANSCRIPT_LIMIT = 50_000


async def review_and_polish(
    draft_content: str,
    original_transcript: str,
    persona_id: str,
    content_type: str,
    job_id: str = None,
    user_id: int = None,
    source_id: int = None,
    brand_voice_summary: str = "",
    brand_tone_markers: str = "",
    brand_phrases_to_avoid: str = "",
) -> Tuple[dict, float]:
    """
    Edit, fact-check, and score a single draft in one combined LLM call.

    Returns (review_result, cost) where review_result contains:
        final_content, changes_made, warnings, guardrails_status,
        citations, unverified_claims, fact_check_notes,
        quality_scores (with overall_score), review_status
    """
    # --- Gather context -------------------------------------------------------

    persona = None
    if persona_id:
        persona = await get_persona(persona_id, user_id=user_id)
    if not persona:
        persona = DEFAULT_PERSONA

    persona_title = persona["title"]
    persona_language = persona.get("language_level", "Professional")
    persona_priorities = ", ".join(persona.get("priorities", []))

    # Brand voice
    brand_vars: dict = {}
    if user_id:
        brand_vars = await get_brand_voice_template_vars(user_id, content_type=content_type)

    bv_summary = brand_voice_summary or brand_vars.get("brand_voice_summary", "")
    bv_tone = brand_tone_markers or brand_vars.get("brand_tone_markers", "")
    bv_avoid = brand_phrases_to_avoid or brand_vars.get("brand_phrases_to_avoid", "")

    # Source of Truth
    sot_vars: dict = {}
    if job_id:
        sot_vars = await get_source_of_truth_template_vars(job_id)

    core_narratives = sot_vars.get("core_narratives", "")
    primary_pain_point = sot_vars.get("primary_pain_point", "")
    the_promise = sot_vars.get("the_promise", "")

    # Verified statistics for fact-checking
    verified_stats_section = ""
    if source_id:
        stats = await get_statistics_for_factcheck(source_id)
        if stats:
            lines = []
            for s in stats:
                citation = s.get("citation", "N/A")
                confidence = s.get("confidence", "N/A")
                lines.append(f"- {s.get('stat', '')} [Citation: {citation}] (Confidence: {confidence})")
            verified_stats_section = (
                "VERIFIED STATISTICS (check claims against these FIRST):\n"
                + "\n".join(lines)
                + "\n"
            )

    truncated_transcript = original_transcript[:TRANSCRIPT_LIMIT] if original_transcript else ""

    # --- Build combined prompt ------------------------------------------------

    brand_alignment_criteria = ""
    if bv_summary or bv_tone:
        brand_alignment_criteria = (
            f"Brand voice: {bv_summary or 'professional and authentic'}. "
            f"Tone markers: {bv_tone or 'authoritative, helpful'}. "
            f"Avoid: {bv_avoid or 'overly salesy language'}."
        )
    else:
        brand_alignment_criteria = (
            "Professional and authentic tone. Avoid overly salesy language."
        )

    sot_block = ""
    if core_narratives or primary_pain_point or the_promise:
        parts = []
        if core_narratives:
            parts.append(f"Core narratives:\n{core_narratives}")
        if primary_pain_point:
            parts.append(f"Primary pain point: {primary_pain_point}")
        if the_promise:
            parts.append(f"The promise: {the_promise}")
        sot_block = "SOURCE OF TRUTH:\n" + "\n".join(parts) + "\n"

    prompt = f"""You are an expert content editor, fact-checker, and quality scorer. Perform ALL THREE tasks on the draft below and return a single JSON response.

CONTENT TYPE: {content_type}
TARGET AUDIENCE: {persona_title} (language level: {persona_language}, priorities: {persona_priorities})
BRAND VOICE: {brand_alignment_criteria}

{sot_block}{verified_stats_section}
SOURCE TRANSCRIPT (use for fact-checking):
{truncated_transcript}

DRAFT TO REVIEW:
{draft_content}

TASK 1 — EDIT FOR AUDIENCE
- Simplify jargon for the target audience
- Improve flow and readability
- Match the brand voice described above
- Apply guardrails: active voice, empowerment close, no competitor mentions, appropriate tone

TASK 2 — FACT-CHECK AGAINST SOURCE
- Verify every factual claim against the source transcript and verified statistics
- Flag anything unverified
- Add inline citations where appropriate

TASK 3 — QUALITY SCORE (0-100 each with a reason)
- hook_quality: Does the opening grab attention?
- brand_alignment: Matches the brand voice?
- clarity: Easy to understand, jargon minimized?
- engagement_potential: Will this resonate and provide value?

OUTPUT FORMAT (valid JSON):
{{
  "final_content": "The fully edited and fact-checked content",
  "changes_made": [
    {{"type": "simplification|flow|tone|guardrail|citation", "description": "What was changed"}}
  ],
  "warnings": ["Any warnings for human review"],
  "guardrails_status": {{
    "active_voice": true,
    "empowerment_close": true,
    "no_competitors": true,
    "appropriate_tone": true,
    "citations_flagged": true
  }},
  "citations": [
    {{"claim": "The claim", "source": "Where in transcript", "verified": true}}
  ],
  "unverified_claims": ["Claims that could not be verified"],
  "fact_check_notes": [
    {{"issue": "Description", "severity": "low|medium|high"}}
  ],
  "quality_scores": {{
    "hook_quality": {{"score": 85, "reason": "Reason"}},
    "brand_alignment": {{"score": 90, "reason": "Reason"}},
    "clarity": {{"score": 75, "reason": "Reason"}},
    "engagement_potential": {{"score": 80, "reason": "Reason"}}
  }}
}}"""

    # --- Call LLM -------------------------------------------------------------

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="editing",
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    # --- Parse response -------------------------------------------------------

    try:
        result = parse_llm_json(response_text, context="combined review response")
        result["review_status"] = "success"
    except ValueError as e:
        logger.warning(f"Review parse failed for job {job_id}: {e}")
        result = {
            "final_content": draft_content,
            "changes_made": [],
            "warnings": ["Review failed \u2014 manual review needed"],
            "guardrails_status": {},
            "citations": [],
            "unverified_claims": [],
            "fact_check_notes": [
                {"issue": f"Could not parse LLM response: {e}", "severity": "high"}
            ],
            "quality_scores": {
                "hook_quality": {"score": 0, "reason": "Review failed \u2014 manual review needed"},
                "brand_alignment": {"score": 0, "reason": "Review failed \u2014 manual review needed"},
                "clarity": {"score": 0, "reason": "Review failed \u2014 manual review needed"},
                "engagement_potential": {"score": 0, "reason": "Review failed \u2014 manual review needed"},
            },
            "review_status": "failed",
        }

    # Calculate overall_score from the 4 dimensions
    qs = result.get("quality_scores", {})
    dim_scores = [
        qs.get("hook_quality", {}).get("score", 0),
        qs.get("brand_alignment", {}).get("score", 0),
        qs.get("clarity", {}).get("score", 0),
        qs.get("engagement_potential", {}).get("score", 0),
    ]
    qs["overall_score"] = round(sum(dim_scores) / len(dim_scores)) if dim_scores else 0
    result["quality_scores"] = qs

    return result, cost


async def batch_review_and_polish(
    drafts: list[dict],
    original_transcript: str,
    persona_id: str,
    job_id: str = None,
    user_id: int = None,
    source_id: int = None,
) -> Tuple[list[dict], float]:
    """
    Review multiple drafts. Fetches brand voice vars once, then loops.

    Returns (reviewed_drafts, total_cost) with DB-compatible keys:
        step2_edited, step3_final, changes_made, warnings,
        guardrails_status, citations, unverified_claims,
        fact_check_notes, compliance_status, quality_scores
    """
    # Fetch brand voice vars once for the whole batch
    brand_vars: dict = {}
    if user_id:
        # Use first draft's content_type as representative; vars aren't type-specific
        rep_type = drafts[0].get("content_type", "linkedin") if drafts else "linkedin"
        brand_vars = await get_brand_voice_template_vars(user_id, content_type=rep_type)

    bv_summary = brand_vars.get("brand_voice_summary", "")
    bv_tone = brand_vars.get("brand_tone_markers", "")
    bv_avoid = brand_vars.get("brand_phrases_to_avoid", "")

    reviewed_drafts = []
    total_cost = 0.0

    for draft in drafts:
        content = draft.get("content", "")
        content_type = draft.get("content_type", "linkedin")

        if not content:
            reviewed_drafts.append(draft)
            continue

        result, cost = await review_and_polish(
            draft_content=content,
            original_transcript=original_transcript,
            persona_id=persona_id,
            content_type=content_type,
            job_id=job_id,
            user_id=user_id,
            source_id=source_id,
            brand_voice_summary=bv_summary,
            brand_tone_markers=bv_tone,
            brand_phrases_to_avoid=bv_avoid,
        )
        total_cost += cost

        final = result.get("final_content", content)

        reviewed_draft = {
            **draft,
            "step2_edited": final,
            "step3_final": final,
            "changes_made": result.get("changes_made", []),
            "warnings": result.get("warnings", []),
            "guardrails_status": result.get("guardrails_status", {}),
            "citations": result.get("citations", []),
            "unverified_claims": result.get("unverified_claims", []),
            "fact_check_notes": result.get("fact_check_notes", []),
            "compliance_status": {
                "all_claims_sourced": not result.get("unverified_claims"),
                "no_misrepresentation": True,
            },
            "quality_scores": result.get("quality_scores"),
        }
        reviewed_drafts.append(reviewed_draft)

    return reviewed_drafts, total_cost
