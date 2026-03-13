"""
Runtime adapter layer for local and delegated agent execution.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

import httpx
import structlog

from core.memory import MemoryPolicy
from core.progress import emit_progress

logger = structlog.get_logger(__name__)


class RuntimeProtocol(str, Enum):
    """Supported execution runtimes/protocols."""

    LOCAL_SKILLS = "local_skills"
    MCP = "mcp"
    A2A = "a2a"
    ACP = "acp"
    DEEPAGENTS = "deepagents"
    OPENCLAW = "openclaw"
    CODEX_OPERATOR = "codex_operator"


@dataclass(slots=True)
class RuntimeExecutionRequest:
    """Execution request consumed by runtime adapters."""

    action: str
    args: dict[str, Any]
    user_id: str
    project_id: str | None = None
    context: dict[str, Any] | None = None
    context_keys: list[str] | None = None
    preferred_protocol: RuntimeProtocol | None = None


@dataclass(slots=True)
class RuntimeExecutionResult:
    """Normalized output contract across local/delegated runtimes."""

    success: bool
    output: Any
    runtime: RuntimeProtocol
    latency_ms: int
    error: str | None = None


class AgentRuntimeAdapter(ABC):
    """Base adapter contract for execution backends."""

    protocol: RuntimeProtocol

    @abstractmethod
    async def execute(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        """Execute one request in this runtime."""

    def can_handle(self, request: RuntimeExecutionRequest) -> bool:
        return True


class LocalSkillsAdapter(AgentRuntimeAdapter):
    """Executes actions through the local SkillRegistry."""

    protocol = RuntimeProtocol.LOCAL_SKILLS

    def __init__(
        self,
        registry,
        executor: Callable[[RuntimeExecutionRequest], Awaitable[Any]] | None = None,
    ):
        self.registry = registry
        self._executor = executor

    def can_handle(self, request: RuntimeExecutionRequest) -> bool:
        return self.registry.get(request.action) is not None

    async def execute(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        started = time.perf_counter()
        if self._executor is not None:
            output = await self._executor(request)
        else:
            output = await self.registry.execute_skill(request.action, request.args)
        return RuntimeExecutionResult(
            success=True,
            output=output,
            runtime=self.protocol,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


class MCPAdapter(AgentRuntimeAdapter):
    """Delegates actions to an MCP endpoint."""

    protocol = RuntimeProtocol.MCP

    def __init__(self, base_url: str, api_key: str | None = None, timeout_s: int = 30):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

    async def execute(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        started = time.perf_counter()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        payload = {"name": request.action, "arguments": request.args or {}}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(
                    f"{self.base_url}/mcp/v1/tools/call",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            return RuntimeExecutionResult(
                success="error" not in data,
                output=data.get("content", data),
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=data.get("error"),
            )
        except Exception as exc:  # pragma: no cover - network path
            return RuntimeExecutionResult(
                success=False,
                output=None,
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
            )


class A2AAdapter(AgentRuntimeAdapter):
    """Delegates through an A2A-compatible endpoint."""

    protocol = RuntimeProtocol.A2A

    def __init__(self, endpoint: str, timeout_s: int = 30):
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    async def execute(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        started = time.perf_counter()
        payload = {
            "task": request.action,
            "arguments": request.args or {},
            "context": request.context or {},
            "user_id": request.user_id,
            "project_id": request.project_id,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
            return RuntimeExecutionResult(
                success=bool(data.get("success", True)),
                output=data.get("output", data),
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=data.get("error"),
            )
        except Exception as exc:  # pragma: no cover - network path
            return RuntimeExecutionResult(
                success=False,
                output=None,
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
            )


class ACPAdapter(AgentRuntimeAdapter):
    """Delegates through an ACP-compatible endpoint."""

    protocol = RuntimeProtocol.ACP

    def __init__(self, endpoint: str, timeout_s: int = 30):
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    async def execute(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        started = time.perf_counter()
        payload = {
            "action": request.action,
            "params": request.args or {},
            "context": request.context or {},
            "identity": {"user_id": request.user_id, "project_id": request.project_id},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
            return RuntimeExecutionResult(
                success=bool(data.get("success", True)),
                output=data.get("output", data),
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=data.get("error"),
            )
        except Exception as exc:  # pragma: no cover - network path
            return RuntimeExecutionResult(
                success=False,
                output=None,
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
            )


class DeepAgentsAdapter(AgentRuntimeAdapter):
    """Delegates through a DeepAgents-compatible endpoint."""

    protocol = RuntimeProtocol.DEEPAGENTS

    def __init__(self, endpoint: str, timeout_s: int = 30):
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    async def execute(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        started = time.perf_counter()
        payload = {
            "task": {"name": request.action, "input": request.args or {}},
            "context": request.context or {},
            "identity": {"user_id": request.user_id, "project_id": request.project_id},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
            return RuntimeExecutionResult(
                success=bool(data.get("success", True)),
                output=data.get("output", data),
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=data.get("error"),
            )
        except Exception as exc:  # pragma: no cover - network path
            return RuntimeExecutionResult(
                success=False,
                output=None,
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
            )


class OpenClawAdapter(AgentRuntimeAdapter):
    """Delegates through an OpenClaw-compatible gateway endpoint."""

    protocol = RuntimeProtocol.OPENCLAW

    def __init__(self, endpoint: str, api_key: str | None = None, timeout_s: int = 30):
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_s = timeout_s

    async def execute(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        started = time.perf_counter()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        payload = {
            "channel": "agentvps",
            "action": request.action,
            "arguments": request.args or {},
            "context": request.context or {},
            "meta": {"user_id": request.user_id, "project_id": request.project_id},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            return RuntimeExecutionResult(
                success=bool(data.get("success", True)),
                output=data.get("output", data),
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=data.get("error"),
            )
        except Exception as exc:  # pragma: no cover - network path
            return RuntimeExecutionResult(
                success=False,
                output=None,
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
            )


class CodexOperatorAdapter(AgentRuntimeAdapter):
    """Delegates complex specialist flows to a local Codex CLI operator."""

    protocol = RuntimeProtocol.CODEX_OPERATOR

    def __init__(
        self,
        *,
        codex_command: str = "codex",
        workdir: str,
        python_executable: str | None = None,
        model: str | None = None,
        timeout_s: int = 120,
    ):
        self.codex_command = codex_command.strip() or "codex"
        self.workdir = os.path.abspath(workdir)
        self.python_executable = python_executable or sys.executable
        self.model = model
        self.timeout_s = timeout_s

    async def execute(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        started = time.perf_counter()
        if shutil.which(self.codex_command) is None:
            return RuntimeExecutionResult(
                success=False,
                output=None,
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"Codex CLI not found: {self.codex_command}",
            )

        auth_path = os.path.expanduser("~/.codex/auth.json")
        if not os.path.exists(auth_path):
            return RuntimeExecutionResult(
                success=False,
                output=None,
                runtime=self.protocol,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error="Codex auth not configured",
            )

        await emit_progress("external_call", server="codex_operator", status="start")

        with tempfile.TemporaryDirectory(prefix="agentvps-codex-") as tmpdir:
            tmpdir = os.path.abspath(tmpdir)
            schema_path = os.path.join(tmpdir, "output_schema.json")
            output_path = os.path.join(tmpdir, "codex_output.json")
            with open(schema_path, "w", encoding="utf-8") as schema_file:
                json.dump(_codex_output_schema(), schema_file, ensure_ascii=True)

            command = [
                self.codex_command,
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--json",
                "--color",
                "never",
                "--sandbox",
                "workspace-write",
                "-C",
                tmpdir,
                "--output-schema",
                schema_path,
                "-o",
                output_path,
            ]
            if self.model:
                command.extend(["-m", self.model])
            command.append("-")

            prompt = self._build_prompt(request)
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                f"{self.workdir}{os.pathsep}{existing_pythonpath}"
                if existing_pythonpath
                else self.workdir
            )
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir,
                env=env,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(prompt.encode("utf-8")),
                    timeout=self.timeout_s,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return RuntimeExecutionResult(
                    success=False,
                    output=None,
                    runtime=self.protocol,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error="Codex operator timeout",
                )

            if process.returncode != 0:
                error_text = (
                    stderr.decode("utf-8", errors="ignore").strip()
                    or stdout.decode("utf-8", errors="ignore").strip()
                )
                return RuntimeExecutionResult(
                    success=False,
                    output=None,
                    runtime=self.protocol,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error=f"Codex operator failed: {error_text[:500]}",
                )

            if not os.path.exists(output_path):
                return RuntimeExecutionResult(
                    success=False,
                    output=None,
                    runtime=self.protocol,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error="Codex operator returned no output file",
                )

            with open(output_path, "r", encoding="utf-8") as output_file:
                payload = json.load(output_file)

        return RuntimeExecutionResult(
            success=True,
            output=payload,
            runtime=self.protocol,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    def _build_prompt(self, request: RuntimeExecutionRequest) -> str:
        specialist_hint = request.action
        allowed_specialists = _allowed_codex_specialists(specialist_hint)
        bridge_cmd = (
            f"{shlex.quote(self.python_executable)} -m core.codex_operator_bridge run-skill "
            f"--skill <skill> --args-json '<json>'"
        )
        envelope = {
            "task": request.args.get("query") or request.args.get("raw_input") or request.action,
            "specialist_hint": specialist_hint,
            "allowed_specialists": allowed_specialists,
            "context": request.context or {},
            "constraints": {
                "no_file_edits": True,
                "no_dangerous_skills": True,
                "max_specialist_calls": 4,
            },
        }
        return (
            "Voce e o operador Codex do AgentVPS.\n"
            "Objetivo: operar apenas especialistas allowlisted e devolver uma resposta estruturada.\n"
            "Regras obrigatorias:\n"
            "1. Nao edite arquivos.\n"
            "2. Nao execute comandos fora do bridge abaixo.\n"
            "3. Use apenas estes especialistas: " + ", ".join(allowed_specialists) + ".\n"
            "4. Se faltar dado, diga explicitamente em unresolved_items.\n"
            "5. Nao exponha segredos ou caminhos sensiveis.\n\n"
            f"Bridge permitido:\n{bridge_cmd}\n\n"
            "Envelope da tarefa:\n"
            f"{json.dumps(envelope, ensure_ascii=False, indent=2)}\n"
        )


def _allowed_codex_specialists(specialist_hint: str) -> list[str]:
    if specialist_hint == "fleetintel_orchestrator":
        return ["fleetintel_orchestrator", "fleetintel_analyst", "brazilcnpj"]
    if specialist_hint == "fleetintel_analyst":
        return ["fleetintel_analyst", "brazilcnpj"]
    if specialist_hint == "brazilcnpj":
        return ["brazilcnpj"]
    return ["fleetintel_analyst", "brazilcnpj"]


def _codex_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "answer",
            "confidence",
            "facts",
            "tool_trace",
            "unresolved_items",
            "requires_human_approval",
        ],
        "properties": {
            "summary": {"type": "string"},
            "answer": {"type": "string"},
            "confidence": {"type": "number"},
            "facts": {"type": "array", "items": {"type": "string"}},
            "tool_trace": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["tool", "status"],
                    "properties": {
                        "tool": {"type": "string"},
                        "status": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                },
            },
            "unresolved_items": {"type": "array", "items": {"type": "string"}},
            "requires_human_approval": {"type": "boolean"},
        },
    }


class RuntimeRouter:
    """
    Router for local vs delegated runtimes with least-privilege context.
    """

    def __init__(
        self, adapters: list[AgentRuntimeAdapter], memory_policy: MemoryPolicy | None = None
    ):
        if not adapters:
            raise ValueError("RuntimeRouter requires at least one adapter")
        self._adapters = {adapter.protocol: adapter for adapter in adapters}
        self._memory_policy = memory_policy or MemoryPolicy()

    async def dispatch(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        prepared_request = self._prepare_request(request)
        adapter = self._select_adapter(prepared_request)
        logger.info(
            "runtime_dispatch",
            protocol=adapter.protocol.value,
            action=prepared_request.action,
            user_id=prepared_request.user_id,
        )
        return await adapter.execute(prepared_request)

    def has_protocol(self, protocol: RuntimeProtocol) -> bool:
        return protocol in self._adapters

    def _prepare_request(self, request: RuntimeExecutionRequest) -> RuntimeExecutionRequest:
        allowed_keys = set(request.context_keys) if request.context_keys else None
        sanitized_context = self._memory_policy.sanitize_context(request.context, allowed_keys)
        return replace(request, context=sanitized_context)

    def _select_adapter(self, request: RuntimeExecutionRequest) -> AgentRuntimeAdapter:
        preferred = request.preferred_protocol
        if preferred is not None and preferred in self._adapters:
            return self._adapters[preferred]

        local_adapter = self._adapters.get(RuntimeProtocol.LOCAL_SKILLS)
        if local_adapter is not None and local_adapter.can_handle(request):
            return local_adapter

        for protocol in (
            RuntimeProtocol.MCP,
            RuntimeProtocol.A2A,
            RuntimeProtocol.ACP,
            RuntimeProtocol.DEEPAGENTS,
            RuntimeProtocol.OPENCLAW,
            RuntimeProtocol.CODEX_OPERATOR,
        ):
            if protocol in self._adapters:
                return self._adapters[protocol]

        return next(iter(self._adapters.values()))
