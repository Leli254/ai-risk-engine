"""
AI Risk Assessment Pipeline.

This module implements a two-pass "Isolation Pattern":
Pass 1: Structured Extraction - Sanitizes and extracts raw data from unstructured text.
Pass 2: Risk Scoring - Evaluates risk based strictly on the extracted signals.

Design Pattern: Lazy Initialization and Retry Logic.
"""

import os
import structlog
from typing import Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from schemas import ApplicationRequest, ExtractedSignals, RiskScore

logger = structlog.get_logger()

# --- LAZY INITIALIZATION ---
# We define a global placeholder but don't initialize it yet.
_openai_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """
    Returns a thread-safe OpenAI client instance using lazy initialization.
    Ensures that environment variables (like API keys) are accessed only
    when needed, preventing startup crashes.
    """
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error(
                "OPENAI_API_KEY is missing from environment variables.")
            raise ValueError("OpenAI API Key not configured.")

        _openai_client = OpenAI(api_key=api_key)
    return _openai_client

# --- PIPELINE PHASES ---


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def pass_one_extract(request: ApplicationRequest) -> ExtractedSignals:
    """
    Pass 1: Structured Data Extraction.
    Uses OpenAI Beta Structured Outputs to enforce a Pydantic schema on the raw text.
    """
    client = get_client()
    logger.info("pipeline_pass_one_started",
                application_id=request.application_id)

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Extract financial signals from text. Focus on income, debt, and stability. Return JSON only."
            },
            {"role": "user", "content": request.text}
        ],
        response_format=ExtractedSignals,
        temperature=0,  # Deterministic output for financial extraction
    )

    return completion.choices[0].message.parsed


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=6),
    reraise=True
)
def pass_two_score(signals: ExtractedSignals, application_id: str) -> RiskScore:
    """
    Pass 2: Analytical Scoring.
    Evaluates risk based ONLY on the structured output of Pass 1. 
    This prevents the model from being distracted by irrelevant text in the original request.
    """
    client = get_client()
    logger.info("pipeline_pass_two_started", application_id=application_id)

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a senior credit analyst. Score risk (0-100) based strictly on signals."
            },
            {"role": "user", "content": signals.model_dump_json()}
        ],
        response_format=RiskScore,
        temperature=0,
    )

    return completion.choices[0].message.parsed


def run_pipeline(request: ApplicationRequest) -> RiskScore:
    """
    Orchestrates the extraction and scoring phases.
    This function is the single entry point for the AI logic.
    """
    try:
        # Pass 1: Extraction
        signals = pass_one_extract(request)

        # Pass 2: Scoring
        result = pass_two_score(signals, request.application_id)

        return result
    except Exception as e:
        logger.error("pipeline_execution_failed",
                     application_id=request.application_id,
                     error=str(e))
        raise
