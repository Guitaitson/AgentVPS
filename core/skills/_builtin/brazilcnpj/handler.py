"""BrazilCNPJ specialist skill backed by the external BrazilCNPJ MCP server."""

from __future__ import annotations

import re
from typing import Any

import structlog

from core.integrations import (
    ConsumerSyncError,
    RemoteMCPClient,
    RemoteMCPError,
    build_specialist_mcp_client,
    get_consumer_sync_manager,
    render_result_block,
)
from core.skills.base import SkillBase

logger = structlog.get_logger()

_CNPJ_RE = re.compile(r"\b(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\d{14})\b")


class BrazilCNPJSkill(SkillBase):
    async def execute(self, args: dict[str, Any] | None = None) -> str:
        payload = args or {}
        query = str(payload.get("raw_input") or payload.get("query") or "").strip()
        if not query:
            return "Informe um CNPJ, empresa, socios, grupo economico ou CNAE para consulta."

        try:
            client = build_specialist_mcp_client(
                "brazilcnpj",
                client_name="agentvps-brazilcnpj",
            )
        except ConsumerSyncError as exc:
            return str(exc)

        tool_name, tool_args = self._route(query)
        logger.info("brazilcnpj_execute", tool=tool_name)
        try:
            result = await client.call_tool(tool_name, tool_args)
        except ConsumerSyncError as exc:
            return str(exc)
        except RemoteMCPError as exc:
            return await self._format_remote_failure(client=client, error=exc, tool_name=tool_name)
        return self._format(tool_name, result)

    def _route(self, query: str) -> tuple[str, dict[str, Any]]:
        msg = query.lower()
        cnpj = self._extract_cnpj(query)
        preferred = self._preferred_tools()

        if any(keyword in msg for keyword in ("health", "saude", "status", "bootstrap")):
            return ("get_bootstrap_status" if "bootstrap" in msg else "health_check"), {}
        if "grupo economico" in msg:
            if cnpj:
                if "get_group_context_brief" in preferred:
                    return "get_group_context_brief", {"cnpj": cnpj}
                return "get_grupo_economico", {"cnpj": cnpj}
            return "search_empresa", self._company_lookup_args(query)
        if any(keyword in msg for keyword in ("socio", "socios")):
            if cnpj:
                return "get_socios", {"cnpj": cnpj}
            return "search_socios", self._partner_lookup_args(query)
        if "cnae" in msg:
            cnae = self._extract_cnae(msg)
            args: dict[str, Any] = {"limit": 20}
            if cnae:
                args["cnae"] = cnae
            uf = self._extract_uf(msg)
            if uf:
                args["uf"] = uf
            if "search_companies_by_cnae_brief" in preferred:
                return "search_companies_by_cnae_brief", args
            return "search_by_cnae", args
        if any(keyword in msg for keyword in ("enriquec", "atualiza", "refresh")) and cnpj:
            return "enrich_cnpj", {"cnpj": cnpj, "force_refresh": True}
        if any(keyword in msg for keyword in ("completa", "completo", "perfil completo")) and cnpj:
            return "get_empresa_completa", {"cnpj": cnpj}
        if cnpj:
            if "get_company_registry_brief" in preferred:
                return "get_company_registry_brief", {"cnpj": cnpj}
            if any(keyword in msg for keyword in ("cache", "rapido", "cached")):
                return "get_cached_cnpj_profile", {"cnpj": cnpj}
            return "search_empresa", {"cnpj": cnpj, "limit": 5}
        return "search_empresa", self._company_lookup_args(query)

    @staticmethod
    def _preferred_tools() -> set[str]:
        manager = get_consumer_sync_manager()
        if not manager.should_use_preferred_tools("brazilcnpj"):
            return set()
        return set(manager.preferred_tools_for("brazilcnpj"))

    @staticmethod
    def _extract_cnpj(text: str) -> str | None:
        match = _CNPJ_RE.search(text)
        if not match:
            return None
        digits = re.sub(r"\D", "", match.group(1))
        return digits if len(digits) == 14 else None

    @staticmethod
    def _extract_cnae(text: str) -> str | None:
        match = re.search(r"\b\d{4}-\d/\d{2}\b|\b\d{7}\b", text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_uf(text: str) -> str | None:
        match = re.search(
            r"\b(ac|al|ap|am|ba|ce|df|es|go|ma|mt|ms|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to)\b",
            text,
        )
        return match.group(1).upper() if match else None

    @staticmethod
    def _company_lookup_args(query: str) -> dict[str, Any]:
        cleaned = query.strip().strip("?")
        return {"razao_social": cleaned[:120], "limit": 10}

    @staticmethod
    def _partner_lookup_args(query: str) -> dict[str, Any]:
        cleaned = query.strip().strip("?")
        return {"nome": cleaned[:120], "limit": 10}

    def _format(self, tool_name: str, result: Any) -> str:
        title = "BrazilCNPJ"
        if tool_name == "health_check" and isinstance(result, dict):
            return (
                "BrazilCNPJ\n\n"
                f"status={result.get('status')} "
                f"database_ok={result.get('database_ok')} "
                f"schema_ok={result.get('schema_ok')}"
            )
        if tool_name == "get_company_registry_brief" and isinstance(result, dict):
            lines = ["BrazilCNPJ", ""]
            lines.append(
                f"Empresa: {result.get('company_name') or result.get('razao_social') or '-'}"
            )
            lines.append(f"CNPJ: {result.get('cnpj') or '-'}")
            if result.get("uf"):
                lines.append(f"UF: {result.get('uf')}")
            if result.get("porte"):
                lines.append(f"Porte: {result.get('porte')}")
            if result.get("situacao_cadastral"):
                lines.append(f"Situacao: {result.get('situacao_cadastral')}")
            return "\n".join(lines)
        if tool_name == "get_group_context_brief" and isinstance(result, dict):
            return render_result_block("BrazilCNPJ", result, max_chars=1200)
        if tool_name == "search_empresa" and isinstance(result, dict):
            empresas = result.get("empresas") or result.get("results") or []
            if not empresas:
                return "BrazilCNPJ\n\nNenhuma empresa encontrada."
            lines = ["BrazilCNPJ\n", "Empresas encontradas:"]
            for item in empresas[:5]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"- {item.get('razao_social') or item.get('nome_fantasia') or 'empresa'} | "
                    f"CNPJ {item.get('cnpj', '-')} | UF {item.get('uf', '-')}"
                )
            return "\n".join(lines)
        return render_result_block(title, result)

    async def _format_remote_failure(
        self,
        *,
        client: RemoteMCPClient,
        error: RemoteMCPError,
        tool_name: str,
    ) -> str:
        health_summary = ""
        if tool_name != "health_check":
            try:
                health = await client.call_tool("health_check", {})
                if isinstance(health, dict):
                    health_summary = (
                        "\n"
                        f"Preflight BrazilCNPJ: status={health.get('status', '-')} "
                        f"database_ok={health.get('database_ok', '-')} "
                        f"schema_ok={health.get('schema_ok', '-')}"
                    )
            except Exception:
                health_summary = "\nPreflight BrazilCNPJ indisponivel no momento."

        status_fragment = f"HTTP {error.status_code}" if error.status_code else error.error_type
        return (
            "BrazilCNPJ\n\n"
            f"A consulta falhou ao executar `{tool_name}`.\n"
            f"Falha detectada: {status_fragment} na etapa `{error.stage}`."
            f"{health_summary}\n"
            "Posso tentar novamente depois ou limitar a resposta ao que ja estiver em cache."
        )
