"""Integration helpers for external runtimes and MCP servers."""

from .external_mcp import RemoteMCPClient, RemoteMCPError, extract_cnpjs, render_result_block
from .fleetintel_router import (
    detect_external_skill,
    extract_company_count_query,
    should_delegate_specialist_to_codex,
)

__all__ = [
    "RemoteMCPClient",
    "RemoteMCPError",
    "detect_external_skill",
    "extract_company_count_query",
    "should_delegate_specialist_to_codex",
    "extract_cnpjs",
    "render_result_block",
]
