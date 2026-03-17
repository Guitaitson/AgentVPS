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


@dataclass(frozen=True, slots=True)
class Account360Case:
    label: str
    input_used: dict[str, Any]
    brief_type: str | None
    status: str | None
    headline: str | None
    has_executive_summary: bool
    has_key_findings: bool
    consumable_without_raw_json: bool
    response_shape: str


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
    if isinstance(payload, dict):
        if "error" in payload:
            return payload["error"], True
        if "result" in payload:
            return payload["result"], response.status_code >= 400
    return payload, response.status_code >= 400


class ContractValidationRunner:
    def __init__(self) -> None:
        self.settings = get_settings().consumer_sync
        self.manager = get_consumer_sync_manager()

    async def run(
        self,
        *,
        known_cnpj: str = "48430290000130",
        known_company_name: str = "ADDIANTE S.A.",
        known_trade_name: str = "ADDIANTE",
        known_partner_name: str = "FABIO ROBERTO LEITE",
        post_report: bool = True,
    ) -> dict[str, Any]:
        state = await self.manager.sync()
        checks: list[ValidationCheck] = []
        tool_catalog: dict[str, Any] | None = None
        account_360_cases: list[dict[str, Any]] = []

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
            tool_catalog = await self._list_tools(state=state, service="fleetintel")
            checks.append(
                ValidationCheck(
                    name="fleet_tools_list",
                    endpoint=tool_catalog["endpoint"],
                    jsonrpc_method="tools/list",
                    status=tool_catalog["status"],
                    http_status=tool_catalog["http_status"],
                    elapsed_seconds=tool_catalog["elapsed_seconds"],
                    server_header=tool_catalog["server_header"],
                    cf_ray=tool_catalog["cf_ray"],
                    body_excerpt=tool_catalog["body_excerpt"],
                    suspected_layer="upstream_mcp" if tool_catalog["status"] != "passed" else None,
                    retried=tool_catalog["retried"],
                    retry_succeeded=tool_catalog["retry_succeeded"],
                )
            )
            checks.append(
                await self._call_preferred_tool(
                    state=state,
                    service="fleetintel",
                    tool_name="get_client_readiness_status",
                    arguments={},
                )
            )
            account_360_tool = self._find_tool_spec(tool_catalog, "get_account_360_brief")
            strong_case_args, flexible_case_args = self._resolve_account_360_inputs(
                account_360_tool=account_360_tool,
                known_cnpj=known_cnpj,
                known_company_name=known_company_name,
                known_trade_name=known_trade_name,
                known_partner_name=known_partner_name,
            )
            strong_result = await self._call_account_360_case(
                state=state,
                arguments=strong_case_args,
                label="strong",
            )
            checks.append(strong_result["check"])
            account_360_cases.append(asdict(strong_result["case"]))
            flexible_result = await self._call_account_360_case(
                state=state,
                arguments=flexible_case_args,
                label="flexible",
            )
            checks.append(flexible_result["check"])
            account_360_cases.append(asdict(flexible_result["case"]))
        else:
            checks.extend(
                [
                    self._skipped_check(
                        service="fleetintel",
                        tool_name="tools/list",
                        body_excerpt=(
                            "Validacao de tools/list pulada porque "
                            f"compatibility_status={compatibility_status or '-'}."
                        ),
                    ),
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
                        tool_name="get_account_360_brief",
                        body_excerpt=(
                            "Validacao de preferred_client_tools pulada porque "
                            f"compatibility_status={compatibility_status or '-'}."
                        ),
                    ),
                    self._skipped_check(
                        service="fleetintel",
                        tool_name="get_account_360_brief:flexible",
                        body_excerpt=(
                            "Validacao de preferred_client_tools pulada porque "
                            f"compatibility_status={compatibility_status or '-'}."
                        ),
                    ),
                ]
            )
        final_state = state
        report_result = None
        if post_report:
            report_result = await self._post_validation_report(
                state=state,
                validation_status=self._pre_report_status(
                    state=state,
                    compatibility_status=compatibility_status,
                    checks=checks,
                ),
                checks=checks,
            )
            final_state = await self.manager.sync()

        validation_status = self._overall_status(
            state=final_state,
            compatibility_status=compatibility_status,
            checks=checks,
            report_result=report_result,
        )

        result = {
            "consumer_slug": self.manager.consumer_slug,
            "agent_name": "AgentVPS",
            "agent_version": get_agent_version(),
            "agent_commit": get_agent_commit(),
            "client_behavior_version": self.manager.client_behavior_version(),
            "sync": {
                "sync_status": final_state.last_sync_status,
                "release_id": final_state.current_release_id,
                "bundle_hash": final_state.current_bundle_hash,
                "contract_version": final_state.contract.contract_version
                if final_state.contract
                else None,
                "response_contract_version": self._response_contract_version(final_state),
                "server_release": asdict(final_state.contract.server_release)
                if final_state.contract and final_state.contract.server_release
                else None,
                "client_adaptation": asdict(final_state.client_adaptation)
                if final_state.client_adaptation
                else None,
                "rollout_status": asdict(final_state.rollout_status)
                if final_state.rollout_status
                else None,
                "preferred_client_tools_used": preferred_tools_used,
            },
            "tool_catalog": tool_catalog,
            "account_360_cases": account_360_cases,
            "checks": [asdict(check) for check in checks],
            "validation_status": validation_status,
            "required_actions": final_state.client_adaptation.required_actions
            if final_state.client_adaptation
            else [],
        }
        result["validation_report"] = report_result
        return result

    def _pre_report_status(
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

    def _overall_status(
        self,
        *,
        state: ConsumerSyncState,
        compatibility_status: str | None,
        checks: list[ValidationCheck],
        report_result: dict[str, Any] | None,
    ) -> str:
        if (
            self._pre_report_status(
                state=state,
                compatibility_status=compatibility_status,
                checks=checks,
            )
            != "passed"
        ):
            return "failed"
        if not report_result or report_result.get("validation_status") != "passed":
            return "failed"
        rollout_status = state.rollout_status.status if state.rollout_status else None
        if rollout_status != "canary_passable":
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

    async def _list_tools(
        self,
        *,
        state: ConsumerSyncState,
        service: str,
    ) -> dict[str, Any]:
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
                "id": "list-tools",
                "method": "tools/list",
                "params": {},
            },
            stage="tools/list",
        )
        payload, is_error = _extract_payload(response)
        tools = self._extract_tools(payload)
        return {
            "endpoint": connection.base_url,
            "jsonrpc_method": "tools/list",
            "status": "passed" if response.status_code < 400 and not is_error else "failed",
            "http_status": response.status_code,
            "elapsed_seconds": round(response.elapsed.total_seconds(), 3)
            if response.elapsed is not None
            else 0.0,
            "server_header": response.headers.get("server"),
            "cf_ray": response.headers.get("cf-ray"),
            "retried": retried,
            "retry_succeeded": retry_succeeded,
            "tool_names": [tool.get("name") for tool in tools if isinstance(tool, dict)],
            "tools": tools,
            "body_excerpt": _response_excerpt(response) if response.status_code >= 400 else None,
        }

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

    async def _call_account_360_case(
        self,
        *,
        state: ConsumerSyncState,
        arguments: dict[str, Any],
        label: str,
    ) -> dict[str, Any]:
        check = await self._call_preferred_tool(
            state=state,
            service="fleetintel",
            tool_name="get_account_360_brief",
            arguments=arguments,
        )
        response_payload = await self._call_tool_payload(
            state=state,
            service="fleetintel",
            tool_name="get_account_360_brief",
            arguments=arguments,
        )
        case = self._summarize_account_360_case(
            label=label,
            arguments=arguments,
            payload=response_payload["payload"],
        )
        case_check = ValidationCheck(
            name=f"fleet_account_360_{label}",
            endpoint=response_payload["endpoint"],
            jsonrpc_method="tools/call:get_account_360_brief",
            status="passed"
            if check.status == "passed" and case.consumable_without_raw_json
            else "failed",
            http_status=response_payload["http_status"],
            elapsed_seconds=response_payload["elapsed_seconds"],
            server_header=response_payload["server_header"],
            cf_ray=response_payload["cf_ray"],
            body_excerpt=check.body_excerpt
            if check.status != "passed"
            else None
            if case.consumable_without_raw_json
            else json.dumps(response_payload["payload"])[:400],
            suspected_layer=check.suspected_layer,
            retried=response_payload["retried"],
            retry_succeeded=response_payload["retry_succeeded"],
        )
        return {"check": case_check, "case": case}

    async def _call_tool_payload(
        self,
        *,
        state: ConsumerSyncState,
        service: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
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
        payload, _ = _extract_payload(response)
        return {
            "endpoint": connection.base_url,
            "http_status": response.status_code,
            "elapsed_seconds": round(response.elapsed.total_seconds(), 3)
            if response.elapsed is not None
            else 0.0,
            "server_header": response.headers.get("server"),
            "cf_ray": response.headers.get("cf-ray"),
            "retried": retried,
            "retry_succeeded": retry_succeeded,
            "payload": payload,
        }

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
            "client_behavior_version": self.manager.client_behavior_version(),
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
    def _extract_tools(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            tools = payload.get("tools")
            if isinstance(tools, list):
                return [tool for tool in tools if isinstance(tool, dict)]
        if isinstance(payload, list):
            return [tool for tool in payload if isinstance(tool, dict)]
        return []

    @staticmethod
    def _find_tool_spec(
        tool_catalog: dict[str, Any] | None, tool_name: str
    ) -> dict[str, Any] | None:
        if not isinstance(tool_catalog, dict):
            return None
        for tool in tool_catalog.get("tools") or []:
            if isinstance(tool, dict) and tool.get("name") == tool_name:
                return tool
        return None

    @staticmethod
    def _resolve_account_360_inputs(
        *,
        account_360_tool: dict[str, Any] | None,
        known_cnpj: str,
        known_company_name: str,
        known_trade_name: str,
        known_partner_name: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        schema = {}
        if isinstance(account_360_tool, dict):
            schema = (
                account_360_tool.get("inputSchema") or account_360_tool.get("input_schema") or {}
            )
        properties = schema.get("properties") if isinstance(schema, dict) else {}
        keys = set(properties.keys()) if isinstance(properties, dict) else set()

        def _pick(*candidates: tuple[str, Any]) -> dict[str, Any]:
            for key, value in candidates:
                if key in keys:
                    return {key: value}
            if "query" in keys:
                return {"query": candidates[0][1]}
            if "input" in keys:
                return {"input": candidates[0][1]}
            if "target" in keys:
                return {"target": candidates[0][1]}
            return {}

        strong = _pick(
            ("cnpj", known_cnpj),
            ("company_name", known_company_name),
            ("razao_social", known_company_name),
            ("legal_name", known_company_name),
            ("query", known_company_name),
        )
        flexible = _pick(
            ("company_name", known_company_name),
            ("trade_name", known_trade_name),
            ("nome_fantasia", known_trade_name),
            ("partner_name", known_partner_name),
            ("socio_name", known_partner_name),
            ("shareholder_name", known_partner_name),
            ("query", known_trade_name),
        )
        return strong, flexible

    @staticmethod
    def _summarize_account_360_case(
        *,
        label: str,
        arguments: dict[str, Any],
        payload: Any,
    ) -> Account360Case:
        if not isinstance(payload, dict):
            return Account360Case(
                label=label,
                input_used=arguments,
                brief_type=None,
                status=None,
                headline=None,
                has_executive_summary=False,
                has_key_findings=False,
                consumable_without_raw_json=False,
                response_shape=type(payload).__name__,
            )
        status = str(payload.get("status") or "").strip() or None
        brief_type = str(payload.get("brief_type") or "").strip() or None
        headline = str(payload.get("headline") or "").strip() or None
        executive_summary = str(payload.get("executive_summary") or "").strip()
        key_findings = payload.get("key_findings")
        shortlist = payload.get("shortlist") or payload.get("candidates")
        refinement = payload.get("refinement_instruction") or payload.get("next_step")
        has_key_findings = isinstance(key_findings, list) and bool(key_findings)
        disambiguation_ok = (
            status == "needs_disambiguation"
            and brief_type == "account_360_disambiguation"
            and isinstance(shortlist, list)
            and bool(shortlist)
            and bool(refinement)
        )
        consumable = bool(
            disambiguation_ok or (headline and (executive_summary or has_key_findings))
        )
        return Account360Case(
            label=label,
            input_used=arguments,
            brief_type=brief_type,
            status=status,
            headline=headline,
            has_executive_summary=bool(executive_summary),
            has_key_findings=has_key_findings,
            consumable_without_raw_json=consumable,
            response_shape="dict",
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
            ("fleetintel", "tools/list"): "fleet_tools_list",
            ("fleetintel", "get_account_360_brief"): "fleet_account_360",
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
