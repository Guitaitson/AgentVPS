"""Contract-driven canary validation for FleetIntel/BrazilCNPJ releases."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from core.config import get_settings

from .consumer_sync import (
    ConsumerSyncState,
    get_agent_commit,
    get_agent_version,
    get_consumer_sync_manager,
)


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    name: str
    endpoint: str
    jsonrpc_method: str
    status: str
    http_status: int | None
    elapsed_seconds: float
    server_header: str | None
    cf_ray: str | None
    body_excerpt: str | None = None
    suspected_layer: str | None = None
    retried: bool = False
    retry_succeeded: bool = False


def _response_excerpt(response: httpx.Response) -> str:
    text = (response.text or "").strip().replace("\n", " ")
    return text[:400]


def _extract_payload(response: httpx.Response) -> tuple[Any, bool]:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if not line.startswith("data: "):
                continue
            try:
                payload = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            result = payload.get("result") or {}
            if result.get("isError"):
                blocks = result.get("content") or []
                text = ""
                if blocks and isinstance(blocks[0], dict):
                    text = str(blocks[0].get("text") or "")
                return text or result, True
            content = result.get("content") or []
            if blocks := [
                item for item in content if isinstance(item, dict) and item.get("type") == "text"
            ]:
                text = str(blocks[0].get("text") or "")
                try:
                    return json.loads(text), False
                except Exception:
                    return text, False
            return result, False
        return None, False
    try:
        payload = response.json()
    except Exception:
        return _response_excerpt(response), response.status_code >= 400
    return payload, response.status_code >= 400


class ContractValidationRunner:
    def __init__(self) -> None:
        self.settings = get_settings().consumer_sync
        self.manager = get_consumer_sync_manager()

    async def run(
        self,
        *,
        known_cnpj: str = "48430290000130",
        post_report: bool = True,
    ) -> dict[str, Any]:
        state = await self.manager.sync()
        checks: list[ValidationCheck] = []

        fleet_init = await self._initialize("fleetintel")
        checks.append(fleet_init["check"])
        cnpj_init = await self._initialize("brazilcnpj")
        checks.append(cnpj_init["check"])

        preferred_tools_used = {
            "fleetintel": self.manager.preferred_tools_for("fleetintel", state),
            "brazilcnpj": self.manager.preferred_tools_for("brazilcnpj", state),
        }
        compatibility_status = (
            state.client_adaptation.compatibility_status if state.client_adaptation else None
        )
        if compatibility_status == "compatible":
            checks.append(
                await self._call_preferred_tool(
                    state=state,
                    service="fleetintel",
                    tool_name="get_client_readiness_status",
                    arguments={},
                )
            )
            checks.append(
                await self._call_preferred_tool(
                    state=state,
                    service="fleetintel",
                    tool_name="get_market_changes_brief",
                    arguments={"limit_items": 5},
                )
            )
            checks.append(
                await self._call_preferred_tool(
                    state=state,
                    service="brazilcnpj",
                    tool_name="health_check",
                    arguments={},
                )
            )
            checks.append(
                await self._call_preferred_tool(
                    state=state,
                    service="brazilcnpj",
                    tool_name="get_company_registry_brief",
                    arguments={"cnpj": known_cnpj},
                )
            )
        else:
            checks.extend(
                [
                    self._skipped_check(
                        service="fleetintel",
                        tool_name="get_client_readiness_status",
                        body_excerpt=(
                            "Validacao de preferred_client_tools pulada porque "
                            f"compatibility_status={compatibility_status or '-'}."
                        ),
                    ),
                    self._skipped_check(
                        service="fleetintel",
                        tool_name="get_market_changes_brief",
                        body_excerpt=(
                            "Validacao de preferred_client_tools pulada porque "
                            f"compatibility_status={compatibility_status or '-'}."
                        ),
                    ),
                    self._skipped_check(
                        service="brazilcnpj",
                        tool_name="health_check",
                        body_excerpt=(
                            "Validacao de preferred_client_tools pulada porque "
                            f"compatibility_status={compatibility_status or '-'}."
                        ),
                    ),
                    self._skipped_check(
                        service="brazilcnpj",
                        tool_name="get_company_registry_brief",
                        body_excerpt=(
                            "Validacao de preferred_client_tools pulada porque "
                            f"compatibility_status={compatibility_status or '-'}."
                        ),
                    ),
                ]
            )
        validation_status = self._overall_status(
            state=state,
            compatibility_status=compatibility_status,
            checks=checks,
        )

        result = {
            "consumer_slug": self.manager.consumer_slug,
            "agent_name": "AgentVPS",
            "agent_version": get_agent_version(),
            "agent_commit": get_agent_commit(),
            "client_behavior_version": "contract_driven_v1",
            "sync": {
                "sync_status": state.last_sync_status,
                "release_id": state.current_release_id,
                "bundle_hash": state.current_bundle_hash,
                "contract_version": state.contract.contract_version if state.contract else None,
                "response_contract_version": self._response_contract_version(state),
                "server_release": asdict(state.contract.server_release)
                if state.contract and state.contract.server_release
                else None,
                "client_adaptation": asdict(state.client_adaptation)
                if state.client_adaptation
                else None,
                "preferred_client_tools_used": preferred_tools_used,
            },
            "checks": [asdict(check) for check in checks],
            "validation_status": validation_status,
            "required_actions": state.client_adaptation.required_actions
            if state.client_adaptation
            else [],
        }

        report_result = None
        if post_report:
            report_result = await self._post_validation_report(
                state=state,
                validation_status=validation_status,
                checks=checks,
            )
        result["validation_report"] = report_result
        return result

    def _overall_status(
        self,
        *,
        state: ConsumerSyncState,
        compatibility_status: str | None,
        checks: list[ValidationCheck],
    ) -> str:
        if state.last_sync_status not in {"up_to_date", "bundle_update_required"}:
            return "failed"
        if compatibility_status != "compatible":
            return "failed"
        if any(check.status != "passed" for check in checks):
            return "failed"
        return "passed"

    def _response_contract_version(self, state: ConsumerSyncState) -> str | None:
        if state.client_adaptation and state.client_adaptation.response_contract_version_to_use:
            return state.client_adaptation.response_contract_version_to_use
        if state.contract:
            return state.contract.response_contract_version
        return None

    async def _initialize(self, service: str) -> dict[str, Any]:
        connection = await self.manager.resolve_service_connection(service)
        headers = self._headers(connection)
        payload = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agentvps-contract-validator", "version": "1.0"},
            },
        }
        response, retried, retry_succeeded = await self._post_with_refresh_retry(
            service=service,
            endpoint=connection.base_url,
            headers=headers,
            payload=payload,
            stage="initialize",
        )
        prefix = "cnpj" if service == "brazilcnpj" else "fleet"
        check = self._build_check(
            name=f"{prefix}_initialize",
            endpoint=connection.base_url,
            jsonrpc_method="initialize",
            response=response,
            retried=retried,
            retry_succeeded=retry_succeeded,
            stage="initialize",
        )
        return {"check": check, "response": response}

    async def _call_preferred_tool(
        self,
        *,
        state: ConsumerSyncState,
        service: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ValidationCheck:
        preferred = self.manager.preferred_tools_for(service, state)
        if tool_name not in preferred:
            return ValidationCheck(
                name=self._check_name(service, tool_name),
                endpoint="",
                jsonrpc_method="tools/call",
                status="failed",
                http_status=None,
                elapsed_seconds=0.0,
                server_header=None,
                cf_ray=None,
                body_excerpt=f"Tool {tool_name} nao consta em preferred_client_tools para {service}.",
                suspected_layer="upstream_mcp",
            )

        connection = await self.manager.resolve_service_connection(service)
        init_payload = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agentvps-contract-validator", "version": "1.0"},
            },
        }
        headers = self._headers(connection)
        init_response, _, _ = await self._post_with_refresh_retry(
            service=service,
            endpoint=connection.base_url,
            headers=headers,
            payload=init_payload,
            stage="initialize",
        )
        session_id = init_response.headers.get("mcp-session-id")
        if session_id:
            headers = {**headers, "mcp-session-id": session_id}
        response, retried, retry_succeeded = await self._post_with_refresh_retry(
            service=service,
            endpoint=connection.base_url,
            headers=headers,
            payload={
                "jsonrpc": "2.0",
                "id": f"call-{tool_name}",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
            stage="tools/call",
        )
        return self._build_check(
            name=self._check_name(service, tool_name),
            endpoint=connection.base_url,
            jsonrpc_method=f"tools/call:{tool_name}",
            response=response,
            retried=retried,
            retry_succeeded=retry_succeeded,
            stage="tools/call",
        )

    async def _post_validation_report(
        self,
        *,
        state: ConsumerSyncState,
        validation_status: str,
        checks: list[ValidationCheck],
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.manager.bootstrap_secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "consumer_slug": self.manager.consumer_slug,
            "agent_name": "AgentVPS",
            "agent_version": get_agent_version(),
            "agent_commit": get_agent_commit(),
            "client_behavior_version": "contract_driven_v1",
            "contract_version": state.contract.contract_version if state.contract else None,
            "response_contract_version": self._response_contract_version(state),
            "server_release": asdict(state.contract.server_release)
            if state.contract and state.contract.server_release
            else None,
            "validation_status": validation_status,
            "summary": {
                "sync_status": state.last_sync_status,
                "release_id": state.current_release_id,
                "bundle_hash": state.current_bundle_hash,
            },
            "checks": [
                {
                    "name": check.name,
                    "status": check.status,
                    "http_status": check.http_status,
                }
                for check in checks
            ],
        }
        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            started = time.perf_counter()
            response = await client.post(
                self.settings.validation_report_url,
                headers=headers,
                json=payload,
            )
            elapsed = round(time.perf_counter() - started, 3)
        data: dict[str, Any] = {}
        try:
            data = response.json()
        except Exception:
            data = {}
        return {
            "http_status": response.status_code,
            "elapsed_seconds": elapsed,
            "validation_run_id": data.get("validation_run_id"),
            "validation_status": data.get("validation_status"),
            "body_excerpt": None if response.status_code < 400 else _response_excerpt(response),
        }

    async def _post_with_refresh_retry(
        self,
        *,
        service: str,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        stage: str,
    ) -> tuple[httpx.Response, bool, bool]:
        retried = False
        retry_succeeded = False
        response = await self._post(endpoint=endpoint, headers=headers, payload=payload)
        if response.status_code == 403:
            retried = True
            await self.manager.refresh_bundle_once(service)
            connection = await self.manager.resolve_service_connection(service)
            headers = self._headers(connection)
            if stage == "tools/call":
                init_payload = {
                    "jsonrpc": "2.0",
                    "id": "init-retry",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "agentvps-contract-validator",
                            "version": "1.0",
                        },
                    },
                }
                init_response = await self._post(
                    endpoint=connection.base_url,
                    headers=headers,
                    payload=init_payload,
                )
                session_id = init_response.headers.get("mcp-session-id")
                if session_id:
                    headers = {**headers, "mcp-session-id": session_id}
                endpoint = connection.base_url
            else:
                endpoint = connection.base_url
            response = await self._post(endpoint=endpoint, headers=headers, payload=payload)
            retry_succeeded = response.status_code < 400
        return response, retried, retry_succeeded

    async def _post(
        self,
        *,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            return await client.post(endpoint, headers=headers, json=payload)

    @staticmethod
    def _headers(connection: Any) -> dict[str, str]:
        return {
            "CF-Access-Client-Id": connection.access_client_id,
            "CF-Access-Client-Secret": connection.access_client_secret,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _build_check(
        self,
        *,
        name: str,
        endpoint: str,
        jsonrpc_method: str,
        response: httpx.Response,
        retried: bool,
        retry_succeeded: bool,
        stage: str,
    ) -> ValidationCheck:
        payload, is_error = _extract_payload(response)
        status = "passed" if response.status_code < 400 and not is_error else "failed"
        return ValidationCheck(
            name=name,
            endpoint=endpoint,
            jsonrpc_method=jsonrpc_method,
            status=status,
            http_status=response.status_code,
            elapsed_seconds=round(response.elapsed.total_seconds(), 3)
            if response.elapsed is not None
            else 0.0,
            server_header=response.headers.get("server"),
            cf_ray=response.headers.get("cf-ray"),
            body_excerpt=_response_excerpt(response) if status == "failed" else None,
            suspected_layer=self._suspected_layer(response=response, payload=payload, stage=stage),
            retried=retried,
            retry_succeeded=retry_succeeded,
        )

    @staticmethod
    def _suspected_layer(*, response: httpx.Response, payload: Any, stage: str) -> str | None:
        if response.status_code in {401, 403}:
            return "access"
        if response.status_code >= 500 and stage == "initialize":
            return "edge_proxy"
        if response.status_code >= 500:
            return "upstream_mcp"
        if isinstance(payload, str) and "Unknown tool:" in payload:
            return "upstream_mcp"
        return None

    @staticmethod
    def _check_name(service: str, tool_name: str) -> str:
        explicit = {
            ("fleetintel", "get_client_readiness_status"): "fleet_client_readiness",
            ("fleetintel", "get_market_changes_brief"): "fleet_market_changes_brief",
            ("brazilcnpj", "health_check"): "cnpj_health_check",
            ("brazilcnpj", "get_company_registry_brief"): "cnpj_company_registry_brief",
        }
        if (service, tool_name) in explicit:
            return explicit[(service, tool_name)]
        prefixes = {"fleetintel": "fleet", "brazilcnpj": "cnpj"}
        prefix = prefixes.get(service, service)
        cleaned = tool_name.replace("get_", "")
        return f"{prefix}_{cleaned}"

    def _skipped_check(self, *, service: str, tool_name: str, body_excerpt: str) -> ValidationCheck:
        return ValidationCheck(
            name=self._check_name(service, tool_name),
            endpoint="",
            jsonrpc_method=f"tools/call:{tool_name}",
            status="skipped",
            http_status=None,
            elapsed_seconds=0.0,
            server_header=None,
            cf_ray=None,
            body_excerpt=body_excerpt,
            suspected_layer=None,
            retried=False,
            retry_succeeded=False,
        )


async def run_release_validation(
    *,
    known_cnpj: str = "48430290000130",
    post_report: bool = True,
) -> dict[str, Any]:
    runner = ContractValidationRunner()
    return await runner.run(known_cnpj=known_cnpj, post_report=post_report)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run FleetIntel/BrazilCNPJ contract validation")
    parser.add_argument("--known-cnpj", default="48430290000130")
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Do not POST the validation report",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    result = asyncio.run(
        run_release_validation(
            known_cnpj=args.known_cnpj,
            post_report=not args.skip_report,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
