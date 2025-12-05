# backend/services/stripe_service.py
"""
Stripe payment service for subscription management.
"""
import os
from typing import Optional, Dict, Any
import stripe
from dotenv import dotenv_values
from pathlib import Path

# Load Stripe key from config/.env or environment
CFG_PATH = Path(__file__).resolve().parents[2] / "config" / ".env"
cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY") or cfg.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET") or cfg.get("STRIPE_WEBHOOK_SECRET")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
else:
    # In development, allow missing key (will fail when actually used)
    # In production, this should always be set
    print("WARNING: STRIPE_SECRET_KEY not found. Stripe features will not work.")
    stripe.api_key = None

def charge_customer_for_royalties(
    user_id: str,
    user_email: str,
    amount_cents: int,
    description: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    PHASE 4: Charge a customer for outstanding royalties via Stripe.
    """
    return charge_customer_for_fees(user_id, user_email, amount_cents, description, metadata)

def charge_customer_for_fees(
    user_id: str,
    user_email: str,
    amount_cents: int,
    description: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    FIX 5: Charge a customer for platform fees via Stripe.
    
    Args:
        user_id: User ID
        user_email: User email
        amount_cents: Amount to charge in cents
        description: Description for the charge
        metadata: Additional metadata for the charge
    
    Returns:
        Dictionary with charge result
    """
    if not stripe.api_key:
        raise ValueError("STRIPE_SECRET_KEY is not configured. Please add it to config/.env")
    
    if amount_cents <= 0:
        return {
            "success": True,
            "message": "No charge needed (amount is zero)",
            "charge_id": None,
            "amount_charged": 0.0
        }
    
    try:
        # First, get or create a Stripe customer
        customer_id = None
        
        # Try to find existing customer by email
        customers = stripe.Customer.list(email=user_email, limit=1)
        if customers.data:
            customer_id = customers.data[0].id
        else:
            # Create new customer
            customer = stripe.Customer.create(
                email=user_email,
                metadata={"user_id": user_id}
            )
            customer_id = customer.id
        
        # Create a payment intent for the fee charge
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            customer=customer_id,
            description=description,
            metadata={
                "user_id": user_id,
                "type": metadata.get("type", "fee_payment") if metadata else "fee_payment",
                **(metadata or {})
            },
            payment_method_types=["card"],
            # For now, we'll require manual payment method attachment
            # In production, you'd want to save payment methods for automatic charging
        )
        
        return {
            "success": True,
            "message": "Payment intent created. Manual confirmation required.",
            "charge_id": payment_intent.id,
            "payment_intent_id": payment_intent.id,
            "id": payment_intent.id,  # FIX 5: Add 'id' field for compatibility
            "amount_charged": amount_cents / 100.0,
            "customer_id": customer_id,
            "requires_action": True,
            "client_secret": payment_intent.client_secret
        }
    except stripe.error.StripeError as e:
        raise ValueError(f"Stripe error: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to charge customer: {str(e)}")


def create_checkout_session(
    plan_id: str,
    plan_name: str,
    price_cents: int,
    user_id: str,
    user_email: str,
    success_url: str,
    cancel_url: str
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout Session for subscription payment.
    
    Args:
        plan_id: Internal plan ID
        plan_name: Display name of the plan
        price_cents: Price in cents (e.g. 3999 for $39.99)
        user_id: User ID for metadata
        user_email: User email
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect if payment is cancelled
    
    Returns:
        Stripe checkout session object
    """
    if not stripe.api_key:
        raise ValueError("STRIPE_SECRET_KEY is not configured. Please add it to config/.env")
    
    try:
        # Handle free plans (price_cents = 0)
        if price_cents == 0:
            # For free plans, we can either skip Stripe or create a $0 subscription
            # For now, we'll create a $0 subscription which Stripe allows
            line_items = [{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'{plan_name} Plan',
                        'description': f'Monthly subscription to {plan_name} plan (Free)',
                    },
                    'unit_amount': 0,  # Free plan
                    'recurring': {
                        'interval': 'month',
                    },
                },
                'quantity': 1,
            }]
        else:
            line_items = [{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'{plan_name} Plan',
                        'description': f'Monthly subscription to {plan_name} plan',
                    },
                    'unit_amount': price_cents,
                    'recurring': {
                        'interval': 'month',
                    },
                },
                'quantity': 1,
            }]
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='subscription',
            customer_email=user_email,
            metadata={
                'user_id': user_id,
                'plan_id': plan_id,
                'plan_name': plan_name,
            },
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True,
        )
        return {
            'session_id': session.id,
            'url': session.url,
            'status': 'created'
        }
    except stripe.error.StripeError as e:
        raise Exception(f"Stripe error: {str(e)}")

def verify_webhook_signature(payload: bytes, signature: str) -> Optional[Dict[str, Any]]:
    """
    Verify Stripe webhook signature.
    
    Args:
        payload: Raw request body as bytes
        signature: Stripe signature from header
    
    Returns:
        Event object if valid, None otherwise
    """
    if not STRIPE_WEBHOOK_SECRET:
        # In development, you might skip verification
        # In production, always verify!
        return None
    
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )
        return event
    except ValueError as e:
        # Invalid payload
        raise Exception(f"Invalid payload: {str(e)}")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise Exception(f"Invalid signature: {str(e)}")

def get_customer_subscription_status(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Get customer's subscription status from Stripe.
    """
    try:
        subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
        if subscriptions.data:
            sub = subscriptions.data[0]
            return {
                'status': sub.status,
                'current_period_end': sub.current_period_end,
                'cancel_at_period_end': sub.cancel_at_period_end,
            }
        return None
    except stripe.error.StripeError as e:
        raise Exception(f"Stripe error: {str(e)}")

