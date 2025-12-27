"""
Unit tests for input validation utilities.
"""

import pytest
from pathlib import Path


class TestSafeFilename:
    """Tests for validate_safe_filename function."""

    def test_valid_filename(self):
        """Test valid filenames pass validation."""
        from src.utils.validation import validate_safe_filename

        assert validate_safe_filename("test.txt") == "test.txt"
        assert validate_safe_filename("my-file_123.mp3") == "my-file_123.mp3"

    def test_path_traversal_blocked(self):
        """Test path traversal attempts are blocked after basename extraction."""
        from src.utils.validation import validate_safe_filename, PathTraversalError

        # Note: os.path.basename extracts filename, so "../etc/passwd" becomes "passwd"
        # which is valid. Test with actual traversal patterns.
        with pytest.raises(PathTraversalError):
            validate_safe_filename("..test")  # Has .. in name

        # Test that basename extraction works as expected
        result = validate_safe_filename("some/path/file.txt")
        assert result == "file.txt"  # basename is extracted

    def test_empty_filename_rejected(self):
        """Test empty filename raises error."""
        from src.utils.validation import validate_safe_filename

        with pytest.raises(ValueError):
            validate_safe_filename("")


class TestScriptIdValidation:
    """Tests for validate_script_id function."""

    def test_valid_script_ids(self):
        """Test valid script IDs pass validation."""
        from src.utils.validation import validate_script_id

        assert validate_script_id("dd-20241227") == "dd-20241227"
        assert validate_script_id("dd-20241227-2") == "dd-20241227-2"
        assert validate_script_id("job-a1b2c3d4") == "job-a1b2c3d4"
        assert validate_script_id("episode-test") == "episode-test"

    def test_invalid_script_ids(self):
        """Test invalid script IDs are rejected."""
        from src.utils.validation import validate_script_id

        with pytest.raises(ValueError):
            validate_script_id("script with spaces extra long invalid")

        with pytest.raises(ValueError):
            validate_script_id("../etc/passwd")

    def test_empty_script_id(self):
        """Test empty script ID is rejected."""
        from src.utils.validation import validate_script_id

        with pytest.raises(ValueError):
            validate_script_id("")

        with pytest.raises(ValueError):
            validate_script_id(None)


class TestSafePathJoin:
    """Tests for safe_path_join function."""

    def test_valid_path_join(self):
        """Test valid path joins work correctly."""
        from src.utils.validation import safe_path_join

        result = safe_path_join("/base/dir", "subdir", "file.txt")
        assert result == Path("/base/dir/subdir/file.txt")

    def test_path_traversal_blocked(self):
        """Test path traversal is blocked."""
        from src.utils.validation import safe_path_join, PathTraversalError

        with pytest.raises(PathTraversalError):
            safe_path_join("/base/dir", "../etc/passwd")

        with pytest.raises(PathTraversalError):
            safe_path_join("/base/dir", "subdir", "../../secret.txt")


class TestSafeInt:
    """Tests for safe_int function."""

    def test_valid_integers(self):
        """Test valid integer conversion."""
        from src.utils.validation import safe_int

        assert safe_int("123") == 123
        assert safe_int(456) == 456
        assert safe_int("-789") == -789

    def test_default_value(self):
        """Test default value for invalid input."""
        from src.utils.validation import safe_int

        assert safe_int("not a number", default=0) == 0
        assert safe_int(None, default=42) == 42
        assert safe_int("", default=-1) == -1

    def test_range_validation(self):
        """Test min/max range validation."""
        from src.utils.validation import safe_int

        assert safe_int("5", min_val=0, max_val=10) == 5
        assert safe_int("100", min_val=0, max_val=10, default=10) == 10
        assert safe_int("-5", min_val=0, max_val=10, default=0) == 0


