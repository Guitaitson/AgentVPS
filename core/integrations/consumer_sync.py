"""Consumer sync machine-pull for FleetIntel/BrazilCNPJ external credentials."""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import structlog

from core.__version__ import __version__ as core_version
from core.config import get_settings

from .external_mcp import RemoteMCPClient, RemoteMCPConnection

logger = structlog.get_logger()

_STALE_RELEASE_ID = "stale-release"
_STALE_BUNDLE_HASH = "stale-hash"
_REQUIRED_BUNDLE_KEYS = {
    "FLEETINTEL_MCP_URL",
    "FLEETINTEL_CF_ACCESS_CLIENT_ID",
    "FLEETINTEL_CF_ACCESS_CLIENT_SECRET",
    "BRAZILCNPJ_MCP_URL",
    "BRAZILCNPJ_CF_ACCESS_CLIENT_ID",
    "BRAZILCNPJ_CF_ACCESS_CLIENT_SECRET",
}
_SERVICE_KEY_MAP = {
    "fleetintel": (
        "FLEETINTEL_MCP_URL",
        "FLEETINTEL_CF_ACCESS_CLIENT_ID",
        "FLEETINTEL_CF_ACCESS_CLIENT_SECRET",
    ),
    "brazilcnpj": (
        "BRAZILCNPJ_MCP_URL",
        "BRAZILCNPJ_CF_ACCESS_CLIENT_ID",
        "BRAZILCNPJ_CF_ACCESS_CLIENT_SECRET",
    ),
}
_SUPPORTED_CONTRACT_VERSIONS = ["v1"]
_SUPPORTED_RESPONSE_CONTRACT_VERSIONS = ["client_brief_v1"]
_SUPPORTED_TOOL_FAMILIES = ["client_brief_v1", "raw_tools"]
_CLIENT_BEHAVIOR_VERSION = "contract_driven_v1"


class ConsumerSyncError(RuntimeError):
    """Base error for consumer sync failures."""


class ConsumerSyncUnavailableError(ConsumerSyncError):
    """Raised when FleetIntel disables or revokes the external consumer."""


@dataclass(frozen=True, slots=True)
class ServerReleaseInfo:
    version: str | None = None
    git_sha: str | None = None
    build_timestamp: str | None = None
    supported_contract_versions: list[str] = field(default_factory=list)
    source: str | None = None


@dataclass(frozen=True, slots=True)
class ClientCapabilities:
    supported_contract_versions: list[str] = field(default_factory=list)
    supported_response_contract_versions: list[str] = field(default_factory=list)
    supported_tool_families: list[str] = field(default_factory=list)
    client_behavior_version: str | None = None


@dataclass(frozen=True, slots=True)
class ConsumerSyncContract:
    contract_version: str | None = None
    response_contract_version: str | None = None
    preferred_client_tools: dict[str, list[str]] = field(default_factory=dict)
    legacy_tool_policy: dict[str, Any] = field(default_factory=dict)
    release_change_summary: list[str] = field(default_factory=list)
    client_impact_summary: list[str] = field(default_factory=list)
    behavioral_change_flags: dict[str, Any] = field(default_factory=dict)
    refresh_policy: dict[str, Any] = field(default_factory=dict)
    error_semantics: dict[str, Any] = field(default_factory=dict)
    responsibility_boundary: dict[str, Any] = field(default_factory=dict)
    server_release: ServerReleaseInfo | None = None


@dataclass(frozen=True, slots=True)
class ClientAdaptation:
    compatibility_status: str | None = None
    compatibility_reason_codes: list[str] = field(default_factory=list)
    criteria: dict[str, Any] = field(default_factory=dict)
    criteria_results: dict[str, Any] = field(default_factory=dict)
    response_contract_version_to_use: str | None = None
    recognized_client_behavior_version: str | None = None
    recognized_response_contract_version: str | None = None
    recognized_preferred_client_tools: dict[str, list[str]] = field(default_factory=dict)
    preferred_client_tools: dict[str, list[str]] = field(default_factory=dict)
    fallback_tools: dict[str, list[str]] = field(default_factory=dict)
    tool_surface: str | None = None
    client_capabilities_seen: ClientCapabilities | None = None
    required_actions: list[str] = field(default_factory=list)
    deprecation_notices: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RolloutStatus:
    status: str | None = None
    reason: str | None = None
    validation_requirements: list[str] = field(default_factory=list)
    latest_validation_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConsumerSyncState:
    current_release_id: str | None = None
    current_bundle_hash: str | None = None
    current_bundle: dict[str, Any] | None = None
    last_sync_status: str | None = None
    last_sync_at: str | None = None
    contract: ConsumerSyncContract | None = None
    client_adaptation: ClientAdaptation | None = None
    rollout_status: RolloutStatus | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_state_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return _repo_root() / path


