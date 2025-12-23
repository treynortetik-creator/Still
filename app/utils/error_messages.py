"""Enhanced error messages with specific, actionable guidance."""
from enum import Enum
from typing import Optional


class ErrorCode(Enum):
    """Error codes for specific error types."""
    # Upload errors
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    CORRUPTED_FILE = "CORRUPTED_FILE"
    EMPTY_FILE = "EMPTY_FILE"

    # Transcription errors
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    AUDIO_TOO_QUIET = "AUDIO_TOO_QUIET"
    AUDIO_TOO_SHORT = "AUDIO_TOO_SHORT"
    LANGUAGE_NOT_DETECTED = "LANGUAGE_NOT_DETECTED"

    # API errors
    API_RATE_LIMIT = "API_RATE_LIMIT"
    API_QUOTA_EXCEEDED = "API_QUOTA_EXCEEDED"
    API_UNAVAILABLE = "API_UNAVAILABLE"
    API_TIMEOUT = "API_TIMEOUT"

    # Processing errors
    CONTENT_TOO_SHORT = "CONTENT_TOO_SHORT"
    CONTENT_TOO_LONG = "CONTENT_TOO_LONG"
    NO_ATOMS_EXTRACTED = "NO_ATOMS_EXTRACTED"
    GENERATION_FAILED = "GENERATION_FAILED"

    # Auth errors
    UNAUTHORIZED = "UNAUTHORIZED"
    CREDITS_EXHAUSTED = "CREDITS_EXHAUSTED"

    # Generic
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# Map error codes to user-friendly messages with actions
ERROR_MESSAGES = {
    ErrorCode.FILE_TOO_LARGE: {
        "title": "File Too Large",
        "message": "The uploaded file exceeds the maximum size limit of 100MB.",
        "action": "Please compress your file or split it into smaller segments before uploading.",
        "retry": False,
    },
    ErrorCode.UNSUPPORTED_FORMAT: {
        "title": "Unsupported File Format",
        "message": "This file type is not supported.",
        "action": "Please upload a video (MP4, MOV, WebM), audio (MP3, WAV, M4A), PDF, or text file.",
        "retry": False,
    },
    ErrorCode.CORRUPTED_FILE: {
        "title": "File Could Not Be Read",
        "message": "The file appears to be corrupted or incomplete.",
        "action": "Please re-export the file from its source application and try uploading again.",
        "retry": False,
    },
    ErrorCode.EMPTY_FILE: {
        "title": "Empty File",
        "message": "The uploaded file contains no content.",
        "action": "Please check the file and ensure it has content before uploading.",
        "retry": False,
    },
    ErrorCode.TRANSCRIPTION_FAILED: {
        "title": "Transcription Failed",
        "message": "We couldn't transcribe the audio in your file.",
        "action": "Check that the audio is clear and in a supported language (English). Try re-uploading or paste the text directly.",
        "retry": True,
    },
    ErrorCode.AUDIO_TOO_QUIET: {
        "title": "Audio Too Quiet",
        "message": "The audio level in your file is too low to transcribe accurately.",
        "action": "Try amplifying the audio in an editing tool, or paste the transcript directly.",
        "retry": False,
    },
    ErrorCode.AUDIO_TOO_SHORT: {
        "title": "Audio Too Short",
        "message": "The audio content is too short to process meaningfully.",
        "action": "Please upload content that is at least 30 seconds long.",
        "retry": False,
    },
    ErrorCode.LANGUAGE_NOT_DETECTED: {
        "title": "Language Not Detected",
        "message": "We couldn't detect a supported language in your content.",
        "action": "Currently, only English content is fully supported. Please upload English content or contact support for other languages.",
        "retry": False,
    },
    ErrorCode.API_RATE_LIMIT: {
        "title": "Processing Limit Reached",
        "message": "You've reached the temporary processing limit.",
        "action": "Please wait a few minutes before trying again. Upgrade your plan for higher limits.",
        "retry": True,
    },
    ErrorCode.API_QUOTA_EXCEEDED: {
        "title": "Monthly Quota Exceeded",
        "message": "You've used all your processing credits for this billing period.",
        "action": "Upgrade your subscription or wait until your credits reset at the start of the next billing cycle.",
        "retry": False,
    },
    ErrorCode.API_UNAVAILABLE: {
        "title": "Service Temporarily Unavailable",
        "message": "Our AI service is currently experiencing issues.",
        "action": "Please try again in a few minutes. If the problem persists, check our status page.",
        "retry": True,
    },
    ErrorCode.API_TIMEOUT: {
        "title": "Processing Timeout",
        "message": "The processing took too long and timed out.",
        "action": "This usually happens with very long content. Try splitting it into smaller parts or retry shortly.",
        "retry": True,
    },
    ErrorCode.CONTENT_TOO_SHORT: {
        "title": "Content Too Short",
        "message": "The content doesn't have enough material to generate meaningful outputs.",
        "action": "Please provide at least a few paragraphs of content (minimum 500 characters).",
        "retry": False,
    },
    ErrorCode.CONTENT_TOO_LONG: {
        "title": "Content Too Long",
        "message": "The content exceeds our processing limit.",
        "action": "Please split your content into multiple uploads, each under 50,000 words.",
        "retry": False,
    },
    ErrorCode.NO_ATOMS_EXTRACTED: {
        "title": "No Content Atoms Found",
        "message": "We couldn't extract meaningful content atoms from your input.",
        "action": "Ensure your content contains specific insights, data, stories, or actionable information. Generic content may not yield useful atoms.",
        "retry": False,
    },
    ErrorCode.GENERATION_FAILED: {
        "title": "Content Generation Failed",
        "message": "We couldn't generate content from the extracted atoms.",
        "action": "This usually happens when the source content lacks clear themes. Try adding more specific, topical content.",
        "retry": True,
    },
    ErrorCode.UNAUTHORIZED: {
        "title": "Session Expired",
        "message": "Your session has expired.",
        "action": "Please log in again to continue.",
        "retry": False,
    },
    ErrorCode.CREDITS_EXHAUSTED: {
        "title": "Credits Exhausted",
        "message": "You've used all your available credits.",
        "action": "Purchase additional credits or upgrade your subscription to continue.",
        "retry": False,
    },
    ErrorCode.UNKNOWN_ERROR: {
        "title": "Something Went Wrong",
        "message": "An unexpected error occurred while processing your request.",
        "action": "Please try again. If the problem persists, contact support with error reference: {reference}",
        "retry": True,
    },
}


