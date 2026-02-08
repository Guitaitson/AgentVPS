"""
Security Module - Allowlist de Segurança.

Este módulo fornece funcionalidades para:
- Allowlist de comandos e operações permitidas
- Verificação de permissões
- Controle de acesso a recursos
"""

from .allowlist import (
    PermissionLevel,
    ResourceType,
    AllowlistRule,
    AllowlistResult,
    SecurityAllowlist,
    create_default_allowlist,
    load_allowlist_from_file,
    save_allowlist_to_file,
)

__all__ = [
    "PermissionLevel",
    "ResourceType",
    "AllowlistRule",
    "AllowlistResult",
    "SecurityAllowlist",
    "create_default_allowlist",
    "load_allowlist_from_file",
    "save_allowlist_to_file",
]
