"""
Unit tests for startup validation.
"""

import pytest
import os
from unittest.mock import patch, MagicMock


class TestGeminiValidation:
    """Tests for Gemini API validation."""

    def test_missing_api_key(self):
        """Test validation fails without API key."""
        from src.config.startup_validation import validate_gemini_api, ServiceStatus

        with patch.dict(os.environ, {}, clear=True):
            result = validate_gemini_api()
            assert result.status == ServiceStatus.UNAVAILABLE
            assert "GEMINI_API_KEY" in result.message

    def test_short_api_key(self):
        """Test validation fails with short API key."""
        from src.config.startup_validation import validate_gemini_api, ServiceStatus

        with patch.dict(os.environ, {"GEMINI_API_KEY": "short"}, clear=True):
            result = validate_gemini_api()
            assert result.status == ServiceStatus.UNAVAILABLE
            assert "invalid" in result.message.lower()

    def test_valid_api_key(self):
        """Test validation passes with valid API key."""
        from src.config.startup_validation import validate_gemini_api, ServiceStatus

        with patch.dict(os.environ, {"GEMINI_API_KEY": "a" * 40}, clear=True):
            with patch("google.genai.Client") as mock_client:
                mock_client.return_value = MagicMock()
                result = validate_gemini_api()
                assert result.status == ServiceStatus.AVAILABLE


class TestSupabaseValidation:
    """Tests for Supabase validation."""

    def test_missing_credentials(self):
        """Test validation degrades without credentials."""
        from src.config.startup_validation import validate_supabase, ServiceStatus

        with patch.dict(os.environ, {}, clear=True):
            result = validate_supabase()
            assert result.status == ServiceStatus.DEGRADED
            assert "sqlite" in result.message.lower() or "missing" in result.message.lower()

    def test_partial_credentials(self):
        """Test validation degrades with partial credentials."""
        from src.config.startup_validation import validate_supabase, ServiceStatus

        # Only providing URL, missing keys
        with patch.dict(os.environ, {"SUPABASE_URL": "https://example.supabase.co"}, clear=True):
            result = validate_supabase()
            assert result.status == ServiceStatus.DEGRADED

    def test_valid_credentials(self):
        """Test validation passes with all credentials."""
        from src.config.startup_validation import validate_supabase, ServiceStatus

        env = {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_KEY": "service-key",
            "SUPABASE_ANON_KEY": "anon-key",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("supabase.create_client") as mock_client:
                mock_client.return_value = MagicMock()
                result = validate_supabase()
                assert result.status == ServiceStatus.AVAILABLE


class TestFlaskValidation:
    """Tests for Flask configuration validation."""

    def test_missing_secret_key(self):
        """Test validation warns without secret key."""
        from src.config.startup_validation import validate_flask_config, ServiceStatus

        with patch.dict(os.environ, {}, clear=True):
            result = validate_flask_config()
            assert result.status == ServiceStatus.DEGRADED

    def test_short_secret_key(self):
        """Test validation warns with short secret key."""
        from src.config.startup_validation import validate_flask_config, ServiceStatus

        with patch.dict(os.environ, {"FLASK_SECRET_KEY": "short"}, clear=True):
            result = validate_flask_config()
            assert result.status == ServiceStatus.DEGRADED

    def test_valid_secret_key(self):
        """Test validation passes with valid secret key."""
        from src.config.startup_validation import validate_flask_config, ServiceStatus

        with patch.dict(os.environ, {"FLASK_SECRET_KEY": "a" * 64}, clear=True):
            result = validate_flask_config()
            assert result.status == ServiceStatus.AVAILABLE


class TestStripeValidation:
    """Tests for Stripe validation."""

    def test_missing_stripe_key(self):
        """Test validation degrades without Stripe key."""
        from src.config.startup_validation import validate_stripe, ServiceStatus

        with patch.dict(os.environ, {}, clear=True):
            result = validate_stripe()
            assert result.status == ServiceStatus.DEGRADED
            assert "demo" in result.message.lower()

    def test_invalid_stripe_key_format(self):
        """Test validation fails with invalid key format."""
        from src.config.startup_validation import validate_stripe, ServiceStatus

        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "invalid_key_format"}, clear=True):
            result = validate_stripe()
            assert result.status == ServiceStatus.DEGRADED

    def test_test_mode_key(self):
        """Test validation passes with test mode key."""
        from src.config.startup_validation import validate_stripe, ServiceStatus

        env = {"STRIPE_SECRET_KEY": "sk_test_" + "a" * 40}
        with patch.dict(os.environ, env, clear=True):
            # Mock stripe module
            with patch.dict('sys.modules', {'stripe': MagicMock()}):
                result = validate_stripe()
                assert result.status == ServiceStatus.AVAILABLE
                assert "test" in result.message.lower()

    def test_live_mode_key(self):
        """Test validation passes with live mode key."""
        from src.config.startup_validation import validate_stripe, ServiceStatus

        env = {"STRIPE_SECRET_KEY": "sk_live_" + "a" * 40}
        with patch.dict(os.environ, env, clear=True):
            with patch.dict('sys.modules', {'stripe': MagicMock()}):
                result = validate_stripe()
                assert result.status == ServiceStatus.AVAILABLE
                assert "live" in result.message.lower()

    def test_webhook_warning(self):
        """Test warning when webhook secret missing."""
        from src.config.startup_validation import validate_stripe, ServiceStatus

        # Only secret key, no webhook secret
        env = {"STRIPE_SECRET_KEY": "sk_test_" + "a" * 40}
        with patch.dict(os.environ, env, clear=True):
            with patch.dict('sys.modules', {'stripe': MagicMock()}):
                result = validate_stripe()
                assert "webhook" in result.message.lower()


