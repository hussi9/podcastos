"""
Input Validation and Security Utilities for PodcastOS.

Provides secure input validation, sanitization, and path handling.
"""

import re
import os
import logging
from pathlib import Path
from typing import Optional, Union, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ============== Path Security ==============

class PathTraversalError(Exception):
    """Raised when a path traversal attack is detected."""
    pass


def validate_safe_filename(filename: str, allow_uuid: bool = True) -> str:
    """
    Validate and sanitize a filename to prevent path traversal attacks.
    
    Args:
        filename: The filename to validate
        allow_uuid: Whether to allow UUID-style filenames with hyphens
        
    Returns:
        The sanitized filename
        
    Raises:
        PathTraversalError: If the filename is unsafe
        ValueError: If the filename is empty or invalid
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # Remove any path components
    filename = os.path.basename(filename)
    
    # Check for path traversal attempts
    if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
        logger.warning(f"Path traversal attempt detected: {filename}")
        raise PathTraversalError(f"Invalid filename: {filename}")
    
    # Define allowed pattern
    if allow_uuid:
        # Allow alphanumeric, hyphens, underscores (UUID-compatible)
        pattern = r'^[\w\-]+$'
    else:
        # Stricter: only alphanumeric and underscores
        pattern = r'^\w+$'
    
    # Remove file extension for validation
    name_without_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
    
    if not re.match(pattern, name_without_ext):
        logger.warning(f"Invalid filename format: {filename}")
        raise ValueError(f"Invalid filename format: {filename}")
    
    return filename


def validate_script_id(script_id: str) -> str:
    """
    Validate a script ID to prevent path traversal.
    
    Script IDs should match pattern: dd-YYYYMMDD or dd-YYYYMMDD-N
    
    Args:
        script_id: The script ID to validate
        
    Returns:
        The validated script ID
        
    Raises:
        ValueError: If the script ID is invalid
    """
    if not script_id:
        raise ValueError("Script ID cannot be empty")
    
    # Script IDs should match: dd-YYYYMMDD or dd-YYYYMMDD-N or job-XXXXXXXX
    patterns = [
        r'^dd-\d{8}(-\d+)?$',      # dd-20241227 or dd-20241227-2
        r'^job-[a-f0-9]{8}$',       # job-a1b2c3d4
        r'^[\w\-]{1,50}$',          # Generic safe ID (fallback)
    ]
    
    for pattern in patterns:
        if re.match(pattern, script_id):
            return script_id
    
    logger.warning(f"Invalid script ID format: {script_id}")
    raise ValueError(f"Invalid script ID format: {script_id}")


def safe_path_join(base_dir: Union[str, Path], *parts: str) -> Path:
    """
    Safely join path components, preventing traversal outside base_dir.
    
    Args:
        base_dir: The base directory (must be absolute)
        *parts: Path components to join
        
    Returns:
        The joined path
        
    Raises:
        PathTraversalError: If the result would be outside base_dir
    """
    base = Path(base_dir).resolve()
    
    # Validate each part
    for part in parts:
        if '..' in part or part.startswith('/') or part.startswith('\\'):
            raise PathTraversalError(f"Invalid path component: {part}")
    
    # Join and resolve
    result = base.joinpath(*parts).resolve()
    
    # Verify result is under base
    try:
        result.relative_to(base)
    except ValueError:
        logger.warning(f"Path traversal attempt: {result} not under {base}")
        raise PathTraversalError(f"Path traversal detected: {result}")
    
    return result


# ============== Input Validation ==============

def safe_int(value, default: int = 0, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """
    Safely convert a value to integer with bounds checking.
    
    Args:
        value: The value to convert
        default: Default value if conversion fails
        min_val: Minimum allowed value (optional)
        max_val: Maximum allowed value (optional)
        
    Returns:
        The converted integer, bounded if limits specified
    """
    try:
        result = int(value) if value is not None else default
    except (ValueError, TypeError):
        result = default
    
    if min_val is not None:
        result = max(min_val, result)
    if max_val is not None:
        result = min(max_val, result)
    
    return result


def safe_float(value, default: float = 0.0, min_val: Optional[float] = None, max_val: Optional[float] = None) -> float:
    """
    Safely convert a value to float with bounds checking.
    """
    try:
        result = float(value) if value is not None else default
    except (ValueError, TypeError):
        result = default
    
    if min_val is not None:
        result = max(min_val, result)
    if max_val is not None:
        result = min(max_val, result)
    
    return result


def validate_string(
    value: Optional[str],
    max_length: int = 255,
    min_length: int = 0,
    default: str = '',
    strip: bool = True,
    allow_empty: bool = True
) -> str:
    """
    Validate and sanitize string input.
    
    Args:
        value: The string to validate
        max_length: Maximum allowed length
        min_length: Minimum required length
        default: Default value if validation fails
        strip: Whether to strip whitespace
        allow_empty: Whether empty strings are allowed
        
    Returns:
        The validated string
    """
    if value is None:
        return default
    
    value = str(value)
    
    if strip:
        value = value.strip()
    
    if not allow_empty and not value:
        return default
    
    if len(value) < min_length:
        return default
    
    if len(value) > max_length:
        value = value[:max_length]
    
    return value


def validate_url(url: str, require_https: bool = False, allowed_schemes: Optional[List[str]] = None) -> bool:
    """
    Validate a URL format.
    
    Args:
        url: The URL to validate
        require_https: Whether to require HTTPS
        allowed_schemes: List of allowed schemes (default: http, https)
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
    
    try:
        result = urlparse(url)
        
        # Check scheme
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        if result.scheme not in allowed_schemes:
            return False
        
        if require_https and result.scheme != 'https':
            return False
        
        # Must have netloc (domain)
        if not result.netloc:
            return False
        
        return True
        
    except Exception:
        return False


