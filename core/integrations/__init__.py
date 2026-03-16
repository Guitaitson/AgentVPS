"""Integration helpers for external runtimes and MCP servers."""

from .external_mcp import RemoteMCPClient, RemoteMCPError, extract_cnpjs, render_result_block
from .fleetintel_router import (
    detect_external_skill,
    extract_company_count_query,
    should_delegate_specialist_to_codex,
)
from .specialist_health import (
    assess_specialist_health,
    emit_health_failure_progress,
    format_specialist_health_failure,
)

__all__ = [
    "RemoteMCPClient",
    "RemoteMCPError",
    "detect_external_skill",
    "extract_company_count_query",
    "should_delegate_specialist_to_codex",
    "assess_specialist_health",
    "emit_health_failure_progress",
    "format_specialist_health_failure",
    "extract_cnpjs",
    "render_result_block",
]
