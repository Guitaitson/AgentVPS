"""Shared routing rules for FleetIntel/BrazilCNPJ specialist skills."""

from __future__ import annotations

import re
import unicodedata

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


def should_delegate_specialist_to_codex(message: str, specialist_name: str) -> bool:
    msg = _normalize_text(message)
    if "skill fleetintel" in msg:
        return False
    if "codex" in msg:
        return True
    if specialist_name == "fleetintel_orchestrator":
        return True
    if specialist_name not in {"fleetintel_analyst", "brazilcnpj"}:
        return False

    complexity_markers = (
        "resumir",
        "resuma",
        "analisar",
        "analise",
        "investigar",
        "explique",
        "por que",
        "porque",
        "o que mudou",
        "sinais relevantes",
    )
    has_complexity = any(marker in msg for marker in complexity_markers)
    has_multi_domain_hint = "cnpj" in msg and any(keyword in msg for keyword in FLEET_KEYWORDS)
    return has_complexity and has_multi_domain_hint


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
