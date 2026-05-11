"""
Data models for the AI Risk Scorer pipeline.

This module defines the structured contracts for loan applications, 
intermediate extraction signals, and final risk assessments.
"""

from enum import Enum
from decimal import Decimal
from typing import Literal, Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- SHARED TYPES & CONSTANTS ---

# Common field for application IDs to ensure consistent validation across models
AppID = Annotated[str, Field(..., min_length=1, examples=["APP-12345"])]


class RiskLevel(str, Enum):
    """Categorical classification of credit risk."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PaymentStatus(str, Enum):
    """Lifecycle states of a payment transaction."""
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    NOT_FOUND = "not_found"

# --- MODELS ──────────────────────────────────────────────────────────────────


class ApplicationRequest(BaseModel):
    """
    Initial entry point for raw loan application text.
    """
    model_config = ConfigDict(frozen=True)

    application_id: AppID
    text: str = Field(...,
                      description="The raw free-text loan application content.")


class ExtractedSignals(BaseModel):
    """
    The 'Data Firewall' model.
    Output of Pass 1 (Extraction). Sanitizes raw text into structured signals.
    """
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    monthly_income_usd: Optional[Decimal] = Field(
        None, ge=0, description="Applicant's monthly income in USD."
    )
    stated_employment: Optional[str] = Field(
        None, max_length=100, description="Job title or employment status."
    )
    loan_purpose: Optional[str] = Field(
        None, max_length=200, description="Primary use of requested funds."
    )
    mentions_debt: bool = Field(
        default=False, description="Presence of existing liabilities mentioned in text."
    )
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        ..., description="Sentiment analysis of the application tone."
    )

    @field_validator("monthly_income_usd", mode="before")
    @classmethod
    def handle_empty_values(cls, v):
        """Standardizes LLM 'empty' outputs to None."""
        if v in ("", None, "N/A", "null"):
            return None
        return v


class RiskScore(BaseModel):
    """
    The output of Pass 2 (Scoring). 
    Final analytical result of the risk engine.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    application_id: AppID
    score: int = Field(
        ..., ge=0, le=100, description="Risk probability (100 = critical risk)."
    )
    risk_level: RiskLevel
    reasoning: str = Field(
        ..., min_length=20, description="Qualitative justification for the score."
    )


class PaymentRequest(BaseModel):
    """Client request to initiate the payment lifecycle."""
    application_id: AppID
    email: str = Field(..., pattern=r"^\S+@\S+\.\S+$",
                       examples=["user@example.com"])
    amount_usd: Decimal = Field(default=Decimal("15.00"), ge=0)


class PaymentIntent(BaseModel):
    """
    Stripe transaction metadata returned to the client.
    """
    application_id: AppID
    payment_intent_id: str = Field(...,
                                   description="The Stripe 'pi_...' identifier.")
    client_secret: str = Field(...,
                               description="Secret used by the frontend to complete payment.")
    amount_usd: Decimal
    status: PaymentStatus = PaymentStatus.PENDING


class AssessmentResult(BaseModel):
    """
    Unified polling response. 
    Combines payment state and (if available) the AI risk score.
    """
    application_id: AppID
    payment_status: PaymentStatus
    risk_score: Optional[RiskScore] = None
    message: str = Field(...,
                         description="Status message for frontend display.")
