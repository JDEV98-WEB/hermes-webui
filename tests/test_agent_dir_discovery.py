"""Regression tests for bootstrap.discover_agent_dir().

The WebUI resolves the Hermes Agent source directory to locate run_agent.py,
the agent config, and the CLI.

Two guarantees are tested:
- HERMES_WEBUI_AGENT_DIR is honoured when it points at a valid agent tree
  (override path, fully hermetic).
- The single-container / PaaS baked location /opt/hermes is a discovery
  candidate (verified statically from the source so it has zero filesystem
  side effects and cannot pollute sibling tests).

Isolated via a temp agent dir + HERMES_WEBUI_AGENT_DIR so no real install is
touched.
"""
import importlib
import inspect
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import bootstrap  # noqa: E402

importlib.reload(bootstrap)


def _make_agent_dir(root: Path) -> Path:
    (root / "run_agent.py").write_text("# placeholder agent entrypoint\n")
    return root


def test_discover_honours_agent_dir_override(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "my-agent"
    tmp.mkdir(parents=True)
    _make_agent_dir(tmp)
    monkeypatch.setenv("HERMES_WEBUI_AGENT_DIR", str(tmp))
    monkeypatch.delenv("HERMES_HOME", raising=False)
    found = bootstrap.discover_agent_dir()
    assert found is not None
    assert Path(found) == tmp.resolve()


def test_opt_hermes_is_discovery_candidate():
    """The baked single-container / PaaS agent location must be a discovery
    candidate so a Render-style image (agent baked into /opt/hermes, no agent
    volume mounted) actually resolves the agent directory at runtime.

    Checked statically from the function source to avoid touching the real
    filesystem (which would leak into sibling tests' agent discovery).
    """
    source = inspect.getsource(bootstrap.discover_agent_dir)
    assert '"/opt/hermes"' in source
