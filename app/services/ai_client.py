"""Unified AI client for all pipeline steps using OpenRouter."""
import os
import base64
import json
import aiofiles
from pathlib import Path
from typing import Tuple, Optional, Any
import openai

from app.config import get_settings
from app.services import settings_manager
from app.utils.retry import retry_async

settings = get_settings()


def get_openrouter_client() -> openai.OpenAI:
    """Get OpenRouter client (OpenAI-compatible)."""
    api_key = settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY not configured. "
            "Please set it in your .env file or environment variables."
        )

    return openai.OpenAI(
        api_key=api_key,
        base_url=settings.openrouter_base_url,
    )


def normalize_model_name(model_name: str) -> str:
    """
    Normalize model names to OpenRouter format.

    Examples:
    - "gemini-2.0-flash" -> "google/gemini-2.0-flash"
    - "google/gemini-2.0-flash" -> "google/gemini-2.0-flash" (unchanged)
    - "claude-3.5-sonnet" -> "anthropic/claude-3.5-sonnet"
    """
    if "/" in model_name:
        # Already in provider/model format
        return model_name

    # Map common model prefixes to providers
    if model_name.startswith("gemini"):
        return f"google/{model_name}"
    elif model_name.startswith("claude"):
        return f"anthropic/{model_name}"
    elif model_name.startswith("gpt"):
        return f"openai/{model_name}"
    else:
        # Return as-is for unknown formats
        return model_name


async def call_llm_text(
    prompt: str,
    step: str,
    max_tokens: int = 4096,
    response_format: Optional[str] = None,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[str, int, int, str]:
    """
    Call LLM for text-only prompts via OpenRouter.

    Args:
        prompt: The text prompt to send
        step: Pipeline step name (transcription, atomization, drafting, editing, factcheck)
        max_tokens: Maximum tokens for response
        response_format: Optional format hint ("json" for JSON responses)
        job_id: Optional job ID for logging
        user_id: Optional user ID for logging

    Returns:
        (response_text, input_tokens, output_tokens, model_used)
    """
    # Get model from settings
    model_name = settings_manager.get_model_for_step(step)
    model = normalize_model_name(model_name)

    client = get_openrouter_client()

    messages = [{"role": "user", "content": prompt}]

    async def do_call():
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "extra_headers": {
                "HTTP-Referer": "https://contentmultiplier.com",
                "X-Title": "ContentMultiplier",
            }
        }

        # Add JSON response format if requested
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        return client.chat.completions.create(**kwargs)

    response = await retry_async(
        do_call,
        max_retries=3,
        base_delay=2.0,
        job_id=job_id,
        user_id=user_id,
        context=f"openrouter_{step}",
    )

    response_text = response.choices[0].message.content
    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0

    return response_text, input_tokens, output_tokens, model


async def call_llm_with_file(
    file_path: Path,
    prompt: str,
    step: str = "transcription",
    max_tokens: int = 8192,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[str, int, int, str]:
    """
    Call LLM with a file (PDF, image, etc.) via OpenRouter.

    Uses OpenRouter's multimodal file input format.

    Args:
        file_path: Path to the file to process
        prompt: The text prompt/instructions
        step: Pipeline step name for model selection
        max_tokens: Maximum tokens for response
        job_id: Optional job ID for logging
        user_id: Optional user ID for logging

    Returns:
        (response_text, input_tokens, output_tokens, model_used)
    """
    # Get model from settings
    model_name = settings_manager.get_model_for_step(step)
    model = normalize_model_name(model_name)

    client = get_openrouter_client()

    # Determine MIME type
    ext = file_path.suffix.lower()
    mime_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/x-m4a",
    }
    mime_type = mime_types.get(ext, "application/octet-stream")

    # Read and encode file as base64
    async with aiofiles.open(file_path, "rb") as f:
        file_content = await f.read()

    file_base64 = base64.b64encode(file_content).decode("utf-8")
    file_data_url = f"data:{mime_type};base64,{file_base64}"

    # Build message with file content using OpenRouter's format
    # For PDFs, use the file content type
    if ext == ".pdf":
        content = [
            {"type": "text", "text": prompt},
            {
                "type": "file",
                "file": {
                    "filename": file_path.name,
                    "file_data": file_data_url
                }
            }
        ]
    else:
        # For images, use image_url format
        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": file_data_url
                }
            }
        ]

    messages = [{"role": "user", "content": content}]

    async def do_call():
        return client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            extra_headers={
                "HTTP-Referer": "https://contentmultiplier.com",
                "X-Title": "ContentMultiplier",
            }
        )

    response = await retry_async(
        do_call,
        max_retries=3,
        base_delay=2.0,
        job_id=job_id,
        user_id=user_id,
        context=f"openrouter_{step}_file",
    )

    response_text = response.choices[0].message.content
    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0

    return response_text, input_tokens, output_tokens, model


def calculate_openrouter_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for OpenRouter API usage.

    OpenRouter pricing varies by model. This provides estimates.
    For accurate billing, check your OpenRouter dashboard.
    """
    # Approximate pricing per 1M tokens (input/output)
    # These are estimates - actual pricing from OpenRouter may vary
    model_costs = {
        # Google models
        "google/gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "google/gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
        "google/gemini-2.5-flash": {"input": 0.15, "output": 0.60},
        "google/gemini-3-flash-preview": {"input": 0.15, "output": 0.60},
        # Anthropic models
        "anthropic/claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
        "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
        # Default fallback
        "default": {"input": 0.50, "output": 2.00},
    }

    costs = model_costs.get(model, model_costs["default"])
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]

    return input_cost + output_cost
