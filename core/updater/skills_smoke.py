"""
Smoke validation for externally tracked FleetIntel/BrazilCNPJ skills.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.skills._builtin.brazilcnpj.handler import BrazilCNPJSkill
from core.skills._builtin.fleetintel_analyst.handler import FleetIntelAnalystSkill
from core.skills._builtin.fleetintel_orchestrator.handler import FleetIntelOrchestratorSkill
from core.skills.base import SecurityLevel, SkillConfig


@dataclass(frozen=True, slots=True)
class SmokeSpec:
    external_name: str
    local_name: str
    query: str
    expected_markers: tuple[str, ...]
    reject_markers: tuple[str, ...]


SMOKE_SPECS: dict[str, SmokeSpec] = {
    "fleetintel-analyst": SmokeSpec(
        external_name="fleetintel-analyst",
        local_name="fleetintel_analyst",
        query="Use o FleetIntel para analisar o CNPJ 48.430.290/0001-30.",
        expected_markers=("ADDIANTE", "emplacamentos"),
        reject_markers=("HTTP 502", "ERROR:", "❌"),
    ),
    "fleetintel-orchestrator": SmokeSpec(
        external_name="fleetintel-orchestrator",
        local_name="fleetintel_orchestrator",
        query=(
            "Cruze FleetIntel e BrazilCNPJ para o CNPJ 48.430.290/0001-30 "
            "e resuma empresa, grupo economico e frota."
        ),
        expected_markers=("Operacao FleetIntel: status=", "BrazilCNPJ health: status="),
        reject_markers=("Falha FleetIntel:", "HTTP 502", "ERROR:", "indisponivel"),
    ),
    "brazilcnpj-enricher": SmokeSpec(
        external_name="brazilcnpj-enricher",
        local_name="brazilcnpj",
        query="Valide o CNPJ 48.430.290/0001-30 e me diga grupo economico e resumo da empresa.",
        expected_markers=("BrazilCNPJ", "ADDIANTE"),
        reject_markers=("HTTP 502", "ERROR:", "indisponivel"),
    ),
}


def _config(name: str) -> SkillConfig:
    return SkillConfig(name=name, description=f"smoke:{name}", security_level=SecurityLevel.SAFE)


class ExternalSkillsSmokeRunner:
    """Runs smoke tests against the real built-in integration handlers."""

    def __init__(self) -> None:
        self._handlers = {
            "fleetintel_analyst": FleetIntelAnalystSkill(_config("fleetintel_analyst")),
            "fleetintel_orchestrator": FleetIntelOrchestratorSkill(
                _config("fleetintel_orchestrator")
            ),
            "brazilcnpj": BrazilCNPJSkill(_config("brazilcnpj")),
        }

    async def run(self, external_skill_names: list[str]) -> dict[str, Any]:
        selected_specs = [
            SMOKE_SPECS[name] for name in sorted(set(external_skill_names)) if name in SMOKE_SPECS
        ]
        if not selected_specs:
            return {
                "success": True,
                "skipped": True,
                "results": [],
                "message": "No mapped smoke targets for changed skills",
            }

        results: list[dict[str, Any]] = []
        overall_success = True
        for spec in selected_specs:
            handler = self._handlers[spec.local_name]
            output = await handler.execute({"query": spec.query, "raw_input": spec.query})
            passed, failure_reason = self._evaluate_output(spec, output)
            overall_success = overall_success and passed
            results.append(
                {
                    "external_skill": spec.external_name,
                    "local_skill": spec.local_name,
                    "success": passed,
                    "failure_reason": failure_reason,
                    "output_preview": output[:400],
                }
            )

        return {
            "success": overall_success,
            "skipped": False,
            "results": results,
        }

    @staticmethod
    def _evaluate_output(spec: SmokeSpec, output: str) -> tuple[bool, str | None]:
        text = (output or "").strip()
        if not text:
            return False, "empty_output"
        for marker in spec.reject_markers:
            if marker in text:
                return False, f"reject_marker:{marker}"
        for marker in spec.expected_markers:
            if marker not in text:
                return False, f"missing_marker:{marker}"
        return True, None