def _run_git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    value = (result.stdout or "").strip()
    return value or None


def _agent_version() -> str:
    exact_tag = _run_git("describe", "--tags", "--exact-match")
    if exact_tag:
        return exact_tag[1:] if exact_tag.startswith("v") else exact_tag
    latest_tag = _run_git("describe", "--tags", "--abbrev=0")
    if latest_tag:
        return latest_tag[1:] if latest_tag.startswith("v") else latest_tag
    return core_version


def _agent_commit() -> str:
    return _run_git("rev-parse", "--short", "HEAD") or ""


def get_agent_version() -> str:
    return _agent_version()


def get_agent_commit() -> str:
    return _agent_commit()


def _normalize_tool_mapping(payload: Any) -> dict[str, list[str]]:
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for service, tools in payload.items():
        if isinstance(tools, list):
            normalized[str(service)] = [str(item).strip() for item in tools if str(item).strip()]
    return normalized


def _normalize_string_list(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def _parse_client_capabilities(payload: Any) -> ClientCapabilities | None:
    if not isinstance(payload, dict):
        return None
    return ClientCapabilities(
        supported_contract_versions=_normalize_string_list(
            payload.get("supported_contract_versions")
        ),
        supported_response_contract_versions=_normalize_string_list(
            payload.get("supported_response_contract_versions")
        ),
        supported_tool_families=_normalize_string_list(payload.get("supported_tool_families")),
        client_behavior_version=str(payload.get("client_behavior_version") or "").strip() or None,
    )


def _parse_server_release(payload: Any) -> ServerReleaseInfo | None:
    if not isinstance(payload, dict):
        return None
    return ServerReleaseInfo(
        version=str(payload.get("version") or "").strip() or None,
        git_sha=str(payload.get("git_sha") or "").strip() or None,
        build_timestamp=str(payload.get("build_timestamp") or "").strip() or None,
        supported_contract_versions=_normalize_string_list(
            payload.get("supported_contract_versions")
        ),
        source=str(payload.get("source") or "").strip() or None,
    )


def _parse_contract(payload: Any) -> ConsumerSyncContract | None:
    if not isinstance(payload, dict):
        return None
    return ConsumerSyncContract(
        contract_version=str(payload.get("contract_version") or "").strip() or None,
        response_contract_version=str(payload.get("response_contract_version") or "").strip()
        or None,
        preferred_client_tools=_normalize_tool_mapping(payload.get("preferred_client_tools")),
        legacy_tool_policy=payload.get("legacy_tool_policy")
        if isinstance(payload.get("legacy_tool_policy"), dict)
        else {},
        release_change_summary=_normalize_string_list(payload.get("release_change_summary")),
        client_impact_summary=_normalize_string_list(payload.get("client_impact_summary")),
        behavioral_change_flags=payload.get("behavioral_change_flags")
        if isinstance(payload.get("behavioral_change_flags"), dict)
        else {},
        refresh_policy=payload.get("refresh_policy")
        if isinstance(payload.get("refresh_policy"), dict)
        else {},
        error_semantics=payload.get("error_semantics")
        if isinstance(payload.get("error_semantics"), dict)
        else {},
        responsibility_boundary=payload.get("responsibility_boundary")
        if isinstance(payload.get("responsibility_boundary"), dict)
        else {},
        server_release=_parse_server_release(payload.get("server_release")),
    )


def _parse_client_adaptation(payload: Any) -> ClientAdaptation | None:
    if not isinstance(payload, dict):
        return None
    return ClientAdaptation(
        compatibility_status=str(payload.get("compatibility_status") or "").strip() or None,
        compatibility_reason_codes=_normalize_string_list(
            payload.get("compatibility_reason_codes")
        ),
        criteria=payload.get("criteria") if isinstance(payload.get("criteria"), dict) else {},
        criteria_results=payload.get("criteria_results")
        if isinstance(payload.get("criteria_results"), dict)
        else {},
        response_contract_version_to_use=str(
            payload.get("response_contract_version_to_use") or ""
        ).strip()
        or None,
        recognized_client_behavior_version=str(
            payload.get("recognized_client_behavior_version") or ""
        ).strip()
        or None,
        recognized_response_contract_version=str(
            payload.get("recognized_response_contract_version") or ""
        ).strip()
        or None,
        recognized_preferred_client_tools=_normalize_tool_mapping(
            payload.get("recognized_preferred_client_tools")
        ),
        preferred_client_tools=_normalize_tool_mapping(payload.get("preferred_client_tools")),
        fallback_tools=_normalize_tool_mapping(payload.get("fallback_tools")),
        tool_surface=str(payload.get("tool_surface") or "").strip() or None,
        client_capabilities_seen=_parse_client_capabilities(
            payload.get("client_capabilities_seen")
        ),
        required_actions=_normalize_string_list(payload.get("required_actions")),
        deprecation_notices=_normalize_string_list(payload.get("deprecation_notices")),
    )


def _parse_rollout_status(payload: Any) -> RolloutStatus | None:
    if not isinstance(payload, dict):
        return None
    return RolloutStatus(
        status=str(payload.get("status") or "").strip() or None,
        reason=str(payload.get("reason") or "").strip() or None,
        validation_requirements=_normalize_string_list(payload.get("validation_requirements")),
        latest_validation_summary=payload.get("latest_validation_summary")
        if isinstance(payload.get("latest_validation_summary"), dict)
        else {},
    )


class ConsumerSyncManager:
    """Fetches and persists the current external credential bundle."""

    def __init__(
        self,
        *,
        sync_url: str,
        consumer_slug: str,
        bootstrap_secret: str | None,
        state_file: str,
        timeout_seconds: float,
    ) -> None:
        self.sync_url = sync_url.strip()
        self.consumer_slug = consumer_slug.strip()
        self.bootstrap_secret = (bootstrap_secret or "").strip()
        self.state_path = _resolve_state_path(state_file)
        self.timeout_seconds = timeout_seconds
        self._sync_lock = asyncio.Lock()

    @property
    def is_configured(self) -> bool:
        return bool(self.sync_url and self.consumer_slug and self.bootstrap_secret)

    def load_state(self) -> ConsumerSyncState:
        if not self.state_path.is_file():
            return ConsumerSyncState()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("consumer_sync_state_invalid", path=str(self.state_path))
            return ConsumerSyncState()
        return ConsumerSyncState(
            current_release_id=payload.get("current_release_id"),
            current_bundle_hash=payload.get("current_bundle_hash"),
            current_bundle=payload.get("current_bundle"),
            last_sync_status=payload.get("last_sync_status"),
            last_sync_at=payload.get("last_sync_at"),
            contract=_parse_contract(payload.get("contract")),
            client_adaptation=_parse_client_adaptation(payload.get("client_adaptation")),
            rollout_status=_parse_rollout_status(payload.get("rollout_status")),
        )

    def save_state(self, state: ConsumerSyncState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(asdict(state), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _validate_bundle(self, bundle: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(bundle, dict):
            raise ConsumerSyncError("Consumer sync nao retornou credential_bundle valido.")
        values = bundle.get("values")
        if not isinstance(values, dict):
            raise ConsumerSyncError("Consumer sync nao retornou credential_bundle.values valido.")
        missing = sorted(
            key for key in _REQUIRED_BUNDLE_KEYS if not str(values.get(key) or "").strip()
        )
        if missing:
            raise ConsumerSyncError(
                "Credential bundle incompleto. Chaves ausentes: " + ", ".join(missing)
            )
        return values

    def _sync_payload(self, state: ConsumerSyncState) -> dict[str, Any]:
        return {
            "consumer_slug": self.consumer_slug,
            "agent_name": "AgentVPS",
            "agent_version": _agent_version(),
            "agent_commit": _agent_commit(),
            "current_release_id": state.current_release_id or _STALE_RELEASE_ID,
            "current_bundle_hash": state.current_bundle_hash or _STALE_BUNDLE_HASH,
            "client_capabilities": {
                "supported_contract_versions": list(_SUPPORTED_CONTRACT_VERSIONS),
                "supported_response_contract_versions": list(_SUPPORTED_RESPONSE_CONTRACT_VERSIONS),
                "supported_tool_families": list(_SUPPORTED_TOOL_FAMILIES),
                "client_behavior_version": _CLIENT_BEHAVIOR_VERSION,
            },
        }

    async def sync(self, *, force_refresh: bool = False) -> ConsumerSyncState:
        if not self.is_configured:
            raise ConsumerSyncError(
                "Consumer sync nao configurado. Ajuste CONSUMER_SYNC_URL, "
                "CONSUMER_SLUG e CONSUMER_BOOTSTRAP_SECRET."
            )

        async with self._sync_lock:
            state = self.load_state()
            payload = self._sync_payload(state)
            headers = {
                "Authorization": f"Bearer {self.bootstrap_secret}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            logger.info(
                "consumer_sync_request",
                sync_url=self.sync_url,
                consumer_slug=self.consumer_slug,
                force_refresh=force_refresh,
                current_release_id=payload["current_release_id"],
                current_bundle_hash=payload["current_bundle_hash"],
            )
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(self.sync_url, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise ConsumerSyncError("Consumer sync expirou antes de responder.") from exc
            except httpx.HTTPError as exc:
                raise ConsumerSyncError("Falha de rede ao executar consumer sync.") from exc

            if response.status_code >= 400:
                excerpt = (response.text or "").strip().replace("\n", " ")[:240]
                raise ConsumerSyncError(
                    f"Consumer sync retornou HTTP {response.status_code}."
                    + (f" Excerpt: {excerpt}" if excerpt else "")
                )

            try:
                result = response.json()
            except ValueError as exc:
                raise ConsumerSyncError("Consumer sync retornou JSON invalido.") from exc

            sync_status = str(result.get("sync_status") or "").strip()
            now = datetime.now(timezone.utc).isoformat()
            if sync_status == "bundle_update_required":
                bundle = result.get("credential_bundle")
                self._validate_bundle(bundle)
                new_state = ConsumerSyncState(
                    current_release_id=str(
                        result.get("release_id") or state.current_release_id or ""
                    ).strip()
                    or None,
                    current_bundle_hash=str(
                        result.get("bundle_hash") or (bundle or {}).get("hash") or ""
                    ).strip()
                    or None,
                    current_bundle=bundle,
                    last_sync_status=sync_status,
                    last_sync_at=now,
                    contract=_parse_contract(result.get("contract")),
                    client_adaptation=_parse_client_adaptation(result.get("client_adaptation")),
                    rollout_status=_parse_rollout_status(result.get("rollout_status")),
                )
            elif sync_status == "up_to_date":
                if state.current_bundle is None:
                    raise ConsumerSyncError(
                        "Consumer sync retornou up_to_date mas nao existe credential bundle local."
                    )
                new_state = ConsumerSyncState(
                    current_release_id=str(
                        result.get("release_id") or state.current_release_id or ""
                    ).strip()
                    or None,
                    current_bundle_hash=str(
                        result.get("bundle_hash") or state.current_bundle_hash or ""
                    ).strip()
                    or None,
                    current_bundle=state.current_bundle,
                    last_sync_status=sync_status,
                    last_sync_at=now,
                    contract=_parse_contract(result.get("contract")) or state.contract,
                    client_adaptation=_parse_client_adaptation(result.get("client_adaptation"))
                    or state.client_adaptation,
                    rollout_status=_parse_rollout_status(result.get("rollout_status"))
                    or state.rollout_status,
                )
            elif sync_status in {"revoked", "disabled"}:
                new_state = ConsumerSyncState(
                    current_release_id=str(
                        result.get("release_id") or state.current_release_id or ""
                    ).strip()
                    or None,
                    current_bundle_hash=str(
                        result.get("bundle_hash") or state.current_bundle_hash or ""
                    ).strip()
                    or None,
                    current_bundle=state.current_bundle,
                    last_sync_status=sync_status,
                    last_sync_at=now,
                    contract=_parse_contract(result.get("contract")) or state.contract,
                    client_adaptation=_parse_client_adaptation(result.get("client_adaptation"))
                    or state.client_adaptation,
                    rollout_status=_parse_rollout_status(result.get("rollout_status"))
                    or state.rollout_status,
                )
            else:
                raise ConsumerSyncError(
                    f"Consumer sync retornou sync_status invalido: {sync_status or '-'}"
                )

            self.save_state(new_state)
            logger.info(
                "consumer_sync_result",
                sync_status=new_state.last_sync_status,
                release_id=new_state.current_release_id,
                bundle_hash=new_state.current_bundle_hash,
            )
            return new_state

    async def ensure_bundle(self) -> ConsumerSyncState:
        state = self.load_state()
        if state.last_sync_status in {"revoked", "disabled"}:
            raise ConsumerSyncUnavailableError(
                "Especialista externo desabilitado pelo provider FleetIntel."
            )
        if state.current_bundle is None:
            state = await self.sync()
        if state.last_sync_status in {"revoked", "disabled"}:
            raise ConsumerSyncUnavailableError(
                "Especialista externo desabilitado pelo provider FleetIntel."
            )
        return state

    def _connection_from_state(self, service: str, state: ConsumerSyncState) -> RemoteMCPConnection:
        keys = _SERVICE_KEY_MAP.get(service)
        if keys is None:
            raise ConsumerSyncError(f"Servico externo desconhecido: {service}")
        values = (state.current_bundle or {}).get("values") or {}
        url_key, client_id_key, client_secret_key = keys
        base_url = str(values.get(url_key) or "").strip()
        access_client_id = str(values.get(client_id_key) or "").strip()
        access_client_secret = str(values.get(client_secret_key) or "").strip()
        if not (base_url and access_client_id and access_client_secret):
            raise ConsumerSyncError(
                f"Credential bundle local nao possui credenciais completas para {service}."
            )
        return RemoteMCPConnection(
            base_url=base_url,
            access_client_id=access_client_id,
            access_client_secret=access_client_secret,
        )

    async def resolve_service_connection(self, service: str) -> RemoteMCPConnection:
        state = await self.ensure_bundle()
        return self._connection_from_state(service, state)

    async def refresh_bundle_once(self, service: str) -> bool:
        refreshed = await self.sync(force_refresh=True)
        if refreshed.last_sync_status in {"revoked", "disabled"}:
            raise ConsumerSyncUnavailableError(
                f"Especialista externo {service} desabilitado pelo provider FleetIntel."
            )
        return True

    def preferred_tools_for(
        self, service: str, state: ConsumerSyncState | None = None
    ) -> list[str]:
        current_state = state or self.load_state()
        if current_state.client_adaptation:
            tools = current_state.client_adaptation.preferred_client_tools.get(service)
            if tools:
                return tools
        if current_state.contract:
            return current_state.contract.preferred_client_tools.get(service, [])
        return []

    def fallback_tools_for(self, service: str, state: ConsumerSyncState | None = None) -> list[str]:
        current_state = state or self.load_state()
        if current_state.client_adaptation:
            return current_state.client_adaptation.fallback_tools.get(service, [])
        return []

    def compatibility_status(self, state: ConsumerSyncState | None = None) -> str | None:
        current_state = state or self.load_state()
        if current_state.client_adaptation:
            return current_state.client_adaptation.compatibility_status
        return None

    def should_use_preferred_tools(
        self,
        service: str,
        state: ConsumerSyncState | None = None,
    ) -> bool:
        current_state = state or self.load_state()
        return self.compatibility_status(current_state) == "compatible" and bool(
            self.preferred_tools_for(service, current_state)
        )

    def client_behavior_version(self) -> str:
        return _CLIENT_BEHAVIOR_VERSION

    def client_capabilities(self) -> ClientCapabilities:
        return ClientCapabilities(
            supported_contract_versions=list(_SUPPORTED_CONTRACT_VERSIONS),
            supported_response_contract_versions=list(_SUPPORTED_RESPONSE_CONTRACT_VERSIONS),
            supported_tool_families=list(_SUPPORTED_TOOL_FAMILIES),
            client_behavior_version=_CLIENT_BEHAVIOR_VERSION,
        )


@lru_cache(maxsize=1)
def get_consumer_sync_manager() -> ConsumerSyncManager:
    settings = get_settings().consumer_sync
    return ConsumerSyncManager(
        sync_url=settings.sync_url,
        consumer_slug=settings.slug,
        bootstrap_secret=settings.bootstrap_secret,
        state_file=settings.state_file,
        timeout_seconds=float(settings.timeout_seconds),
    )


def reset_consumer_sync_manager_for_tests() -> None:
    get_consumer_sync_manager.cache_clear()


def build_specialist_mcp_client(
    service: str,
    *,
    client_name: str,
    timeout_seconds: float = 25.0,
    max_attempts: int = 2,
    retry_backoff_seconds: float = 0.6,
) -> RemoteMCPClient:
    manager = get_consumer_sync_manager()
    if not manager.is_configured:
        raise ConsumerSyncError(
            "Consumer sync nao configurado. Ajuste CONSUMER_SYNC_URL, "
            "CONSUMER_SLUG e CONSUMER_BOOTSTRAP_SECRET."
        )
    return RemoteMCPClient(
        client_name=client_name,
        server_name=service,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
        connection_provider=lambda: manager.resolve_service_connection(service),
        auth_refresh_callback=lambda: manager.refresh_bundle_once(service),
    )


async def warmup_consumer_sync() -> None:
    manager = get_consumer_sync_manager()
    if not manager.is_configured:
        return
    try:
        await manager.sync()
    except Exception as exc:
        logger.warning("consumer_sync_warmup_failed", error=str(exc))
