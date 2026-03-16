import pytest

from core.vps_langgraph.external_workflows import (
    ExternalWorkflowPlan,
    detect_external_workflow,
    run_external_workflow,
)


class _FakeRegistry:
    def __init__(self, outputs):
        self.outputs = outputs
        self.executed = []

    async def execute_skill(self, name, args):
        self.executed.append((name, args))
        return self.outputs[name]


class _FakeSyncManager:
    def __init__(self, preferred=None, use_preferred_tools=True):
        self._preferred = preferred or {}
        self._use_preferred_tools = use_preferred_tools

    def should_use_preferred_tools(self, service):
        return self._use_preferred_tools and bool(self._preferred.get(service))

    def preferred_tools_for(self, service):
        return self._preferred.get(service, [])


def test_detect_external_workflow_for_combined_prompt(monkeypatch):
    monkeypatch.setattr(
        "core.vps_langgraph.external_workflows.get_consumer_sync_manager",
        lambda: _FakeSyncManager(),
    )

    plan = detect_external_workflow(
        "Use BrazilCNPJ Enricher para validar este CNPJ (48.430.290/0001-30), "
        "mostrar socios, grupo economico e me dizer sobre ela, depois use o "
        "FleetIntel Orchestrator para falar da frota e o FleetIntel Analyst para me dar insights."
    )

    assert plan == ExternalWorkflowPlan(
        kind="account_360_plus_insights",
        steps=("fleetintel_orchestrator", "fleetintel_analyst"),
        response_mode="single_answer",
        provider_composite_tool=None,
    )


@pytest.mark.asyncio
async def test_run_external_workflow_combines_skill_outputs():
    registry = _FakeRegistry(
        {
            "fleetintel_orchestrator": "FleetIntel Orchestrator\n\nLeitura de frota:\n- empresa: ADDIANTE",
            "fleetintel_analyst": "FleetIntel\n\nLeitura de mercado:\n- movimento relevante",
        }
    )
    result = await run_external_workflow(
        message="cruze cnpj e frota e me de insights",
        registry=registry,
        plan=ExternalWorkflowPlan(
            kind="account_360_plus_insights",
            steps=("fleetintel_orchestrator", "fleetintel_analyst"),
            response_mode="single_answer",
        ),
    )

    assert "Visao consolidada:" in result
    assert "Conta e cadastro:" in result
    assert "Insights de mercado:" in result
    assert "Leitura de frota:" in result
    assert "Leitura de mercado:" in result
    assert registry.executed == [
        (
            "fleetintel_orchestrator",
            {
                "raw_input": "cruze cnpj e frota e me de insights",
                "query": "cruze cnpj e frota e me de insights",
            },
        ),
        (
            "fleetintel_analyst",
            {
                "raw_input": "cruze cnpj e frota e me de insights",
                "query": "cruze cnpj e frota e me de insights",
            },
        ),
    ]


def test_detect_external_workflow_marks_provider_composite_when_available(monkeypatch):
    monkeypatch.setattr(
        "core.vps_langgraph.external_workflows.get_consumer_sync_manager",
        lambda: _FakeSyncManager({"fleetintel": ["get_account_360_brief"]}),
    )

    plan = detect_external_workflow(
        "Use BrazilCNPJ Enricher para validar o CNPJ 48.430.290/0001-30 e fale da frota."
    )

    assert plan is not None
    assert plan.provider_composite_tool == "get_account_360_brief"
