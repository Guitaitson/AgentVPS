"""Cross-domain FleetIntel + BrazilCNPJ orchestrator skill."""

from __future__ import annotations

import os
import re
from typing import Any

import structlog

from core.integrations import RemoteMCPClient, extract_cnpjs, render_result_block
from core.skills.base import SkillBase

logger = structlog.get_logger()

FLEETINTEL_MCP_URL = os.getenv("FLEETINTEL_MCP_URL", "https://mcp.gtaitson.space/mcp")
FLEETINTEL_MCP_TOKEN = os.getenv("FLEETINTEL_MCP_TOKEN", "")
BRAZILCNPJ_MCP_URL = os.getenv("BRAZILCNPJ_MCP_URL", "https://cnpj-mcp.gtaitson.space/mcp")
BRAZILCNPJ_MCP_TOKEN = os.getenv("BRAZILCNPJ_MCP_TOKEN", "")


class FleetIntelOrchestratorSkill(SkillBase):
    async def execute(self, args: dict[str, Any] | None = None) -> str:
        payload = args or {}
        query = str(payload.get("raw_input") or payload.get("query") or "").strip()
        if not query:
            return "Informe a pergunta comercial que deve cruzar FleetIntel e BrazilCNPJ."

        fleet_client = RemoteMCPClient(
            base_url=FLEETINTEL_MCP_URL,
            token=FLEETINTEL_MCP_TOKEN,
            client_name="agentvps-fleetintel-orchestrator",
            server_name="fleetintel",
        )
        cnpj_client = RemoteMCPClient(
            base_url=BRAZILCNPJ_MCP_URL,
            token=BRAZILCNPJ_MCP_TOKEN,
            client_name="agentvps-brazilcnpj-orchestrator",
            server_name="brazilcnpj",
        )
        if not fleet_client.is_configured:
            return (
                "FleetIntel MCP nao configurado. Ajuste FLEETINTEL_MCP_URL e FLEETINTEL_MCP_TOKEN."
            )

        logger.info("fleetintel_orchestrator_execute", query=query[:120])
        ops = await fleet_client.call_tool("get_operations_status", {})
        fleet_tool, fleet_args = self._route_fleet_query(query)
        fleet_result = await fleet_client.call_tool(fleet_tool, fleet_args)

        needs_cnpj = self._needs_cnpj(query)
        cnpj_health = None
        enrichments: list[dict[str, Any]] = []

        candidate_cnpjs = extract_cnpjs(fleet_result)
        explicit_cnpj = self._extract_cnpj(query)
        if explicit_cnpj and explicit_cnpj not in candidate_cnpjs:
            candidate_cnpjs.insert(0, explicit_cnpj)

        if needs_cnpj and cnpj_client.is_configured:
            cnpj_health = await cnpj_client.call_tool("health_check", {})
            if isinstance(cnpj_health, dict) and cnpj_health.get("status") == "ok":
                for cnpj in candidate_cnpjs[:3]:
                    enrichments.append(
                        await cnpj_client.call_tool("get_cached_cnpj_profile", {"cnpj": cnpj})
                    )

        return self._format(
            query=query,
            ops=ops,
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
        args: dict[str, Any] = {"limit": 5}
        uf = self._extract_uf(query)
        if uf:
            args["uf"] = uf
        if any(keyword in msg for keyword in ("o que mudou", "ultimo sync", "insights")):
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
            return "buying_signals", args
        if any(keyword in msg for keyword in ("entrantes", "novo entrante")):
            return "new_entrants", args
        if any(keyword in msg for keyword in ("tendencia", "trend", "variacao")):
            return "trend_analysis", args
        explicit_cnpj = self._extract_cnpj(query)
        if explicit_cnpj:
            return "empresa_profile", {"cnpj": explicit_cnpj}
        return "top_empresas_by_registrations", args

    def _format(
        self,
        *,
        query: str,
        ops: Any,
        fleet_tool: str,
        fleet_result: Any,
        cnpj_health: Any,
        enrichments: list[dict[str, Any]],
    ) -> str:
        lines = ["FleetIntel Orchestrator", ""]
        if isinstance(ops, dict):
            lines.append(
                "Operacao FleetIntel: "
                f"status={ops.get('status', '-')} "
                f"freshness={ops.get('data_freshness') or ops.get('freshness') or '-'}"
            )
        lines.append(f"Consulta: {query}")
        lines.append(f"Tool principal: {fleet_tool}")
        lines.append("")
        lines.append("Resultado FleetIntel:")
        lines.append(render_result_block("", fleet_result, max_chars=1400).strip())

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
