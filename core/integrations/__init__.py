"""Integration helpers for external runtimes and MCP servers."""

from .external_mcp import RemoteMCPClient, extract_cnpjs, render_result_block
from .fleetintel_router import detect_external_skill

__all__ = [
    "RemoteMCPClient",
    "detect_external_skill",
    "extract_cnpjs",
    "render_result_block",
]
