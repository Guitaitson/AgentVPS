"""
Utilities para localizar e carregar arquivo de ambiente do AgentVPS.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


def _iter_env_candidates() -> Iterable[str]:
    override = os.getenv("AGENTVPS_ENV_FILE")
    if override:
        yield override

    yield "/opt/vps-agent/.env"
    yield "/opt/vps-agent/configs/.env"
    yield "/opt/vps-agent/core/.env"  # legacy
    yield ".env"
    yield "configs/.env"


ENV_FILE_CANDIDATES = tuple(dict.fromkeys(_iter_env_candidates()))


def resolve_env_file() -> str | None:
    """Retorna o primeiro arquivo .env existente."""
    for candidate in ENV_FILE_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def load_project_env() -> str | None:
    """Carrega variáveis do primeiro arquivo .env encontrado."""
    env_file = resolve_env_file()
    if env_file:
        load_dotenv(env_file, override=False)
        return env_file

    load_dotenv(override=False)
    return None
