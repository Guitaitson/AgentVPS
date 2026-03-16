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
        return object() if name in {"fleetintel_analyst", "fleetintel_orchestrator"} else None

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


class _NoCodexRouter:
    def has_protocol(self, protocol):
        return False

    async def dispatch(self, request):  # pragma: no cover - defensive
        raise AssertionError(f"unexpected dispatch: {request}")


class _DegradedAssessment:
    healthy = False
    snapshots = ()


class _HealthyAssessment:
    healthy = True
    snapshots = ()


async def _healthy_assessment(*_args, **_kwargs):
    return _HealthyAssessment()


async def _degraded_assessment(*_args, **_kwargs):
    return _DegradedAssessment()


@pytest.mark.asyncio
async def test_node_react_prefers_codex_operator_for_complex_specialist_queries(monkeypatch):
    registry = _FakeRegistry()

    monkeypatch.setattr("core.vps_langgraph.react_node.get_skill_registry", lambda: registry)
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.detect_external_skill",
        lambda _message: "fleetintel_analyst",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.select_codex_execution_mode",
        lambda _message, _skill: "codex_operator",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.get_runtime_router",
        lambda: _FakeRouter(),
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.assess_specialist_health",
        _healthy_assessment,
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


@pytest.mark.asyncio
async def test_node_react_executes_specialist_directly_when_explicit_skill_bypasses_codex(
    monkeypatch,
):
    registry = _FakeRegistry()

    monkeypatch.setattr("core.vps_langgraph.react_node.get_skill_registry", lambda: registry)
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.detect_external_skill",
        lambda _message: "fleetintel_orchestrator",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.select_codex_execution_mode",
        lambda _message, _skill: "direct_local",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.get_external_skill_contract",
        lambda _skill: type(
            "Contract",
            (),
            {
                "external_name": "fleetintel-orchestrator",
                "version": "abc123",
                "execution_mode": "specialist_response",
                "response_owner": "specialist",
                "raw_output_policy": "on_user_request",
                "description": "x",
            },
        )(),
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.get_runtime_router",
        lambda: _FakeRouter(),
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.assess_specialist_health",
        _healthy_assessment,
    )

    state = {
        "user_id": "u-1",
        "user_message": "Use o FleetIntel Orchestrator para cruzar frota e CNPJ e me responder.",
        "conversation_history": [],
    }

    result = await node_react(state)

    assert result["response"] == "local specialist"
    assert registry.executed == [
        (
            "fleetintel_orchestrator",
            {
                "raw_input": "Use o FleetIntel Orchestrator para cruzar frota e CNPJ e me responder.",
                "query": "Use o FleetIntel Orchestrator para cruzar frota e CNPJ e me responder.",
            },
        )
    ]


@pytest.mark.asyncio
async def test_node_react_uses_codex_synthesizer_for_explicit_insight_queries(monkeypatch):
    registry = _FakeRegistry()

    monkeypatch.setattr("core.vps_langgraph.react_node.get_skill_registry", lambda: registry)
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.detect_external_skill",
        lambda _message: "fleetintel_analyst",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.select_codex_execution_mode",
        lambda _message, _skill: "codex_synthesizer",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.wants_raw_specialist_output",
        lambda _message: False,
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.get_external_skill_contract",
        lambda _skill: type(
            "Contract",
            (),
            {
                "external_name": "fleetintel-analyst",
                "version": "abc123",
                "execution_mode": "specialist_response",
                "response_owner": "specialist",
                "raw_output_policy": "on_user_request",
                "description": "x",
            },
        )(),
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.get_runtime_router",
        lambda: _FakeRouter(),
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.assess_specialist_health",
        _healthy_assessment,
    )

    state = {
        "user_id": "u-1",
        "user_message": "Use o FleetIntel Analyst para me dar os latest insights do FleetIntel.",
        "conversation_history": [],
    }

    result = await node_react(state)

    assert "Resposta sintetizada pelo Codex." in result["response"]
    assert "Pontos principais:" in result["response"]
    assert registry.executed == [
        (
            "fleetintel_analyst",
            {
                "raw_input": "Use o FleetIntel Analyst para me dar os latest insights do FleetIntel.",
                "query": "Use o FleetIntel Analyst para me dar os latest insights do FleetIntel.",
            },
        )
    ]


@pytest.mark.asyncio
async def test_node_react_hides_raw_payload_when_synthesizer_unavailable(monkeypatch):
    registry = _FakeRegistry()

    monkeypatch.setattr("core.vps_langgraph.react_node.get_skill_registry", lambda: registry)
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.detect_external_skill",
        lambda _message: "fleetintel_analyst",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.select_codex_execution_mode",
        lambda _message, _skill: "codex_synthesizer",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.wants_raw_specialist_output",
        lambda _message: False,
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.get_external_skill_contract",
        lambda _skill: type(
            "Contract",
            (),
            {
                "external_name": "fleetintel-analyst",
                "version": "abc123",
                "execution_mode": "specialist_response",
                "response_owner": "specialist",
                "raw_output_policy": "on_user_request",
                "description": "x",
            },
        )(),
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.get_runtime_router",
        lambda: _NoCodexRouter(),
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.assess_specialist_health",
        _healthy_assessment,
    )

    state = {
        "user_id": "u-1",
        "user_message": "Use o FleetIntel Analyst para me dar os latest insights do FleetIntel.",
        "conversation_history": [],
    }

    result = await node_react(state)

    assert "nao vou despejar json cru" in result["response"].lower()
    assert registry.executed == [
        (
            "fleetintel_analyst",
            {
                "raw_input": "Use o FleetIntel Analyst para me dar os latest insights do FleetIntel.",
                "query": "Use o FleetIntel Analyst para me dar os latest insights do FleetIntel.",
            },
        )
    ]


@pytest.mark.asyncio
async def test_node_react_fail_fast_when_specialist_health_is_degraded(monkeypatch):
    registry = _FakeRegistry()
    progress_calls = []

    async def _emit_failure_progress(_assessment):
        progress_calls.append("emitted")

    monkeypatch.setattr("core.vps_langgraph.react_node.get_skill_registry", lambda: registry)
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.detect_external_skill",
        lambda _message: "fleetintel_orchestrator",
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.get_runtime_router",
        lambda: _FakeRouter(),
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.assess_specialist_health",
        _degraded_assessment,
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.emit_health_failure_progress",
        _emit_failure_progress,
    )
    monkeypatch.setattr(
        "core.vps_langgraph.react_node.format_specialist_health_failure",
        lambda _assessment: "Especialista externo indisponivel no momento.",
    )

    state = {
        "user_id": "u-1",
        "user_message": "Use o FleetIntel Orchestrator para cruzar frota e CNPJ e me responder.",
        "conversation_history": [],
    }

    result = await node_react(state)

    assert result["response"] == "Especialista externo indisponivel no momento."
    assert registry.executed == []
    assert progress_calls == ["emitted"]
