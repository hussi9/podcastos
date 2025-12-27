"""
Stripe Billing Router for PodcastOS.

Provides API endpoints for:
- Creating checkout sessions
- Verifying payments
- Handling webhooks
"""

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, Field
from typing import Optional
import os
import logging

from src.app.billing import (
    create_checkout_session,
    verify_payment,
    handle_webhook,
    STRIPE_PRICES,
    get_price,
    format_price,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


class StripeNotConfiguredError(Exception):
    """Raised when Stripe is not properly configured."""
    pass


def _check_stripe_configured() -> bool:
    """Check if Stripe API key is configured."""
    return bool(os.getenv("STRIPE_SECRET_KEY"))


def _require_stripe():
    """Raise error if Stripe is not configured."""
    if not _check_stripe_configured():
        raise StripeNotConfiguredError(
            "Stripe is not configured. Set STRIPE_SECRET_KEY environment variable."
        )


class CheckoutRequest(BaseModel):
    """Request to create a checkout session."""
    plan: str = Field(..., description="Plan type: newsletter, podcast, or bundle")
    brand_name: str = Field(..., description="Brand or company name")
    topic: Optional[str] = Field(None, description="Content topic")
    return_url: Optional[str] = Field(None, description="Custom return URL after payment")


class CheckoutResponse(BaseModel):
    """Response with checkout session details."""
    session_id: str
    checkout_url: str
    plan: str
    amount_cents: int
    amount_display: str
    mode: str = "live"


class PaymentStatusResponse(BaseModel):
    """Response with payment verification status."""
    paid: bool
    plan: str
    customer_email: Optional[str] = None
    ready_for_generation: bool = False


class PlansResponse(BaseModel):
    """Response with available plans."""
    plans: dict
    stripe_configured: bool


@router.get("/status")
async def get_billing_status():
    """
    Check if billing is properly configured.

    Returns:
        Configuration status including Stripe availability
    """
    stripe_configured = _check_stripe_configured()
    webhook_secret_configured = bool(os.getenv("STRIPE_WEBHOOK_SECRET"))

    return {
        "stripe_configured": stripe_configured,
        "webhook_configured": webhook_secret_configured,
        "mode": "live" if stripe_configured else "demo",
        "message": (
            "Billing is ready" if stripe_configured
            else "Set STRIPE_SECRET_KEY to enable payments"
        ),
    }


@router.get("/plans", response_model=PlansResponse)
async def get_available_plans():
    """
    Get available pricing plans.

    Returns:
        All available plans with pricing information
    """
    plans = {}
    for plan_id, plan_info in STRIPE_PRICES.items():
        plans[plan_id] = {
            "id": plan_id,
            "name": plan_info["name"],
            "description": plan_info["description"],
            "price_cents": plan_info["price_cents"],
            "price_display": format_price(plan_info["price_cents"]),
        }

    return PlansResponse(
        plans=plans,
        stripe_configured=_check_stripe_configured(),
    )


@router.post("/create-session", response_model=CheckoutResponse)
async def create_checkout(request: CheckoutRequest):
    """
    Create a Stripe Checkout session.

    Creates a payment session for the selected plan. Returns a checkout URL
    that redirects the user to Stripe's hosted payment page.

    Args:
        request: Checkout request with plan and metadata

    Returns:
        Checkout session with URL to redirect user

    Raises:
        HTTPException: If Stripe is not configured or plan is invalid
    """
    # Validate plan
    if request.plan not in STRIPE_PRICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan: {request.plan}. Available: {list(STRIPE_PRICES.keys())}",
        )

    # Check Stripe configuration
    if not _check_stripe_configured():
        logger.warning("Stripe not configured, returning demo mode response")
        # Return demo mode for development
        import uuid
        mock_session_id = f"demo_{uuid.uuid4().hex[:12]}"
        return CheckoutResponse(
            session_id=mock_session_id,
            checkout_url=f"/api/billing/demo-success?session_id={mock_session_id}",
            plan=request.plan,
            amount_cents=get_price(request.plan),
            amount_display=format_price(get_price(request.plan)),
            mode="demo",
        )

    try:
        # Build URLs
        base_url = request.return_url or os.getenv("APP_BASE_URL", "http://localhost:5000")
        success_url = f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/payment/cancel"

        # Create checkout session
        session = create_checkout_session(
            plan=request.plan,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "plan": request.plan,
                "brand_name": request.brand_name,
                "topic": request.topic or "",
            },
        )

        logger.info(f"Created checkout session {session.session_id} for plan {request.plan}")

        return CheckoutResponse(
            session_id=session.session_id,
            checkout_url=session.checkout_url,
            plan=session.plan,
            amount_cents=session.amount_cents,
            amount_display=format_price(session.amount_cents),
            mode="live",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment session")


@router.get("/verify/{session_id}", response_model=PaymentStatusResponse)
async def verify_payment_status(session_id: str):
    """
    Verify payment status for a checkout session.

    Check if a payment was completed successfully. This should be called
    after the user returns from Stripe's checkout page.

    Args:
        session_id: Stripe checkout session ID

    Returns:
        Payment status including whether content generation can proceed
    """
    # Handle demo mode
    if session_id.startswith("demo_"):
        logger.info(f"Demo mode payment verification for {session_id}")
        return PaymentStatusResponse(
            paid=True,
            plan="demo",
            customer_email="demo@example.com",
            ready_for_generation=True,
        )

    if not _check_stripe_configured():
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured. Cannot verify payment.",
        )

    try:
        verification = verify_payment(session_id)

        return PaymentStatusResponse(
            paid=verification.paid,
            plan=verification.plan,
            customer_email=verification.customer_email,
            ready_for_generation=verification.paid,
        )

    except Exception as e:
        logger.error(f"Payment verification failed for {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to verify payment status",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    """
    Handle Stripe webhook events.

    Processes webhook events from Stripe for reliable payment confirmation.
    This endpoint should be configured in your Stripe dashboard.

    Required header: Stripe-Signature
    """
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        logger.warning("Webhook received but STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=503,
            detail="Webhook endpoint not configured",
        )

    if not stripe_signature:
        raise HTTPException(
            status_code=400,
            detail="Missing Stripe-Signature header",
        )

    try:
        payload = await request.body()
        result = handle_webhook(payload, stripe_signature, webhook_secret)

        if "error" in result:
            logger.error(f"Webhook error: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])

        if result.get("event") == "payment_completed":
            logger.info(
                f"Payment completed: session={result.get('session_id')}, "
                f"email={result.get('customer_email')}"
            )
            # Here you could trigger content generation or send confirmation email
            # For now, we just log and acknowledge

        return {"received": True, "event": result.get("event")}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get("/demo-success")
async def demo_success(session_id: str):
    """
    Demo mode success endpoint.

    Used in demo mode when Stripe is not configured.
    """
    return {
        "status": "success",
        "session_id": session_id,
        "message": "Demo payment successful. In production, use real Stripe checkout.",
        "ready_for_generation": True,
    }
