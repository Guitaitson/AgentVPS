"""
In-process audit trail for memory actions.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from .policy import MemoryScope, MemoryType

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class MemoryAuditEvent:
    """Represents one auditable memory operation."""

    action: str
    memory_type: MemoryType
    user_id: str
    key: str
    scope: MemoryScope
    project_id: str | None = None
    redacted: bool = False
    outcome: str = "success"
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MemoryAuditTrail:
    """Small in-memory audit buffer for recent memory operations."""

    def __init__(self, max_events: int = 2000):
        self._events: deque[MemoryAuditEvent] = deque(maxlen=max_events)

    def record(self, event: MemoryAuditEvent) -> None:
        self._events.append(event)
        logger.info(
            "memory_audit",
            action=event.action,
            memory_type=event.memory_type.value,
            user_id=event.user_id,
            scope=event.scope.value,
            key=event.key,
            outcome=event.outcome,
        )

    def recent(self, limit: int = 50, user_id: str | None = None) -> list[MemoryAuditEvent]:
        if user_id is None:
            events = list(self._events)
        else:
            events = [event for event in self._events if event.user_id == user_id]
        return events[-limit:]
