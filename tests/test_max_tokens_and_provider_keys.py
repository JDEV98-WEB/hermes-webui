"""Regression tests for max-output-token budgeting and provider key mapping.

Two production-critical behaviours called out in the deployment hardening audit:

1. Model output budget (mandate #4): a configured ``max_tokens`` must cap the
   effective output budget and a bogus value must be rejected without corrupting
   the stored config or crashing the Settings write path.
2. Provider credentials (mandate #4): the canonical provider -> env-var key map
   must be stable and must NOT cover OAuth/token-flow providers whose keys the
   WebUI cannot manage (so Settings never falsely reports them as "configured").

State is isolated to a temp HERMES_WEBUI_STATE_DIR so the real profile
config.yaml is never touched.
"""
import importlib
import os
import sys
import tempfile
from pathlib import Path

_TEST_STATE = Path(tempfile.mkdtemp())
os.environ["HERMES_WEBUI_STATE_DIR"] = str(_TEST_STATE)

sys.path.insert(0, str(Path(__file__).parent.parent))

import api.config as config  # noqa: E402

importlib.reload(config)  # pick up isolated state dir


def test_get_max_tokens_status_default_is_none():
    status = config.get_max_tokens_status()
    assert status["max_tokens"] is None
    # effective resolves to the agent fallback (None when unset)
    assert "max_tokens_effective" in status
    assert "max_tokens_fallback" in status


def test_set_max_tokens_round_trip():
    try:
        out = config.set_max_tokens(2048)
        assert out["max_tokens"] == 2048
        assert out["max_tokens_effective"] == 2048

        again = config.get_max_tokens_status()
        assert again["max_tokens"] == 2048
    finally:
        config.set_max_tokens("")  # clear override


def test_set_max_tokens_rejects_negative_and_non_int():
    # Precondition: ensure a known good value first, then feed garbage.
    config.set_max_tokens(1024)
    try:
        # A negative number is not a positive int -> rejected, status unchanged.
        out = config.set_max_tokens(-5)
        assert out["max_tokens"] == 1024
        # A non-numeric string -> rejected, status unchanged (no crash).
        out2 = config.set_max_tokens("not-a-number")
        assert out2["max_tokens"] == 1024
    finally:
        config.set_max_tokens("")  # clear override


def test_set_max_tokens_zero_is_rejected_not_cleared():
    # 0 is neither a valid positive budget nor the clear sentinel (None/""),
    # so it must be rejected and leave the existing override untouched.
    config.set_max_tokens(4096)
    rejected = config.set_max_tokens(0)
    assert rejected["max_tokens"] == 4096
    # Only None/"" clears the root override.
    cleared = config.set_max_tokens("")
    assert cleared["max_tokens"] is None


def test_provider_env_var_map_covers_known_providers():
    from api.providers import _PROVIDER_ENV_VAR

    assert _PROVIDER_ENV_VAR["openrouter"] == "OPENROUTER_API_KEY"
    assert _PROVIDER_ENV_VAR["anthropic"] == "ANTHROPIC_API_KEY"
    assert _PROVIDER_ENV_VAR["openai"] == "OPENAI_API_KEY"
    assert _PROVIDER_ENV_VAR["google"] == "GOOGLE_API_KEY"
    assert _PROVIDER_ENV_VAR["ollama-cloud"] == "OLLAMA_API_KEY"
    # Local Ollama is keyless by default and must not be mapped here.
    assert "ollama" not in _PROVIDER_ENV_VAR or _PROVIDER_ENV_VAR.get("ollama") != "OLLAMA_API_KEY"


def test_oauth_providers_not_in_env_var_map():
    """The WebUI cannot manage OAuth/token-flow keys; never report them as
    API-key configurable."""
    from api.providers import _OAUTH_PROVIDERS, _PROVIDER_ENV_VAR

    for pid in _OAUTH_PROVIDERS:
        assert pid not in _PROVIDER_ENV_VAR, (
            f"{pid} is an OAuth provider whose key the WebUI cannot manage, "
            "but it appears in the env-var key map"
        )
