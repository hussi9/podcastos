"""
Startup Validation Module for PodcastOS.

Validates all required credentials and configuration on application startup.
Provides clear error messages and graceful degradation options.
"""

import os
import sys
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Status of a validated service."""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    service: str
    status: ServiceStatus
    message: str
    required: bool = True
    details: Optional[Dict[str, Any]] = None


@dataclass
class StartupValidation:
    """Complete startup validation results."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    services: Dict[str, ValidationResult] = field(default_factory=dict)
    
    def add_result(self, result: ValidationResult):
        """Add a validation result."""
        self.services[result.service] = result
        
        if result.status == ServiceStatus.UNAVAILABLE:
            if result.required:
                self.is_valid = False
                self.errors.append(f"[{result.service}] {result.message}")
            else:
                self.warnings.append(f"[{result.service}] {result.message}")
        elif result.status == ServiceStatus.DEGRADED:
            self.warnings.append(f"[{result.service}] {result.message}")
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("🔍 PodcastOS Startup Validation")
        print("=" * 60)
        
        for service, result in self.services.items():
            icon = {
                ServiceStatus.AVAILABLE: "✅",
                ServiceStatus.DEGRADED: "⚠️",
                ServiceStatus.UNAVAILABLE: "❌"
            }[result.status]
            print(f"{icon} {service}: {result.status.value}")
            if result.status != ServiceStatus.AVAILABLE:
                print(f"   → {result.message}")
        
        print("-" * 60)
        
        if self.errors:
            print("\n❌ CRITICAL ERRORS (must fix to start):")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS (optional services unavailable):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if self.is_valid:
            print("\n✅ Validation PASSED - Application can start")
        else:
            print("\n❌ Validation FAILED - Fix errors above before starting")
        
        print("=" * 60 + "\n")


