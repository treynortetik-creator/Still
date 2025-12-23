"""Fact-checking service - Step 3 of the pipeline."""
import json
from typing import Tuple
import google.generativeai as genai

from app.config import get_settings, calculate_cost
from app.services.prompt_manager import get_rendered_prompt
from app.utils.retry import retry_async, gemini_circuit_breaker

settings = get_settings()


async def factcheck_content(
    edited_content: str,
    original_transcript: str,
) -> Tuple[dict, float]:
    """
    Fact-check content against source material.

    Verifies claims, adds citations, checks for misrepresentation.

    Returns (factcheck_result, cost) tuple.
    """
    variables = {
        "original_transcript": original_transcript[:15000],  # Limit transcript size
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

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(config["model"])

    async def do_factcheck():
        return model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                max_output_tokens=config["max_tokens"],
            )
        )

    # Use retry logic for API call
    response = await retry_async(
        do_factcheck,
        max_retries=3,
        base_delay=2.0,
        context="factcheck_content",
    )

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError:
        text = response.text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
        else:
            raise ValueError("Failed to parse factcheck response as JSON")

    # Calculate cost
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    cost = calculate_cost(config["model"], input_tokens, output_tokens)

    return result, cost


async def batch_factcheck_content(
    edited_drafts: list[dict],
    original_transcript: str,
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

        result, cost = await factcheck_content(content, original_transcript)
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