class TestStartupValidation:
    """Tests for the full startup validation."""

    def test_run_all_validations(self):
        """Test running all validations."""
        from src.config.startup_validation import run_startup_validation

        env = {
            "GEMINI_API_KEY": "a" * 40,
            "FLASK_SECRET_KEY": "a" * 64,
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("google.genai.Client"):
                result = run_startup_validation(
                    require_gemini=True,
                    require_supabase=False,
                    print_summary=False
                )
                assert "Gemini API" in result.services
                assert "Flask Config" in result.services

    def test_validation_fails_on_required_service(self):
        """Test validation fails when required service missing."""
        from src.config.startup_validation import run_startup_validation

        with patch.dict(os.environ, {}, clear=True):
            result = run_startup_validation(
                require_gemini=True,
                print_summary=False
            )
            assert result.is_valid is False
            assert len(result.errors) > 0

    def test_get_service_status(self):
        """Test getting individual service status."""
        from src.config.startup_validation import get_service_status, ServiceStatus

        with patch.dict(os.environ, {"GEMINI_API_KEY": "a" * 40}, clear=True):
            with patch("google.genai.Client"):
                status = get_service_status("gemini")
                assert status == ServiceStatus.AVAILABLE


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Test creating ValidationResult."""
        from src.config.startup_validation import ValidationResult, ServiceStatus

        result = ValidationResult(
            service="Test Service",
            status=ServiceStatus.AVAILABLE,
            message="Service is working"
        )

        assert result.service == "Test Service"
        assert result.status == ServiceStatus.AVAILABLE
        assert result.message == "Service is working"

    def test_startup_validation_add_result(self):
        """Test adding results to StartupValidation."""
        from src.config.startup_validation import (
            StartupValidation,
            ValidationResult,
            ServiceStatus
        )

        validation = StartupValidation()

        # Add available service
        validation.add_result(ValidationResult(
            service="Service1",
            status=ServiceStatus.AVAILABLE,
            message="OK"
        ))
        assert validation.is_valid is True

        # Add unavailable required service
        validation.add_result(ValidationResult(
            service="Service2",
            status=ServiceStatus.UNAVAILABLE,
            message="Not configured",
            required=True
        ))
        assert validation.is_valid is False
        assert len(validation.errors) == 1

    def test_startup_validation_warnings(self):
        """Test warnings are tracked separately."""
        from src.config.startup_validation import (
            StartupValidation,
            ValidationResult,
            ServiceStatus
        )

        validation = StartupValidation()

        # Add degraded optional service
        validation.add_result(ValidationResult(
            service="OptionalService",
            status=ServiceStatus.DEGRADED,
            message="Using fallback",
            required=False
        ))

        assert validation.is_valid is True  # Still valid
        assert len(validation.warnings) == 1
