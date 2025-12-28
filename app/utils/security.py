"""Security utility functions."""
import re
import os
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.

    - Removes any directory components (path traversal prevention)
    - Replaces dangerous characters
    - Preserves the file extension
    - Returns a safe filename

    Args:
        filename: The potentially unsafe filename from user input

    Returns:
        A sanitized filename safe for filesystem use
    """
    if not filename:
        return "unnamed_file"

    # Extract just the basename, removing any path components
    # This handles both Unix (../) and Windows (..\) path traversal attempts
    filename = os.path.basename(filename)

    # Also handle cases where basename might still contain problematic chars
    # Remove null bytes and other control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)

    # Replace path separators that might have slipped through
    filename = filename.replace('/', '_').replace('\\', '_')

    # Remove leading/trailing dots and spaces (problematic on some filesystems)
    filename = filename.strip('. ')

    # If filename is now empty or just an extension, provide a default
    if not filename or filename.startswith('.'):
        return "unnamed_file" + filename

    return filename


def is_safe_redirect_url(url: str, allowed_prefixes: list[str] = None) -> bool:
    """
    Check if a redirect URL is safe (internal only).

    Args:
        url: The URL to validate
        allowed_prefixes: List of allowed URL prefixes (defaults to internal paths)

    Returns:
        True if the URL is safe for redirect, False otherwise
    """
    if allowed_prefixes is None:
        allowed_prefixes = ['/admin/', '/']

    # Must be a relative URL (no scheme)
    if '://' in url:
        return False

    # Must not start with // (protocol-relative URL)
    if url.startswith('//'):
        return False

    # Must start with one of the allowed prefixes
    for prefix in allowed_prefixes:
        if url.startswith(prefix):
            return True

    return False
