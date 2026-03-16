"""Helpers for calling authenticated remote MCP servers over HTTP."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from core.progress import emit_progress

_CNPJ_RE = re.compile(r"\d{14}")


@dataclass(frozen=True, slots=True)
class RemoteMCPConnection:
    """Resolved connection payload for a remote MCP server."""

    base_url: str
    access_client_id: str
    access_client_secret: str


class RemoteMCPError(RuntimeError):
    """Structured error raised for remote MCP failures."""

    def __init__(
        self,
        *,
        server_name: str,
        stage: str,
        error_type: str,
        message: str,
        status_code: int | None = None,
        response_excerpt: str | None = None,
    ) -> None:
        self.server_name = server_name
        self.stage = stage
        self.error_type = error_type
        self.status_code = status_code
        self.response_excerpt = response_excerpt
        super().__init__(message)

    @property
    def is_transient(self) -> bool:
        return self.error_type in {"timeout", "network"} or self.status_code in {502, 503, 504}

    def describe_short(self) -> str:
        parts = [self.server_name, self.stage, self.error_type]
        if self.status_code is not None:
            parts.append(f"http {self.status_code}")
        return " / ".join(parts)


class RemoteMCPClient:
    """Small client for stateless HTTP MCP servers protected by Cloudflare Access."""

    def __init__(
        self,
        *,
        base_url: str = "",
        access_client_id: str = "",
        access_client_secret: str = "",
        client_name: str,
        server_name: str,
        timeout_seconds: float = 25.0,
        max_attempts: int = 2,
        retry_backoff_seconds: float = 0.6,
        connection_provider: Any | None = None,
        auth_refresh_callback: Any | None = None,
    ):
        self.base_url = base_url.strip()
        self.access_client_id = access_client_id.strip()
        self.access_client_secret = access_client_secret.strip()
        self.client_name = client_name
        self.server_name = server_name
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.connection_provider = connection_provider
        self.auth_refresh_callback = auth_refresh_callback

    @property
    def is_configured(self) -> bool:
        if self.connection_provider is not None:
            return True
        return bool(self.base_url and self.access_client_id and self.access_client_secret)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        if not self.is_configured:
            raise RuntimeError(f"{self.server_name} MCP is not configured")

        refreshed_after_auth_failure = False
        while True:
            connection = await self._resolve_connection()
            try:
                return await self._call_tool_once(connection, tool_name, arguments or {})
            except RemoteMCPError as exc:
                if (
                    exc.status_code == 403
                    and not refreshed_after_auth_failure
                    and self.auth_refresh_callback is not None
                ):
                    refreshed_after_auth_failure = True
                    refreshed = await self._maybe_await(self.auth_refresh_callback())
                    if refreshed:
                        await emit_progress(
                            "external_call",
                            server=self.server_name,
                            stage=exc.stage,
                            status="refreshing_auth",
                            tool=tool_name,
                            error=exc.describe_short(),
                        )
                        continue
                raise

    async def _call_tool_once(
        self,
        connection: RemoteMCPConnection,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        headers = {
            "CF-Access-Client-Id": connection.access_client_id,
            "CF-Access-Client-Secret": connection.access_client_secret,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": self.client_name, "version": "1.0"},
            },
        }
        tool_payload = {
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            await emit_progress(
                "external_call",
                server=self.server_name,
                stage="initialize",
                status="start",
                tool=tool_name,
            )
            init_response = await self._post_with_retry(
                client=client,
                base_url=connection.base_url,
                payload=initialize_payload,
                headers=headers,
                stage="initialize",
                tool_name=tool_name,
            )
            session_id = init_response.headers.get("mcp-session-id")
            tool_headers = {**headers, "mcp-session-id": session_id} if session_id else headers
            await emit_progress(
                "external_call",
                server=self.server_name,
                stage="tools/call",
                status="start",
                tool=tool_name,
            )
            tool_response = await self._post_with_retry(
                client=client,
                base_url=connection.base_url,
                payload=tool_payload,
                headers=tool_headers,
                stage="tools/call",
                tool_name=tool_name,
            )

        content_type = tool_response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(tool_response.text)
        return self._extract_result(tool_response.json())

    async def _post_with_retry(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        stage: str,
        tool_name: str,
    ) -> httpx.Response:
        last_error: RemoteMCPError | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = await client.post(base_url, json=payload, headers=headers)
                if response.status_code >= 400:
                    error = self._http_error(response=response, stage=stage)
                    if error.is_transient and attempt < self.max_attempts:
                        await emit_progress(
                            "external_call",
                            server=self.server_name,
                            stage=stage,
                            status="retrying",
                            tool=tool_name,
                            error=error.describe_short(),
                            attempt=attempt,
                        )
                        await asyncio.sleep(self.retry_backoff_seconds * attempt)
                        last_error = error
                        continue
                    raise error
                return response
            except httpx.TimeoutException as exc:
                error = RemoteMCPError(
                    server_name=self.server_name,
                    stage=stage,
                    error_type="timeout",
                    message=f"{self.server_name} MCP timeout during {stage}",
                )
                if attempt < self.max_attempts:
                    await emit_progress(
                        "external_call",
                        server=self.server_name,
                        stage=stage,
                        status="retrying",
                        tool=tool_name,
                        error=error.describe_short(),
                        attempt=attempt,
                    )
                    await asyncio.sleep(self.retry_backoff_seconds * attempt)
                    last_error = error
                    continue
                raise error from exc
            except httpx.ConnectError as exc:
                error = RemoteMCPError(
                    server_name=self.server_name,
                    stage=stage,
                    error_type="network",
                    message=f"{self.server_name} MCP connection failed during {stage}",
                )
                if attempt < self.max_attempts:
                    await emit_progress(
                        "external_call",
                        server=self.server_name,
                        stage=stage,
                        status="retrying",
                        tool=tool_name,
                        error=error.describe_short(),
                        attempt=attempt,
                    )
                    await asyncio.sleep(self.retry_backoff_seconds * attempt)
                    last_error = error
                    continue
                raise error from exc
            except httpx.HTTPError as exc:
                error = RemoteMCPError(
                    server_name=self.server_name,
                    stage=stage,
                    error_type="network",
                    message=f"{self.server_name} MCP request failed during {stage}",
                )
                raise error from exc

        if last_error is not None:
            raise last_error
        raise RemoteMCPError(
            server_name=self.server_name,
            stage=stage,
            error_type="network",
            message=f"{self.server_name} MCP request failed during {stage}",
        )

    def _parse_sse(self, payload: str) -> Any:
        for line in payload.splitlines():
            if not line.startswith("data: "):
                continue
            try:
                return self._extract_result(json.loads(line[6:]))
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _extract_result(payload: dict[str, Any]) -> Any:
        if "error" in payload:
            raise RemoteMCPError(
                server_name="remote-mcp",
                stage="tools/call",
                error_type="bad_payload",
                message=str(payload["error"]),
            )
        result = payload.get("result", {})
        content = result.get("content", [])
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "text":
                    continue
                text = block.get("text", "")
                try:
                    return json.loads(text)
                except Exception:
                    return text
        return result

    def _http_error(self, *, response: httpx.Response, stage: str) -> RemoteMCPError:
        excerpt = (response.text or "").strip().replace("\n", " ")[:240]
        error_type = "http_5xx" if response.status_code >= 500 else "auth"
        if response.status_code in {400, 404, 409, 422}:
            error_type = "bad_payload"
        elif response.status_code in {401, 403}:
            error_type = "auth"
        elif response.status_code >= 500:
            error_type = "http_5xx"
        return RemoteMCPError(
            server_name=self.server_name,
            stage=stage,
            error_type=error_type,
            status_code=response.status_code,
            response_excerpt=excerpt or None,
            message=f"{self.server_name} MCP returned HTTP {response.status_code} during {stage}",
        )

    async def _resolve_connection(self) -> RemoteMCPConnection:
        if self.connection_provider is not None:
            connection = await self._maybe_await(self.connection_provider())
            if not isinstance(connection, RemoteMCPConnection):
                raise RuntimeError(
                    f"{self.server_name} MCP connection provider returned invalid payload"
                )
            return connection
        return RemoteMCPConnection(
            base_url=self.base_url,
            access_client_id=self.access_client_id,
            access_client_secret=self.access_client_secret,
        )

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if hasattr(value, "__await__"):
            return await value
        return value


def extract_cnpjs(data: Any) -> list[str]:
    found: list[str] = []

    def visit(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if isinstance(value, str):
            found.extend(_CNPJ_RE.findall(value))

    visit(data)
    unique: list[str] = []
    for cnpj in found:
        if cnpj not in unique:
            unique.append(cnpj)
    return unique


def render_result_block(title: str, data: Any, *, max_chars: int = 2800) -> str:
    if data is None:
        return f"{title}\n\nNenhum dado retornado."
    if isinstance(data, str):
        body = data.strip()
    else:
        body = json.dumps(data, ensure_ascii=False, indent=2)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n... [truncado]"
    return f"{title}\n\n{body}"
