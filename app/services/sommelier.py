"""The Sommelier - AI-powered semantic search for stills in The Reserve."""
import json
import logging
from typing import Tuple, Dict

from app.config import get_settings
from app.database import get_db
from app.db_utils import fetchall, fetchone, execute
from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.utils.json_parser import parse_llm_json

settings = get_settings()

logger = logging.getLogger(__name__)

# Default prompt for parsing user queries
DEFAULT_PARSE_PROMPT = """You are a content search assistant. The user wants to find content stills for their content creation.

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

# Default prompt for reranking search results
DEFAULT_RERANK_PROMPT = """You are The Sommelier, an expert at matching content stills to user needs.

USER IS LOOKING FOR: {understood_intent}
PREFERRED STILL TYPES: {preferred_types}

AVAILABLE STILLS:
{stills_json}

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
- Score 1 = Loosely connected but potentially useful

BE GENEROUS with scoring - when in doubt, score higher rather than lower.
For broad or exploratory queries, include MORE stills to give the user options.
The user WANTS to see their content - help them find it.

Return top {limit} most relevant stills.
Write clear, helpful explanations for why each still is relevant."""


async def get_sommelier_config() -> Dict[str, str]:
    """Get Sommelier configuration from database."""
    async with get_db() as db:
        rows = await fetchall(
            db,
            "SELECT config_key, config_value FROM ai_editor_config WHERE config_key LIKE ?",
            ("sommelier_%",)
        )

        config = {}
        for row in rows:
            config[row["config_key"]] = row["config_value"]

        # Return defaults if not configured
        if "sommelier_parse_prompt" not in config:
            config["sommelier_parse_prompt"] = DEFAULT_PARSE_PROMPT
        if "sommelier_rerank_prompt" not in config:
            config["sommelier_rerank_prompt"] = DEFAULT_RERANK_PROMPT

        return config


async def save_sommelier_config(config_key: str, config_value: str) -> None:
    """Save Sommelier configuration to database."""
    async with get_db() as db:
        if settings.use_postgres:
            await db.execute(
                """
                INSERT INTO ai_editor_config (config_key, config_value, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT(config_key) DO UPDATE SET
                    config_value = EXCLUDED.config_value,
                    updated_at = NOW()
                """,
                config_key, config_value
            )
        else:
            await db.execute(
                """
                INSERT INTO ai_editor_config (config_key, config_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(config_key) DO UPDATE SET
                    config_value = excluded.config_value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (config_key, config_value)
            )
            await db.commit()


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

    # Load configurable prompts
    config = await get_sommelier_config()
    parse_prompt_template = config.get("sommelier_parse_prompt", DEFAULT_PARSE_PROMPT)
    rerank_prompt_template = config.get("sommelier_rerank_prompt", DEFAULT_RERANK_PROMPT)

    # Step 1: Parse query and generate search terms
    parse_prompt = parse_prompt_template.format(query=query)

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=parse_prompt,
        step="sommelier",  # Sommelier has its own model config
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
        # First, check if user has ANY content in their Reserve
        total_count = await fetchone(
            db,
            "SELECT COUNT(*) as count FROM content_library WHERE user_id = ?",
            (user_id,)
        )

        if not total_count or total_count["count"] == 0:
            logger.info(f"Sommelier: User {user_id} has no content in Reserve")
            return [], "Your Reserve is empty. Save some stills from your processed content first!", total_cost

        logger.info(f"Sommelier: User {user_id} has {total_count['count']} items in Reserve, searching with keywords: {search_keywords[:5]}")

        # Build search query - search across content and tags
        # Note: tags is JSONB in PostgreSQL, need to cast to text for LIKE
        conditions = []
        params = [user_id]

        for keyword in search_keywords[:10]:  # Limit to 10 keywords
            if settings.use_postgres:
                # PostgreSQL: cast JSONB to text for LIKE operator
                conditions.append("(content LIKE ? OR tags::text LIKE ?)")
            else:
                # SQLite: tags stored as text
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

        logger.debug(f"Sommelier query: {query}")
        logger.debug(f"Sommelier params count: {len(params)}")

        rows = await fetchall(db, query, tuple(params))

        logger.info(f"Sommelier: Found {len(rows)} matching items for user {user_id}")

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
    rerank_prompt = rerank_prompt_template.format(
        understood_intent=understood_intent,
        preferred_types=", ".join(preferred_types) if preferred_types else "any",
        stills_json=json.dumps(stills_for_ranking, indent=2),
        limit=limit
    )

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=rerank_prompt,
        step="sommelier",
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

    logger.info(f"Sommelier: AI ranked {len(ranked_ids)} stills out of {len(stills_for_ranking)} keyword matches")

    # Fallback: If AI reranking is too strict (returned <3 results from many matches),
    # include keyword-matched stills with a default score
    if len(ranked_ids) < 3 and len(stills_for_ranking) > 3:
        logger.info(f"Sommelier: Reranking too strict, adding fallback keyword matches")
        for still in stills_for_ranking[:limit]:
            if still["id"] not in ranked_ids:
                ranked_ids[still["id"]] = {
                    "id": still["id"],
                    "relevance_score": 2,
                    "why_relevant": "Matched your search keywords"
                }

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
