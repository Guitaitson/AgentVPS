import pytest

from core.orchestration import RuntimeExecutionResult, RuntimeProtocol
from core.vps_langgraph.react_node import node_react


class _FakeRegistry:
    def __init__(self):
        self.executed = []

    def list_tool_schemas(self):
        return []

    def list_skills(self):
        return []

    def get(self, name):
        return object() if name == "fleetintel_analyst" else None

    async def execute_skill(self, name, args):
        self.executed.append((name, args))
        return "local specialist"


class _FakeRouter:
    def has_protocol(self, protocol):
        return protocol == RuntimeProtocol.CODEX_OPERATOR

    async def dispatch(self, request):
        return RuntimeExecutionResult(
            success=True,
            output={
                "summary": "ok",
                "answer": "Resposta sintetizada pelo Codex.",
                "confidence": 0.88,
                "facts": ["Fato 1", "Fato 2"],
                "tool_trace": [{"tool": "fleetintel_analyst", "status": "ok"}],
                "unresolved_items": [],
                "requires_human_approval": False,
            },
            runtime=RuntimeProtocol.CODEX_OPERATOR,
            latency_ms=10,
        )


@pytest.mark.asyncio
async def test_node_react_prefers_codex_operator_for_complex_specialist_queries(monkeypatch):
    registry = _FakeRegistry()

    monkeypatch.setattr("core.vps_langgraph.react_node.get_skill_registry", lambda: registry)
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.detect_external_skill",
        lambda _message: "fleetintel_analyst",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.should_delegate_specialist_to_codex",
        lambda _message, _skill: True,
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.get_runtime_router",
        lambda: _FakeRouter(),
    )

    state = {
        "user_id": "u-1",
        "user_message": "Use o FleetIntel para analisar o CNPJ 23.373.000/0001-32 e resumir sinais relevantes.",
        "conversation_history": [],
    }

    result = await node_react(state)

    assert "Operador Codex" in result["response"]
    assert "Resposta sintetizada pelo Codex." in result["response"]
    assert registry.executed == []
