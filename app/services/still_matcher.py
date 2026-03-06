"""Still matching service for source refresh workflow."""
import logging
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt
from app.services.settings_manager import get_global_setting
from app.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)


def fuzzy_match_score(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two text strings.
    Uses SequenceMatcher for token-based comparison.

    Returns float between 0.0 (no match) and 1.0 (identical).
    """
    if not text1 or not text2:
        return 0.0

    # Normalize texts
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    # Use SequenceMatcher for similarity
    return SequenceMatcher(None, t1, t2).ratio()


def find_best_fuzzy_match(
    new_still: dict,
    old_stills: List[dict]
) -> Tuple[Optional[dict], float]:
    """
    Find the best matching old still for a new still using fuzzy matching.

    Returns (best_match, score) tuple.
    """
    if not old_stills:
        return None, 0.0

    best_match = None
    best_score = 0.0

    for old_still in old_stills:
        score = fuzzy_match_score(new_still["content"], old_still["content"])

        # Boost score if same type
        if new_still.get("still_type") == old_still.get("still_type"):
            score = min(1.0, score + 0.05)

        if score > best_score:
            best_score = score
            best_match = old_still

    return best_match, best_score


async def llm_match(
    old_still: dict,
    new_still_candidates: List[dict],
    source_context: str,
    user_id: int,
) -> dict:
    """
    Use LLM to determine if any candidates match the old still.

    Returns match result dict.
    """
    # Get model from settings
    model = await get_global_setting('still_matching_model', 'google/gemini-2.5-flash')

    # Format candidates for prompt
    candidates_text = "\n".join([
        f"[{i}] ({c.get('still_type', 'unknown').upper()}) {c['content']}"
        for i, c in enumerate(new_still_candidates)
    ])

    variables = {
        "old_still_content": old_still["content"],
        "old_still_type": old_still.get("still_type", "unknown"),
        "new_still_candidates": candidates_text,
        "source_context": source_context or "No additional context",
    }

    try:
        prompt, _ = await get_rendered_prompt("still_matching", variables)

        response_text, _, _, _ = await call_llm_text(
            prompt=prompt,
            step="still_matching",
            response_format="json",
            user_id=user_id,
        )

        result = parse_llm_json(response_text, context="still matching")

        if result.get("match_found") and result.get("matched_candidate_index") is not None:
            idx = result["matched_candidate_index"]
            if 0 <= idx < len(new_still_candidates):
                return {
                    "old": old_still,
                    "new": new_still_candidates[idx],
                    "confidence": result.get("confidence", "medium"),
                    "reasoning": result.get("reasoning", ""),
                    "match_type": "llm",
                }

        return {
            "old": old_still,
            "new": None,
            "confidence": result.get("confidence", "medium"),
            "reasoning": result.get("reasoning", "No match found"),
            "match_type": "llm",
        }

    except Exception as e:
        logger.error(f"LLM matching failed: {e}")
        return {
            "old": old_still,
            "new": None,
            "confidence": "low",
            "reasoning": f"LLM matching error: {str(e)}",
            "match_type": "error",
        }


async def match_stills(
    old_stills: List[dict],
    new_stills: List[dict],
    user_id: int,
    source_context: str = "",
) -> Tuple[List[dict], List[dict]]:
    """
    Match old stills to new stills using hybrid fuzzy + LLM approach.

    Args:
        old_stills: List of existing stills from source
        new_stills: List of new stills from refreshed source
        user_id: User ID for LLM calls
        source_context: Optional context about the source

    Returns:
        (matches, orphans) tuple where:
        - matches: List of {old, new, confidence, match_type} dicts
        - orphans: List of old stills with no match (should be retired)
    """
    # Get thresholds from settings
    high_threshold = float(await get_global_setting('fuzzy_match_high_threshold', '0.85'))
    low_threshold = float(await get_global_setting('fuzzy_match_low_threshold', '0.50'))

    matches = []
    matched_old_ids = set()
    matched_new_ids = set()
    uncertain_pairs = []

    # First pass: fuzzy matching
    for new_still in new_stills:
        best_match, score = find_best_fuzzy_match(new_still, old_stills)

        if score >= high_threshold and best_match:
            # High confidence match
            matches.append({
                "old": best_match,
                "new": new_still,
                "confidence": "high",
                "score": score,
                "match_type": "fuzzy",
            })
            matched_old_ids.add(best_match["id"])
            matched_new_ids.add(new_still["id"])
        elif score >= low_threshold and best_match:
            # Uncertain - queue for LLM
            uncertain_pairs.append({
                "old": best_match,
                "new": new_still,
                "score": score,
            })
        else:
            # No match - this is a new still
            matches.append({
                "old": None,
                "new": new_still,
                "confidence": "new",
                "match_type": "none",
            })
            matched_new_ids.add(new_still["id"])

    # Second pass: LLM for uncertain matches
    for pair in uncertain_pairs:
        if pair["old"]["id"] in matched_old_ids:
            # Already matched, treat as new
            matches.append({
                "old": None,
                "new": pair["new"],
                "confidence": "new",
                "match_type": "none",
            })
            continue

        # Get unmatched new stills as candidates for LLM
        candidates = [pair["new"]]  # Primary candidate

        llm_result = await llm_match(
            pair["old"],
            candidates,
            source_context,
            user_id,
        )

        if llm_result["new"]:
            matched_old_ids.add(pair["old"]["id"])
            matched_new_ids.add(llm_result["new"]["id"])

        matches.append(llm_result)

    # Find orphans (old stills with no match)
    orphans = [s for s in old_stills if s["id"] not in matched_old_ids]

    return matches, orphans
