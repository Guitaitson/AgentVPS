"""
Unified runtime adapter layer for orchestration.
"""

from .router_factory import (
    get_runtime_router,
    parse_runtime_protocol,
    reset_runtime_router_for_tests,
)
from .runtime_adapters import (
    A2AAdapter,
    ACPAdapter,
    AgentRuntimeAdapter,
    DeepAgentsAdapter,
    LocalSkillsAdapter,
    MCPAdapter,
    OpenClawAdapter,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
    RuntimeProtocol,
    RuntimeRouter,
)
from .runtime_control import RuntimeControl, RuntimeState

__all__ = [
    "A2AAdapter",
    "ACPAdapter",
    "AgentRuntimeAdapter",
    "DeepAgentsAdapter",
    "LocalSkillsAdapter",
    "MCPAdapter",
    "OpenClawAdapter",
    "RuntimeExecutionRequest",
    "RuntimeExecutionResult",
    "RuntimeProtocol",
    "RuntimeRouter",
    "RuntimeControl",
    "RuntimeState",
    "get_runtime_router",
    "parse_runtime_protocol",
    "reset_runtime_router_for_tests",
]
