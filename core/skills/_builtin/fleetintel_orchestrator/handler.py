"""Cross-domain FleetIntel + BrazilCNPJ orchestrator skill."""

from __future__ import annotations

import re
from typing import Any

import structlog

from core.integrations import (
    ConsumerSyncError,
    RemoteMCPError,
    build_specialist_mcp_client,
    extract_cnpjs,
    extract_company_count_query,
    get_consumer_sync_manager,
    render_result_block,
)
from core.skills.base import SkillBase

logger = structlog.get_logger()


class FleetIntelOrchestratorSkill(SkillBase):
    async def execute(self, args: dict[str, Any] | None = None) -> str:
        payload = args or {}
        query = str(payload.get("raw_input") or payload.get("query") or "").strip()
        if not query:
            return "Informe a pergunta comercial que deve cruzar FleetIntel e BrazilCNPJ."

        try:
            fleet_client = build_specialist_mcp_client(
                "fleetintel",
                client_name="agentvps-fleetintel-orchestrator",
            )
            cnpj_client = build_specialist_mcp_client(
                "brazilcnpj",
                client_name="agentvps-brazilcnpj-orchestrator",
            )
        except ConsumerSyncError as exc:
            return str(exc)

        logger.info("fleetintel_orchestrator_execute", query=query[:120])
        try:
            readiness = await fleet_client.call_tool("get_client_readiness_status", {})
        except ConsumerSyncError as exc:
            return str(exc)
        except RemoteMCPError as exc:
            return self._format_fleet_failure(error=exc, query=query)
        fleet_tool, fleet_args = self._route_fleet_query(query)
        try:
            fleet_result = await fleet_client.call_tool(fleet_tool, fleet_args)
        except ConsumerSyncError as exc:
            return str(exc)
        except RemoteMCPError as exc:
            return self._format_fleet_failure(
                error=exc,
                query=query,
                readiness=readiness,
                tool_name=fleet_tool,
            )

        needs_cnpj = self._needs_cnpj(query)
        cnpj_health = None
        enrichments: list[dict[str, Any]] = []

        candidate_cnpjs = extract_cnpjs(fleet_result)
        explicit_cnpj = self._extract_cnpj(query)
        if explicit_cnpj and explicit_cnpj not in candidate_cnpjs:
            candidate_cnpjs.insert(0, explicit_cnpj)

        if needs_cnpj and cnpj_client.is_configured:
            cnpj_tool = (
                "get_company_registry_brief"
                if "get_company_registry_brief" in self._preferred_tools("brazilcnpj")
                else "get_cached_cnpj_profile"
            )
            try:
                cnpj_health = await cnpj_client.call_tool("health_check", {})
                if isinstance(cnpj_health, dict) and cnpj_health.get("status") == "ok":
                    for cnpj in candidate_cnpjs[:3]:
                        enrichments.append(await cnpj_client.call_tool(cnpj_tool, {"cnpj": cnpj}))
            except RemoteMCPError as exc:
                logger.warning("fleetintel_orchestrator_cnpj_degraded", error=str(exc))

        return self._format(
            query=query,
            readiness=readiness,
            fleet_tool=fleet_tool,
            fleet_result=fleet_result,
            cnpj_health=cnpj_health,
            enrichments=enrichments,
        )

    @staticmethod
    def _needs_cnpj(query: str) -> bool:
        msg = query.lower()
        return any(
            keyword in msg
            for keyword in (
                "cnpj",
                "grupo economico",
                "socio",
                "socios",
                "cnae",
                "cadastro",
                "enriquec",
                "cruze",
                "combine",
            )
        )

    @staticmethod
    def _extract_cnpj(query: str) -> str | None:
        digits = re.sub(r"\D", "", query)
        match = re.search(r"\b\d{14}\b", digits)
        return match.group(0) if match else None

    @staticmethod
    def _extract_uf(query: str) -> str | None:
        match = re.search(
            r"\b(ac|al|ap|am|ba|ce|df|es|go|ma|mt|ms|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to)\b",
            query.lower(),
        )
        return match.group(1).upper() if match else None

    def _route_fleet_query(self, query: str) -> tuple[str, dict[str, Any]]:
        msg = query.lower()
        company_count_args = extract_company_count_query(query)
        preferred = self._preferred_tools("fleetintel")
        if company_count_args:
            return "count_empresa_registrations", company_count_args
        args: dict[str, Any] = {"limit": 5}
        uf = self._extract_uf(query)
        if uf:
            args["uf"] = uf
        if any(keyword in msg for keyword in ("o que mudou", "ultimo sync", "insights")):
            if "get_market_changes_brief" in preferred:
                return "get_market_changes_brief", {"limit_items": 10}
            return "get_latest_insights", {"limit_items": 10}
        if any(
            keyword in msg
            for keyword in (
                "priorizar",
                "prioridade",
                "sinais de compra",
                "buying signals",
                "prospeccao",
            )
        ):
            if "get_account_prioritization_brief" in preferred:
                return "get_account_prioritization_brief", {"limit_items": 10}
            return "buying_signals", args
        if any(keyword in msg for keyword in ("entrantes", "novo entrante")):
            return "new_entrants", args
        if any(keyword in msg for keyword in ("tendencia", "trend", "variacao")):
            return "trend_analysis", args
        explicit_cnpj = self._extract_cnpj(query)
        if explicit_cnpj:
            if "get_fleet_account_brief" in preferred:
                return "get_fleet_account_brief", {"cnpj": explicit_cnpj}
            return "empresa_profile", {"cnpj": explicit_cnpj}
        return "top_empresas_by_registrations", args

    @staticmethod
    def _preferred_tools(service: str) -> set[str]:
        return set(get_consumer_sync_manager().preferred_tools_for(service))

    @staticmethod
    def _format_fleet_failure(
        *,
        error: RemoteMCPError,
        query: str,
        readiness: Any | None = None,
        tool_name: str | None = None,
    ) -> str:
        lines = ["FleetIntel Orchestrator", ""]
        lines.append(f"Consulta: {query}")
        if tool_name:
            lines.append(f"Tool principal: {tool_name}")
        lines.append(
            f"Falha FleetIntel: {'HTTP ' + str(error.status_code) if error.status_code else error.error_type} "
            f"na etapa `{error.stage}`."
        )
        summary = FleetIntelOrchestratorSkill._format_readiness_summary(readiness)
        if summary:
            lines.append(f"Preflight FleetIntel: {summary}")
        else:
            lines.append("Preflight FleetIntel indisponivel no momento.")
        lines.append("Posso tentar novamente depois ou responder sem enriquecimento externo.")
        return "\n".join(lines)

    def _format(
        self,
        *,
        query: str,
        readiness: Any,
        fleet_tool: str,
        fleet_result: Any,
        cnpj_health: Any,
        enrichments: list[dict[str, Any]],
    ) -> str:
        lines = ["FleetIntel Orchestrator", ""]
        summary = self._format_readiness_summary(readiness)
        if summary:
            lines.append(f"Prontidao FleetIntel: {summary}")
        lines.append(f"Consulta: {query}")
        lines.append(f"Tool principal: {fleet_tool}")
        lines.append("")
        lines.append("Resultado FleetIntel:")
        lines.append(self._format_fleet_result(fleet_tool=fleet_tool, fleet_result=fleet_result))

        if cnpj_health is not None:
            lines.append("")
            lines.append(
                "BrazilCNPJ health: "
                f"status={cnpj_health.get('status', '-')} "
                f"database_ok={cnpj_health.get('database_ok', '-')}"
            )
        if enrichments:
            lines.append("")
            lines.append("Enriquecimento seletivo:")
            for item in enrichments[:3]:
                if not isinstance(item, dict):
                    lines.append(f"- {item}")
                    continue
                name = (
                    item.get("razao_social")
                    or item.get("nome_fantasia")
                    or item.get("company_name")
                )
                cnpj = item.get("cnpj") or "-"
                uf = item.get("uf") or "-"
                porte = item.get("porte") or "-"
                lines.append(f"- {name or 'empresa'} | CNPJ {cnpj} | UF {uf} | porte {porte}")

        return "\n".join(lines)

    @staticmethod
    def _format_readiness_summary(readiness: Any) -> str:
        if not isinstance(readiness, dict):
            return ""

        parts = [f"status={readiness.get('status', '-')}"]
        snapshot_status = readiness.get("snapshot_status")
        if snapshot_status is not None:
            parts.append(f"snapshot_status={snapshot_status}")
        snapshot_age_seconds = readiness.get("snapshot_age_seconds")
        if snapshot_age_seconds is not None:
            parts.append(f"snapshot_age_seconds={snapshot_age_seconds}")
        generated_at = readiness.get("generated_at")
        if generated_at:
            parts.append(f"generated_at={generated_at}")
        return " ".join(parts)

    @staticmethod
    def _format_fleet_result(*, fleet_tool: str, fleet_result: Any) -> str:
        if fleet_tool in {"empresa_profile", "get_fleet_account_brief"} and isinstance(
            fleet_result, dict
        ):
            if fleet_result.get("error"):
                return str(fleet_result.get("error"))

            empresa = fleet_result.get("empresa") or {}
            if not empresa and fleet_result.get("company_name"):
                empresa = {
                    "razao_social": fleet_result.get("company_name"),
                    "cnpj": fleet_result.get("cnpj"),
                }
            resumo = (
                fleet_result.get("entity_summary", {}).get("resumo")
                or fleet_result.get("resumo")
                or {}
            )
            group_summary = fleet_result.get("group_summary") or {}
            lines = []
            lines.append(
                f"- empresa: {empresa.get('razao_social') or 'empresa'} | CNPJ {empresa.get('cnpj', '-')}"
            )
            if resumo:
                lines.append(
                    "- historico: "
                    f"{resumo.get('total_emplacamentos', 0)} emplacamentos, "
                    f"R$ {float(resumo.get('valor_total', 0) or 0):,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )
                if resumo.get("primeira_compra_historico") or resumo.get("ultima_compra_historico"):
                    lines.append(
                        "- janela: "
                        f"{resumo.get('primeira_compra_historico', '-')} ate "
                        f"{resumo.get('ultima_compra_historico', '-')}"
                    )
                if (
                    resumo.get("marcas_distintas") is not None
                    or resumo.get("ufs_distintas") is not None
                ):
                    lines.append(
                        "- diversidade: "
                        f"{resumo.get('marcas_distintas', 0)} marcas, "
                        f"{resumo.get('ufs_distintas', 0)} UFs"
                    )
            if group_summary:
                members = group_summary.get("group_members") or []
                lines.append(
                    "- grupo: "
                    f"{len(members)} membros, "
                    f"{group_summary.get('total_emplacamentos', 0)} emplacamentos totais"
                )
                if group_summary.get("ultima_compra_grupo"):
                    lines.append(
                        f"- ultima compra do grupo: {group_summary['ultima_compra_grupo']}"
                    )
            return "\n".join(lines)
        if fleet_tool in {"get_market_changes_brief", "get_account_prioritization_brief"}:
            return render_result_block("", fleet_result, max_chars=1400).strip()

        return render_result_block("", fleet_result, max_chars=1400).strip()
