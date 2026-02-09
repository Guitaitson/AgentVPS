# VPS-Agent Versioning
# Used for self-improvement and releases

__version__ = "2.0.0"
__version_info__ = (2, 0, 0)
__name__ = "vps-agent"
__author__ = "VPS-Agent Autonomous System"

# Changelog URL
CHANGELOG_URL = "https://github.com/SEU_USUARIO/vps-agent/blob/main/CHANGELOG.md"

# Release URL
RELEASES_URL = "https://github.com/SEU_USUARIO/vps-agent/releases"

# Update check URL
UPDATE_CHECK_URL = "https://api.github.com/repos/SEU_USUARIO/vps-agent/releases/latest"

# Supported models for CLI
SUPPORTED_MODELS = {
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
    "openrouter": ["minimax/minimax-m2.1", "anthropic/claude-3.5-sonnet", "openai/gpt-4o"],
    "kilocode": ["default"],
}

# Installation types
INSTALL_TYPES = {
    "docker": "Docker Compose",
    "manual": "Manual Installation",
    "kubernetes": "Kubernetes",
}

# Resource limits
RESOURCE_LIMITS = {
    "max_ram_mb": 2458,
    "max_containers": 10,
    "reserved_core_mb": 750,
    "max_tools_simultaneous": 2,
}