class TestSafeFloat:
    """Tests for safe_float function."""

    def test_valid_floats(self):
        """Test valid float conversion."""
        from src.utils.validation import safe_float

        assert safe_float("3.14") == 3.14
        assert safe_float(2.718) == 2.718
        assert safe_float("-1.5") == -1.5

    def test_default_value(self):
        """Test default value for invalid input."""
        from src.utils.validation import safe_float

        assert safe_float("not a float", default=0.0) == 0.0
        assert safe_float(None, default=1.0) == 1.0


class TestValidateString:
    """Tests for validate_string function."""

    def test_valid_strings(self):
        """Test valid string validation."""
        from src.utils.validation import validate_string

        assert validate_string("hello") == "hello"
        assert validate_string("  trimmed  ") == "trimmed"

    def test_length_truncation(self):
        """Test max length truncation."""
        from src.utils.validation import validate_string

        result = validate_string("abcdefghijk", max_length=5)
        assert result == "abcde"
        assert len(result) == 5

    def test_empty_string_default(self):
        """Test empty string returns default."""
        from src.utils.validation import validate_string

        # With allow_empty=False, empty returns default
        result = validate_string("", allow_empty=False, default="default")
        assert result == "default"

    def test_none_returns_default(self):
        """Test None returns default."""
        from src.utils.validation import validate_string

        assert validate_string(None, default="fallback") == "fallback"


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_urls(self):
        """Test valid URLs return True."""
        from src.utils.validation import validate_url

        assert validate_url("https://example.com") is True
        assert validate_url("http://localhost:8000") is True
        assert validate_url("https://api.example.com/path?query=1") is True

    def test_invalid_urls(self):
        """Test invalid URLs return False."""
        from src.utils.validation import validate_url

        assert validate_url("not-a-url") is False
        assert validate_url("ftp://example.com") is False  # Only http/https allowed by default
        assert validate_url("") is False

    def test_require_https(self):
        """Test HTTPS requirement."""
        from src.utils.validation import validate_url

        assert validate_url("https://example.com", require_https=True) is True
        assert validate_url("http://example.com", require_https=True) is False


class TestValidateEmail:
    """Tests for validate_email function."""

    def test_valid_emails(self):
        """Test valid emails return True."""
        from src.utils.validation import validate_email

        assert validate_email("user@example.com") is True
        assert validate_email("user.name@domain.org") is True

    def test_invalid_emails(self):
        """Test invalid emails return False."""
        from src.utils.validation import validate_email

        assert validate_email("not-an-email") is False
        assert validate_email("@domain.com") is False
        assert validate_email("user@") is False
        assert validate_email("") is False


class TestJobIdValidation:
    """Tests for validate_job_id function."""

    def test_valid_job_ids(self):
        """Test valid job IDs pass validation."""
        from src.utils.validation import validate_job_id

        assert validate_job_id("job-a1b2c3d4") == "job-a1b2c3d4"
        assert validate_job_id("job-00000000") == "job-00000000"

    def test_invalid_job_ids(self):
        """Test invalid job IDs are rejected."""
        from src.utils.validation import validate_job_id

        with pytest.raises(ValueError):
            validate_job_id("invalid-format")

        with pytest.raises(ValueError):
            validate_job_id("")


class TestJsonValidation:
    """Tests for JSON validation utilities."""

    def test_validate_json_structure(self):
        """Test JSON structure validation."""
        from src.utils.validation import validate_json_structure

        data = {"name": "test", "value": 123}
        assert validate_json_structure(data, ["name", "value"]) is True
        assert validate_json_structure(data, ["name", "missing"]) is False
        assert validate_json_structure("not a dict", ["name"]) is False

    def test_sanitize_json_for_storage(self):
        """Test JSON sanitization."""
        from src.utils.validation import sanitize_json_for_storage

        data = {"key": "value", "none_val": None}
        result = sanitize_json_for_storage(data)
        assert "none_val" not in result  # None values removed
        assert result["key"] == "value"
