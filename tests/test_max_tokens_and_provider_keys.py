"""Regression tests for max-output-token budgeting and provider key mapping.

Two production-critical behaviours called out in the deployment hardening audit:

1. Model output budget (mandate #4): a configured ``max_tokens`` must cap the
   effective output budget and a bogus value must be rejected without corrupting
   the stored config or crashing the Settings write path.
2. Provider credentials (mandate #4): the canonical provider -> env-var key map
   must be stable and must NOT cover OAuth/token-flow providers whose keys the
   WebUI cannot manage (so Settings never falsely reports them as "configured").

Config writes are isolated to a temp config.yaml via HERMES_CONFIG_PATH so the
real profile config is never touched and no shared module state leaks into other
tests.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import api.config as config  # noqa: E402
from api.providers import _OAUTH_PROVIDERS, _PROVIDER_ENV_VAR  # noqa: E402


def _isolated_config(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "config.yaml"
    tmp.write_text("{}\n")  # start from an empty valid config
    monkeypatch.setenv("HERMES_CONFIG_PATH", str(tmp))
    return tmp


def test_get_max_tokens_status_default_is_none(monkeypatch):
    _isolated_config(monkeypatch)
    status = config.get_max_tokens_status()
    assert status["max_tokens"] is None
    assert "max_tokens_effective" in status
    assert "max_tokens_fallback" in status


def test_set_max_tokens_round_trip(monkeypatch):
    cfg = _isolated_config(monkeypatch)
    try:
        out = config.set_max_tokens(2048)
        assert out["max_tokens"] == 2048
        assert out["max_tokens_effective"] == 2048
        again = config.get_max_tokens_status()
        assert again["max_tokens"] == 2048
    finally:
        config.set_max_tokens("")


def test_set_max_tokens_rejects_negative_and_non_int(monkeypatch):
    cfg = _isolated_config(monkeypatch)
    try:
        config.set_max_tokens(1024)
        # Negative is not a positive int -> rejected, status unchanged.
        out = config.set_max_tokens(-5)
        assert out["max_tokens"] == 1024
        # Non-numeric string -> rejected, status unchanged (no crash).
        out2 = config.set_max_tokens("not-a-number")
        assert out2["max_tokens"] == 1024
    finally:
        config.set_max_tokens("")


def test_set_max_tokens_zero_is_rejected_not_cleared(monkeypatch):
    # 0 is neither a valid positive budget nor the clear sentinel (None/""),
    # so it must be rejected and leave the existing override untouched.
    _isolated_config(monkeypatch)
    config.set_max_tokens(4096)
    rejected = config.set_max_tokens(0)
    assert rejected["max_tokens"] == 4096
    # Only None/"" clears the root override.
    cleared = config.set_max_tokens("")
    assert cleared["max_tokens"] is None


def test_provider_env_var_map_covers_known_providers():
    assert _PROVIDER_ENV_VAR["openrouter"] == "OPENROUTER_API_KEY"
    assert _PROVIDER_ENV_VAR["anthropic"] == "ANTHROPIC_API_KEY"
    assert _PROVIDER_ENV_VAR["openai"] == "OPENAI_API_KEY"
    assert _PROVIDER_ENV_VAR["google"] == "GOOGLE_API_KEY"
    assert _PROVIDER_ENV_VAR["ollama-cloud"] == "OLLAMA_API_KEY"
    # Local Ollama is keyless by default and must not be mapped to OLLAMA_API_KEY.
    assert "ollama" not in _PROVIDER_ENV_VAR or _PROVIDER_ENV_VAR.get("ollama") != "OLLAMA_API_KEY"


def test_oauth_providers_not_in_env_var_map():
    """The WebUI cannot manage OAuth/token-flow keys; never report them as
    API-key configurable."""
    for pid in _OAUTH_PROVIDERS:
        assert pid not in _PROVIDER_ENV_VAR, (
            f"{pid} is an OAuth provider whose key the WebUI cannot manage, "
            "but it appears in the env-var key map"
        )
