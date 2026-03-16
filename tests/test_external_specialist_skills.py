import pytest

from core.integrations import (
    ConsumerSyncError,
    RemoteMCPError,
    detect_external_skill,
    extract_company_count_query,
    select_codex_execution_mode,
    should_delegate_specialist_to_codex,
)
from core.integrations import specialist_health as specialist_health_module
from core.skills._builtin.brazilcnpj.handler import BrazilCNPJSkill
from core.skills._builtin.fleetintel.handler import FleetIntelSkill
from core.skills._builtin.fleetintel_analyst.handler import FleetIntelAnalystSkill
from core.skills._builtin.fleetintel_orchestrator.handler import FleetIntelOrchestratorSkill
from core.skills.base import SecurityLevel, SkillConfig


class _FakeClient:
    def __init__(self, service: str, call_impl):
        self.server_name = service
        self._call_impl = call_impl
        self.is_configured = True

    async def call_tool(self, tool_name, arguments=None):
        return await self._call_impl(self.server_name, tool_name, arguments or {})


class _FakeSyncManager:
    def __init__(self, preferred_tools=None, fallback_tools=None):
        self._preferred_tools = preferred_tools or {}
        self._fallback_tools = fallback_tools or {}

    def preferred_tools_for(self, service):
        return self._preferred_tools.get(service, [])

    def fallback_tools_for(self, service):
        return self._fallback_tools.get(service, [])


def _config(name: str) -> SkillConfig:
    return SkillConfig(name=name, description=name, security_level=SecurityLevel.SAFE)


def _patch_builder(monkeypatch, module_path: str, call_impl):
    monkeypatch.setattr(
        module_path,
        lambda service, **_kwargs: _FakeClient(service, call_impl),
    )


def test_detect_external_skill_routes():
    assert detect_external_skill("enriquece este cnpj 12345678000199") == "brazilcnpj"
    assert (
        detect_external_skill("quais contas devo priorizar por sinais de compra?")
        == "fleetintel_analyst"
    )
    assert detect_external_skill("Quantos caminhoes o Grupo Vamos comprou em 2025?") == (
        "fleetintel_analyst"
    )
    assert detect_external_skill(
        "Use a skill fleetintel para consultar o CNPJ 23.373.000/0001-32"
    ) == ("fleetintel")
    assert detect_external_skill("Use o FleetIntel Orchestrator para cruzar frota e CNPJ") == (
        "fleetintel_orchestrator"
    )


def test_extract_company_count_query_for_company_year_volume():
    assert extract_company_count_query("Quantos caminhoes o Grupo Vamos comprou em 2025?") == {
        "razao_social": "Grupo Vamos",
        "ano": 2025,
    }


def test_select_codex_execution_mode_for_specialist_requests():
    assert (
        select_codex_execution_mode(
            "Use o FleetIntel Analyst para me dar os latest insights do FleetIntel.",
            "fleetintel_analyst",
        )
        == "direct_local"
    )
    assert (
        select_codex_execution_mode(
            "Use o FleetIntel Orchestrator para cruzar frota e CNPJ e me dizer sobre a conta.",
            "fleetintel_orchestrator",
        )
        == "direct_local"
    )
    assert (
        select_codex_execution_mode(
            "Use o FleetIntel Orchestrator para validar o CNPJ 23.373.000/0001-32 e mostrar socios.",
            "fleetintel_orchestrator",
        )
        == "direct_local"
    )
    assert (
        select_codex_execution_mode(
            "Use BrazilCNPJ Enricher para validar este CNPJ (48.430.290/0001-30), mostrar socios, grupo economico e me dizer sobre ela, depois use o FleetIntel Orchestrator para falar da frota e o FleetIntel Analyst para me dar insights sobre.",
            "fleetintel_orchestrator",
        )
        == "direct_local"
    )
    assert (
        select_codex_execution_mode(
            "Quais contas devo priorizar por sinais de compra cruzando FleetIntel e CNPJ?",
            "fleetintel_orchestrator",
        )
        == "codex_operator"
    )
    assert (
        should_delegate_specialist_to_codex(
            "Use o FleetIntel Analyst para me dar os latest insights do FleetIntel.",
            "fleetintel_analyst",
        )
        is False
    )
    assert (
        should_delegate_specialist_to_codex(
            "Enriqueca o CNPJ 23.373.000/0001-32",
            "brazilcnpj",
        )
        is False
    )


