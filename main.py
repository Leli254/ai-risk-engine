"""
Main Entry Point for the AI Risk Engine.

This module orchestrates the payment-gated AI assessment pipeline. It handles:
1. Environment bootstrapping and logging configuration.
2. Request lifecycle management via FastAPI Lifespan.
3. Security middleware (Rate Limiting & Zero-Retention Logging).
4. Webhook integration with Stripe for asynchronous payment confirmation.
5. Idempotent AI assessment execution.
"""

# 1. BOOTSTRAP: Load environment variables BEFORE importing local modules
from store import store
from stripe_service import (
    create_payment_intent,
    verify_webhook_signature,
    get_application_id
)
from rate_limiter import limiter
from pipeline import run_pipeline
from schemas import (
    ApplicationRequest, RiskScore,
    PaymentRequest, PaymentIntent, AssessmentResult
)
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, HTTPException, status
import structlog
import os
from dotenv import load_dotenv
load_dotenv()


# 2. LOCAL IMPORTS: Safe to import now that environment is loaded

# 3. LOGGING CONFIGURATION
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown events.
    Use this for initializing DB pools or external AI clients.
    """
    log.info("service_started", version="1.0.0", status="ready")
    yield
    log.info("service_shutdown", status="cleanup_complete")

app = FastAPI(
    title="AI Risk Engine",
    description="Secure, payment-gated AI loan risk assessment API.",
    version="1.0.0",
    lifespan=lifespan
)

# ── MIDDLEWARE ───────────────────────────────────────────────────────────────


@app.middleware("http")
async def security_and_observability_middleware(request: Request, call_next):
    """
    Intercepts all requests to apply security policies and structured logging.
    
    Security: Applies rate limiting to non-webhook endpoints.
    Privacy: Implements 'Zero-Retention' by logging only metadata, never request bodies.
    """
    client_ip = request.client.host
    path = request.url.path

    # Logic Isolation: Webhooks are validated by Stripe signatures, not rate limits.
    if not path.startswith("/webhook"):
        if not limiter.is_allowed(client_ip):
            log.warning("rate_limit_exceeded", client_ip=client_ip, path=path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Please try again later."}
            )

    # Initial request context for traceability
    log.info("request_received", method=request.method,
             path=path, ip=client_ip)

    try:
        response = await call_next(request)
        log.info("request_completed", status_code=response.status_code)
        return response
    except Exception as e:
        log.error("unhandled_exception", path=path, error=str(e))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )

# ── ENDPOINTS ────────────────────────────────────────────────────────────────


@app.post("/payment/create", response_model=PaymentIntent, tags=["Payments"])
async def create_payment(request: PaymentRequest):
    """
    Step 1: Create a Stripe PaymentIntent.
    
    Checks local store to prevent duplicate payment attempts for the same application.
    Returns a client_secret for frontend Stripe.js integration.
    """
    current_status = store.get_payment_status(request.application_id)

    if current_status in ["paid", "processing"]:
        log.warning("payment_already_exists",
                    application_id=request.application_id, status=current_status)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application has already been paid or is currently processing."
        )

    try:
        intent = create_payment_intent(request)

        # Atomically link intent and track status
        store.link_payment(intent.payment_intent_id, request.application_id)
        store.set_payment_status(request.application_id, "pending")

        return intent
    except Exception as e:
        log.error("stripe_integration_error", error=str(
            e), application_id=request.application_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize payment with provider."
        )


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = verify_webhook_signature(payload, sig_header)

        # --- SENIOR DEBUG BLOCK ---
        # This will show you exactly what is inside the StripeObject
        log.debug("inspecting_stripe_object",
                  type=type(event),
                  attributes=dir(event))

        # Convert to a real dict so you can use .get() again
        event_dict = event.to_dict()
        # ---------------------------

        event_type = event_dict.get("type")
        log.info("webhook_received", type=event_type)

        if event_type == "payment_intent.succeeded":
            # Direct inspection of the nested object
            obj = event_dict.get("data", {}).get("object", {})
            metadata = obj.get("metadata", {})

            # Check your terminal for this!
            log.info("inspecting_metadata", metadata=metadata)

            app_id = metadata.get("application_id")
            if app_id:
                log.info("payment_confirmed", application_id=app_id)
                store.set_payment_status(app_id, "paid")
            else:
                log.error("application_id_missing_in_metadata")

        return {"status": "success"}

    except Exception as e:
        log.error("webhook_crash", error=str(e), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/assess", response_model=RiskScore, tags=["AI Assessment"])
async def assess_application(request: ApplicationRequest):
    """
    Step 3: Run the two-pass AI assessment pipeline.
    
    Requires 'paid' status in the store. Implements idempotency by 
    returning cached results if the assessment has already been performed.
    """
    # 1. Gatekeeper Check
    if store.get_payment_status(request.application_id) != "paid":
        log.warning("unauthorized_access_attempt",
                    application_id=request.application_id)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment is required before running the AI assessment."
        )

    # 2. Idempotency Check (Save tokens/cost)
    cached_result = store.get_assessment(request.application_id)
    if cached_result:
        log.info("idempotent_return", application_id=request.application_id)
        return cached_result

    # 3. Pipeline Execution
    try:
        log.info("ai_pipeline_started", application_id=request.application_id)
        result = run_pipeline(request)

        store.save_assessment(request.application_id, result)
        log.info("ai_pipeline_completed",
                 application_id=request.application_id)
        return result
    except Exception as e:
        log.error("ai_pipeline_failed",
                  application_id=request.application_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Risk assessment engine encountered an error."
        )


@app.get("/result/{application_id}", response_model=AssessmentResult, tags=["Reporting"])
async def get_application_status(application_id: str):
    """
    Polling endpoint for clients to check assessment status and retrieve results.
    """
    return AssessmentResult(
        application_id=application_id,
        payment_status=store.get_payment_status(application_id) or "not_found",
        risk_score=store.get_assessment(application_id),
        message="Assessment available" if store.get_assessment(
            application_id) else "Processing or awaiting payment"
    )


@app.get("/health", tags=["System"])
async def health_check():
    """Service health monitoring."""
    return {"status": "healthy", "environment": os.getenv("ENVIRONMENT", "development")}
