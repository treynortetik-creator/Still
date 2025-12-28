"""Robust JSON parsing utilities for LLM outputs."""
import json
import re
import logging

logger = logging.getLogger(__name__)


def repair_json_string(s: str) -> str:
    """
    Attempt to repair common JSON issues from LLM outputs.

    Fixes:
    - Unescaped newlines inside strings
    - Unescaped quotes inside strings (best effort)
    - Control characters
    """
    # Remove any markdown code fences
    s = re.sub(r'^```json\s*', '', s, flags=re.MULTILINE)
    s = re.sub(r'^```\s*$', '', s, flags=re.MULTILINE)
    s = s.strip()

    # Replace literal tabs and other control characters (except \n which we handle specially)
    # First, protect already-escaped sequences
    s = s.replace('\\n', '\x00NEWLINE\x00')
    s = s.replace('\\t', '\x00TAB\x00')
    s = s.replace('\\r', '\x00CR\x00')
    s = s.replace('\\"', '\x00QUOTE\x00')

    # Now handle unescaped control characters
    # Replace actual tabs with escaped tabs
    s = s.replace('\t', '\\t')
    # Replace actual carriage returns
    s = s.replace('\r', '')

    # Handle unescaped newlines inside JSON strings
    # This is tricky - we need to find newlines that are inside string values
    # Strategy: process character by character tracking string state
    result = []
    in_string = False
    i = 0
    while i < len(s):
        char = s[i]

        if char == '"' and (i == 0 or s[i-1] != '\\'):
            in_string = not in_string
            result.append(char)
        elif char == '\n':
            if in_string:
                # Newline inside a string - escape it
                result.append('\\n')
            else:
                # Newline outside string is fine (JSON formatting)
                result.append(char)
        else:
            result.append(char)
        i += 1

    s = ''.join(result)

    # Restore protected sequences
    s = s.replace('\x00NEWLINE\x00', '\\n')
    s = s.replace('\x00TAB\x00', '\\t')
    s = s.replace('\x00CR\x00', '\\r')
    s = s.replace('\x00QUOTE\x00', '\\"')

    return s


def extract_json_object(text: str) -> str:
    """
    Extract a JSON object from text using bracket matching.

    Handles cases where LLM includes extra text before/after JSON.
    """
    # Find the first {
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in text")

    # Use bracket counting to find matching }
    depth = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:i+1]

    # If we didn't find a matching }, try the last }
    end = text.rfind('}')
    if end > start:
        return text[start:end+1]

    raise ValueError("Could not find complete JSON object")


def parse_llm_json(text: str, context: str = "LLM response") -> dict:
    """
    Parse JSON from LLM output with multiple fallback strategies.

    Args:
        text: The raw LLM response text
        context: Description for error messages

    Returns:
        Parsed JSON as a dictionary

    Raises:
        ValueError: If JSON cannot be parsed after all attempts
    """
    if not text or not text.strip():
        raise ValueError(f"Empty {context}")

    original_text = text
    errors = []

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        errors.append(f"Direct parse: {e}")

    # Strategy 2: Extract JSON object and parse
    try:
        extracted = extract_json_object(text)
        return json.loads(extracted)
    except (json.JSONDecodeError, ValueError) as e:
        errors.append(f"Extract and parse: {e}")

    # Strategy 3: Repair and parse
    try:
        repaired = repair_json_string(text)
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        errors.append(f"Repair and parse: {e}")

    # Strategy 4: Extract then repair
    try:
        extracted = extract_json_object(text)
        repaired = repair_json_string(extracted)
        return json.loads(repaired)
    except (json.JSONDecodeError, ValueError) as e:
        errors.append(f"Extract, repair and parse: {e}")

    # All strategies failed
    # Log the problematic text for debugging (truncated)
    preview = original_text[:500] + "..." if len(original_text) > 500 else original_text
    logger.error(f"Failed to parse {context}. Attempts: {errors}. Preview: {preview}")

    raise ValueError(
        f"Failed to parse {context} as JSON after multiple attempts. "
        f"Last error: {errors[-1]}"
    )