def get_error_message(error_code: ErrorCode, reference: Optional[str] = None) -> dict:
    """
    Get user-friendly error message for an error code.

    Returns dict with title, message, action, and retry flag.
    """
    error_info = ERROR_MESSAGES.get(error_code, ERROR_MESSAGES[ErrorCode.UNKNOWN_ERROR])

    result = {
        "error_code": error_code.value,
        "title": error_info["title"],
        "message": error_info["message"],
        "action": error_info["action"],
        "can_retry": error_info["retry"],
    }

    if reference and "{reference}" in result["action"]:
        result["action"] = result["action"].replace("{reference}", reference)

    return result


def detect_error_type(exception: Exception, context: str = "") -> ErrorCode:
    """
    Detect error type from exception and context.

    Returns appropriate ErrorCode based on exception type and message.
    """
    error_str = str(exception).lower()
    exc_type = type(exception).__name__

    # Rate limit errors
    if "rate" in error_str and "limit" in error_str:
        return ErrorCode.API_RATE_LIMIT
    if "quota" in error_str or "exceeded" in error_str:
        return ErrorCode.API_QUOTA_EXCEEDED

    # Timeout errors
    if "timeout" in error_str or "timed out" in error_str:
        return ErrorCode.API_TIMEOUT

    # Connection/availability errors
    if any(term in error_str for term in ["connection", "unavailable", "503", "502", "500"]):
        return ErrorCode.API_UNAVAILABLE

    # File errors
    if "file not found" in error_str or "no such file" in error_str:
        return ErrorCode.CORRUPTED_FILE
    if "too large" in error_str or "size" in error_str:
        return ErrorCode.FILE_TOO_LARGE

    # Transcription context
    if context == "transcription":
        if "audio" in error_str and "short" in error_str:
            return ErrorCode.AUDIO_TOO_SHORT
        if "language" in error_str:
            return ErrorCode.LANGUAGE_NOT_DETECTED
        return ErrorCode.TRANSCRIPTION_FAILED

    # Atomization context
    if context == "atomization":
        if "no atoms" in error_str or "empty" in error_str:
            return ErrorCode.NO_ATOMS_EXTRACTED
        if "short" in error_str:
            return ErrorCode.CONTENT_TOO_SHORT

    # Generation context
    if context == "generation" or context == "drafting":
        return ErrorCode.GENERATION_FAILED

    # Auth errors
    if "unauthorized" in error_str or "401" in error_str:
        return ErrorCode.UNAUTHORIZED

    return ErrorCode.UNKNOWN_ERROR


def format_pipeline_error(exception: Exception, step: str, job_id: str) -> str:
    """
    Format a pipeline error into a user-friendly message string.

    Returns a formatted error message suitable for storing in the database.
    """
    error_code = detect_error_type(exception, step)
    error_info = get_error_message(error_code, job_id[:8])

    return f"{error_info['title']}: {error_info['message']} {error_info['action']}"
