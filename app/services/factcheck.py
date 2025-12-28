"""Fact-checking service - Step 3 of the pipeline."""
import json
from typing import Tuple

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt
from app.utils.json_parser import parse_llm_json


async def factcheck_content(
    edited_content: str,
    original_transcript: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[dict, float]:
    """
    Fact-check content against source material.

    Verifies claims, adds citations, checks for misrepresentation.

    Returns (factcheck_result, cost) tuple.
    """
    variables = {
        "original_transcript": original_transcript[:100000],  # Limit transcript size (Gemini Flash supports 1M tokens)
        "edited_draft_from_step2": edited_content,
    }

    prompt, config = await get_rendered_prompt("factcheck", variables)

    # Add output instruction
    full_prompt = prompt + """

OUTPUT FORMAT (valid JSON):
{
  "final_content": "The content with citations added inline",
  "citations_added": [
    {"claim": "The claim text", "source": "Where in transcript", "verified": true}
  ],
  "fact_check_notes": [
    {"issue": "Description of any issues found", "severity": "low|medium|high"}
  ],
  "warnings": ["Any warnings for human review"],
  "unverified_claims": ["Claims that couldn't be verified from source"],
  "compliance_status": {
    "all_claims_sourced": true,
    "no_misrepresentation": true,
    "disclaimer_added": true
  },
  "disclaimer": "This content was AI-generated from [source]. Please review before publication."
}"""

    # Call LLM via unified client
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=full_prompt,
        step="factcheck",
        max_tokens=config.get("max_tokens", 4096),
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Use robust JSON parser that handles common LLM output issues
    try:
        result = parse_llm_json(response_text, context="factcheck response")
    except ValueError as e:
        # If parsing still fails, return a minimal result with the original content
        result = {
            "final_content": edited_content,
            "citations_added": [],
            "fact_check_notes": [{"issue": f"Could not parse LLM response: {str(e)}", "severity": "medium"}],
            "warnings": ["Fact-check incomplete due to parsing error"],
            "unverified_claims": [],
            "compliance_status": {},
            "disclaimer": "This content was AI-generated. Please review before publication."
        }

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return result, cost


async def batch_factcheck_content(
    edited_drafts: list[dict],
    original_transcript: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[list[dict], float]:
    """
    Fact-check multiple edited drafts.

    Returns (factchecked_drafts, total_cost) tuple.
    """
    factchecked_results = []
    total_cost = 0.0

    for draft in edited_drafts:
        content = draft.get("step2_edited", draft.get("content", ""))

        if not content:
            factchecked_results.append(draft)
            continue

        result, cost = await factcheck_content(
            content, original_transcript, job_id, user_id
        )
        total_cost += cost

        factchecked_draft = {
            **draft,
            "step3_final": result.get("final_content", content),
            "citations": result.get("citations_added", []),
            "fact_check_notes": result.get("fact_check_notes", []),
            "unverified_claims": result.get("unverified_claims", []),
            "compliance_status": result.get("compliance_status", {}),
            "disclaimer": result.get("disclaimer", ""),
        }

        # Combine warnings
        existing_warnings = draft.get("warnings", [])
        new_warnings = result.get("warnings", [])
        factchecked_draft["warnings"] = existing_warnings + new_warnings

        factchecked_results.append(factchecked_draft)

    return factchecked_results, total_cost
