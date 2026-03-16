import json

import pytest

from core.config import get_settings
from core.integrations.consumer_sync import (
    ConsumerSyncError,
    ConsumerSyncUnavailableError,
    get_consumer_sync_manager,
    reset_consumer_sync_manager_for_tests,
)


class _MockResponse:
    def __init__(self, *, json_data=None, status_code=200, text=""):
        self._json_data = json_data
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._json_data


@pytest.fixture(autouse=True)
def _reset_settings_and_manager(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "CONSUMER_SYNC_URL",
        "https://request-access.gtaitson.space/api/consumer-sync/v1/sync",
    )
    monkeypatch.setenv("CONSUMER_SLUG", "agentvps")
    monkeypatch.setenv("CONSUMER_BOOTSTRAP_SECRET", "bootstrap-secret")
    monkeypatch.setenv("CONSUMER_SYNC_STATE_FILE", str(tmp_path / "agentvps.json"))
    get_settings.cache_clear()
    reset_consumer_sync_manager_for_tests()
    yield
    get_settings.cache_clear()
    reset_consumer_sync_manager_for_tests()


@pytest.mark.asyncio
async def test_consumer_sync_persists_bundle_update_then_up_to_date(monkeypatch, tmp_path):
    responses = [
        _MockResponse(
            json_data={
                "sync_status": "bundle_update_required",
                "release_id": "rel-2",
                "bundle_hash": "hash-2",
                "credential_bundle": {
                    "values": {
                        "FLEETINTEL_MCP_URL": "https://agent-fleet.gtaitson.space/mcp",
                        "FLEETINTEL_CF_ACCESS_CLIENT_ID": "fleet-id",
                        "FLEETINTEL_CF_ACCESS_CLIENT_SECRET": "fleet-secret",
                        "BRAZILCNPJ_MCP_URL": "https://agent-cnpj.gtaitson.space/mcp",
                        "BRAZILCNPJ_CF_ACCESS_CLIENT_ID": "cnpj-id",
                        "BRAZILCNPJ_CF_ACCESS_CLIENT_SECRET": "cnpj-secret",
                    },
                    "text": "bundle text",
                    "hash": "hash-2",
                },
                "contract": {
                    "contract_version": "v1",
                    "response_contract_version": "client_brief_v1",
                    "preferred_client_tools": {
                        "fleetintel": ["get_client_readiness_status", "get_market_changes_brief"],
                        "brazilcnpj": ["health_check", "get_company_registry_brief"],
                    },
                    "legacy_tool_policy": {"raw_tools_default_for_clients": False},
                    "release_change_summary": ["troca para surfaces brief"],
                    "client_impact_summary": ["cliente deve usar preferred_client_tools"],
                    "behavioral_change_flags": {"brief_surfaces_enabled": True},
                    "refresh_policy": {"on_403": "sync_once_retry_once"},
                    "error_semantics": {"http_403": "access"},
                    "responsibility_boundary": {"specialist_output": "fleetintel"},
                    "server_release": {
                        "version": "0.1.0",
                        "git_sha": "abc1234",
                        "build_timestamp": "2026-03-16T15:42:44Z",
                        "supported_contract_versions": ["v1"],
                    },
                },
                "client_adaptation": {
                    "compatibility_status": "compatible",
                    "response_contract_version_to_use": "client_brief_v1",
                    "preferred_client_tools": {
                        "fleetintel": ["get_client_readiness_status", "get_market_changes_brief"],
                        "brazilcnpj": ["health_check", "get_company_registry_brief"],
                    },
                    "fallback_tools": {
                        "fleetintel": ["get_operations_status"],
                        "brazilcnpj": ["health_check"],
                    },
                    "required_actions": ["nenhuma"],
                    "deprecation_notices": ["raw tools deprecated"],
                },
            }
        ),
        _MockResponse(
            json_data={
                "sync_status": "up_to_date",
                "release_id": "rel-2",
                "bundle_hash": "hash-2",
            }
        ),
    ]
    seen_payloads = []

    async def fake_post(self, url, json=None, headers=None):
        seen_payloads.append(json)
        return responses.pop(0)

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    manager = get_consumer_sync_manager()
    first = await manager.sync()
    second = await manager.sync()

    assert first.current_release_id == "rel-2"
    assert first.current_bundle_hash == "hash-2"
    assert second.last_sync_status == "up_to_date"
    assert seen_payloads[0]["current_release_id"] == "stale-release"
    assert seen_payloads[0]["current_bundle_hash"] == "stale-hash"
    assert seen_payloads[1]["current_release_id"] == "rel-2"
    assert seen_payloads[1]["current_bundle_hash"] == "hash-2"

    state_path = tmp_path / "agentvps.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["current_release_id"] == "rel-2"
    assert payload["current_bundle_hash"] == "hash-2"
    assert payload["current_bundle"]["values"]["FLEETINTEL_CF_ACCESS_CLIENT_ID"] == "fleet-id"
    assert payload["contract"]["contract_version"] == "v1"
    assert payload["client_adaptation"]["compatibility_status"] == "compatible"

    fleet_connection = await manager.resolve_service_connection("fleetintel")
    assert fleet_connection.base_url == "https://agent-fleet.gtaitson.space/mcp"
    assert fleet_connection.access_client_id == "fleet-id"
    assert second.contract.contract_version == "v1"
    assert second.contract.server_release.version == "0.1.0"
    assert second.client_adaptation.response_contract_version_to_use == "client_brief_v1"
    assert manager.preferred_tools_for("fleetintel", second) == [
        "get_client_readiness_status",
        "get_market_changes_brief",
    ]
    assert manager.fallback_tools_for("fleetintel", second) == ["get_operations_status"]
    assert manager.should_use_preferred_tools("fleetintel", second) is True


