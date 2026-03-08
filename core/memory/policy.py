"""
Memory policy primitives for typed memory, retention, and redaction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class MemoryType(str, Enum):
    """Supported first-class memory types."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PROFILE = "profile"
    GOALS = "goals"


class MemoryScope(str, Enum):
    """Scope used when storing/retrieving memory entries."""

    USER = "user"
    PROJECT = "project"
    GLOBAL = "global"


def _default_ttl_seconds() -> dict[MemoryType, int | None]:
    return {
        MemoryType.EPISODIC: 30 * 24 * 60 * 60,
        MemoryType.SEMANTIC: 180 * 24 * 60 * 60,
        MemoryType.PROCEDURAL: None,
        MemoryType.PROFILE: None,
        MemoryType.GOALS: None,
    }


def _default_retention_limits() -> dict[MemoryType, int]:
    return {
        MemoryType.EPISODIC: 2000,
        MemoryType.SEMANTIC: 4000,
        MemoryType.PROCEDURAL: 500,
        MemoryType.PROFILE: 250,
        MemoryType.GOALS: 250,
    }


def _default_scope_by_type() -> dict[MemoryType, MemoryScope]:
    return {
        MemoryType.EPISODIC: MemoryScope.USER,
        MemoryType.SEMANTIC: MemoryScope.USER,
        MemoryType.PROCEDURAL: MemoryScope.PROJECT,
        MemoryType.PROFILE: MemoryScope.USER,
        MemoryType.GOALS: MemoryScope.PROJECT,
    }


_DEFAULT_SENSITIVE_KEYS = (
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "authorization",
    "cookie",
    "session",
    "private_key",
)


def _default_sensitive_patterns() -> tuple[re.Pattern[str], ...]:
    return (
        re.compile(r"(?i)\bbearer\s+[a-z0-9\-\._~\+\/]+=*"),
        re.compile(r"(?i)\bsk-[a-z0-9]{16,}\b"),
        re.compile(r"(?i)\bghp_[a-z0-9]{20,}\b"),
        re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
    )


@dataclass(slots=True)
class MemoryPolicy:
    """Retention and redaction defaults for all memory operations."""

    ttl_seconds: dict[MemoryType, int | None] = field(default_factory=_default_ttl_seconds)
    retention_limits: dict[MemoryType, int] = field(default_factory=_default_retention_limits)
    default_scope_by_type: dict[MemoryType, MemoryScope] = field(
        default_factory=_default_scope_by_type
    )
    sensitive_keys: tuple[str, ...] = _DEFAULT_SENSITIVE_KEYS
    sensitive_patterns: tuple[re.Pattern[str], ...] = field(
        default_factory=_default_sensitive_patterns
    )
    redaction_token: str = "[REDACTED]"

    def ttl_for(self, memory_type: MemoryType) -> int | None:
        return self.ttl_seconds.get(memory_type)

    def retention_for(self, memory_type: MemoryType) -> int:
        return self.retention_limits.get(memory_type, 500)

    def scope_for(self, memory_type: MemoryType) -> MemoryScope:
        return self.default_scope_by_type.get(memory_type, MemoryScope.USER)

    def redact_value(self, value: Any) -> Any:
        """Redact values recursively for known secret patterns."""
        if isinstance(value, Mapping):
            output: dict[str, Any] = {}
            for key, item in value.items():
                if self._is_sensitive_key(key):
                    output[str(key)] = self.redaction_token
                else:
                    output[str(key)] = self.redact_value(item)
            return output

        if isinstance(value, list):
            return [self.redact_value(item) for item in value]

        if isinstance(value, tuple):
            return tuple(self.redact_value(item) for item in value)

        if isinstance(value, str):
            redacted = value
            for pattern in self.sensitive_patterns:
                redacted = pattern.sub(self.redaction_token, redacted)
            return redacted

        return value

    def sanitize_context(
        self,
        context: Mapping[str, Any] | None,
        allowed_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        """Keep only allowed keys and redact sensitive values."""
        if not context:
            return {}

        if allowed_keys is None:
            filtered = dict(context)
        else:
            filtered = {key: context[key] for key in allowed_keys if key in context}

        return self.redact_value(filtered)

    def _is_sensitive_key(self, key: str) -> bool:
        key_lc = key.strip().lower()
        return any(token in key_lc for token in self.sensitive_keys)
