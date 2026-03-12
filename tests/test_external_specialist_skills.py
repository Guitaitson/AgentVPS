import pytest

from core.integrations import detect_external_skill
from core.skills._builtin.brazilcnpj.handler import BrazilCNPJSkill
from core.skills._builtin.fleetintel_analyst.handler import FleetIntelAnalystSkill
from core.skills._builtin.fleetintel_orchestrator.handler import FleetIntelOrchestratorSkill
from core.skills.base import SecurityLevel, SkillConfig


def _config(name: str) -> SkillConfig:
    return SkillConfig(name=name, description=name, security_level=SecurityLevel.SAFE)


def test_detect_external_skill_routes():
    assert detect_external_skill("enriquece este cnpj 12345678000199") == "brazilcnpj"
    assert detect_external_skill("quais contas devo priorizar por sinais de compra?") == (
        "fleetintel_analyst"
    )
    assert detect_external_skill("cruze sinais de compra com cnpj das contas") == (
        "fleetintel_orchestrator"
    )


@pytest.mark.asyncio
async def test_brazilcnpj_skill_routes_socios(monkeypatch):
    calls = []

    async def fake_call(self, tool_name, arguments=None):
        calls.append((self.server_name, tool_name, arguments or {}))
        return {"socios": [{"nome": "Fulano"}]}

    monkeypatch.setattr(
        "core.skills._builtin.brazilcnpj.handler.BRAZILCNPJ_CF_ACCESS_CLIENT_ID",
        "client-id",
    )
    monkeypatch.setattr(
        "core.skills._builtin.brazilcnpj.handler.BRAZILCNPJ_CF_ACCESS_CLIENT_SECRET",
        "client-secret",
    )
    monkeypatch.setattr(
        "core.skills._builtin.brazilcnpj.handler.RemoteMCPClient.call_tool", fake_call
    )

    skill = BrazilCNPJSkill(_config("brazilcnpj"))
    await skill.execute({"query": "quero os socios do CNPJ 12.345.678/0001-99"})

    assert calls[0][0] == "brazilcnpj"
    assert calls[0][1] == "get_socios"
    assert calls[0][2]["cnpj"] == "12345678000199"


@pytest.mark.asyncio
async def test_fleetintel_analyst_routes_priority_queries(monkeypatch):
    calls = []

    async def fake_call(self, tool_name, arguments=None):
        calls.append((self.server_name, tool_name, arguments or {}))
        return {"items": [{"razao_social": "Empresa A", "cnpj": "12345678000199", "score": 98}]}

    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_analyst.handler.FLEETINTEL_CF_ACCESS_CLIENT_ID",
        "client-id",
    )
    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_analyst.handler.FLEETINTEL_CF_ACCESS_CLIENT_SECRET",
        "client-secret",
    )
    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_analyst.handler.RemoteMCPClient.call_tool", fake_call
    )

    skill = FleetIntelAnalystSkill(_config("fleetintel_analyst"))
    result = await skill.execute({"query": "quais contas devo priorizar agora?"})

    assert calls[0][0] == "fleetintel"
    assert calls[0][1] == "buying_signals"
    assert "Empresa A" in result


@pytest.mark.asyncio
async def test_fleetintel_orchestrator_uses_both_servers(monkeypatch):
    calls = []

    async def fake_call(self, tool_name, arguments=None):
        calls.append((self.server_name, tool_name, arguments or {}))
        if self.server_name == "fleetintel" and tool_name == "get_operations_status":
            return {"status": "ok", "freshness": "fresh"}
        if self.server_name == "fleetintel" and tool_name == "buying_signals":
            return {
                "items": [
                    {
                        "razao_social": "Empresa A",
                        "cnpj": "12345678000199",
                        "score": 91,
                    }
                ]
            }
        if self.server_name == "brazilcnpj" and tool_name == "health_check":
            return {"status": "ok", "database_ok": True}
        if self.server_name == "brazilcnpj" and tool_name == "get_cached_cnpj_profile":
            return {
                "razao_social": "Empresa A",
                "cnpj": arguments["cnpj"],
                "uf": "SP",
                "porte": "M",
            }
        return {}

    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_orchestrator.handler.FLEETINTEL_CF_ACCESS_CLIENT_ID",
        "fleet-client-id",
    )
    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_orchestrator.handler.FLEETINTEL_CF_ACCESS_CLIENT_SECRET",
        "fleet-client-secret",
    )
    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_orchestrator.handler.BRAZILCNPJ_CF_ACCESS_CLIENT_ID",
        "cnpj-client-id",
    )
    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_orchestrator.handler.BRAZILCNPJ_CF_ACCESS_CLIENT_SECRET",
        "cnpj-client-secret",
    )
    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_orchestrator.handler.RemoteMCPClient.call_tool",
        fake_call,
    )

    skill = FleetIntelOrchestratorSkill(_config("fleetintel_orchestrator"))
    result = await skill.execute({"query": "priorizar contas e cruzar com cnpj"})

    assert ("fleetintel", "get_operations_status", {}) in calls
    assert any(server == "fleetintel" and tool == "buying_signals" for server, tool, _ in calls)
    assert any(server == "brazilcnpj" and tool == "health_check" for server, tool, _ in calls)
    assert any(
        server == "brazilcnpj" and tool == "get_cached_cnpj_profile" for server, tool, _ in calls
    )
    assert "Enriquecimento seletivo" in result
