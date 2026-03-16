"""Shared routing rules for FleetIntel/BrazilCNPJ specialist skills."""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

FLEET_KEYWORDS = [
    "camin",
    "caminhao",
    "caminhoes",
    "emplac",
    "emplacamento",
    "frota",
    "market share",
    "participacao de mercado",
    "comprou caminhao",
    "buying signal",
    "sinais de compra",
    "trend",
    "tendencia",
    "entrantes",
    "fleetintel",
    "locadora",
    "implemento",
    "priorizar contas",
]

CNPJ_KEYWORDS = [
    "cnpj",
    "grupo economico",
    "socio",
    "socios",
    "cnae",
    "cadastro",
    "cadastral",
    "receita federal",
    "enriquecer",
    "enriqueca",
    "enrichment",
    "empresa completa",
]

ORCHESTRATION_KEYWORDS = [
    "cruze",
    "combina",
    "combine",
    "o que mudou",
    "unica resposta",
]

CNPJ_ENRICHMENT_KEYWORDS = [
    "grupo economico",
    "socio",
    "socios",
    "cnae",
    "cadastro",
    "cadastral",
    "receita federal",
    "enriquecer",
    "enriqueca",
    "enrichment",
    "empresa completa",
]

COMPANY_VOLUME_VERBS = [
    "comprou",
    "compraram",
    "emplacou",
    "emplacaram",
    "registrou",
    "registraram",
    "adquiriu",
    "adquiriram",
]

COMPANY_VOLUME_NOUNS = [
    "caminh",
    "veicul",
    "emplac",
    "unidad",
]

CodexExecutionMode = Literal["direct_local", "codex_synthesizer", "codex_operator"]


def detect_external_skill(message: str) -> str | None:
    msg = _normalize_text(message)
    mentions_generic_fleet = "skill fleetintel" in msg or "use a skill fleetintel" in msg
    mentions_analyst = "skill fleetintel_analyst" in msg or "fleetintel analyst" in msg
    mentions_orchestrator = (
        "skill fleetintel_orchestrator" in msg or "fleetintel orchestrator" in msg
    )
    mentions_brazilcnpj = "skill brazilcnpj" in msg or "brazilcnpj enricher" in msg

    if mentions_orchestrator:
        return "fleetintel_orchestrator"
    if mentions_brazilcnpj and (mentions_analyst or mentions_generic_fleet):
        return "fleetintel_orchestrator"
    if mentions_analyst and mentions_brazilcnpj:
        return "fleetintel_orchestrator"
    if mentions_generic_fleet and not (mentions_analyst or mentions_brazilcnpj):
        return "fleetintel"
    if mentions_analyst:
        return "fleetintel_analyst"
    if mentions_brazilcnpj:
        return "brazilcnpj"

    has_fleet = any(keyword in msg for keyword in FLEET_KEYWORDS)
    has_cnpj = any(keyword in msg for keyword in CNPJ_KEYWORDS)
    has_cnpj_enrichment = any(keyword in msg for keyword in CNPJ_ENRICHMENT_KEYWORDS)
    wants_orchestration = any(keyword in msg for keyword in ORCHESTRATION_KEYWORDS)

    if has_fleet and (wants_orchestration or has_cnpj_enrichment):
        return "fleetintel_orchestrator"
    if has_cnpj and not has_fleet:
        return "brazilcnpj"
    if has_fleet:
        return "fleetintel_analyst"
    return None


