"""
Unit tests for Stripe billing functionality.
"""

import pytest
import os
from unittest.mock import patch, MagicMock


class TestBillingPricing:
    """Tests for billing pricing configuration."""

    def test_prices_defined(self):
        """Test all plan prices are defined."""
        from src.app.billing import STRIPE_PRICES

        assert "newsletter" in STRIPE_PRICES
        assert "podcast" in STRIPE_PRICES
        assert "bundle" in STRIPE_PRICES

    def test_price_structure(self):
        """Test price entries have required fields."""
        from src.app.billing import STRIPE_PRICES

        for plan_id, plan in STRIPE_PRICES.items():
            assert "name" in plan
            assert "price_cents" in plan
            assert "description" in plan
            assert isinstance(plan["price_cents"], int)
            assert plan["price_cents"] > 0

    def test_get_price(self):
        """Test get_price returns correct values."""
        from src.app.billing import get_price, STRIPE_PRICES

        for plan_id, plan in STRIPE_PRICES.items():
            assert get_price(plan_id) == plan["price_cents"]

    def test_get_price_invalid_plan(self):
        """Test get_price raises for invalid plan."""
        from src.app.billing import get_price

        with pytest.raises(ValueError, match="Invalid plan"):
            get_price("nonexistent_plan")

    def test_format_price(self):
        """Test price formatting."""
        from src.app.billing import format_price

        assert format_price(2900) == "$29"
        assert format_price(4900) == "$49"
        assert format_price(100) == "$1"


class TestCheckoutSession:
    """Tests for checkout session creation."""

    def test_create_checkout_invalid_plan(self):
        """Test creating checkout with invalid plan fails."""
        from src.app.billing import create_checkout_session

        with pytest.raises(ValueError, match="Invalid plan"):
            create_checkout_session(
                plan="invalid",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    def test_create_checkout_success(self):
        """Test successful checkout session creation."""
        from src.app.billing import create_checkout_session

        with patch("stripe.checkout.Session.create") as mock_create:
            mock_session = MagicMock()
            mock_session.id = "cs_test_123"
            mock_session.url = "https://checkout.stripe.com/session"
            mock_create.return_value = mock_session

            result = create_checkout_session(
                plan="newsletter",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                metadata={"brand": "TestBrand"},
            )

            assert result.session_id == "cs_test_123"
            assert result.checkout_url == "https://checkout.stripe.com/session"
            assert result.plan == "newsletter"

    def test_create_checkout_with_metadata(self):
        """Test metadata is passed to Stripe."""
        from src.app.billing import create_checkout_session

        with patch("stripe.checkout.Session.create") as mock_create:
            mock_session = MagicMock()
            mock_session.id = "cs_test_123"
            mock_session.url = "https://checkout.stripe.com/session"
            mock_create.return_value = mock_session

            create_checkout_session(
                plan="podcast",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                metadata={"brand": "TestBrand", "topic": "AI News"},
            )

            # Check metadata was passed
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["metadata"]["brand"] == "TestBrand"


class TestPaymentVerification:
    """Tests for payment verification."""

    def test_verify_paid_session(self):
        """Test verifying a paid session."""
        from src.app.billing import verify_payment

        with patch("stripe.checkout.Session.retrieve") as mock_retrieve:
            mock_session = MagicMock()
            mock_session.payment_status = "paid"
            mock_session.metadata = {"plan": "newsletter"}
            mock_session.customer_details = MagicMock(email="test@example.com")
            mock_session.payment_intent = "pi_123"
            mock_retrieve.return_value = mock_session

            result = verify_payment("cs_test_123")

            assert result.paid is True
            assert result.plan == "newsletter"
            assert result.customer_email == "test@example.com"

    def test_verify_unpaid_session(self):
        """Test verifying an unpaid session."""
        from src.app.billing import verify_payment

        with patch("stripe.checkout.Session.retrieve") as mock_retrieve:
            mock_session = MagicMock()
            mock_session.payment_status = "unpaid"
            mock_session.metadata = {"plan": "podcast"}
            mock_session.customer_details = None
            mock_session.payment_intent = None
            mock_retrieve.return_value = mock_session

            result = verify_payment("cs_test_123")

            assert result.paid is False

    def test_verify_stripe_error(self):
        """Test verification handles Stripe errors."""
        from src.app.billing import verify_payment
        import stripe

        with patch("stripe.checkout.Session.retrieve") as mock_retrieve:
            mock_retrieve.side_effect = stripe.error.StripeError("API Error")

            result = verify_payment("cs_invalid")

            assert result.paid is False
            assert result.plan == "unknown"


class TestWebhookHandling:
    """Tests for Stripe webhook handling."""

    def test_handle_valid_webhook(self):
        """Test handling valid webhook event."""
        from src.app.billing import handle_webhook

        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_event = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_123",
                        "customer_details": {"email": "test@example.com"},
                        "metadata": {"plan": "bundle"},
                    }
                },
            }
            mock_construct.return_value = mock_event

            result = handle_webhook(
                payload=b"{}",
                sig_header="test_sig",
                webhook_secret="whsec_test",
            )

            assert result["event"] == "payment_completed"
            assert result["session_id"] == "cs_test_123"

    def test_handle_invalid_signature(self):
        """Test handling webhook with invalid signature."""
        from src.app.billing import handle_webhook
        import stripe

        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.side_effect = stripe.error.SignatureVerificationError(
                "Invalid signature", "sig"
            )

            result = handle_webhook(
                payload=b"{}",
                sig_header="invalid_sig",
                webhook_secret="whsec_test",
            )

            assert "error" in result
            assert result["error"] == "Invalid signature"

    def test_handle_other_events(self):
        """Test handling non-checkout events."""
        from src.app.billing import handle_webhook

        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_event = {
                "type": "payment_intent.succeeded",
                "data": {"object": {}},
            }
            mock_construct.return_value = mock_event

            result = handle_webhook(
                payload=b"{}",
                sig_header="test_sig",
                webhook_secret="whsec_test",
            )

            assert result["event"] == "payment_intent.succeeded"


class TestBillingModels:
    """Tests for billing Pydantic models."""

    def test_checkout_session_model(self):
        """Test CheckoutSession model."""
        from src.app.billing import CheckoutSession

        session = CheckoutSession(
            session_id="cs_123",
            checkout_url="https://stripe.com/checkout",
            plan="newsletter",
            amount_cents=2900,
        )

        assert session.session_id == "cs_123"
        assert session.amount_cents == 2900

    def test_payment_verification_model(self):
        """Test PaymentVerification model."""
        from src.app.billing import PaymentVerification

        verification = PaymentVerification(
            paid=True,
            plan="podcast",
            customer_email="test@example.com",
        )

        assert verification.paid is True
        assert verification.customer_email == "test@example.com"