@pytest.mark.asyncio
async def test_brazilcnpj_skill_routes_socios(monkeypatch):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        return {"socios": [{"nome": "Fulano"}]}

    _patch_builder(
        monkeypatch,
        "core.skills._builtin.brazilcnpj.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = BrazilCNPJSkill(_config("brazilcnpj"))
    await skill.execute({"query": "quero os socios do CNPJ 12.345.678/0001-99"})

    assert calls == [("brazilcnpj", "get_socios", {"cnpj": "12345678000199"})]


@pytest.mark.asyncio
async def test_brazilcnpj_skill_uses_preferred_company_registry_brief(monkeypatch):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        return {"company_name": "Empresa X", "cnpj": arguments["cnpj"], "uf": "SP"}

    monkeypatch.setattr(
        "core.skills._builtin.brazilcnpj.handler.get_consumer_sync_manager",
        lambda: _FakeSyncManager({"brazilcnpj": ["get_company_registry_brief"]}),
    )
    _patch_builder(
        monkeypatch,
        "core.skills._builtin.brazilcnpj.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = BrazilCNPJSkill(_config("brazilcnpj"))
    result = await skill.execute({"query": "valide o CNPJ 12.345.678/0001-99"})

    assert calls == [("brazilcnpj", "get_company_registry_brief", {"cnpj": "12345678000199"})]
    assert "Empresa X" in result


@pytest.mark.asyncio
async def test_fleetintel_analyst_routes_priority_queries(monkeypatch):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        return {"items": [{"razao_social": "Empresa A", "cnpj": "12345678000199", "score": 98}]}

    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel_analyst.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelAnalystSkill(_config("fleetintel_analyst"))
    result = await skill.execute({"query": "quais contas devo priorizar agora?"})

    assert calls == [("fleetintel", "buying_signals", {"limit": 10})]
    assert "Empresa A" in result


@pytest.mark.asyncio
async def test_fleetintel_analyst_uses_preferred_market_changes_brief(monkeypatch):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        return {"status": "ok", "items": [{"headline": "Mercado aquecido"}]}

    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_analyst.handler.get_consumer_sync_manager",
        lambda: _FakeSyncManager({"fleetintel": ["get_market_changes_brief"]}),
    )
    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel_analyst.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelAnalystSkill(_config("fleetintel_analyst"))
    result = await skill.execute({"query": "quais os insights e o que mudou no mercado?"})

    assert calls == [("fleetintel", "get_market_changes_brief", {"limit_items": 10})]
    assert "Mercado aquecido" in result


@pytest.mark.asyncio
async def test_fleetintel_analyst_formats_empresa_profile_summary(monkeypatch):
    async def fake_call(service, tool_name, arguments):
        assert service == "fleetintel"
        assert tool_name == "empresa_profile"
        assert arguments == {"cnpj": "48430290000130"}
        return {
            "empresa": {"cnpj": "48430290000130", "razao_social": "ADDIANTE S.A"},
            "resumo": {
                "total_emplacamentos": 914,
                "valor_total": 2921246934.76,
                "primeira_compra_historico": "2023-04-11",
                "ultima_compra_historico": "2026-02-24",
                "marcas_distintas": 7,
                "ufs_distintas": 1,
            },
        }

    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel_analyst.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelAnalystSkill(_config("fleetintel_analyst"))
    result = await skill.execute(
        {"query": "Use o FleetIntel para analisar o CNPJ 48.430.290/0001-30"}
    )

    assert "ADDIANTE S.A" in result
    assert "914 emplacamentos" in result
    assert "Janela observada" in result


@pytest.mark.asyncio
async def test_fleetintel_analyst_refines_company_count_when_entity_not_resolved(monkeypatch):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        if tool_name == "count_empresa_registrations":
            return {"count": 0, "empresas": [], "error": "Empresa nao encontrada"}
        if tool_name == "search_empresas":
            return {
                "empresas": [
                    {
                        "razao_social": "VAMOS LOCACAO DE CAMINHOES",
                        "cnpj": "11111111000111",
                        "grupo_locadora": "VAMOS",
                    }
                ]
            }
        return {}

    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel_analyst.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelAnalystSkill(_config("fleetintel_analyst"))
    result = await skill.execute({"query": "Quantos caminhoes o Grupo Vamos comprou em 2025?"})

    assert calls[0] == (
        "fleetintel",
        "count_empresa_registrations",
        {"razao_social": "Grupo Vamos", "ano": 2025},
    )
    assert calls[1] == (
        "fleetintel",
        "search_empresas",
        {"razao_social": "Grupo Vamos", "limit": 5},
    )
    assert "Nao consegui travar a entidade exata" in result
    assert "VAMOS LOCACAO DE CAMINHOES" in result


@pytest.mark.asyncio
async def test_fleetintel_orchestrator_uses_both_servers(monkeypatch):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        if service == "fleetintel" and tool_name == "get_client_readiness_status":
            return {"status": "ok", "snapshot_status": "ready", "snapshot_age_seconds": 12.5}
        if service == "fleetintel" and tool_name == "buying_signals":
            return {"items": [{"razao_social": "Empresa A", "cnpj": "12345678000199", "score": 91}]}
        if service == "brazilcnpj" and tool_name == "health_check":
            return {"status": "ok", "database_ok": True}
        if service == "brazilcnpj" and tool_name == "get_cached_cnpj_profile":
            return {
                "razao_social": "Empresa A",
                "cnpj": arguments["cnpj"],
                "uf": "SP",
                "porte": "M",
            }
        return {}

    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_orchestrator.handler.get_consumer_sync_manager",
        lambda: _FakeSyncManager(
            {},
            {"brazilcnpj": ["get_cached_cnpj_profile"]},
        ),
    )
    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel_orchestrator.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelOrchestratorSkill(_config("fleetintel_orchestrator"))
    result = await skill.execute({"query": "priorizar contas e cruzar com cnpj 12.345.678/0001-99"})

    assert ("fleetintel", "get_client_readiness_status", {}) in calls
    assert ("brazilcnpj", "health_check", {}) in calls
    assert any(
        service == "brazilcnpj" and tool == "get_cached_cnpj_profile" for service, tool, _ in calls
    )
    assert "Prontidao FleetIntel: status=ok" in result
    assert "Cadastro da empresa:" in result


