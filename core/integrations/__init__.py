"""Integration helpers for external runtimes and MCP servers."""

from .consumer_sync import (
    ConsumerSyncError,
    ConsumerSyncUnavailableError,
    build_specialist_mcp_client,
    get_consumer_sync_manager,
    reset_consumer_sync_manager_for_tests,
    warmup_consumer_sync,
)
from .external_mcp import (
    RemoteMCPClient,
    RemoteMCPConnection,
    RemoteMCPError,
    extract_cnpjs,
    render_result_block,
)
from .fleetintel_router import (
    detect_external_skill,
    extract_company_count_query,
    select_codex_execution_mode,
    should_delegate_specialist_to_codex,
    wants_raw_specialist_output,
)
from .specialist_health import (
    assess_specialist_health,
    emit_health_failure_progress,
    format_specialist_health_failure,
)

__all__ = [
    "RemoteMCPClient",
    "RemoteMCPConnection",
    "RemoteMCPError",
    "ConsumerSyncError",
    "ConsumerSyncUnavailableError",
    "build_specialist_mcp_client",
    "get_consumer_sync_manager",
    "reset_consumer_sync_manager_for_tests",
    "warmup_consumer_sync",
    "detect_external_skill",
    "extract_company_count_query",
    "select_codex_execution_mode",
    "should_delegate_specialist_to_codex",
    "wants_raw_specialist_output",
    "assess_specialist_health",
    "emit_health_failure_progress",
    "format_specialist_health_failure",
    "extract_cnpjs",
    "render_result_block",
]
