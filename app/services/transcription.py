"""Transcription and document extraction service using OpenRouter."""
import aiofiles
from pathlib import Path
from typing import Tuple
from docx import Document

from app.services.ai_client import call_llm_text, call_llm_with_file, calculate_openrouter_cost


def extract_text_from_docx(file_path: Path) -> str:
    """
    Extract text content from a Word document (.docx).

    Args:
        file_path: Path to the .docx file

    Returns:
        Extracted text content with preserved paragraph structure
    """
    doc = Document(file_path)
    paragraphs = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    # Also extract text from tables
    for table in doc.tables:
        for row in table.rows:
            row_text = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    row_text.append(cell_text)
            if row_text:
                paragraphs.append(" | ".join(row_text))

    return "\n\n".join(paragraphs)


async def transcribe_file(
    file_path: Path,
    file_type: str,
    job_id: str = None,
    user_id: int = None,
    magic_words: str = None,
) -> Tuple[str, float]:
    """
    Transcribe audio/video file or extract text from document.

    Args:
        file_path: Path to the file
        file_type: Type of file (audio, video, document)
        job_id: Optional job ID for tracking
        user_id: Optional user ID for tracking
        magic_words: Optional comma-separated list of domain vocabulary
                    (brand names, acronyms, technical terms) to recognize accurately.

    Returns (transcript, cost) tuple.
    """
    ext = file_path.suffix.lower()

    # For plain text files, just read directly (no API cost)
    if ext in [".txt", ".md"]:
        async with aiofiles.open(file_path, "r", errors="ignore") as f:
            content = await f.read()
        return content, 0.0

    # For Word documents, extract text directly (no API cost)
    # Gemini doesn't support .docx files directly
    if ext in [".docx", ".doc"]:
        try:
            content = extract_text_from_docx(file_path)
            if content.strip():
                return content, 0.0
        except Exception as e:
            raise ValueError(f"Failed to extract text from Word document: {e}")

    # Build prompt with optional magic words
    vocabulary_section = ""
    if magic_words and magic_words.strip():
        vocabulary_section = f"""
IMPORTANT VOCABULARY TO RECOGNIZE ACCURATELY:
{magic_words}

These are domain-specific terms, brand names, acronyms, or technical terms.
Make sure to transcribe them correctly as written above.

"""

    prompt = f"""{vocabulary_section}Transcribe this content completely and accurately.

Instructions:
1. Transcribe all spoken words exactly as said
2. Include speaker labels if there are multiple speakers (e.g., "Speaker 1:", "Speaker 2:")
3. Note any significant non-verbal sounds in [brackets] (e.g., [applause], [laughter])
4. For documents/PDFs, extract all readable text content
5. Preserve paragraph breaks where natural
6. If there are timestamps visible, include them

Output the full transcript only, no additional commentary."""

    # Call LLM with file
    response_text, input_tokens, output_tokens, model = await call_llm_with_file(
        file_path=file_path,
        prompt=prompt,
        step="transcription",
        max_tokens=8192,
        job_id=job_id,
        user_id=user_id,
    )

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)
    return response_text, cost


async def cleanup_transcript(
    transcript: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[str, float]:
    """
    Clean up transcript by removing filler words, fixing formatting.

    Returns (cleaned_transcript, cost) tuple.
    """
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

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="transcription",
        max_tokens=8192,
        job_id=job_id,
        user_id=user_id,
    )

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)
    return response_text, cost


async def extract_document_content(
    file_path: Path,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[str, float]:
    """
    Extract text content from documents (PDF, DOCX) with image/graph analysis.

    Unlike transcribe_file, this function:
    - Extracts text directly from documents
    - Analyzes any images, charts, graphs, or visual content
    - Returns content ready for atomization (no cleanup needed)

    Returns (extracted_content, cost) tuple.
    """
    ext = file_path.suffix.lower()

    # For plain text files, just read directly (no API cost)
    if ext in [".txt", ".md"]:
        async with aiofiles.open(file_path, "r", errors="ignore") as f:
            content = await f.read()
        return content, 0.0

    # For Word documents, extract text directly (no API cost for basic extraction)
    # Gemini doesn't support .docx files directly
    if ext in [".docx", ".doc"]:
        try:
            content = extract_text_from_docx(file_path)
            if content.strip():
                return content, 0.0
        except Exception as e:
            # If extraction fails, we'll try sending to AI as fallback
            # but for .docx this will likely fail too
            raise ValueError(f"Failed to extract text from Word document: {e}")

    # Build extraction prompt with image analysis (for PDFs and images)
    prompt = """Extract all content from this document comprehensively.

EXTRACTION INSTRUCTIONS:

1. TEXT CONTENT:
   - Extract all readable text content completely
   - Preserve the logical structure and organization
   - Maintain headings, subheadings, and section breaks
   - Keep bullet points, numbered lists, and formatting cues
   - Preserve any quotes, citations, or references

2. VISUAL CONTENT ANALYSIS (VERY IMPORTANT):
   - For any images, charts, graphs, diagrams, or visual elements:
     * Describe what the visual shows
     * Extract any data points, numbers, or statistics visible
     * Explain the key insights or trends depicted
     * Transcribe any text or labels within the visual
   - Format visual analysis as: [VISUAL: description and analysis]

3. TABLES AND DATA:
   - Extract table contents in a readable format
   - Preserve column relationships and data alignment
   - Note any footnotes or annotations

4. OUTPUT FORMAT:
   - Present the content in a clean, well-organized manner
   - Use clear paragraph breaks
   - Keep the original flow and narrative structure
   - Include visual content analysis inline where the visuals appear

Extract the complete document content now:"""

    # Call LLM with file (for PDFs and images that support multimodal)
    response_text, input_tokens, output_tokens, model = await call_llm_with_file(
        file_path=file_path,
        prompt=prompt,
        step="transcription",
        max_tokens=8192,
        job_id=job_id,
        user_id=user_id,
    )

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)
    return response_text, cost
