from datetime import timedelta

import pytest

from core.config import get_settings
from core.integrations.consumer_contract_validation import run_release_validation
from core.integrations.consumer_sync import reset_consumer_sync_manager_for_tests


class _MockResponse:
    def __init__(
        self,
        *,
        json_data=None,
        status_code=200,
        text="",
        headers=None,
        elapsed_seconds=0.25,
    ):
        self._json_data = json_data
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.elapsed = timedelta(seconds=elapsed_seconds)

    def json(self):
        return self._json_data


@pytest.fixture(autouse=True)
def _reset_settings_and_manager(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "CONSUMER_SYNC_URL",
        "https://consumer-sync.gtaitson.space/api/consumer-sync/v1/sync",
    )
    monkeypatch.setenv(
        "CONSUMER_VALIDATION_REPORT_URL",
        "https://consumer-sync.gtaitson.space/api/consumer-sync/v1/validation-report",
    )
    monkeypatch.setenv("CONSUMER_SLUG", "agentvps")
    monkeypatch.setenv("CONSUMER_BOOTSTRAP_SECRET", "bootstrap-secret")
    monkeypatch.setenv("CONSUMER_SYNC_STATE_FILE", str(tmp_path / "agentvps.json"))
    get_settings.cache_clear()
    reset_consumer_sync_manager_for_tests()
    yield
    get_settings.cache_clear()
    reset_consumer_sync_manager_for_tests()


def _sync_payload(compatibility_status="compatible"):
    return {
        "sync_status": "bundle_update_required",
        "release_id": "rel-42",
        "bundle_hash": "hash-42",
        "credential_bundle": {
            "values": {
                "FLEETINTEL_MCP_URL": "https://agent-fleet.gtaitson.space/mcp",
                "FLEETINTEL_CF_ACCESS_CLIENT_ID": "fleet-id",
                "FLEETINTEL_CF_ACCESS_CLIENT_SECRET": "fleet-secret",
                "BRAZILCNPJ_MCP_URL": "https://agent-cnpj.gtaitson.space/mcp",
                "BRAZILCNPJ_CF_ACCESS_CLIENT_ID": "cnpj-id",
                "BRAZILCNPJ_CF_ACCESS_CLIENT_SECRET": "cnpj-secret",
            },
            "hash": "hash-42",
        },
        "contract": {
            "contract_version": "v1",
            "response_contract_version": "client_brief_v1",
            "preferred_client_tools": {
                "fleetintel": ["get_client_readiness_status", "get_market_changes_brief"],
                "brazilcnpj": ["health_check", "get_company_registry_brief"],
            },
            "legacy_tool_policy": {"raw_tools_default_for_clients": False},
            "release_change_summary": ["brief tools published"],
            "client_impact_summary": ["switch to preferred client tools"],
            "behavioral_change_flags": {"brief_surfaces_enabled": True},
            "refresh_policy": {"on_403": "sync_once_retry_once"},
            "error_semantics": {"5xx_post_initialize": "upstream_mcp"},
            "responsibility_boundary": {"specialist_output": "fleetintel"},
            "server_release": {
                "version": "0.1.0",
                "git_sha": "f075623",
                "build_timestamp": "2026-03-16T15:42:44.776543+00:00",
                "supported_contract_versions": ["v1"],
            },
        },
        "client_adaptation": {
            "compatibility_status": compatibility_status,
            "response_contract_version_to_use": "client_brief_v1",
            "preferred_client_tools": {
                "fleetintel": ["get_client_readiness_status", "get_market_changes_brief"],
                "brazilcnpj": ["health_check", "get_company_registry_brief"],
            },
            "fallback_tools": {
                "fleetintel": ["get_operations_status"],
                "brazilcnpj": ["health_check"],
            },
            "required_actions": ["Implementar preferred_client_tools"],
            "deprecation_notices": ["raw tools deprecated"],
        },
    }


