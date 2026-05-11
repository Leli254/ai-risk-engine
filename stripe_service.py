"""
Stripe Service Integration.

Handles outbound communication with Stripe (PaymentIntents) 
and inbound verification (Webhooks). 

Senior Level Implementation:
- Lazy, safe environment variable resolution.
- Strict Type-Safety matching Pydantic schemas.
- Error context capture for structured logging.
"""

import os
import stripe
import structlog
from typing import Optional, Any
from schemas import PaymentRequest, PaymentIntent, PaymentStatus

log = structlog.get_logger()

# --- INTERNAL HELPERS ---


def _get_stripe_config() -> tuple[str, str]:
    """
    Resolves Stripe credentials from the environment.
    
    Returns:
        tuple: (secret_key, webhook_secret)
    """
    secret_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if not secret_key:
        log.error("stripe_config_missing", var="STRIPE_SECRET_KEY")
        raise ValueError(
            "Critical Security Error: Stripe Secret Key not configured.")

    return secret_key, webhook_secret or ""

# --- SERVICE METHODS ---


def create_payment_intent(request: PaymentRequest) -> PaymentIntent:
    """
    Initializes a Stripe PaymentIntent.
    
    Converts USD to Cents (Stripe standard) and attaches metadata 
    to maintain the link between Stripe and our Internal App ID.
    """
    secret_key, _ = _get_stripe_config()

    # We set the key globally for the library, but in a senior setup
    # we use the api_key parameter in the create call for thread safety.
    try:
        # Step 1: Financial conversion (Senior: Use round and int to avoid floating point errors)
        amount_cents = int(round(float(request.amount_usd) * 100))

        # Step 2: Outbound API Call
        intent = stripe.PaymentIntent.create(
            api_key=secret_key,
            amount=amount_cents,
            currency="usd",
            metadata={
                "application_id": request.application_id,
                "email": request.email
            },
            description=f"Risk Assessment Fee - {request.application_id}"
        )

        log.info("stripe_intent_created",
                 application_id=request.application_id,
                 intent_id=intent.id)

        # Step 3: Return Contract (Strictly matching schemas.py)
        return PaymentIntent(
            application_id=request.application_id,
            payment_intent_id=intent.id,
            client_secret=intent.client_secret,
            amount_usd=request.amount_usd,
            status=PaymentStatus.PENDING
        )

    except stripe.error.StripeError as e:
        log.error("stripe_api_error",
                  application_id=request.application_id,
                  error_type=type(e).__name__,
                  message=str(e))
        raise


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict[str, Any]:
    """
    Validates the authenticity of an incoming Stripe Webhook.
    
    Crucial Security Step: Prevents 'Webhook Spoofing' where an attacker 
    tries to fake a payment success message.
    """
    secret_key, webhook_secret = _get_stripe_config()

    if not webhook_secret:
        log.error("stripe_webhook_secret_missing")
        raise ValueError(
            "Webhook secret not found. Cannot verify authenticity.")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret, api_key=secret_key
        )
        return event
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        log.error("webhook_verification_failed", error=str(e))
        raise


def get_application_id(event: Any) -> Optional[str]:
    """
    Safely retrieves application_id from the Stripe Event object or dictionary.
    """
    try:
        # Accessing nested attributes on Stripe objects is safest via dict-like access
        # but the object itself often doesn't support .get() at the top level
        # unless converted.
        data_obj = event['data']['object']
        metadata = data_obj.get('metadata', {})

        return metadata.get('application_id')
    except (KeyError, AttributeError, TypeError) as e:
        log.error("metadata_extraction_failed", error=str(e))
        return None
