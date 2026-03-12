"""Helpers for calling authenticated remote MCP servers over HTTP."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

_CNPJ_RE = re.compile(r"\b\d{14}\b")


class RemoteMCPClient:
    """Small client for stateless HTTP MCP servers protected by Cloudflare Access."""

    def __init__(
        self,
        *,
        base_url: str,
        access_client_id: str,
        access_client_secret: str,
        client_name: str,
        server_name: str,
        timeout_seconds: float = 25.0,
    ):
        self.base_url = base_url.strip()
        self.access_client_id = access_client_id.strip()
        self.access_client_secret = access_client_secret.strip()
        self.client_name = client_name
        self.server_name = server_name
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.access_client_id and self.access_client_secret)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        if not self.is_configured:
            raise RuntimeError(f"{self.server_name} MCP is not configured")

        headers = {
            "CF-Access-Client-Id": self.access_client_id,
            "CF-Access-Client-Secret": self.access_client_secret,
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
                "arguments": arguments or {},
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            init_response = await client.post(
                self.base_url, json=initialize_payload, headers=headers
            )
            init_response.raise_for_status()
            session_id = init_response.headers.get("mcp-session-id")
            tool_headers = {**headers, "mcp-session-id": session_id} if session_id else headers
            tool_response = await client.post(
                self.base_url, json=tool_payload, headers=tool_headers
            )
            tool_response.raise_for_status()

        content_type = tool_response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(tool_response.text)
        return self._extract_result(tool_response.json())

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
            raise RuntimeError(str(payload["error"]))
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