def _initialize_response(session_id="session-1"):
    return _MockResponse(
        json_data={"result": {"protocolVersion": "2024-11-05"}},
        headers={"server": "cloudflare", "cf-ray": "ray-1", "mcp-session-id": session_id},
    )


def _tool_response(payload, *, session_id="session-1"):
    return _MockResponse(
        text=f'data: {{"result": {{"content": [{{"type": "text", "text": "{payload}"}}]}}}}',
        headers={
            "server": "cloudflare",
            "cf-ray": "ray-2",
            "mcp-session-id": session_id,
            "content-type": "text/event-stream",
        },
    )


@pytest.mark.asyncio
async def test_run_release_validation_posts_passed_report_when_contract_is_compatible(
    monkeypatch,
):
    posted_reports = []

    async def fake_post(self, url, json=None, headers=None):
        if "consumer-sync" in url and "validation-report" not in url:
            return _MockResponse(
                json_data=_sync_payload("compatible"),
                headers={"server": "cloudflare", "cf-ray": "sync-ray"},
            )
        if "validation-report" in url:
            posted_reports.append(json)
            return _MockResponse(
                json_data={"validation_run_id": "run-123", "validation_status": "passed"},
                headers={"server": "cloudflare", "cf-ray": "report-ray"},
            )
        if (json or {}).get("method") == "initialize":
            return _initialize_response()
        tool_name = json["params"]["name"]
        payload_by_tool = {
            "get_client_readiness_status": '{"status":"ok"}',
            "get_market_changes_brief": '{"status":"ok","items":[{"headline":"Mercado aquecido"}]}',
            "health_check": '{"status":"ok","database_ok":true}',
            "get_company_registry_brief": '{"cnpj":"48430290000130","company_name":"Empresa X"}',
        }
        return _tool_response(payload_by_tool[tool_name])

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    result = await run_release_validation()

    assert result["validation_status"] == "passed"
    assert result["sync"]["contract_version"] == "v1"
    assert result["sync"]["response_contract_version"] == "client_brief_v1"
    assert result["sync"]["client_adaptation"]["compatibility_status"] == "compatible"
    assert result["sync"]["preferred_client_tools_used"]["fleetintel"] == [
        "get_client_readiness_status",
        "get_market_changes_brief",
    ]
    assert result["validation_report"]["http_status"] == 200
    assert result["validation_report"]["validation_run_id"] == "run-123"
    assert posted_reports[0]["client_behavior_version"] == "contract_driven_v1"
    assert posted_reports[0]["validation_status"] == "passed"
    assert {check["name"] for check in result["checks"]} >= {
        "fleet_initialize",
        "cnpj_initialize",
        "fleet_client_readiness",
        "fleet_market_changes_brief",
        "cnpj_health_check",
        "cnpj_company_registry_brief",
    }


@pytest.mark.asyncio
async def test_run_release_validation_fails_and_skips_preferred_tools_when_not_compatible(
    monkeypatch,
):
    posted_reports = []
    tool_calls = []

    async def fake_post(self, url, json=None, headers=None):
        if "consumer-sync" in url and "validation-report" not in url:
            return _MockResponse(json_data=_sync_payload("upgrade_recommended"))
        if "validation-report" in url:
            posted_reports.append(json)
            return _MockResponse(
                json_data={"validation_run_id": "run-456", "validation_status": "failed"}
            )
        if (json or {}).get("method") == "initialize":
            return _initialize_response()
        if (json or {}).get("method") == "tools/call":
            tool_calls.append(json["params"]["name"])
            return _tool_response('{"status":"ok"}')
        raise AssertionError(f"unexpected request: {url}")

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    result = await run_release_validation()

    assert result["validation_status"] == "failed"
    assert result["required_actions"] == ["Implementar preferred_client_tools"]
    assert tool_calls == []
    skipped = [check for check in result["checks"] if check["status"] == "skipped"]
    assert len(skipped) == 4
    assert posted_reports[0]["validation_status"] == "failed"
