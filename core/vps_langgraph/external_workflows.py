"""Deterministic external specialist workflows for combined prompts."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import structlog

from core.integrations import (
    ConsumerSyncError,
    RemoteMCPError,
    build_specialist_mcp_client,
    get_consumer_sync_manager,
    wants_raw_specialist_output,
)

if TYPE_CHECKING:
    from core.skills.registry import SkillRegistry

logger = structlog.get_logger()

_FLEET_MARKERS = (
    "fleetintel",
    "frota",
    "emplac",
    "caminh",
    "market share",
    "participacao de mercado",
    "sinais de compra",
    "buying signals",
    "priorizar",
    "prioridade",
)
_CNPJ_MARKERS = (
    "grupo economico",
    "grupo econômico",
    "socio",
    "socio",
    "cadastro",
    "cadastral",
    "receita",
    "brazilcnpj",
)
_INSIGHT_MARKERS = (
    "fleetintel analyst",
    "skill fleetintel_analyst",
    "insights",
    "o que mudou",
    "ultimo sync",
    "último sync",
    "priorizar",
    "prioridade",
    "buying signals",
    "market share",
    "participacao de mercado",
)


@dataclass(frozen=True, slots=True)
class ExternalWorkflowPlan:
    kind: Literal["account_360", "account_360_plus_insights"]
    steps: tuple[str, ...]
    response_mode: Literal["single_answer", "sectioned_answer"]
    provider_composite_tool: str | None = None


def detect_external_workflow(message: str) -> ExternalWorkflowPlan | None:
    msg = _normalize_text(message)
    has_fleet = any(marker in msg for marker in _FLEET_MARKERS)
    has_cnpj_context = any(marker in msg for marker in _CNPJ_MARKERS)
    mentions_brazilcnpj = "brazilcnpj enricher" in msg or "skill brazilcnpj" in msg
    mentions_orchestrator = (
        "fleetintel orchestrator" in msg or "skill fleetintel_orchestrator" in msg
    )
    mentions_analyst = "fleetintel analyst" in msg or "skill fleetintel_analyst" in msg
    wants_insights = any(marker in msg for marker in _INSIGHT_MARKERS)

    is_combined = (
        (has_fleet and (has_cnpj_context or mentions_brazilcnpj))
        or (mentions_orchestrator and mentions_analyst)
        or (mentions_brazilcnpj and wants_insights)
    )
    if not is_combined:
        return None

    steps = ["fleetintel_orchestrator"]
    if mentions_analyst or wants_insights:
        steps.append("fleetintel_analyst")

    preferred = set()
    try:
        manager = get_consumer_sync_manager()
        if manager.should_use_preferred_tools("fleetintel"):
            preferred = set(manager.preferred_tools_for("fleetintel"))
    except Exception:
        preferred = set()

    provider_composite_tool = (
        "get_account_360_brief" if "get_account_360_brief" in preferred else None
    )
    response_mode = "sectioned_answer" if wants_raw_specialist_output(msg) else "single_answer"
    kind = "account_360_plus_insights" if "fleetintel_analyst" in steps else "account_360"
    return ExternalWorkflowPlan(
        kind=kind,
        steps=tuple(steps),
        response_mode=response_mode,
        provider_composite_tool=provider_composite_tool,
    )


async def run_external_workflow(
    *,
    message: str,
    registry: "SkillRegistry",
    plan: ExternalWorkflowPlan,
) -> str:
    sections: list[tuple[str, str]] = []
    composite_answer = await _try_provider_composite(message=message, plan=plan)
    if composite_answer:
        sections.append(("Conta e cadastro", composite_answer))
    else:
        for step in plan.steps:
            result = await registry.execute_skill(step, {"raw_input": message, "query": message})
            cleaned = _strip_heading(str(result))
            if cleaned:
                sections.append((_label_for_step(step), cleaned))

    return _compose_sections(sections, response_mode=plan.response_mode)


async def _try_provider_composite(
    *,
    message: str,
    plan: ExternalWorkflowPlan,
) -> str | None:
    if not plan.provider_composite_tool:
        return None
    try:
        client = build_specialist_mcp_client(
            "fleetintel",
            client_name="agentvps-fleetintel-workflow",
        )
        arguments = await _resolve_account_360_arguments(client=client, message=message)
        if not arguments:
            return None
        result = await client.call_tool(plan.provider_composite_tool, arguments)
    except (ConsumerSyncError, RemoteMCPError, RuntimeError) as exc:
        logger.warning("external_workflow_composite_fallback", error=str(exc))
        return None
    return _format_brief_result(result)


def _format_brief_result(result: object) -> str:
    if isinstance(result, str):
        return result.strip()
    if not isinstance(result, dict):
        return str(result)

    lines: list[str] = []
    headline = str(result.get("headline") or "").strip()
    executive_summary = str(result.get("executive_summary") or "").strip()
    refinement_instruction = str(result.get("refinement_instruction") or "").strip()
    if headline:
        lines.append(headline)
    if executive_summary:
        lines.append(executive_summary)

    findings = result.get("key_findings") or []
    if isinstance(findings, list) and findings:
        lines.append("")
        lines.append("Pontos principais:")
        for finding in findings[:4]:
            if not isinstance(finding, dict):
                continue
            detail = finding.get("why_it_matters") or finding.get("title")
            if detail:
                lines.append(f"- {detail}")

    next_steps = result.get("recommended_next_steps") or []
    if isinstance(next_steps, list) and next_steps:
        lines.append("")
        lines.append("Proximos passos:")
        for item in next_steps[:3]:
            lines.append(f"- {item}")

    shortlist = result.get("shortlist") or result.get("candidates") or []
    if isinstance(shortlist, list) and shortlist:
        lines.append("")
        lines.append("Opcoes encontradas:")
        for item in shortlist[:4]:
            if not isinstance(item, dict):
                lines.append(f"- {item}")
                continue
            title = (
                item.get("headline")
                or item.get("company_name")
                or item.get("razao_social")
                or item.get("name")
                or "opcao"
            )
            cnpj = item.get("cnpj")
            suffix = f" | CNPJ {cnpj}" if cnpj else ""
            lines.append(f"- {title}{suffix}")

    if refinement_instruction:
        lines.append("")
        lines.append(f"Refine assim: {refinement_instruction}")

    limitations = result.get("limitations") or []
    if isinstance(limitations, list) and limitations:
        lines.append("")
        lines.append("Limitacoes:")
        for item in limitations[:3]:
            lines.append(f"- {item}")

    return "\n".join(line for line in lines if line is not None).strip()


async def _resolve_account_360_arguments(
    *,
    client: object,
    message: str,
) -> dict[str, str] | None:
    list_tools = getattr(client, "list_tools", None)
    query = message.strip()
    cnpj = _extract_cnpj(message)
    if not callable(list_tools):
        return {"cnpj": cnpj} if cnpj else {"query": query}

    try:
        catalog = await list_tools()
    except Exception:
        return {"cnpj": cnpj} if cnpj else {"query": query}

    tool_spec = _find_tool_spec(catalog, "get_account_360_brief")
    input_schema = {}
    if isinstance(tool_spec, dict):
        input_schema = tool_spec.get("inputSchema") or tool_spec.get("input_schema") or {}
    properties = input_schema.get("properties") if isinstance(input_schema, dict) else {}
    property_names = set(properties.keys()) if isinstance(properties, dict) else set()

    if cnpj and "cnpj" in property_names:
        return {"cnpj": cnpj}
    for generic in ("query", "input", "target"):
        if generic in property_names:
            return {generic: query}
    if cnpj:
        return {"cnpj": cnpj}
    for semantic_key in (
        "company_name",
        "razao_social",
        "legal_name",
        "trade_name",
        "nome_fantasia",
        "partner_name",
        "socio_name",
        "shareholder_name",
    ):
        if semantic_key in property_names:
            return {semantic_key: query}
    return {"query": query}


def _find_tool_spec(catalog: object, tool_name: str) -> dict[str, object] | None:
    if isinstance(catalog, dict):
        tools = catalog.get("tools")
        if isinstance(tools, list):
            for tool in tools:
                if isinstance(tool, dict) and tool.get("name") == tool_name:
                    return tool
    if isinstance(catalog, list):
        for tool in catalog:
            if isinstance(tool, dict) and tool.get("name") == tool_name:
                return tool
    return None


def _compose_sections(
    sections: list[tuple[str, str]],
    *,
    response_mode: Literal["single_answer", "sectioned_answer"],
) -> str:
    if not sections:
        return "Nao consegui montar a resposta externa combinada."
    if len(sections) == 1 and response_mode == "single_answer":
        return sections[0][1]

    lines = [
        "Visao consolidada:" if response_mode == "single_answer" else "Resposta por etapa:",
        "",
    ]
    for index, (label, body) in enumerate(sections):
        lines.append(f"{label}:")
        lines.append(body)
        if index < len(sections) - 1:
            lines.append("")
    return "\n".join(lines).strip()


def _strip_heading(value: str) -> str:
    lines = [line.rstrip() for line in value.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ""
    if lines[0].strip() in {
        "FleetIntel Orchestrator",
        "FleetIntel",
        "BrazilCNPJ",
        "Operador Codex",
    }:
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def _label_for_step(step: str) -> str:
    if step == "fleetintel_orchestrator":
        return "Conta e cadastro"
    if step == "fleetintel_analyst":
        return "Insights de mercado"
    if step == "brazilcnpj":
        return "Cadastro"
    return step


def _extract_cnpj(message: str) -> str | None:
    digits = re.sub(r"\D", "", message)
    match = re.search(r"\b\d{14}\b", digits)
    return match.group(0) if match else None


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().strip())
    return "".join(char for char in normalized if not unicodedata.combining(char))
