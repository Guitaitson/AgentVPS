import pytest

from core.integrations import RemoteMCPError, detect_external_skill, extract_company_count_query
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
    assert detect_external_skill("Quantos caminhões o Grupo Vamos comprou em 2025?") == (
        "fleetintel_analyst"
    )
    assert detect_external_skill("Use o FleetIntel para analisar o CNPJ 23.373.000/0001-32") == (
        "fleetintel_analyst"
    )
    assert (
        detect_external_skill("Use a skill fleetintel para consultar o CNPJ 23.373.000/0001-32")
        == "fleetintel"
    )
    assert detect_external_skill("cruze sinais de compra com cnpj das contas") == (
        "fleetintel_orchestrator"
    )


def test_extract_company_count_query_for_company_year_volume():
    args = extract_company_count_query("Quantos caminhões o Grupo Vamos comprou em 2025?")

    assert args == {"razao_social": "Grupo Vamos", "ano": 2025}


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
async def test_fleetintel_analyst_routes_company_volume_queries(monkeypatch):
    calls = []

    async def fake_call(self, tool_name, arguments=None):
        calls.append((self.server_name, tool_name, arguments or {}))
        return {
            "count": 42,
            "ano": 2025,
            "empresas": [{"razao_social": "Grupo Vamos", "cnpj": "12345678000199"}],
        }

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
    result = await skill.execute({"query": "Quantos caminhões o Grupo Vamos comprou em 2025?"})

    assert calls[0][1] == "count_empresa_registrations"
    assert calls[0][2] == {"razao_social": "Grupo Vamos", "ano": 2025}
    assert "42" in result
    assert "Grupo Vamos" in result


@pytest.mark.asyncio
async def test_fleetintel_analyst_degrades_with_preflight_when_primary_call_fails(monkeypatch):
    calls = []

    async def fake_call(self, tool_name, arguments=None):
        calls.append((tool_name, arguments or {}))
        if tool_name == "count_empresa_registrations":
            raise RemoteMCPError(
                server_name="fleetintel",
                stage="tools/call",
                error_type="http_5xx",
                message="bad gateway",
                status_code=502,
            )
        if tool_name == "get_operations_status":
            return {
                "status": "warning",
                "freshness": "stale",
                "generated_at": "2026-03-12T10:00:00Z",
            }
        return {}

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
    result = await skill.execute({"query": "Quantos caminhões o Grupo Vamos comprou em 2025?"})

    assert ("count_empresa_registrations", {"razao_social": "Grupo Vamos", "ano": 2025}) in calls
    assert ("get_operations_status", {}) in calls
    assert "HTTP 502" in result
    assert "status=warning" in result


@pytest.mark.asyncio
async def test_fleetintel_analyst_refines_company_count_when_entity_not_resolved(monkeypatch):
    calls = []

    async def fake_call(self, tool_name, arguments=None):
        calls.append((tool_name, arguments or {}))
        if tool_name == "count_empresa_registrations":
            return {"count": 0, "empresas": [], "error": "Empresa nao encontrada"}
        if tool_name == "search_empresas":
            return {
                "empresas": [
                    {
                        "razao_social": "VAMOS LOCACAO DE CAMINHOES",
                        "cnpj": "11111111000111",
                        "grupo_locadora": "VAMOS",
                    },
                    {
                        "razao_social": "VAMOS COMERCIO DE VEICULOS",
                        "cnpj": "22222222000122",
                        "grupo_locadora": "VAMOS",
                    },
                ]
            }
        return {}

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
    result = await skill.execute({"query": "Quantos caminhoes o Grupo Vamos comprou em 2025?"})

    assert ("count_empresa_registrations", {"razao_social": "Grupo Vamos", "ano": 2025}) in calls
    assert ("search_empresas", {"razao_social": "Grupo Vamos", "limit": 5}) in calls
    assert "Nao consegui travar a entidade exata" in result
    assert "VAMOS LOCACAO DE CAMINHOES" in result


@pytest.mark.asyncio
async def test_fleetintel_analyst_returns_explicit_resolution_failure_when_no_match_exists(
    monkeypatch,
):
    async def fake_call(self, tool_name, arguments=None):
        if tool_name == "count_empresa_registrations":
            return {"count": 0, "empresas": [], "error": "Empresa nao encontrada"}
        if tool_name == "search_empresas":
            return {"status": "ok", "count": 0, "empresas": []}
        return {}

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
    result = await skill.execute({"query": "Quantos caminhoes o Grupo Vamos comprou em 2025?"})

    assert "Nao encontrei uma entidade exata" in result
    assert "CNPJ" in result


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


@pytest.mark.asyncio
async def test_fleetintel_orchestrator_formats_empresa_profile_summary(monkeypatch):
    async def fake_call(self, tool_name, arguments=None):
        if self.server_name == "fleetintel" and tool_name == "get_operations_status":
            return {"status": "ok", "freshness": "fresh"}
        if self.server_name == "fleetintel" and tool_name == "empresa_profile":
            return {
                "empresa": {
                    "cnpj": "48430290000130",
                    "razao_social": "ADDIANTE S.A",
                },
                "resumo": {
                    "total_emplacamentos": 914,
                    "valor_total": 2921246934.76,
                    "primeira_compra_historico": "2023-04-11",
                    "ultima_compra_historico": "2026-02-24",
                    "marcas_distintas": 7,
                    "ufs_distintas": 1,
                },
                "group_summary": {
                    "group_members": [{"cnpj": "48430290000130"}],
                    "total_emplacamentos": 915,
                    "ultima_compra_grupo": "2026-02-24",
                },
            }
        if self.server_name == "brazilcnpj" and tool_name == "health_check":
            return {"status": "ok", "database_ok": True}
        if self.server_name == "brazilcnpj" and tool_name == "get_cached_cnpj_profile":
            return {"razao_social": "ADDIANTE S.A", "cnpj": "48430290000130", "uf": "PR"}
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
    result = await skill.execute(
        {"query": "Use o FleetIntel para analisar o CNPJ 48.430.290/0001-30"}
    )

    assert "ADDIANTE S.A" in result
    assert "914 emplacamentos" in result
    assert "grupo: 1 membros" in result
