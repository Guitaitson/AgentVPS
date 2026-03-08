from dataclasses import dataclass

import pytest

from core.orchestration import RuntimeExecutionResult, RuntimeProtocol
from core.vps_langgraph import nodes


@dataclass
class _DummySkill:
    name: str


class _DummyRegistry:
    def __init__(self, known_action: str | None = None):
        self._known_action = known_action

    def get(self, name: str):
        if self._known_action and name == self._known_action:
            return _DummySkill(name=name)
        return None

    def find_by_trigger(self, _text: str):
        return None

    def list_skills(self):
        return []


class _CapturingRouter:
    def __init__(self, result: RuntimeExecutionResult):
        self.result = result
        self.last_request = None

    async def dispatch(self, request):
        self.last_request = request
        return self.result


class _FakeMemory:
    def search_semantic_memory(self, *, user_id: str, query_text: str, project_id=None, limit=3):
        return [
            {
                "key": "semantic:1",
                "text": f"recall:{query_text}",
                "score": 0.77,
                "project_id": project_id,
            }
        ]


def _base_state():
    return {
        "user_id": "u-1",
        "user_message": "execute command",
        "blocked_by_security": False,
        "plan": [],
        "current_step": 0,
        "tool_suggestion": "",
        "intent": "task",
        "user_context": {"profile": "alpha"},
        "conversation_history": [],
    }


@pytest.mark.asyncio
async def test_node_execute_dispatches_plan_action_to_runtime_router(monkeypatch):
    router = _CapturingRouter(
        RuntimeExecutionResult(
            success=True,
            output="ok-remote",
            runtime=RuntimeProtocol.MCP,
            latency_ms=5,
        )
    )
    state = _base_state()
    state["plan"] = [
        {
            "type": "skill",
            "action": "remote_lookup",
            "args": {"query": "status"},
            "protocol": "mcp",
            "context_keys": ["intent", "user_message"],
        }
    ]

    monkeypatch.setattr("core.orchestration.router_factory.get_runtime_router", lambda: router)
    monkeypatch.setattr(nodes, "get_skill_registry", lambda: _DummyRegistry())

    result = await nodes.node_execute(state)

    assert result["execution_result"] == "ok-remote"
    assert router.last_request is not None
    assert router.last_request.preferred_protocol == RuntimeProtocol.MCP
    assert router.last_request.context_keys == ["intent", "user_message"]


@pytest.mark.asyncio
async def test_node_execute_fallbacks_to_local_when_remote_fails(monkeypatch):
    router = _CapturingRouter(
        RuntimeExecutionResult(
            success=False,
            output=None,
            runtime=RuntimeProtocol.MCP,
            latency_ms=8,
            error="remote unavailable",
        )
    )
    state = _base_state()
    state["plan"] = [
        {
            "type": "skill",
            "action": "shell_exec",
            "args": {"command": "whoami"},
            "runtime": "mcp",
        }
    ]

    async def _fake_execute_with_hooks(_registry, _skill_name, _skill_args, _user_id):
        return "local-fallback-ok", None

    monkeypatch.setattr("core.orchestration.router_factory.get_runtime_router", lambda: router)
    monkeypatch.setattr(
        nodes, "get_skill_registry", lambda: _DummyRegistry(known_action="shell_exec")
    )
    monkeypatch.setattr(nodes, "_execute_with_hooks", _fake_execute_with_hooks)

    result = await nodes.node_execute(state)

    assert result["execution_result"] == "local-fallback-ok"


@pytest.mark.asyncio
async def test_node_execute_includes_semantic_recall_in_runtime_context(monkeypatch):
    router = _CapturingRouter(
        RuntimeExecutionResult(
            success=True,
            output="ok-remote",
            runtime=RuntimeProtocol.MCP,
            latency_ms=5,
        )
    )
    state = _base_state()
    state["plan"] = [
        {
            "type": "skill",
            "action": "remote_lookup",
            "args": {"query": "status"},
            "protocol": "mcp",
        }
    ]

    monkeypatch.setattr("core.orchestration.router_factory.get_runtime_router", lambda: router)
    monkeypatch.setattr(nodes, "get_skill_registry", lambda: _DummyRegistry())
    monkeypatch.setattr(nodes, "memory", _FakeMemory())

    result = await nodes.node_execute(state)

    assert result["execution_result"] == "ok-remote"
    assert router.last_request is not None
    assert router.last_request.context["semantic_recall"][0]["text"] == "recall:execute command"
