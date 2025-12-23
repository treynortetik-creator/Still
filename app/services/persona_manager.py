"""Persona management service."""
import json
import aiofiles
from pathlib import Path
from typing import Optional

from app.config import get_settings

settings = get_settings()

# Cache for personas
_personas_cache: Optional[dict] = None


async def load_personas() -> dict:
    """Load personas from the JSON file."""
    global _personas_cache

    if _personas_cache is not None:
        return _personas_cache

    personas_file = settings.data_dir / "personas.json"

    if not personas_file.exists():
        # Return default personas if file doesn't exist
        _personas_cache = get_default_personas()
        # Save to file for future edits
        await save_personas(_personas_cache)
        return _personas_cache

    async with aiofiles.open(personas_file, "r") as f:
        content = await f.read()
        _personas_cache = json.loads(content)

    return _personas_cache


async def save_personas(personas_data: dict):
    """Save personas to the JSON file."""
    global _personas_cache

    personas_file = settings.data_dir / "personas.json"
    personas_file.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(personas_file, "w") as f:
        await f.write(json.dumps(personas_data, indent=2))

    _personas_cache = personas_data


async def get_persona(persona_id: str) -> Optional[dict]:
    """Get a specific persona by ID."""
    personas = await load_personas()

    for persona in personas.get("personas", []):
        if persona.get("id") == persona_id:
            return persona

    return None


async def list_personas() -> list[dict]:
    """List all available personas."""
    personas = await load_personas()
    return personas.get("personas", [])


def get_default_personas() -> dict:
    """Return the default hardcoded personas for MVP."""
    return {
        "personas": [
            {
                "id": "ceo_longterm_care",
                "title": "CEO of Long-Term Care Facility",
                "company_size": "1000+ beds",
                "pain_points": [
                    "Staffing shortages",
                    "Resident retention",
                    "Regulatory compliance",
                    "Profitability pressure"
                ],
                "language_level": "Executive - high-level ROI focus",
                "priorities": [
                    "Bottom line impact",
                    "Competitive advantage",
                    "Operational efficiency"
                ],
                "content_preferences": {
                    "length": "Short - time-constrained",
                    "data_density": "High - wants metrics immediately",
                    "tone": "Confident and outcome-focused"
                }
            },
            {
                "id": "don_memory_care",
                "title": "Director of Nursing (Memory Care)",
                "company_size": "100-300 beds",
                "pain_points": [
                    "Resident safety",
                    "Staff training and retention",
                    "Family communication",
                    "Care quality documentation"
                ],
                "language_level": "Professional - clinical but accessible",
                "priorities": [
                    "Resident outcomes",
                    "Staff empowerment",
                    "Family trust"
                ],
                "content_preferences": {
                    "length": "Medium - wants actionable detail",
                    "data_density": "Moderate - clinical evidence appreciated",
                    "tone": "Empathetic and supportive"
                }
            },
            {
                "id": "marketing_director",
                "title": "Marketing Director (Senior Living)",
                "company_size": "500+ beds across multiple communities",
                "pain_points": [
                    "Lead generation",
                    "Brand differentiation",
                    "Content production at scale",
                    "ROI measurement"
                ],
                "language_level": "Professional - marketing-savvy",
                "priorities": [
                    "Conversion rates",
                    "Content velocity",
                    "Brand consistency"
                ],
                "content_preferences": {
                    "length": "Long - wants comprehensive insight",
                    "data_density": "Moderate - case studies over raw stats",
                    "tone": "Creative but strategic"
                }
            }
        ]
    }


def invalidate_cache():
    """Invalidate the personas cache to force reload."""
    global _personas_cache
    _personas_cache = None
