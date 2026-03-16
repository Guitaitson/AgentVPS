"""Short-lived health gate for external FleetIntel/BrazilCNPJ specialists."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from core.config import get_settings
from core.progress import emit_progress

from .consumer_sync import (
    ConsumerSyncError,
    ConsumerSyncUnavailableError,
    build_specialist_mcp_client,
)
from .external_mcp import RemoteMCPError


@dataclass(frozen=True, slots=True)
class ServiceHealthSnapshot:
    service: str
    healthy: bool
    checked_at: float
    error_type: str | None = None
    status_code: int | None = None
    stage: str | None = None
    message: str | None = None
    from_cache: bool = False


@dataclass(frozen=True, slots=True)
class SpecialistHealthAssessment:
    specialist_name: str
    required_services: tuple[str, ...]
    snapshots: tuple[ServiceHealthSnapshot, ...]

    @property
    def healthy(self) -> bool:
        return all(snapshot.healthy for snapshot in self.snapshots)


_HEALTH_CACHE: dict[str, ServiceHealthSnapshot] = {}
_CNPJ_ENRICHMENT_KEYWORDS = (
    "cnpj",
    "grupo economico",
    "socio",
    "socios",
    "cnae",
    "cadastro",
    "cadastral",
    "receita federal",
    "enriquec",
    "empresa completa",
    "qsa",
)


def required_services_for_specialist(message: str, specialist_name: str) -> tuple[str, ...]:
    if specialist_name == "brazilcnpj":
        return ("brazilcnpj",)
    if specialist_name == "fleetintel_orchestrator":
        lowered = message.lower()
        if any(keyword in lowered for keyword in _CNPJ_ENRICHMENT_KEYWORDS):
            return ("fleetintel", "brazilcnpj")
        return ("fleetintel",)
    if specialist_name in {"fleetintel", "fleetintel_analyst"}:
        return ("fleetintel",)
    return ()


async def assess_specialist_health(
    message: str,
    specialist_name: str,
) -> SpecialistHealthAssessment:
    services = required_services_for_specialist(message, specialist_name)
    snapshots = []
    for service in services:
        snapshots.append(await _get_service_health(service))
    return SpecialistHealthAssessment(
        specialist_name=specialist_name,
        required_services=services,
        snapshots=tuple(snapshots),
    )


def format_specialist_health_failure(assessment: SpecialistHealthAssessment) -> str:
    if not assessment.snapshots:
        return "O especialista externo necessario nao esta disponivel no momento."

    unhealthy = [snapshot for snapshot in assessment.snapshots if not snapshot.healthy]
    names = ", ".join(_display_name(snapshot.service) for snapshot in unhealthy)
    lines = [f"Especialista externo indisponivel no momento: {names}.", ""]
    for snapshot in unhealthy:
        reason = snapshot.error_type or "erro"
        if snapshot.status_code is not None:
            reason = f"HTTP {snapshot.status_code}"
        stage = f" na etapa `{snapshot.stage}`" if snapshot.stage else ""
        lines.append(f"- {_display_name(snapshot.service)}: {reason}{stage}.")
    lines.append("O AgentVPS esta saudavel, mas o especialista externo nao respondeu.")
    lines.append("Posso tentar novamente depois ou seguir sem dados externos.")
    return "\n".join(lines)


async def emit_health_failure_progress(assessment: SpecialistHealthAssessment) -> None:
    for snapshot in assessment.snapshots:
        if snapshot.healthy:
            continue
        await emit_progress(
            "external_call",
            server=snapshot.service,
            status="degraded",
            label=f"{_display_name(snapshot.service)} indisponivel no momento. Status: anormal.",
            error=snapshot.error_type or "erro",
        )
    await emit_progress(
        "routing",
        server="codex_operator",
        status="skipped",
        label="Especialista externo indisponivel. Respondendo com diagnostico operacional.",
    )


async def _get_service_health(service: str) -> ServiceHealthSnapshot:
    settings = get_settings().orchestration
    now = time.monotonic()
    cached = _HEALTH_CACHE.get(service)
    if cached and (now - cached.checked_at) <= settings.specialist_preflight_ttl_seconds:
        data = asdict(cached)
        data["from_cache"] = True
        return ServiceHealthSnapshot(**data)

    try:
        client, tool_name = _build_preflight_client(service)
        await client.call_tool(tool_name, {})
        snapshot = ServiceHealthSnapshot(service=service, healthy=True, checked_at=now)
    except RemoteMCPError as exc:
        snapshot = ServiceHealthSnapshot(
            service=service,
            healthy=False,
            checked_at=now,
            error_type=exc.error_type,
            status_code=exc.status_code,
            stage=exc.stage,
            message=str(exc),
        )
    except (ConsumerSyncUnavailableError, ConsumerSyncError) as exc:
        snapshot = ServiceHealthSnapshot(
            service=service,
            healthy=False,
            checked_at=now,
            error_type="consumer_sync",
            message=str(exc),
        )
    except Exception as exc:  # pragma: no cover
        snapshot = ServiceHealthSnapshot(
            service=service,
            healthy=False,
            checked_at=now,
            error_type="network",
            message=str(exc),
        )

    _HEALTH_CACHE[service] = snapshot
    return snapshot


def _build_preflight_client(service: str):
    orch = get_settings().orchestration
    return (
        build_specialist_mcp_client(
            service,
            client_name=f"agentvps-specialist-preflight-{service}",
            timeout_seconds=float(orch.specialist_preflight_timeout_seconds),
            max_attempts=orch.specialist_preflight_max_attempts,
            retry_backoff_seconds=0.3,
        ),
        "get_operations_status" if service == "fleetintel" else "health_check",
    )


def _display_name(service: str) -> str:
    if service == "fleetintel":
        return "FleetIntel"
    if service == "brazilcnpj":
        return "BrazilCNPJ"
    return service
