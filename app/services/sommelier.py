"""The Sommelier - AI-powered semantic search for stills in The Reserve."""
import json
import logging
from typing import Tuple

from app.config import get_settings
from app.database import get_db
from app.db_utils import fetchall, fetchone
from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.utils.json_parser import parse_llm_json

settings = get_settings()

logger = logging.getLogger(__name__)


async def search_stills(
    query: str,
    user_id: int,
    limit: int = 10,
) -> Tuple[list[dict], str, float]:
    """
    Search stills using AI-powered semantic matching.

    MVP Implementation:
    1. Parse user query with AI to understand intent and generate keywords
    2. Search stills database with expanded keywords
    3. Use AI to rerank results by relevance
    4. Return results with relevance explanations

    Returns (results, query_understood, cost) tuple.
    """
    total_cost = 0.0

    # Step 1: Parse query and generate search terms
    parse_prompt = f"""You are a content search assistant. The user wants to find content stills for their content creation.

USER QUERY: "{query}"

Analyze this query and respond with JSON:
{{
    "understood_intent": "Brief description of what the user is looking for",
    "search_keywords": ["keyword1", "keyword2", "keyword3"],
    "still_types_preferred": ["data", "insight", "story", "problem", "solution", "quote"],
    "topic_focus": "Main topic or theme"
}}

Important:
- Generate 5-10 search keywords covering different phrasings
- Include synonyms and related terms
- Consider the types of content stills that would be useful
- Be generous with keywords to maximize matches"""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=parse_prompt,
        step="distillation",  # Reuse distillation model for search
        response_format="json",
        job_id=None,
        user_id=user_id,
    )
    total_cost += calculate_openrouter_cost(model, input_tokens, output_tokens)

    # Parse the query understanding with robust JSON parser
    try:
        query_result = parse_llm_json(response_text, context="sommelier query")
    except ValueError as e:
        logger.warning(f"Failed to parse sommelier query: {e}")
        # Fallback: use original query as keyword
        query_result = {
            "understood_intent": query,
            "search_keywords": query.split(),
            "still_types_preferred": ["data", "insight", "story", "problem", "solution", "quote"],
            "topic_focus": query,
        }

    understood_intent = query_result.get("understood_intent", query)
    search_keywords = query_result.get("search_keywords", [query])
    preferred_types = query_result.get("still_types_preferred", [])

    # Step 2: Search database with expanded keywords
    async with get_db() as db:
        # Build search query - search across content and tags
        conditions = []
        params = [user_id]

        for keyword in search_keywords[:10]:  # Limit to 10 keywords
            conditions.append("(content LIKE ? OR tags LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where_clause = " OR ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT id, entry_type, content, source, tags, persona_relevance, times_used
            FROM content_library
            WHERE user_id = ? AND ({where_clause})
            ORDER BY times_used DESC
            LIMIT 50
        """
        rows = await fetchall(db, query, tuple(params))

        if not rows:
            return [], understood_intent, total_cost

        # Format stills for AI reranking
        stills_for_ranking = []
        for row in rows:
            stills_for_ranking.append({
                "id": row["id"],
                "type": row["entry_type"],
                "content": row["content"][:500],  # Truncate for prompt
                "source": row["source"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
            })

    # Step 3: AI reranking with relevance explanations
    rerank_prompt = f"""You are The Sommelier, an expert at matching content stills to user needs.

USER IS LOOKING FOR: {understood_intent}
PREFERRED STILL TYPES: {", ".join(preferred_types) if preferred_types else "any"}

AVAILABLE STILLS:
{json.dumps(stills_for_ranking, indent=2)}

Rank these stills by relevance to the user's query. Return JSON:
{{
    "ranked_stills": [
        {{
            "id": <still_id>,
            "relevance_score": 1-5,
            "why_relevant": "Brief explanation of why this still matches the query"
        }}
    ]
}}

Guidelines:
- Score 5 = Perfect match for their needs
- Score 4 = Highly relevant
- Score 3 = Moderately relevant
- Score 2 = Somewhat related
- Score 1 = Tangentially connected

Only include stills with score 2 or higher.
Return top {limit} most relevant stills.
Write clear, helpful explanations for why each still is relevant."""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=rerank_prompt,
        step="distillation",
        response_format="json",
        job_id=None,
        user_id=user_id,
    )
    total_cost += calculate_openrouter_cost(model, input_tokens, output_tokens)

    # Parse ranking results with robust JSON parser
    try:
        ranking_result = parse_llm_json(response_text, context="sommelier ranking")
    except ValueError as e:
        logger.warning(f"Failed to parse sommelier ranking: {e}")
        # Fallback: return unranked results
        return [
            {
                **s,
                "relevance_score": 3,
                "why_relevant": "Matched search keywords",
            }
            for s in stills_for_ranking[:limit]
        ], understood_intent, total_cost

    ranked_ids = {r["id"]: r for r in ranking_result.get("ranked_stills", [])}

    # Step 4: Build final results with full still data
    async with get_db() as db:
        results = []
        for still in stills_for_ranking:
            if still["id"] in ranked_ids:
                ranking = ranked_ids[still["id"]]

                # Get full still data
                row = await fetchone(
                    db,
                    "SELECT * FROM content_library WHERE id = ?",
                    (still["id"],)
                )

                if row:
                    results.append({
                        "id": row["id"],
                        "entry_type": row["entry_type"],
                        "content": row["content"],
                        "source": row["source"],
                        "source_timestamp": row["source_timestamp"],
                        "tags": json.loads(row["tags"]) if row["tags"] else [],
                        "persona_relevance": json.loads(row["persona_relevance"]) if row["persona_relevance"] else {},
                        "times_used": row["times_used"],
                        "relevance_score": ranking.get("relevance_score", 3),
                        "why_relevant": ranking.get("why_relevant", "Matched search criteria"),
                    })

        # Sort by relevance score
        results.sort(key=lambda x: x["relevance_score"], reverse=True)

    return results[:limit], understood_intent, total_cost


async def get_example_queries() -> list[str]:
    """Return example queries for the Sommelier UI."""
    return [
        "Find stats about fall prevention ROI",
        "Get quotes about AI in healthcare",
        "Stories about customer success with technology",
        "Data points for executive presentations",
        "Insights about digital transformation",
        "Problems healthcare administrators face",
    ]