@pytest.mark.asyncio
async def test_consumer_sync_rejects_up_to_date_without_local_bundle(monkeypatch):
    async def fake_post(self, url, json=None, headers=None):
        return _MockResponse(
            json_data={
                "sync_status": "up_to_date",
                "release_id": "rel-2",
                "bundle_hash": "hash-2",
            }
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    manager = get_consumer_sync_manager()
    with pytest.raises(ConsumerSyncError):
        await manager.sync()


@pytest.mark.asyncio
async def test_consumer_sync_marks_revoked_consumer_unavailable(monkeypatch):
    async def fake_post(self, url, json=None, headers=None):
        return _MockResponse(
            json_data={
                "sync_status": "revoked",
                "release_id": "rel-3",
                "bundle_hash": "hash-3",
            }
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    manager = get_consumer_sync_manager()
    state = await manager.sync(force_refresh=True)

    assert state.last_sync_status == "revoked"
    with pytest.raises(ConsumerSyncUnavailableError):
        await manager.ensure_bundle()


@pytest.mark.asyncio
async def test_consumer_sync_disables_preferred_tools_when_not_compatible(monkeypatch):
    async def fake_post(self, url, json=None, headers=None):
        return _MockResponse(
            json_data={
                "sync_status": "bundle_update_required",
                "release_id": "rel-4",
                "bundle_hash": "hash-4",
                "credential_bundle": {
                    "values": {
                        "FLEETINTEL_MCP_URL": "https://agent-fleet.gtaitson.space/mcp",
                        "FLEETINTEL_CF_ACCESS_CLIENT_ID": "fleet-id",
                        "FLEETINTEL_CF_ACCESS_CLIENT_SECRET": "fleet-secret",
                        "BRAZILCNPJ_MCP_URL": "https://agent-cnpj.gtaitson.space/mcp",
                        "BRAZILCNPJ_CF_ACCESS_CLIENT_ID": "cnpj-id",
                        "BRAZILCNPJ_CF_ACCESS_CLIENT_SECRET": "cnpj-secret",
                    }
                },
                "contract": {
                    "contract_version": "v1",
                    "response_contract_version": "client_brief_v1",
                    "preferred_client_tools": {
                        "fleetintel": ["get_client_readiness_status"],
                    },
                },
                "client_adaptation": {
                    "compatibility_status": "upgrade_recommended",
                    "preferred_client_tools": {
                        "fleetintel": ["get_client_readiness_status"],
                    },
                    "fallback_tools": {
                        "fleetintel": ["get_operations_status"],
                    },
                    "required_actions": ["Use preferred_client_tools before promotion."],
                },
            }
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    manager = get_consumer_sync_manager()
    state = await manager.sync()

    assert manager.preferred_tools_for("fleetintel", state) == ["get_client_readiness_status"]
    assert manager.should_use_preferred_tools("fleetintel", state) is False
    assert manager.fallback_tools_for("fleetintel", state) == ["get_operations_status"]
