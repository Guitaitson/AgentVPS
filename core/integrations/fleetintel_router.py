"""Shared routing rules for FleetIntel/BrazilCNPJ specialist skills."""

from __future__ import annotations

FLEET_KEYWORDS = [
    "caminhao",
    "caminhoes",
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
    "socio",
    "socios",
    "grupo economico",
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


def detect_external_skill(message: str) -> str | None:
    msg = message.lower().strip()
    has_fleet = any(keyword in msg for keyword in FLEET_KEYWORDS)
    has_cnpj = any(keyword in msg for keyword in CNPJ_KEYWORDS)
    wants_orchestration = any(keyword in msg for keyword in ORCHESTRATION_KEYWORDS)

    if has_fleet and (has_cnpj or wants_orchestration):
        return "fleetintel_orchestrator"
    if has_cnpj and not has_fleet:
        return "brazilcnpj"
    if has_fleet:
        return "fleetintel_analyst"
    return None
