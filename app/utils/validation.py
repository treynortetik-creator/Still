"""Input validation utilities."""
import json
import re
from typing import Optional, Any
from fastapi import HTTPException

from app.config import get_settings


def validate_text_length(
    value: Optional[str],
    field_name: str,
    max_length: int,
    required: bool = False
) -> Optional[str]:
    """
    Validate text field length.

    Args:
        value: The text value to validate
        field_name: Name of the field for error messages
        max_length: Maximum allowed character length
        required: Whether the field is required

    Returns:
        The validated value (stripped of leading/trailing whitespace)

    Raises:
        HTTPException: If validation fails
    """
    if value is None or value == "":
        if required:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} is required"
            )
        return None

    # Strip whitespace
    value = value.strip()

    if len(value) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} exceeds maximum length of {max_length} characters"
        )

    return value


def validate_json_field(
    value: str,
    field_name: str,
    expected_type: type = None
) -> Any:
    """
    Validate and parse a JSON field.

    Args:
        value: The JSON string to parse
        field_name: Name of the field for error messages
        expected_type: Expected type (list, dict) after parsing

    Returns:
        The parsed JSON value

    Raises:
        HTTPException: If validation fails
    """
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON in {field_name}: {str(e)}"
        )

    if expected_type and not isinstance(parsed, expected_type):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be a {expected_type.__name__}"
        )

    return parsed


def validate_asset_types(asset_types: list) -> list:
    """
    Validate asset types list.

    Args:
        asset_types: List of asset type strings

    Returns:
        The validated list

    Raises:
        HTTPException: If validation fails
    """
    valid_types = {"linkedin", "blog", "email", "email_sequence", "twitter", "thread"}

    if not isinstance(asset_types, list):
        raise HTTPException(
            status_code=400,
            detail="asset_types must be a list"
        )

    if len(asset_types) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one asset type is required"
        )

    if len(asset_types) > 10:
        raise HTTPException(
            status_code=400,
            detail="Too many asset types (maximum 10)"
        )

    for asset_type in asset_types:
        if not isinstance(asset_type, str):
            raise HTTPException(
                status_code=400,
                detail="Each asset type must be a string"
            )
        if asset_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid asset type: {asset_type}. Valid types: {', '.join(valid_types)}"
            )

    return asset_types


def validate_asset_quantities(quantities: dict, asset_types: list) -> dict:
    """
    Validate asset quantities dictionary.

    Args:
        quantities: Dictionary of asset type to quantity
        asset_types: List of requested asset types

    Returns:
        The validated dictionary with defaults filled in

    Raises:
        HTTPException: If validation fails
    """
    if not isinstance(quantities, dict):
        raise HTTPException(
            status_code=400,
            detail="asset_quantities must be a dictionary"
        )

    # Default quantities
    defaults = {
        "linkedin": 3,
        "blog": 1,
        "email": 1,
        "email_sequence": 5,
        "twitter": 3,
        "thread": 1,
    }

    result = {}
    for asset_type in asset_types:
        if asset_type in quantities:
            qty = quantities[asset_type]
            if not isinstance(qty, int) or qty < 1:
                raise HTTPException(
                    status_code=400,
                    detail=f"Quantity for {asset_type} must be a positive integer"
                )
            if qty > 20:
                raise HTTPException(
                    status_code=400,
                    detail=f"Quantity for {asset_type} cannot exceed 20"
                )
            result[asset_type] = qty
        else:
            result[asset_type] = defaults.get(asset_type, 1)

    return result


def validate_processing_mode(mode: str) -> str:
    """
    Validate processing mode.

    Args:
        mode: The processing mode string

    Returns:
        The validated mode

    Raises:
        HTTPException: If validation fails
    """
    valid_modes = {"autopilot", "guided", "quick_distill"}

    if mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid processing mode: {mode}. Valid modes: {', '.join(valid_modes)}"
        )

    return mode


def validate_webhook_url(url: str) -> str:
    """
    Validate webhook URL.

    Args:
        url: The webhook URL

    Returns:
        The validated URL

    Raises:
        HTTPException: If validation fails
    """
    if not url:
        raise HTTPException(
            status_code=400,
            detail="Webhook URL is required"
        )

    if not url.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Webhook URL must use HTTPS"
        )

    # Basic URL format validation
    url_pattern = re.compile(
        r'^https://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )

    if not url_pattern.match(url):
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook URL format"
        )

    if len(url) > 2048:
        raise HTTPException(
            status_code=400,
            detail="Webhook URL exceeds maximum length of 2048 characters"
        )

    return url


def validate_trigger_events(events: list) -> list:
    """
    Validate webhook trigger events.

    Args:
        events: List of trigger event strings

    Returns:
        The validated list

    Raises:
        HTTPException: If validation fails
    """
    valid_events = {"job_completed", "content_generated", "batch_finished"}

    if not isinstance(events, list):
        raise HTTPException(
            status_code=400,
            detail="trigger_events must be a list"
        )

    if len(events) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one trigger event is required"
        )

    for event in events:
        if event not in valid_events:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid trigger event: {event}. Valid events: {', '.join(valid_events)}"
            )

    return list(set(events))  # Remove duplicates
