"""Settings management for storing API keys and model configurations."""
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


SETTINGS_FILE = Path(__file__).parent.parent.parent / "data" / "settings.json"


def _ensure_settings_file():
    """Ensure settings file exists with defaults."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_FILE.exists():
        default_settings = {
            "use_openrouter": True,
            "models": {
                "transcription": "google/gemini-2.5-flash",
                "distillation": "google/gemini-2.5-flash",
                "drafting": "google/gemini-3-flash-preview",
                "editing": "google/gemini-2.5-flash",
                "factcheck": "google/gemini-2.5-flash",
                "workshop_ai_edit": "google/gemini-2.5-flash-preview"
            }
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(default_settings, f, indent=2)


def get_settings() -> Dict[str, Any]:
    """Get all settings."""
    _ensure_settings_file()
    with open(SETTINGS_FILE) as f:
        return json.load(f)


def save_settings(settings: Dict[str, Any]):
    """Save settings to file."""
    _ensure_settings_file()
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def get_api_key_status() -> Dict[str, bool]:
    """Check which API keys are configured (from environment)."""
    return {
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY"))
    }


def get_model_for_step(step: str) -> str:
    """Get the configured model for a specific pipeline step."""
    settings = get_settings()
    models = settings.get("models", {})

    defaults = {
        "transcription": "google/gemini-2.5-flash",
        "distillation": "google/gemini-2.5-flash",
        "atomization": "google/gemini-2.5-flash",  # Alias for distillation
        "drafting": "google/gemini-3-flash-preview",
        "editing": "google/gemini-2.5-flash",
        "factcheck": "google/gemini-2.5-flash",
        "workshop_ai_edit": "google/gemini-2.5-flash-preview"
    }

    # Handle atomization/distillation aliasing - they're the same step
    if step == "distillation":
        # Try distillation first, then atomization as fallback
        return models.get("distillation", models.get("atomization", defaults.get("distillation", "google/gemini-2.5-flash")))
    elif step == "atomization":
        # Try atomization first, then distillation as fallback
        return models.get("atomization", models.get("distillation", defaults.get("atomization", "google/gemini-2.5-flash")))

    return models.get(step, defaults.get(step, "google/gemini-2.5-flash"))


def is_openrouter_enabled() -> bool:
    """Check if OpenRouter is enabled."""
    settings = get_settings()
    return settings.get("use_openrouter", False)


def set_openrouter_enabled(enabled: bool):
    """Enable or disable OpenRouter."""
    settings = get_settings()
    settings["use_openrouter"] = enabled
    save_settings(settings)


def set_model_config(models: Dict[str, str]):
    """Set model configuration for all steps."""
    settings = get_settings()
    settings["models"] = models
    save_settings(settings)