@pytest.mark.asyncio
async def test_fleetintel_orchestrator_uses_preferred_brief_surfaces(monkeypatch):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        if service == "fleetintel" and tool_name == "get_client_readiness_status":
            return {"status": "ok", "snapshot_status": "ready", "snapshot_age_seconds": 12.5}
        if service == "fleetintel" and tool_name == "get_market_changes_brief":
            return {"items": [{"headline": "Mudanca relevante", "cnpj": "12345678000199"}]}
        if service == "brazilcnpj" and tool_name == "health_check":
            return {"status": "ok", "database_ok": True}
        if service == "brazilcnpj" and tool_name == "get_company_registry_brief":
            return {
                "company_name": "Empresa A",
                "cnpj": arguments["cnpj"],
                "uf": "SP",
                "porte": "M",
            }
        return {}

    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_orchestrator.handler.get_consumer_sync_manager",
        lambda: _FakeSyncManager(
            {
                "fleetintel": ["get_market_changes_brief"],
                "brazilcnpj": ["get_company_registry_brief"],
            }
        ),
    )
    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel_orchestrator.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelOrchestratorSkill(_config("fleetintel_orchestrator"))
    result = await skill.execute({"query": "o que mudou e cruze com o cnpj 12.345.678/0001-99"})

    assert ("fleetintel", "get_market_changes_brief", {"limit_items": 10}) in calls
    assert any(
        service == "brazilcnpj" and tool == "get_company_registry_brief"
        for service, tool, _ in calls
    )
    assert "Mudanca relevante" in result


@pytest.mark.asyncio
async def test_fleetintel_orchestrator_combined_prompt_prefers_account_brief_and_partner_fallback(
    monkeypatch,
):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        if service == "fleetintel" and tool_name == "get_client_readiness_status":
            return {"status": "ok", "snapshot_status": "ready", "snapshot_age_seconds": 8.0}
        if service == "fleetintel" and tool_name == "get_fleet_account_brief":
            return {"company_name": "ADDIANTE S.A.", "cnpj": "48430290000130"}
        if service == "brazilcnpj" and tool_name == "health_check":
            return {"status": "ok", "database_ok": True}
        if service == "brazilcnpj" and tool_name == "get_company_registry_brief":
            return {"company_name": "ADDIANTE S.A.", "cnpj": arguments["cnpj"], "uf": "SP"}
        if service == "brazilcnpj" and tool_name == "get_group_context_brief":
            return {"group_name": "Grupo Addiante", "member_count": 3}
        if service == "brazilcnpj" and tool_name == "get_empresa_completa":
            return {"socios": [{"nome": "Fulano de Tal", "qualificacao": "Administrador"}]}
        return {}

    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_orchestrator.handler.get_consumer_sync_manager",
        lambda: _FakeSyncManager(
            {
                "fleetintel": ["get_fleet_account_brief", "get_market_changes_brief"],
                "brazilcnpj": ["get_company_registry_brief", "get_group_context_brief"],
            },
            {
                "brazilcnpj": ["get_empresa_completa"],
            },
        ),
    )
    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel_orchestrator.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelOrchestratorSkill(_config("fleetintel_orchestrator"))
    result = await skill.execute(
        {
            "query": "Use BrazilCNPJ Enricher para validar este CNPJ (48.430.290/0001-30), mostrar socios, grupo economico e me dizer sobre ela, depois use o FleetIntel Orchestrator para falar da frota."
        }
    )

    assert ("fleetintel", "get_fleet_account_brief", {"cnpj": "48430290000130"}) in calls
    assert ("brazilcnpj", "get_company_registry_brief", {"cnpj": "48430290000130"}) in calls
    assert ("brazilcnpj", "get_group_context_brief", {"cnpj": "48430290000130"}) in calls
    assert ("brazilcnpj", "get_empresa_completa", {"cnpj": "48430290000130"}) in calls
    assert "Cadastro da empresa:" in result
    assert "Socios:" in result
    assert "Grupo economico:" in result


