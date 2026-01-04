"""File utility functions."""
from pathlib import Path
from typing import Optional


# Allowed file types and extensions
ALLOWED_EXTENSIONS = {
    "video": [".mp4", ".mov", ".avi", ".webm", ".mkv"],
    "audio": [".mp3", ".wav", ".m4a", ".ogg", ".flac"],
    "document": [".pdf", ".txt", ".md", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp"],
}


def get_file_type(filename: str, content_type: Optional[str] = None) -> Optional[str]:
    """
    Determine file type category from filename and optional content type.

    Args:
        filename: The name of the file including extension.
        content_type: Optional MIME type of the file. Currently unused but
                      accepted for backward compatibility with callers that
                      pass it.

    Returns:
        The file type category ('video', 'audio', or 'document') if the
        file extension is recognized, otherwise None.

    Examples:
        >>> get_file_type("video.mp4")
        'video'
        >>> get_file_type("audio.mp3", "audio/mpeg")
        'audio'
        >>> get_file_type("unknown.xyz")
        None
    """
    ext = Path(filename).suffix.lower()

    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return file_type

    return None
