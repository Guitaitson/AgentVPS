"""
Runtime router factory with lazy singleton wiring.
"""

from __future__ import annotations

from functools import lru_cache

from core.config import get_settings
from core.memory import MemoryPolicy
from core.skills.registry import get_skill_registry

from .runtime_adapters import (
    A2AAdapter,
    ACPAdapter,
    DeepAgentsAdapter,
    LocalSkillsAdapter,
    MCPAdapter,
    OpenClawAdapter,
    RuntimeExecutionRequest,
    RuntimeProtocol,
    RuntimeRouter,
)


def _build_local_executor(registry):
    async def execute_local(request: RuntimeExecutionRequest):
        import time

        from core.hooks.runner import HookContext, get_hook_runner

        hook_runner = get_hook_runner()
        ctx = HookContext(
            skill_name=request.action,
            args=request.args or {},
            user_id=request.user_id,
        )

        should_proceed = await hook_runner.run_pre(ctx)
        if not should_proceed:
            return "Execucao cancelada por politica de seguranca."

        start = time.perf_counter()
        try:
            result = await registry.execute_skill(request.action, request.args or {})
            ctx.duration_ms = (time.perf_counter() - start) * 1000
            ctx.result = str(result)
        except Exception as exc:
            ctx.duration_ms = (time.perf_counter() - start) * 1000
            ctx.error = str(exc)
            await hook_runner.run_post(ctx)
            raise

        await hook_runner.run_post(ctx)
        return result

    return execute_local


@lru_cache(maxsize=1)
def get_runtime_router() -> RuntimeRouter:
    """
    Build and cache the runtime router based on environment settings.
    """
    settings = get_settings()
    registry = get_skill_registry()

    adapters = [
        LocalSkillsAdapter(
            registry=registry,
            executor=_build_local_executor(registry),
        )
    ]

    orch = settings.orchestration
    if orch.enable_mcp:
        adapters.append(
            MCPAdapter(
                base_url=orch.mcp_base_url,
                api_key=orch.mcp_api_key,
                timeout_s=orch.timeout_seconds,
            )
        )
    if orch.enable_a2a and orch.a2a_endpoint:
        adapters.append(A2AAdapter(endpoint=orch.a2a_endpoint, timeout_s=orch.timeout_seconds))
    if orch.enable_acp and orch.acp_endpoint:
        adapters.append(ACPAdapter(endpoint=orch.acp_endpoint, timeout_s=orch.timeout_seconds))
    if orch.enable_deepagents and orch.deepagents_endpoint:
        adapters.append(
            DeepAgentsAdapter(endpoint=orch.deepagents_endpoint, timeout_s=orch.timeout_seconds)
        )
    if orch.enable_openclaw and orch.openclaw_endpoint:
        adapters.append(
            OpenClawAdapter(
                endpoint=orch.openclaw_endpoint,
                api_key=orch.openclaw_api_key,
                timeout_s=orch.timeout_seconds,
            )
        )

    return RuntimeRouter(adapters=adapters, memory_policy=MemoryPolicy())


def reset_runtime_router_for_tests() -> None:
    get_runtime_router.cache_clear()


def parse_runtime_protocol(value: str | None) -> RuntimeProtocol | None:
    if not value:
        return None
    normalized = value.strip().lower()
    for protocol in RuntimeProtocol:
        if protocol.value == normalized:
            return protocol
    return None
