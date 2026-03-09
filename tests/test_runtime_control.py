import pytest

from core.config import get_settings
from core.orchestration.runtime_control import RuntimeControl


def _disable_redis(control: RuntimeControl):
    control._redis = None
    control._local_overrides = {}


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_runtime_control_lists_defaults(monkeypatch):
    monkeypatch.setenv("ORCH_ENABLE_MCP", "true")
    monkeypatch.setenv("ORCH_ENABLE_A2A", "false")
    monkeypatch.setenv("ORCH_ENABLE_ACP", "false")
    monkeypatch.setenv("ORCH_ENABLE_DEEPAGENTS", "false")
    monkeypatch.setenv("ORCH_ENABLE_OPENCLAW", "false")

    control = RuntimeControl()
    _disable_redis(control)

    states = {state.protocol: state for state in control.list_states()}

    assert states["local_skills"].enabled is True
    assert states["mcp"].enabled is True
    assert states["a2a"].enabled is False


def test_runtime_control_enable_disable_override(monkeypatch):
    monkeypatch.setenv("ORCH_ENABLE_MCP", "false")

    control = RuntimeControl()
    _disable_redis(control)

    assert control.is_enabled("mcp") is False

    enabled = control.set_enabled("mcp", True)
    assert enabled["success"] is True
    assert control.is_enabled("mcp") is True

    disabled = control.set_enabled("mcp", False)
    assert disabled["success"] is True
    assert control.is_enabled("mcp") is False


def test_runtime_control_rejects_local_disable():
    control = RuntimeControl()
    _disable_redis(control)

    result = control.set_enabled("local_skills", False)
    assert result["success"] is False
