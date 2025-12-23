"""Transcription service using Gemini."""
import os
import json
import aiofiles
from pathlib import Path
from typing import Optional, Tuple
import google.generativeai as genai

from app.config import get_settings, calculate_cost

settings = get_settings()


def init_gemini():
    """Initialize Gemini API client."""
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured")
    genai.configure(api_key=api_key)


async def transcribe_file(file_path: Path, file_type: str) -> Tuple[str, float]:
    """
    Transcribe audio/video file or extract text from document.

    Returns (transcript, cost) tuple.
    """
    init_gemini()

    file_size = file_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)

    # Read file content
    if file_type == "document":
        # For text files, just read the content
        if file_path.suffix.lower() in [".txt", ".md"]:
            async with aiofiles.open(file_path, "r", errors="ignore") as f:
                transcript = await f.read()
            return transcript, 0.0

    # Prepare file for Gemini
    mime_types = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/x-m4a",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".pdf": "application/pdf",
    }

    ext = file_path.suffix.lower()
    mime_type = mime_types.get(ext, "application/octet-stream")

    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = """Transcribe this content completely and accurately.

Instructions:
1. Transcribe all spoken words exactly as said
2. Include speaker labels if there are multiple speakers (e.g., "Speaker 1:", "Speaker 2:")
3. Note any significant non-verbal sounds in [brackets] (e.g., [applause], [laughter])
4. For documents/PDFs, extract all readable text content
5. Preserve paragraph breaks where natural
6. If there are timestamps visible, include them

Output the full transcript only, no additional commentary."""

    if file_size_mb > 20:
        # Use file upload for large files
        uploaded_file = genai.upload_file(path=str(file_path))
        response = model.generate_content([uploaded_file, prompt])
    else:
        # Read file directly for smaller files
        async with aiofiles.open(file_path, "rb") as f:
            file_content = await f.read()

        response = model.generate_content([
            {"mime_type": mime_type, "data": file_content},
            prompt
        ])

    transcript = response.text

    # Calculate cost
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    cost = calculate_cost("gemini-2.0-flash", input_tokens, output_tokens)

    return transcript, cost


async def cleanup_transcript(transcript: str) -> Tuple[str, float]:
    """
    Clean up transcript by removing filler words, fixing formatting.

    Returns (cleaned_transcript, cost) tuple.
    """
    init_gemini()

    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""Clean up this transcript while preserving all meaningful content.

TRANSCRIPT:
{transcript}

CLEANUP TASKS:
1. Remove filler words (um, uh, like, you know, I mean, basically, actually, sort of, kind of)
2. Remove false starts and repeated words
3. Fix obvious grammatical errors that came from speech-to-text
4. Maintain speaker labels if present
5. Keep all substantive content - do not summarize or remove information
6. Format into clear paragraphs
7. Keep any timestamps or section markers

OUTPUT REQUIREMENTS:
- Return ONLY the cleaned transcript
- Do not add any commentary or notes
- Do not summarize - keep all content
- Maintain the original meaning and flow"""

    response = model.generate_content(prompt)

    cleaned = response.text

    # Calculate cost
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    cost = calculate_cost("gemini-2.0-flash", input_tokens, output_tokens)

    return cleaned, cost