def select_codex_execution_mode(message: str, specialist_name: str) -> CodexExecutionMode:
    msg = _normalize_text(message)
    if wants_raw_specialist_output(msg):
        return "direct_local"

    explicit_specialist_markers = {
        "fleetintel": ("skill fleetintel", "use a skill fleetintel"),
        "fleetintel_analyst": ("skill fleetintel_analyst", "fleetintel analyst"),
        "fleetintel_orchestrator": ("skill fleetintel_orchestrator", "fleetintel orchestrator"),
        "brazilcnpj": ("skill brazilcnpj", "brazilcnpj enricher"),
    }
    explicit_skill = any(
        marker in msg for marker in explicit_specialist_markers.get(specialist_name, ())
    )

    if "codex" in msg:
        return "codex_operator"

    if specialist_name == "fleetintel_orchestrator":
        if explicit_skill and _looks_like_deterministic_profile_request(msg):
            return "direct_local"
        if explicit_skill:
            return "codex_synthesizer"
        return "codex_operator"

    if specialist_name == "fleetintel_analyst":
        if explicit_skill:
            return "codex_synthesizer" if _wants_narrative_synthesis(msg) else "direct_local"
        if _is_implicit_complex_multi_domain(msg):
            return "codex_operator"
        return "direct_local"

    if specialist_name == "brazilcnpj":
        if explicit_skill and _wants_narrative_synthesis(msg) and "cnpj" in msg:
            return "codex_synthesizer"
        return "direct_local"

    return "direct_local"


def should_delegate_specialist_to_codex(message: str, specialist_name: str) -> bool:
    return select_codex_execution_mode(message, specialist_name) in {
        "codex_synthesizer",
        "codex_operator",
    }


def wants_raw_specialist_output(message: str) -> bool:
    return any(
        marker in message
        for marker in (
            " raw",
            "json",
            "payload",
            "bloco tecnico",
            "bloco técnico",
            "output cru",
        )
    )


def _looks_like_deterministic_profile_request(message: str) -> bool:
    has_cnpj = "cnpj" in message or bool(re.search(r"\b\d{14}\b", re.sub(r"\D", "", message)))
    deterministic_markers = (
        "perfil",
        "empresa",
        "validar",
        "cadastro",
        "socio",
        "socios",
        "grupo economico",
        "grupo economico",
    )
    return has_cnpj and any(marker in message for marker in deterministic_markers)


def _wants_narrative_synthesis(message: str) -> bool:
    return any(
        marker in message
        for marker in (
            "insights",
            "o que mudou",
            "resuma",
            "resumir",
            "resumo",
            "analise",
            "analisar",
            "explique",
            "priorizar",
            "prioridade",
            "sinais relevantes",
            "unica resposta",
            "única resposta",
            "me dizer sobre",
            "falar da frota",
        )
    )


def _is_implicit_complex_multi_domain(message: str) -> bool:
    return _wants_narrative_synthesis(message) and (
        ("cnpj" in message and any(keyword in message for keyword in FLEET_KEYWORDS))
        or specialist_name_like_cross_domain(message)
    )


def specialist_name_like_cross_domain(message: str) -> bool:
    return any(keyword in message for keyword in ORCHESTRATION_KEYWORDS)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().strip())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def extract_company_count_query(message: str) -> dict[str, int | str] | None:
    lowered = message.lower()
    year_match = re.search(r"\b(20\d{2})\b", lowered)
    has_company_volume_shape = any(verb in lowered for verb in COMPANY_VOLUME_VERBS) and any(
        noun in lowered for noun in COMPANY_VOLUME_NOUNS
    )
    if not has_company_volume_shape:
        return None

    company_name = _extract_company_name(message)
    if not company_name:
        return None

    result: dict[str, int | str] = {"razao_social": company_name}
    if year_match:
        result["ano"] = int(year_match.group(1))
    return result


def _extract_company_name(message: str) -> str | None:
    patterns = [
        r"\b(?:quantos|quantas|quantidade de|qtd de)\b.*?\b(?:o|a)\s+(?P<company>.+?)\s+\b(?:comprou|compraram|emplacou|emplacaram|registrou|registraram|adquiriu|adquiriram)\b",
        r"\b(?:empresa|grupo|conta)\s+(?P<company>.+?)\s+\b(?:comprou|compraram|emplacou|emplacaram|registrou|registraram|adquiriu|adquiriram)\b",
        r"\b(?:o|a)\s+(?P<company>.+?)\s+\b(?:comprou|compraram|emplacou|emplacaram|registrou|registraram|adquiriu|adquiriram)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if not match:
            continue
        company = match.group("company").strip(" ?.,")
        company = re.sub(
            r"^(?:empresa|conta)\s+",
            "",
            company,
            flags=re.IGNORECASE,
        ).strip(" ?.,")
        if company:
            return company
    return None
