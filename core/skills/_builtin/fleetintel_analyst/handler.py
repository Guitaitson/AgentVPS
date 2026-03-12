"""FleetIntel analyst skill backed by the external FleetIntel MCP server."""

from __future__ import annotations

import os
import re
from typing import Any

import structlog

from core.integrations import (
    RemoteMCPClient,
    RemoteMCPError,
    extract_company_count_query,
    render_result_block,
)
from core.skills.base import SkillBase

logger = structlog.get_logger()

FLEETINTEL_MCP_URL = os.getenv("FLEETINTEL_MCP_URL", "https://agent-fleet.gtaitson.space/mcp")
FLEETINTEL_CF_ACCESS_CLIENT_ID = os.getenv("FLEETINTEL_CF_ACCESS_CLIENT_ID", "")
FLEETINTEL_CF_ACCESS_CLIENT_SECRET = os.getenv("FLEETINTEL_CF_ACCESS_CLIENT_SECRET", "")


class FleetIntelAnalystSkill(SkillBase):
    async def execute(self, args: dict[str, Any] | None = None) -> str:
        payload = args or {}
        query = str(payload.get("raw_input") or payload.get("query") or "").strip()
        if not query:
            return (
                "Informe uma pergunta sobre frota, emplacamentos, sinais de compra ou tendencias."
            )

        client = RemoteMCPClient(
            base_url=FLEETINTEL_MCP_URL,
            access_client_id=FLEETINTEL_CF_ACCESS_CLIENT_ID,
            access_client_secret=FLEETINTEL_CF_ACCESS_CLIENT_SECRET,
            client_name="agentvps-fleetintel-analyst",
            server_name="fleetintel",
        )
        if not client.is_configured:
            return (
                "FleetIntel MCP nao configurado. Ajuste FLEETINTEL_MCP_URL, "
                "FLEETINTEL_CF_ACCESS_CLIENT_ID e FLEETINTEL_CF_ACCESS_CLIENT_SECRET."
            )

        tool_name, tool_args = self._route(query)
        logger.info("fleetintel_analyst_execute", tool=tool_name)
        try:
            result = await client.call_tool(tool_name, tool_args)
        except RemoteMCPError as exc:
            return await self._format_remote_failure(
                client=client,
                error=exc,
                tool_name=tool_name,
            )
        if tool_name == "count_empresa_registrations":
            refined = await self._maybe_refine_company_count(
                client=client,
                tool_args=tool_args,
                result=result,
            )
            if refined is not None:
                return refined
        return self._format(tool_name, result)

    def _route(self, query: str) -> tuple[str, dict[str, Any]]:
        msg = query.lower()
        company_count_args = extract_company_count_query(query)
        if company_count_args:
            return "count_empresa_registrations", company_count_args
        if any(
            keyword in msg
            for keyword in ("saude", "status operacional", "fresh", "sincron", "health")
        ):
            return "get_operations_status", {}
        if any(keyword in msg for keyword in ("insights", "o que mudou", "ultimo sync")):
            return "get_latest_insights", {"limit_items": 10}
        if any(keyword in msg for keyword in ("perguntas sugeridas", "sugestoes", "sugeridas")):
            return "list_suggested_questions", {"limit": 10}
        if any(
            keyword in msg
            for keyword in (
                "sinais de compra",
                "buying signals",
                "priorizar",
                "prioridade",
                "prospeccao",
                "oportunidade",
            )
        ):
            return "buying_signals", self._build_scope_args(msg, default_limit=10)
        if any(
            keyword in msg
            for keyword in ("novo entrante", "novos entrantes", "entrantes", "entrou recentemente")
        ):
            return "new_entrants", self._build_scope_args(msg, default_limit=10)
        if any(keyword in msg for keyword in ("tendencia", "tendencias", "trend", "variacao")):
            return "trend_analysis", self._build_scope_args(msg, default_limit=12)
        if any(
            keyword in msg
            for keyword in ("market share", "participacao de mercado", "cota de mercado")
        ):
            return "get_market_share", self._build_scope_args(msg, default_limit=10)
        if any(keyword in msg for keyword in ("comparar", " vs ", " versus ")):
            return "compare_empresas", self._build_compare_args(query)
        cnpj = self._extract_cnpj(query)
        if cnpj:
            return "empresa_profile", {"cnpj": cnpj}
        if any(
            keyword in msg
            for keyword in ("perfil da empresa", "analise da conta", "perfil da conta")
        ):
            return "search_empresas", {"razao_social": query[:120], "limit": 5}
        return "top_empresas_by_registrations", self._build_scope_args(msg, default_limit=10)

    @staticmethod
    def _extract_cnpj(text: str) -> str | None:
        match = re.search(r"\b\d{14}\b", re.sub(r"\D", "", text))
        return match.group(0) if match else None

    @staticmethod
    def _extract_uf(text: str) -> str | None:
        match = re.search(
            r"\b(ac|al|ap|am|ba|ce|df|es|go|ma|mt|ms|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to)\b",
            text,
        )
        return match.group(1).upper() if match else None

    def _build_scope_args(self, text: str, *, default_limit: int) -> dict[str, Any]:
        args: dict[str, Any] = {"limit": default_limit}
        year = re.search(r"\b(20\d{2})\b", text)
        if year:
            args["year"] = int(year.group(1))
        uf = self._extract_uf(text)
        if uf:
            args["uf"] = uf
        top_n = re.search(r"\btop\s+(\d{1,2})\b", text)
        if top_n:
            args["limit"] = min(int(top_n.group(1)), 20)
        return args

    @staticmethod
    def _build_compare_args(query: str) -> dict[str, Any]:
        clean = query.replace(" versus ", " vs ")
        parts = [part.strip(" ?") for part in clean.split(" vs ") if part.strip(" ?")]
        args: dict[str, Any] = {}
        if len(parts) >= 2:
            args["empresa_a"] = parts[0][:120]
            args["empresa_b"] = parts[1][:120]
        return args

    def _format(self, tool_name: str, result: Any) -> str:
        if tool_name == "get_operations_status" and isinstance(result, dict):
            freshness = result.get("data_freshness") or result.get("freshness") or "-"
            return (
                "FleetIntel\n\n"
                f"status={result.get('status', '-')}\n"
                f"freshness={freshness}\n"
                f"generated_at={result.get('generated_at') or result.get('timestamp', '-')}"
            )
        if tool_name == "count_empresa_registrations" and isinstance(result, dict):
            if result.get("ambiguous"):
                empresas = result.get("empresas") or []
                lines = ["FleetIntel", "", result.get("message", "Empresa ambigua.")]
                for empresa in empresas[:5]:
                    if not isinstance(empresa, dict):
                        continue
                    lines.append(
                        f"- {empresa.get('razao_social') or empresa.get('nome_fantasia') or 'empresa'} | "
                        f"CNPJ {empresa.get('cnpj', '-')} | segmento {empresa.get('segmento_cliente', '-')}"
                    )
                return "\n".join(lines)
            empresas = result.get("empresas") or []
            empresa = empresas[0] if empresas and isinstance(empresas[0], dict) else {}
            ano = result.get("ano")
            periodo = f" em {ano}" if ano else ""
            return (
                "FleetIntel\n\n"
                f"{empresa.get('razao_social') or 'Empresa'} registrou {result.get('count', 0)} "
                f"emplacamentos{periodo}.\n"
                f"CNPJ: {empresa.get('cnpj', '-')}"
            )
        if tool_name == "list_suggested_questions" and isinstance(result, dict):
            items = (
                result.get("questions")
                or result.get("items")
                or result.get("suggested_questions")
                or []
            )
            if isinstance(items, list) and items:
                lines = ["FleetIntel\n", "Perguntas sugeridas:"]
                for item in items[:8]:
                    lines.append(f"- {item}")
                return "\n".join(lines)
        if tool_name in {
            "buying_signals",
            "new_entrants",
            "top_empresas_by_registrations",
        } and isinstance(result, dict):
            return self._format_ranked_result(tool_name, result)
        return render_result_block("FleetIntel", result)

    @staticmethod
    def _format_ranked_result(tool_name: str, result: dict[str, Any]) -> str:
        candidates = []
        for key in ("items", "results", "signals", "empresas", "companies"):
            value = result.get(key)
            if isinstance(value, list):
                candidates = value
                break
        if not candidates:
            return render_result_block("FleetIntel", result)

        lines = [f"FleetIntel\n\n{tool_name}:"]
        for item in candidates[:8]:
            if not isinstance(item, dict):
                lines.append(f"- {item}")
                continue
            name = (
                item.get("razao_social")
                or item.get("empresa")
                or item.get("company_name")
                or item.get("nome")
                or "item"
            )
            score = (
                item.get("score")
                or item.get("total")
                or item.get("registrations")
                or item.get("count")
            )
            cnpj = item.get("cnpj")
            suffix = []
            if score is not None:
                suffix.append(f"score={score}")
            if cnpj:
                suffix.append(f"cnpj={cnpj}")
            details = f" ({', '.join(suffix)})" if suffix else ""
            lines.append(f"- {name}{details}")
        return "\n".join(lines)

    async def _format_remote_failure(
        self,
        *,
        client: RemoteMCPClient,
        error: RemoteMCPError,
        tool_name: str,
    ) -> str:
        health_summary = ""
        if tool_name != "get_operations_status":
            try:
                health = await client.call_tool("get_operations_status", {})
                if isinstance(health, dict):
                    health_summary = (
                        "\n"
                        f"Preflight FleetIntel: status={health.get('status', '-')} "
                        f"freshness={health.get('data_freshness') or health.get('freshness') or '-'} "
                        f"generated_at={health.get('generated_at') or health.get('timestamp', '-')}"
                    )
            except Exception:
                health_summary = "\nPreflight FleetIntel indisponivel no momento."

        status_fragment = f"HTTP {error.status_code}" if error.status_code else error.error_type
        return (
            "FleetIntel\n\n"
            f"A consulta falhou ao executar `{tool_name}`.\n"
            f"Falha detectada: {status_fragment} na etapa `{error.stage}`."
            f"{health_summary}\n"
            "Posso tentar novamente depois ou seguir por outra leitura comercial."
        )

    async def _maybe_refine_company_count(
        self,
        *,
        client: RemoteMCPClient,
        tool_args: dict[str, Any],
        result: Any,
    ) -> str | None:
        if not isinstance(result, dict):
            return None
        empresas = result.get("empresas")
        if isinstance(empresas, list) and empresas:
            return None
        company_name = str(tool_args.get("razao_social") or "").strip()
        if not company_name:
            return None

        try:
            search_result = await client.call_tool(
                "search_empresas",
                {"razao_social": company_name, "limit": 5},
            )
        except Exception:
            return None

        if not isinstance(search_result, dict):
            return (
                "FleetIntel\n\n"
                f"Nao consegui resolver a empresa `{company_name}` por nome na base atual.\n"
                "Se voce me passar o CNPJ ou o nome juridico exato, eu refaco a consulta."
            )
        matches = search_result.get("empresas") or search_result.get("results") or []
        if not isinstance(matches, list) or not matches:
            return (
                "FleetIntel\n\n"
                f"Nao encontrei uma entidade exata para `{company_name}` na base FleetIntel.\n"
                "Se voce me passar o CNPJ ou o nome juridico exato, eu refaco a consulta."
            )

        lines = [
            "FleetIntel",
            "",
            f"Nao consegui travar a entidade exata para `{company_name}` so pelo nome.",
            "Encontrei estas empresas parecidas:",
        ]
        for item in matches[:5]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('razao_social') or item.get('nome_fantasia') or 'empresa'} | "
                f"CNPJ {item.get('cnpj', '-')} | grupo {item.get('grupo_locadora', '-')}"
            )
        lines.append("Se quiser, eu sigo com o CNPJ ou com o nome juridico exato.")
        return "\n".join(lines)