@pytest.mark.asyncio
async def test_fleetintel_skill_routes_explicit_cnpj_to_empresa_profile(monkeypatch):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        return {
            "empresa": {
                "cnpj": "23373000000132",
                "razao_social": "VAMOS LOCACAO DE CAMINHOES, MAQUINAS E EQUIPAMENTOS S.A.",
            },
            "resumo": {
                "total_emplacamentos": 203,
                "valor_total": 570215790.0,
                "primeira_compra_historico": "2017-05-05",
                "ultima_compra_historico": "2024-08-19",
                "marcas_distintas": 4,
                "ufs_distintas": 2,
            },
        }

    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelSkill(_config("fleetintel"))
    result = await skill.execute(
        {"query": "Use a skill fleetintel para consultar o CNPJ 23.373.000/0001-32"}
    )

    assert calls == [("fleetintel", "empresa_profile", {"cnpj": "23373000000132"})]
    assert "Perfil da Empresa" in result
    assert "203 emplacamentos" in result


@pytest.mark.asyncio
async def test_specialist_skills_return_consumer_sync_error(monkeypatch):
    monkeypatch.setattr(
        "core.skills._builtin.fleetintel_analyst.handler.build_specialist_mcp_client",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ConsumerSyncError("Consumer sync nao configurado.")
        ),
    )

    skill = FleetIntelAnalystSkill(_config("fleetintel_analyst"))
    result = await skill.execute({"query": "quais contas devo priorizar?"})

    assert result == "Consumer sync nao configurado."


@pytest.mark.asyncio
async def test_fleetintel_orchestrator_degrades_with_remote_error(monkeypatch):
    async def fake_call(service, tool_name, arguments):
        if service == "fleetintel" and tool_name == "get_client_readiness_status":
            raise RemoteMCPError(
                server_name="fleetintel",
                stage="initialize",
                error_type="http_5xx",
                message="bad gateway",
                status_code=502,
            )
        return {}

    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel_orchestrator.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelOrchestratorSkill(_config("fleetintel_orchestrator"))
    result = await skill.execute({"query": "priorizar contas e cruzar com cnpj"})

    assert "HTTP 502" in result
    assert "Preflight FleetIntel indisponivel" in result


@pytest.mark.asyncio
async def test_fleetintel_analyst_failure_uses_readiness_preflight(monkeypatch):
    calls = []

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        if tool_name == "buying_signals":
            raise RemoteMCPError(
                server_name="fleetintel",
                stage="tools/call",
                error_type="timeout",
                message="timeout",
            )
        if tool_name == "get_client_readiness_status":
            return {"status": "ok", "snapshot_status": "ready", "snapshot_age_seconds": 8.0}
        raise AssertionError(f"unexpected tool {tool_name}")

    _patch_builder(
        monkeypatch,
        "core.skills._builtin.fleetintel_analyst.handler.build_specialist_mcp_client",
        fake_call,
    )

    skill = FleetIntelAnalystSkill(_config("fleetintel_analyst"))
    result = await skill.execute({"query": "quais contas devo priorizar agora?"})

    assert calls == [
        ("fleetintel", "buying_signals", {"limit": 10}),
        ("fleetintel", "get_client_readiness_status", {}),
    ]
    assert "Preflight FleetIntel: status=ok snapshot_status=ready" in result


@pytest.mark.asyncio
async def test_specialist_health_uses_readiness_preflight(monkeypatch):
    calls = []
    specialist_health_module._HEALTH_CACHE.clear()

    async def fake_call(service, tool_name, arguments):
        calls.append((service, tool_name, arguments))
        return {"status": "ok", "snapshot_status": "ready"}

    monkeypatch.setattr(
        specialist_health_module,
        "build_specialist_mcp_client",
        lambda service, **_kwargs: _FakeClient(service, fake_call),
    )

    assessment = await specialist_health_module.assess_specialist_health(
        "Cruze FleetIntel e CNPJ para esta conta",
        "fleetintel_orchestrator",
    )

    assert assessment.healthy is True
    assert ("fleetintel", "get_client_readiness_status", {}) in calls