def validate_gemini_api() -> ValidationResult:
    """Validate Gemini API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        return ValidationResult(
            service="Gemini API",
            status=ServiceStatus.UNAVAILABLE,
            message="GEMINI_API_KEY environment variable not set. "
                    "AI generation features will not work.",
            required=True
        )
    
    if len(api_key) < 20:
        return ValidationResult(
            service="Gemini API",
            status=ServiceStatus.UNAVAILABLE,
            message="GEMINI_API_KEY appears to be invalid (too short).",
            required=True
        )
    
    # Try to initialize the client
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        # Light validation - just check client creation works
        return ValidationResult(
            service="Gemini API",
            status=ServiceStatus.AVAILABLE,
            message="Gemini API configured successfully"
        )
    except ImportError:
        return ValidationResult(
            service="Gemini API",
            status=ServiceStatus.UNAVAILABLE,
            message="google-genai package not installed. Run: pip install google-genai",
            required=True
        )
    except Exception as e:
        return ValidationResult(
            service="Gemini API",
            status=ServiceStatus.UNAVAILABLE,
            message=f"Failed to initialize Gemini client: {e}",
            required=True
        )


def validate_supabase() -> ValidationResult:
    """Validate Supabase credentials."""
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    
    missing = []
    if not url:
        missing.append("SUPABASE_URL")
    if not service_key:
        missing.append("SUPABASE_SERVICE_KEY")
    if not anon_key:
        missing.append("SUPABASE_ANON_KEY")
    
    if missing:
        return ValidationResult(
            service="Supabase",
            status=ServiceStatus.DEGRADED,
            message=f"Missing environment variables: {', '.join(missing)}. "
                    "Cloud database/auth features disabled. Using local SQLite.",
            required=False,
            details={"missing": missing, "fallback": "sqlite"}
        )
    
    # Try to connect
    try:
        from supabase import create_client
        client = create_client(url, service_key)
        # Light check - client creation success
        return ValidationResult(
            service="Supabase",
            status=ServiceStatus.AVAILABLE,
            message="Supabase connected successfully"
        )
    except ImportError:
        return ValidationResult(
            service="Supabase",
            status=ServiceStatus.DEGRADED,
            message="supabase-py package not installed. Using local SQLite.",
            required=False
        )
    except Exception as e:
        return ValidationResult(
            service="Supabase",
            status=ServiceStatus.DEGRADED,
            message=f"Failed to connect to Supabase: {e}. Using local SQLite.",
            required=False
        )


def validate_google_tts() -> ValidationResult:
    """Validate Google Cloud TTS credentials."""
    try:
        from google.cloud import texttospeech
        client = texttospeech.TextToSpeechClient()
        return ValidationResult(
            service="Google Cloud TTS",
            status=ServiceStatus.AVAILABLE,
            message="Google Cloud TTS configured successfully"
        )
    except ImportError:
        return ValidationResult(
            service="Google Cloud TTS",
            status=ServiceStatus.DEGRADED,
            message="google-cloud-texttospeech not installed. Audio generation disabled.",
            required=False
        )
    except Exception as e:
        error_str = str(e)
        if "credentials" in error_str.lower() or "authentication" in error_str.lower():
            return ValidationResult(
                service="Google Cloud TTS",
                status=ServiceStatus.DEGRADED,
                message="Google Cloud credentials not configured. "
                        "Set GOOGLE_APPLICATION_CREDENTIALS or run: gcloud auth application-default login",
                required=False
            )
        return ValidationResult(
            service="Google Cloud TTS",
            status=ServiceStatus.DEGRADED,
            message=f"Google Cloud TTS initialization failed: {e}",
            required=False
        )


def validate_flask_config() -> ValidationResult:
    """Validate Flask configuration."""
    secret_key = os.getenv("FLASK_SECRET_KEY")
    
    if not secret_key:
        return ValidationResult(
            service="Flask Config",
            status=ServiceStatus.DEGRADED,
            message="FLASK_SECRET_KEY not set. Using development default. "
                    "Set this for production!",
            required=False
        )
    
    if len(secret_key) < 32:
        return ValidationResult(
            service="Flask Config",
            status=ServiceStatus.DEGRADED,
            message="FLASK_SECRET_KEY is too short. Use at least 32 characters for security.",
            required=False
        )
    
    return ValidationResult(
        service="Flask Config",
        status=ServiceStatus.AVAILABLE,
        message="Flask configuration valid"
    )


def validate_openai() -> ValidationResult:
    """Validate OpenAI API key (optional, for fallback)."""
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return ValidationResult(
            service="OpenAI API",
            status=ServiceStatus.DEGRADED,
            message="OPENAI_API_KEY not set. OpenAI fallback unavailable.",
            required=False
        )

    return ValidationResult(
        service="OpenAI API",
        status=ServiceStatus.AVAILABLE,
        message="OpenAI API configured (fallback available)"
    )


def validate_stripe() -> ValidationResult:
    """Validate Stripe API keys for billing."""
    secret_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if not secret_key:
        return ValidationResult(
            service="Stripe Billing",
            status=ServiceStatus.DEGRADED,
            message="STRIPE_SECRET_KEY not set. Payments disabled (demo mode only).",
            required=False,
            details={"mode": "demo"}
        )

    if len(secret_key) < 20 or not secret_key.startswith(("sk_live_", "sk_test_")):
        return ValidationResult(
            service="Stripe Billing",
            status=ServiceStatus.DEGRADED,
            message="STRIPE_SECRET_KEY appears invalid. Expected format: sk_live_* or sk_test_*",
            required=False
        )

    # Check webhook secret
    warnings = []
    if not webhook_secret:
        warnings.append("STRIPE_WEBHOOK_SECRET not set - webhooks disabled")

    # Try to import and configure stripe
    try:
        import stripe
        stripe.api_key = secret_key

        mode = "live" if secret_key.startswith("sk_live_") else "test"
        message = f"Stripe configured in {mode} mode"
        if warnings:
            message += f". Warnings: {'; '.join(warnings)}"

        return ValidationResult(
            service="Stripe Billing",
            status=ServiceStatus.AVAILABLE,
            message=message,
            details={"mode": mode, "webhooks_enabled": bool(webhook_secret)}
        )
    except ImportError:
        return ValidationResult(
            service="Stripe Billing",
            status=ServiceStatus.DEGRADED,
            message="stripe package not installed. Run: pip install stripe",
            required=False
        )
    except Exception as e:
        return ValidationResult(
            service="Stripe Billing",
            status=ServiceStatus.DEGRADED,
            message=f"Failed to configure Stripe: {e}",
            required=False
        )


def run_startup_validation(
    require_gemini: bool = True,
    require_supabase: bool = False,
    require_tts: bool = False,
    require_stripe: bool = False,
    exit_on_failure: bool = False,
    print_summary: bool = True
) -> StartupValidation:
    """
    Run complete startup validation.

    Args:
        require_gemini: Whether Gemini API is required
        require_supabase: Whether Supabase is required
        require_tts: Whether Google TTS is required
        require_stripe: Whether Stripe billing is required
        exit_on_failure: Exit process if validation fails
        print_summary: Print validation summary

    Returns:
        StartupValidation with all results
    """
    validation = StartupValidation()

    # Run all validations
    gemini_result = validate_gemini_api()
    gemini_result.required = require_gemini
    validation.add_result(gemini_result)

    supabase_result = validate_supabase()
    supabase_result.required = require_supabase
    validation.add_result(supabase_result)

    tts_result = validate_google_tts()
    tts_result.required = require_tts
    validation.add_result(tts_result)

    flask_result = validate_flask_config()
    validation.add_result(flask_result)

    openai_result = validate_openai()
    validation.add_result(openai_result)

    stripe_result = validate_stripe()
    stripe_result.required = require_stripe
    validation.add_result(stripe_result)

    if print_summary:
        validation.print_summary()

    if exit_on_failure and not validation.is_valid:
        logger.error("Startup validation failed. Exiting.")
        sys.exit(1)

    return validation


def get_service_status(service_name: str) -> Optional[ServiceStatus]:
    """
    Get the status of a specific service.
    Must call run_startup_validation first.
    """
    # This is a quick check function for runtime use
    validators = {
        "gemini": validate_gemini_api,
        "supabase": validate_supabase,
        "tts": validate_google_tts,
        "flask": validate_flask_config,
        "openai": validate_openai,
        "stripe": validate_stripe,
    }
    
    validator = validators.get(service_name.lower())
    if validator:
        result = validator()
        return result.status
    return None


# Module-level validation cache
_validation_cache: Optional[StartupValidation] = None


def get_cached_validation() -> Optional[StartupValidation]:
    """Get cached validation result."""
    return _validation_cache


def ensure_validated(
    require_gemini: bool = True,
    require_supabase: bool = False
) -> StartupValidation:
    """
    Ensure validation has been run, running it if necessary.
    Caches the result.
    """
    global _validation_cache
    
    if _validation_cache is None:
        _validation_cache = run_startup_validation(
            require_gemini=require_gemini,
            require_supabase=require_supabase,
            print_summary=True
        )
    
    return _validation_cache


if __name__ == "__main__":
    # Run validation when executed directly
    validation = run_startup_validation(
        require_gemini=True,
        require_supabase=False,
        exit_on_failure=True
    )
