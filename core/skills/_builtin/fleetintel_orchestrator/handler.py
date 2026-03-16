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
        company_briefs: list[dict[str, Any]] = []
        company_details: list[dict[str, Any]] = []
        group_contexts: list[dict[str, Any]] = []

        candidate_cnpjs = extract_cnpjs(fleet_result)
        explicit_cnpj = self._extract_cnpj(query)
        if explicit_cnpj and explicit_cnpj not in candidate_cnpjs:
            candidate_cnpjs.insert(0, explicit_cnpj)

        if needs_cnpj and cnpj_client.is_configured:
            try:
                cnpj_health = await cnpj_client.call_tool("health_check", {})
                if isinstance(cnpj_health, dict) and cnpj_health.get("status") == "ok":
                    wants_group = "grupo economico" in query.lower()
                    wants_partners = any(
                        marker in query.lower() for marker in ("socio", "socios", "sócio", "sócios")
                    )
                    for cnpj in candidate_cnpjs[:3]:
                        if "get_company_registry_brief" in self._preferred_tools("brazilcnpj"):
                            company_briefs.append(
                                await cnpj_client.call_tool(
                                    "get_company_registry_brief",
                                    {"cnpj": cnpj},
                                )
                            )
                        elif "get_cached_cnpj_profile" in self._fallback_tools("brazilcnpj"):
                            company_briefs.append(
                                await cnpj_client.call_tool(
                                    "get_cached_cnpj_profile",
                                    {"cnpj": cnpj},
                                )
                            )
                        if wants_group:
                            if "get_group_context_brief" in self._preferred_tools("brazilcnpj"):
                                group_contexts.append(
                                    await cnpj_client.call_tool(
                                        "get_group_context_brief",
                                        {"cnpj": cnpj},
                                    )
                                )
                            elif "get_grupo_economico" in self._fallback_tools("brazilcnpj"):
                                group_contexts.append(
                                    await cnpj_client.call_tool(
                                        "get_grupo_economico",
                                        {"cnpj": cnpj},
                                    )
                                )
                        if wants_partners and "get_empresa_completa" in self._fallback_tools(
                            "brazilcnpj"
                        ):
                            company_details.append(
                                await cnpj_client.call_tool(
                                    "get_empresa_completa",
                                    {"cnpj": cnpj},
                                )
                            )
            except RemoteMCPError as exc:
                logger.warning("fleetintel_orchestrator_cnpj_degraded", error=str(exc))

        return self._format(
            query=query,
            readiness=readiness,
            fleet_tool=fleet_tool,
            fleet_result=fleet_result,
            cnpj_health=cnpj_health,
            company_briefs=company_briefs,
            company_details=company_details,
            group_contexts=group_contexts,
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
        explicit_cnpj = self._extract_cnpj(query)
        if company_count_args:
            return "count_empresa_registrations", company_count_args
        args: dict[str, Any] = {"limit": 5}
        uf = self._extract_uf(query)
        if uf:
            args["uf"] = uf
        if explicit_cnpj and any(
            marker in msg
            for marker in (
                "frota",
                "me dizer sobre",
                "falar da frota",
                "conta",
                "empresa",
                "perfil",
            )
        ):
            if "get_fleet_account_brief" in preferred:
                return "get_fleet_account_brief", {"cnpj": explicit_cnpj}
            return "empresa_profile", {"cnpj": explicit_cnpj}
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
        if explicit_cnpj:
            if "get_fleet_account_brief" in preferred:
                return "get_fleet_account_brief", {"cnpj": explicit_cnpj}
            return "empresa_profile", {"cnpj": explicit_cnpj}
        return "top_empresas_by_registrations", args

    @staticmethod
    def _preferred_tools(service: str) -> set[str]:
        manager = get_consumer_sync_manager()
        if not manager.should_use_preferred_tools(service):
            return set()
        return set(manager.preferred_tools_for(service))

    @staticmethod
    def _fallback_tools(service: str) -> set[str]:
        return set(get_consumer_sync_manager().fallback_tools_for(service))

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
        company_briefs: list[dict[str, Any]],
        company_details: list[dict[str, Any]],
        group_contexts: list[dict[str, Any]],
    ) -> str:
        lines = ["FleetIntel Orchestrator", ""]
        summary = self._format_readiness_summary(readiness)
        fleet_answer = self._format_fleet_result(fleet_tool=fleet_tool, fleet_result=fleet_result)
        if fleet_answer:
            lines.append(fleet_answer)
        if company_briefs:
            lines.append("")
            lines.extend(self._format_company_briefs(company_briefs))
        partner_lines = self._format_partner_context(company_details)
        if partner_lines:
            lines.append("")
            lines.extend(partner_lines)
        group_lines = self._format_group_context(group_contexts)
        if group_lines:
            lines.append("")
            lines.extend(group_lines)
        limitations = self._build_limitations(
            company_briefs=company_briefs,
            company_details=company_details,
            group_contexts=group_contexts,
        )
        if limitations:
            lines.append("")
            lines.append("Limitacoes:")
            for item in limitations:
                lines.append(f"- {item}")

        if cnpj_health is not None:
            lines.append("")
            if summary:
                lines.append(f"Prontidao FleetIntel: {summary}")
            lines.append(
                "BrazilCNPJ health: "
                f"status={cnpj_health.get('status', '-')} "
                f"database_ok={cnpj_health.get('database_ok', '-')}"
            )

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
        if fleet_tool == "get_market_changes_brief" and isinstance(fleet_result, dict):
            items = (
                fleet_result.get("key_findings")
                or fleet_result.get("items")
                or fleet_result.get("changes")
                or fleet_result.get("supporting_data", {}).get("movements")
                or []
            )
            lines = ["Leitura de mercado:"]
            headline = fleet_result.get("headline")
            summary = fleet_result.get("executive_summary") or fleet_result.get("summary")
            if headline:
                lines.append(f"- headline: {headline}")
            if summary:
                lines.append(f"- resumo: {summary}")
            if isinstance(items, list) and items:
                for item in items[:4]:
                    if isinstance(item, dict):
                        headline = (
                            item.get("headline")
                            or item.get("title")
                            or item.get("summary")
                            or item.get("change")
                            or item.get("why_it_matters")
                        )
                        subject = item.get("subject") or {}
                        company = (
                            item.get("company_name")
                            or item.get("razao_social")
                            or subject.get("razao_social")
                            or subject.get("title")
                        )
                        if headline and company:
                            lines.append(f"- {company}: {headline}")
                        elif headline:
                            lines.append(f"- {headline}")
                    else:
                        lines.append(f"- {item}")
                return "\n".join(lines)
            return render_result_block("", fleet_result, max_chars=1000).strip()
        if fleet_tool == "get_account_prioritization_brief" and isinstance(fleet_result, dict):
            items = fleet_result.get("items") or fleet_result.get("accounts") or []
            lines = ["Priorizacao comercial:"]
            for item in items[:4]:
                if not isinstance(item, dict):
                    lines.append(f"- {item}")
                    continue
                company = item.get("company_name") or item.get("razao_social") or "conta"
                rationale = item.get("summary") or item.get("reason") or item.get("headline")
                if rationale:
                    lines.append(f"- {company}: {rationale}")
                else:
                    lines.append(f"- {company}")
            return "\n".join(lines)
        if fleet_tool in {"empresa_profile", "get_fleet_account_brief"} and isinstance(
            fleet_result, dict
        ):
            if fleet_result.get("error"):
                return str(fleet_result.get("error"))

            supporting_data = fleet_result.get("supporting_data") or {}
            account_layers = supporting_data.get("account_layers") or {}
            exact_entity = account_layers.get("exact_entity") or {}
            empresa = (
                fleet_result.get("empresa")
                or exact_entity.get("empresa")
                or {}
            )
            if not empresa and (fleet_result.get("company_name") or fleet_result.get("headline")):
                empresa = {
                    "razao_social": fleet_result.get("company_name") or fleet_result.get("headline"),
                    "cnpj": fleet_result.get("cnpj"),
                }
            resumo = (
                fleet_result.get("entity_summary", {}).get("resumo")
                or fleet_result.get("resumo")
                or exact_entity.get("resumo")
                or {}
            )
            group_summary = (
                fleet_result.get("group_summary")
                or account_layers.get("effective_group")
                or {}
            )
            lines = ["Leitura de frota:"]
            lines.append(
                f"- empresa: {empresa.get('razao_social') or 'empresa'} | CNPJ {empresa.get('cnpj', '-')}"
            )
            if fleet_result.get("executive_summary"):
                lines.append(f"- leitura executiva: {fleet_result['executive_summary']}")
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
                if not members:
                    groups = group_summary.get("groups") or []
                    if groups and isinstance(groups[0], dict):
                        members = groups[0].get("members") or []
                lines.append(
                    "- grupo: "
                    f"{len(members)} membros, "
                    f"{group_summary.get('total_emplacamentos', 0)} emplacamentos totais"
                )
                groups = group_summary.get("groups") or []
                if groups and isinstance(groups[0], dict) and groups[0].get("canonical_name"):
                    lines.append(f"- grupo efetivo: {groups[0]['canonical_name']}")
                if group_summary.get("emplacamentos_ano_corrente") is not None:
                    lines.append(
                        f"- ano corrente: {group_summary.get('emplacamentos_ano_corrente', 0)} emplacamentos"
                    )
                if group_summary.get("ultima_compra_grupo"):
                    lines.append(
                        f"- ultima compra do grupo: {group_summary['ultima_compra_grupo']}"
                    )
            return "\n".join(lines)

        return render_result_block("", fleet_result, max_chars=1400).strip()

    @staticmethod
    def _format_company_briefs(company_briefs: list[dict[str, Any]]) -> list[str]:
        lines = ["Cadastro da empresa:"]
        for item in company_briefs[:2]:
            if not isinstance(item, dict):
                lines.append(f"- {item}")
                continue
            layers = (item.get("supporting_data") or {}).get("company_layers") or {}
            exact_entity = layers.get("exact_entity") or {}
            company = (
                item.get("company_name")
                or item.get("razao_social")
                or item.get("headline")
                or exact_entity.get("razao_social")
                or "empresa"
            )
            cnpj = item.get("cnpj") or exact_entity.get("cnpj") or "-"
            details = [f"CNPJ {cnpj}"]
            uf = item.get("uf") or exact_entity.get("uf")
            porte = item.get("porte") or exact_entity.get("porte")
            situacao = item.get("situacao_cadastral") or exact_entity.get("situacao_cadastral")
            cnae = item.get("cnae_principal") or exact_entity.get("cnae_principal")
            if uf:
                details.append(f"UF {uf}")
            if porte:
                details.append(f"porte {porte}")
            if situacao:
                details.append(f"situacao {situacao}")
            if cnae:
                details.append(f"CNAE {cnae}")
            lines.append(f"- {company} | " + " | ".join(details))
            executive_summary = item.get("executive_summary")
            if executive_summary:
                lines.append(f"  resumo: {executive_summary}")
        return lines

    @staticmethod
    def _format_partner_context(company_details: list[dict[str, Any]]) -> list[str]:
        if not company_details:
            return []
        lines = ["Socios:"]
        found = False
        for item in company_details[:1]:
            if not isinstance(item, dict):
                continue
            socios = (
                item.get("socios")
                or item.get("quadro_societario")
                or item.get("integrantes_qsa")
                or []
            )
            for socio in socios[:4]:
                if not isinstance(socio, dict):
                    continue
                name = socio.get("nome") or socio.get("name")
                role = (
                    socio.get("qualificacao")
                    or socio.get("qualificacao_oficial")
                    or socio.get("participant_role_label")
                    or socio.get("role")
                )
                if name:
                    found = True
                    lines.append(f"- {name}" + (f" | {role}" if role else ""))
        return lines if found else []

    @staticmethod
    def _format_group_context(group_contexts: list[dict[str, Any]]) -> list[str]:
        if not group_contexts:
            return []
        lines = ["Grupo economico:"]
        found = False
        for item in group_contexts[:1]:
            if not isinstance(item, dict):
                continue
            supporting_data = item.get("supporting_data") or {}
            group_layers = supporting_data.get("group_layers") or {}
            effective_group = item.get("effective_group") or group_layers.get("effective_group") or {}
            groups = effective_group.get("groups") or []
            first_group = groups[0] if groups and isinstance(groups[0], dict) else {}
            group_name = (
                item.get("group_name")
                or item.get("nome_grupo")
                or first_group.get("canonical_name")
                or item.get("headline")
            )
            members = (
                item.get("members")
                or item.get("group_members")
                or first_group.get("members")
                or []
            )
            total = item.get("member_count") or effective_group.get("count") or (
                len(members) if isinstance(members, list) else None
            )
            if group_name:
                found = True
                summary = f"- {group_name}"
                if total:
                    summary += f" | {total} empresas no contexto retornado"
                lines.append(summary)
            elif total:
                found = True
                lines.append(f"- {total} empresas no contexto retornado")
            related = group_layers.get("related_companies") or item.get("related_companies") or []
            if isinstance(related, list) and related:
                found = True
                lines.append(f"- relacionadas monitoradas: {len(related)} no contexto adicional")
        return lines if found else []

    @staticmethod
    def _build_limitations(
        *,
        company_briefs: list[dict[str, Any]],
        company_details: list[dict[str, Any]],
        group_contexts: list[dict[str, Any]],
    ) -> list[str]:
        limitations: list[str] = []
        if not company_briefs:
            limitations.append(
                "o extrato cadastral retornado foi insuficiente para consolidar o perfil da empresa"
            )
        if company_details:
            details = company_details[0] if isinstance(company_details[0], dict) else {}
            socios = (
                details.get("socios")
                or details.get("quadro_societario")
                or details.get("integrantes_qsa")
                or []
            )
            if not socios:
                limitations.append("o retorno atual nao trouxe socios estruturados")
        if group_contexts:
            first = group_contexts[0] if isinstance(group_contexts[0], dict) else {}
            if not any(
                first.get(key) for key in ("group_name", "nome_grupo", "members", "group_members")
            ):
                limitations.append("o contexto de grupo economico veio sem detalhamento suficiente")
        return limitations
