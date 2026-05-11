import pytest
from decimal import Decimal
from pipeline import run_pipeline
from schemas import ApplicationRequest, ExtractedSignals, RiskScore, RiskLevel


def test_pipeline_success_flow(mocker):
    """
    Tests the happy path where Pass 1 and Pass 2 return valid data.
    """
    # 1. Mock Pass 1 (Extraction)
    mock_signals = ExtractedSignals(
        sentiment="neutral",
        monthly_income_usd=Decimal("15000.00"),
        mentions_debt=False,
        stated_employment="Senior Engineer",
        loan_purpose="Investment"
    )
    mocker.patch("pipeline.pass_one_extract", return_value=mock_signals)

    # 2. Mock Pass 2 (Scoring)
    mock_score = RiskScore(
        application_id="MIKE-001",
        score=10,
        risk_level=RiskLevel.LOW,
        reasoning="Strong income and no debt. High stability signals detected."
    )
    mocker.patch("pipeline.pass_two_score", return_value=mock_score)

    # 3. Execute
    request = ApplicationRequest(
        application_id="MIKE-001",
        text="Senior Engineer, 15k income, no debt."
    )
    result = run_pipeline(request)

    # 4. Assertions
    assert result.score == 10
    assert result.risk_level == RiskLevel.LOW
    assert result.application_id == "MIKE-001"


def test_pipeline_retry_on_failure(mocker):
    """
    Tests that the @retry decorator triggers on API failures.
    We mock the OpenAI client call to force an exception.
    """
    # We mock the client factory so the @retry decorator on the
    # original function stays intact and active.
    mock_get_client = mocker.patch("pipeline.get_client")
    mock_client = mock_get_client.return_value

    # Force the OpenAI parse call to raise the quota error we saw earlier
    mock_client.beta.chat.completions.parse.side_effect = Exception(
        "insufficient_quota")

    request = ApplicationRequest(application_id="ERR-001", text="Sample text")

    # We expect the pipeline to eventually raise the exception after retries
    with pytest.raises(Exception) as excinfo:
        run_pipeline(request)

    assert "insufficient_quota" in str(excinfo.value)

    # Verification: Tenacity default is usually 3 attempts.
    # If this is > 1, the retry logic is working!
    actual_calls = mock_client.beta.chat.completions.parse.call_count
    assert actual_calls > 1, f"Expected retries, but only saw {actual_calls} call(s)."
