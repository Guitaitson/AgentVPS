"""
Runtime availability controls (list/enable/disable) with Redis fallback.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import redis

from core.config import get_settings

_OVERRIDES_REDIS_KEY = "orchestration:runtime_overrides"


@dataclass(slots=True)
class RuntimeState:
    protocol: str
    enabled: bool
    default_enabled: bool
    source: str
    endpoint: str | None = None


class RuntimeControl:
    """
    Manages runtime availability overrides for router construction.

    Override precedence:
    1. Redis/persisted override (enable/disable)
    2. Settings default (ORCH_ENABLE_*)
    """

    def __init__(self):
        self._settings = get_settings().orchestration
        self._redis = self._init_redis_client()
        self._local_overrides: dict[str, bool] = {}

    @staticmethod
    def _normalize_protocol(protocol: str) -> str:
        return protocol.strip().lower().replace("-", "_")

    @staticmethod
    def _endpoint_map(settings) -> dict[str, str | None]:
        return {
            "mcp": settings.mcp_base_url,
            "a2a": settings.a2a_endpoint,
            "acp": settings.acp_endpoint,
            "deepagents": settings.deepagents_endpoint,
            "openclaw": settings.openclaw_endpoint,
            "local_skills": None,
        }

    def _default_enabled_map(self) -> dict[str, bool]:
        return {
            "local_skills": True,
            "mcp": bool(self._settings.enable_mcp),
            "a2a": bool(self._settings.enable_a2a),
            "acp": bool(self._settings.enable_acp),
            "deepagents": bool(self._settings.enable_deepagents),
            "openclaw": bool(self._settings.enable_openclaw),
        }

    def _init_redis_client(self):
        try:
            client = redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True,
            )
            client.ping()
            return client
        except Exception:
            return None

    def _load_overrides(self) -> dict[str, bool]:
        if self._redis:
            try:
                raw = self._redis.get(_OVERRIDES_REDIS_KEY)
                if raw:
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        return {self._normalize_protocol(k): bool(v) for k, v in payload.items()}
            except Exception:
                pass
        return dict(self._local_overrides)

    def _save_overrides(self, overrides: dict[str, bool]) -> None:
        if self._redis:
            try:
                self._redis.set(_OVERRIDES_REDIS_KEY, json.dumps(overrides, ensure_ascii=True))
                return
            except Exception:
                pass
        self._local_overrides = dict(overrides)

    def list_states(self) -> list[RuntimeState]:
        defaults = self._default_enabled_map()
        overrides = self._load_overrides()
        endpoints = self._endpoint_map(self._settings)

        states: list[RuntimeState] = []
        for protocol in ("local_skills", "mcp", "a2a", "acp", "deepagents", "openclaw"):
            default_enabled = defaults.get(protocol, False)
            if protocol in overrides:
                enabled = bool(overrides[protocol])
                source = "override"
            else:
                enabled = default_enabled
                source = "default"

            states.append(
                RuntimeState(
                    protocol=protocol,
                    enabled=enabled,
                    default_enabled=default_enabled,
                    source=source,
                    endpoint=endpoints.get(protocol),
                )
            )
        return states

    def is_enabled(self, protocol: str, *, fallback_default: bool = False) -> bool:
        protocol = self._normalize_protocol(protocol)
        defaults = self._default_enabled_map()
        overrides = self._load_overrides()
        if protocol in overrides:
            return bool(overrides[protocol])
        if protocol in defaults:
            return bool(defaults[protocol])
        return bool(fallback_default)

    def set_enabled(self, protocol: str, enabled: bool) -> dict[str, Any]:
        protocol = self._normalize_protocol(protocol)
        if protocol == "local_skills":
            return {
                "success": False,
                "error": "local_skills cannot be disabled",
                "protocol": protocol,
            }

        known = {"mcp", "a2a", "acp", "deepagents", "openclaw"}
        if protocol not in known:
            return {"success": False, "error": "unknown protocol", "protocol": protocol}

        overrides = self._load_overrides()
        overrides[protocol] = bool(enabled)
        self._save_overrides(overrides)

        return {"success": True, "protocol": protocol, "enabled": bool(enabled)}

    def clear_override(self, protocol: str) -> dict[str, Any]:
        protocol = self._normalize_protocol(protocol)
        overrides = self._load_overrides()
        if protocol in overrides:
            overrides.pop(protocol, None)
            self._save_overrides(overrides)
            return {"success": True, "protocol": protocol, "cleared": True}
        return {"success": True, "protocol": protocol, "cleared": False}
