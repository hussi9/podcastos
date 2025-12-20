"""
Stripe Billing Integration for PodcastOS.

Flow:
1. User selects plan and enters content
2. We create a Stripe Checkout session
3. User pays on Stripe's hosted page
4. Stripe redirects back with session ID
5. We verify payment and generate content
"""

import os
import stripe
from typing import Optional
from pydantic import BaseModel


# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Pricing configuration (in cents)
STRIPE_PRICES = {
    "newsletter": {
        "name": "Newsletter Only",
        "price_cents": 2900,  # $29
        "description": "AI-generated newsletter with research",
    },
    "podcast": {
        "name": "Podcast Only",
        "price_cents": 4900,  # $49
        "description": "AI-generated podcast with audio",
    },
    "bundle": {
        "name": "Newsletter + Podcast Bundle",
        "price_cents": 6900,  # $69
        "description": "Both newsletter and podcast - save $9",
    },
}


class CheckoutSession(BaseModel):
    """Checkout session data."""
    session_id: str
    checkout_url: str
    plan: str
    amount_cents: int


class PaymentVerification(BaseModel):
    """Payment verification result."""
    paid: bool
    plan: str
    customer_email: Optional[str] = None
    payment_intent: Optional[str] = None


def create_checkout_session(
    plan: str,
    success_url: str,
    cancel_url: str,
    metadata: dict = None,
) -> CheckoutSession:
    """
    Create a Stripe Checkout session for one-time payment.

    Args:
        plan: One of 'newsletter', 'podcast', 'bundle'
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect if user cancels
        metadata: Additional data to store with the session

    Returns:
        CheckoutSession with session_id and checkout_url
    """
    if plan not in STRIPE_PRICES:
        raise ValueError(f"Invalid plan: {plan}")

    price_info = STRIPE_PRICES[plan]

    # Create Stripe Checkout Session
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": price_info["name"],
                    "description": price_info["description"],
                },
                "unit_amount": price_info["price_cents"],
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata or {},
    )

    return CheckoutSession(
        session_id=session.id,
        checkout_url=session.url,
        plan=plan,
        amount_cents=price_info["price_cents"],
    )


def verify_payment(session_id: str) -> PaymentVerification:
    """
    Verify that a Checkout session was paid.

    Args:
        session_id: Stripe Checkout session ID

    Returns:
        PaymentVerification with payment status
    """
    try:
        session = stripe.checkout.Session.retrieve(session_id)

        return PaymentVerification(
            paid=session.payment_status == "paid",
            plan=session.metadata.get("plan", "unknown"),
            customer_email=session.customer_details.email if session.customer_details else None,
            payment_intent=session.payment_intent,
        )
    except stripe.error.StripeError as e:
        return PaymentVerification(
            paid=False,
            plan="unknown",
        )


def get_price(plan: str) -> int:
    """Get price in cents for a plan."""
    if plan not in STRIPE_PRICES:
        raise ValueError(f"Invalid plan: {plan}")
    return STRIPE_PRICES[plan]["price_cents"]


def format_price(cents: int) -> str:
    """Format cents as dollars."""
    return f"${cents / 100:.0f}"


# Webhook handling for production
def handle_webhook(payload: bytes, sig_header: str, webhook_secret: str) -> dict:
    """
    Handle Stripe webhook events.

    In production, use webhooks for reliable payment confirmation.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            return {
                "event": "payment_completed",
                "session_id": session["id"],
                "customer_email": session.get("customer_details", {}).get("email"),
                "metadata": session.get("metadata", {}),
            }

        return {"event": event["type"]}

    except stripe.error.SignatureVerificationError:
        return {"error": "Invalid signature"}