def validate_email(email: str) -> bool:
    """
    Basic email format validation.
    """
    if not email:
        return False
    
    # Basic pattern - not exhaustive but catches most issues
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_job_id(job_id: str) -> str:
    """
    Validate a job ID format.
    
    Job IDs should match: job-XXXXXXXX (8 hex chars)
    """
    if not job_id:
        raise ValueError("Job ID cannot be empty")
    
    if not re.match(r'^job-[a-f0-9]{8}$', job_id):
        raise ValueError(f"Invalid job ID format: {job_id}")
    
    return job_id


# ============== JSON Validation ==============

def validate_json_structure(data: dict, required_keys: List[str]) -> bool:
    """
    Validate that a JSON object has required keys.
    
    Args:
        data: The dictionary to validate
        required_keys: List of required key names
        
    Returns:
        True if all required keys present
    """
    if not isinstance(data, dict):
        return False
    
    return all(key in data for key in required_keys)


def sanitize_json_for_storage(data: dict, max_depth: int = 10, max_string_length: int = 10000) -> dict:
    """
    Sanitize JSON data for safe storage.
    
    - Truncates long strings
    - Limits nesting depth
    - Removes None values
    """
    def _sanitize(obj, depth=0):
        if depth > max_depth:
            return "[MAX DEPTH EXCEEDED]"
        
        if isinstance(obj, dict):
            return {
                k: _sanitize(v, depth + 1)
                for k, v in obj.items()
                if v is not None
            }
        elif isinstance(obj, list):
            return [_sanitize(item, depth + 1) for item in obj[:100]]  # Limit list length
        elif isinstance(obj, str):
            return obj[:max_string_length] if len(obj) > max_string_length else obj
        else:
            return obj
    
    return _sanitize(data)


# ============== Rate Limiting Helpers ==============

class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


def check_rate_limit_key(key: str) -> str:
    """Validate and normalize a rate limit key."""
    # Remove any characters that could cause issues in storage
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', key)[:100]
