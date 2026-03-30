"""Unified AI client for all pipeline steps using OpenRouter."""
import asyncio
import os
import base64
import json
import aiofiles
import logging
from pathlib import Path
from typing import Tuple, Optional, Any
import openai
from openai import AsyncOpenAI

from app.config import get_settings
from app.services import settings_manager
from app.utils.retry import retry_async

settings = get_settings()
logger = logging.getLogger(__name__)


def _get_openrouter_api_key() -> str:
    """Get the OpenRouter API key from settings or env."""
    api_key = settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY not configured. "
            "Please set it in your .env file or environment variables."
        )
    return api_key


def get_openrouter_client() -> openai.OpenAI:
    """Get OpenRouter client (OpenAI-compatible)."""
    return openai.OpenAI(
        api_key=_get_openrouter_api_key(),
        base_url=settings.openrouter_base_url,
    )


def get_async_openrouter_client() -> AsyncOpenAI:
    """Get async OpenRouter client (OpenAI-compatible) for non-blocking streaming."""
    return AsyncOpenAI(
        api_key=_get_openrouter_api_key(),
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
    max_tokens: int = None,  # No limit by default - use model's maximum
    response_format: Optional[str] = None,
    job_id: str = None,
    user_id: int = None,
    enable_streaming: bool = True,
) -> Tuple[str, int, int, str]:
    """
    Call LLM for text-only prompts via OpenRouter.

    If a stream manager exists for the job_id and enable_streaming is True,
    this will stream output chunks to connected clients while still returning
    the full response.

    Args:
        prompt: The text prompt to send
        step: Pipeline step name (transcription, atomization, drafting, editing, factcheck)
        max_tokens: Maximum tokens for response (None = no limit, use model's maximum)
        response_format: Optional format hint ("json" for JSON responses)
        job_id: Optional job ID for logging and streaming
        user_id: Optional user ID for logging
        enable_streaming: Whether to stream to connected clients (default True)

    Returns:
        (response_text, input_tokens, output_tokens, model_used)
    """
    from app.services.stream_manager import get_stream

    # Check if we should stream
    stream_manager = None
    if enable_streaming and job_id:
        stream_manager = get_stream(job_id)

    # Get model from settings
    model_name = settings_manager.get_model_for_step(step)
    model = normalize_model_name(model_name)

    messages = [{"role": "user", "content": prompt}]

    # Only stream for the drafting step — other steps (editing, factcheck,
    # scoring, etc.) return structured JSON where streaming is useless.
    use_streaming = stream_manager and step == "drafting"

    if use_streaming:
        kwargs = {
            "model": model,
            "messages": messages,
            "stream": True,
            "extra_headers": {
                "HTTP-Referer": "https://contentmultiplier.com",
                "X-Title": "ContentMultiplier",
            }
        }

        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            async_client = get_async_openrouter_client()
            stream = await async_client.chat.completions.create(**kwargs)

            # Collect chunks with native async iteration (no event loop blocking)
            full_response = []
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_response.append(text)
                    await stream_manager.emit_chunk(text)

            response_text = "".join(full_response)
            # Token counts not available in streaming mode
            # Estimate: ~4 chars per token for English
            input_tokens = len(prompt) // 4
            output_tokens = len(response_text) // 4

            return response_text, input_tokens, output_tokens, model

        except Exception as e:
            logger.warning(f"Streaming failed, falling back to non-streaming: {e}")
            # Fall through to non-streaming call with retry logic

    # Non-streaming call (with retry logic) - uses async client
    client = get_async_openrouter_client()

    async def do_call():
        kwargs = {
            "model": model,
            "messages": messages,
            "extra_headers": {
                "HTTP-Referer": "https://contentmultiplier.com",
                "X-Title": "ContentMultiplier",
            }
        }

        # Only set max_tokens if explicitly provided (no limit by default)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        # Add JSON response format if requested
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        return await client.chat.completions.create(**kwargs)

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
    max_tokens: int = None,  # No limit by default - use model's maximum
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
        max_tokens: Maximum tokens for response (None = no limit, use model's maximum)
        job_id: Optional job ID for logging
        user_id: Optional user ID for logging

    Returns:
        (response_text, input_tokens, output_tokens, model_used)
    """
    # Get model from settings
    model_name = settings_manager.get_model_for_step(step)
    model = normalize_model_name(model_name)

    client = get_async_openrouter_client()

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
        kwargs = {
            "model": model,
            "messages": messages,
            "extra_headers": {
                "HTTP-Referer": "https://contentmultiplier.com",
                "X-Title": "ContentMultiplier",
            }
        }

        # Only set max_tokens if explicitly provided (no limit by default)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        return await client.chat.completions.create(**kwargs)

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
    """Cost tracking disabled. Returns 0.0 for API compatibility."""
    return 0.0
