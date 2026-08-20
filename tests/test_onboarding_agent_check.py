"""Regression tests for the first-run system check's agent import probe.

Reliability / first-run mandate: the onboarding system check must actually test
that the Hermes Agent runtime is importable (verify_hermes_imports), so a broken
or missing agent surfaces as an actionable onboarding state instead of a silent
chat failure. This guards that contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import api.config as config  # noqa: E402


def test_verify_hermes_imports_returns_three_tuple():
    result = config.verify_hermes_imports()
    assert isinstance(result, tuple) and len(result) == 3
    ok, missing, errors = result
    assert isinstance(ok, bool)
    assert isinstance(missing, list)
    assert isinstance(errors, dict)


def test_verify_hermes_imports_detects_agent():
    # When run_agent (the agent runtime) is importable, the probe reports ok and
    # no missing modules. On the baked single-container image docker_init.bash
    # installs run_agent into the venv, so this is the expected deploy state.
    ok, missing, errors = config.verify_hermes_imports()
    assert ok is True
    assert "run_agent" not in missing
    assert "run_agent" not in errors
