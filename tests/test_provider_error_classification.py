"""Regression tests for streaming._classify_provider_error.

Reliability mandate: every external dependency failure (invalid key, out of
credits, rate limit, model not found, credential-pool exhaustion,
cancellation, silent no-response) must surface as an *actionable* user-facing
error rather than a generic crash. This unit owns that mapping.

Pure function, no network / agent required.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import streaming  # noqa: E402


def _label(err_str, exc=None, **kw):
    return streaming._classify_provider_error(err_str, exc=exc, **kw)


def test_invalid_api_key_is_auth_mismatch():
    out = _label("openai error: invalid_api_key (HTTP 401)")
    assert out["type"] == "auth_mismatch"
    assert "API key" in out["hint"] or "credentials" in out["hint"]


def test_401_status_code_is_auth_mismatch():
    out = _label("Authentication failed", exc=RuntimeError("401 Unauthorized"))
    assert out["type"] == "auth_mismatch"


def test_out_of_credits_is_quota_exhausted():
    out = _label("You have insufficient credit balance to complete this request")
    assert out["type"] == "quota_exhausted"
    assert "credits" in out["hint"].lower()


def test_rate_limit_is_rate_limit():
    out = _label("Rate limit reached, please slow down (429)")
    assert out["type"] == "rate_limit"


def test_model_not_found_is_model_not_found():
    out = _label("The model gpt-nonexistent does not exist")
    assert out["type"] == "model_not_found"
    assert "model" in out["hint"].lower()


def test_credential_pool_empty_is_distinct_from_quota():
    # Must NOT be classified as quota_exhausted (that is account/plan credits,
    # a different problem). See #3929.
    out = _label("All 0 credential(s) exhausted for openrouter")
    assert out["type"] == "credential_pool_empty"
    assert "credential" in out["hint"].lower()


def test_cancellation_is_cancelled_type():
    out = _label("task cancelled by user")
    assert out["type"] == "cancelled"


def test_silent_failure_no_response():
    out = _label("", silent_failure=True)
    assert out["type"] == "no_response"
    assert out["hint"]


def test_unknown_error_falls_through_to_generic():
    out = _label("some totally opaque failure with no known signature")
    assert out["type"] == "error"
