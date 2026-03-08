"""
Memory facade used by the agent graph.

Backwards compatible API:
- get_user_facts / save_fact
- get_conversation_history / save_conversation
- get_system_state / set_system_state

New API for Phase 1:
- save_typed_memory / get_typed_memory / cleanup_expired_typed_memory
- prepare_for_delegation (least-privilege + redaction)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg2
import redis
import structlog
from psycopg2.extras import Json, RealDictCursor

from core.env import load_project_env
from core.memory import MemoryAuditEvent, MemoryAuditTrail, MemoryPolicy, MemoryScope, MemoryType

load_project_env()
logger = structlog.get_logger(__name__)

_GLOBAL_MEMORY_USER = "__global__"


class AgentMemory:
    """Persistent memory manager with typed memory policy and local fallback."""

    def __init__(self, policy: MemoryPolicy | None = None):
        self.policy = policy or MemoryPolicy()
        self.audit = MemoryAuditTrail()

        self._db_config = {
            "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "port": int(os.getenv("POSTGRES_PORT", 5432)),
            "dbname": os.getenv("POSTGRES_DB", "vps_agent"),
            "user": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD"),
        }

        self._redis = self._init_redis_client()
        self._semantic_enabled = os.getenv(
            "QDRANT_SEMANTIC_ENABLED", "true"
        ).strip().lower() not in {"0", "false", "no"}
        self._semantic_collection = os.getenv(
            "QDRANT_SEMANTIC_COLLECTION",
            "agent_semantic_memory",
        )
        self._semantic_vector_size = max(
            8,
            int(os.getenv("QDRANT_SEMANTIC_VECTOR_SIZE", "64")),
        )
        self._semantic_recall_default_limit = max(
            1,
            int(os.getenv("QDRANT_SEMANTIC_RECALL_LIMIT", "3")),
        )
        self._qdrant = self._init_qdrant_client() if self._semantic_enabled else None

        # Local fallback when PostgreSQL/Redis are unavailable.
        self._local_facts: dict[str, dict[str, Any]] = {}
        self._local_history: dict[str, list[dict[str, Any]]] = {}
        self._local_system_state: dict[str, dict[str, Any]] = {}
        self._local_typed: dict[str, dict[MemoryType, dict[str, dict[str, Any]]]] = {}
        self._local_audit_buffer: list[dict[str, Any]] = []

    def _init_qdrant_client(self):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as qmodels
        except Exception as exc:
            logger.warning("memory.qdrant_client_unavailable", error=str(exc))
            return None

        try:
            client = QdrantClient(
                url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"),
                api_key=os.getenv("QDRANT_API_KEY") or None,
                timeout=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "5")),
            )
            if not self._qdrant_collection_exists(client):
                client.create_collection(
                    collection_name=self._semantic_collection,
                    vectors_config=qmodels.VectorParams(
                        size=self._semantic_vector_size,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
            return client
        except Exception as exc:
            logger.warning("memory.qdrant_unavailable", error=str(exc))
            return None

    def _qdrant_collection_exists(self, client) -> bool:
        try:
            return bool(client.collection_exists(self._semantic_collection))
        except Exception:
            try:
                collections = client.get_collections()
                return any(
                    getattr(collection, "name", None) == self._semantic_collection
                    for collection in collections.collections
                )
            except Exception:
                return False

    def _semantic_point_id(self, user_id: str, key: str) -> int:
        digest = hashlib.sha1(f"{user_id}:{key}".encode("utf-8")).digest()
        return int.from_bytes(digest[:8], byteorder="big", signed=False) & ((1 << 63) - 1)

    def _semantic_text_from_value(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for candidate in ("text", "content", "summary", "message"):
                raw = value.get(candidate)
                if isinstance(raw, str) and raw.strip():
                    return raw
            return json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
        return str(value)

    def _embed_text(self, text: str) -> list[float]:
        normalized = (text or "").strip().lower()
        vector = [0.0] * self._semantic_vector_size
        if not normalized:
            vector[0] = 1.0
            return vector

        tokens = re.findall(r"[a-z0-9_]{2,}", normalized)
        if not tokens:
            tokens = [normalized]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = (
                int.from_bytes(digest[:4], byteorder="big", signed=False)
                % self._semantic_vector_size
            )
            sign = -1.0 if (digest[4] & 1) else 1.0
            vector[index] += sign

        norm = math.sqrt(sum(item * item for item in vector))
        if norm <= 0:
            vector[0] = 1.0
            return vector
        return [item / norm for item in vector]

    def _upsert_semantic_memory(
        self,
        *,
        user_id: str,
        key: str,
        value: Any,
        project_id: str | None,
    ) -> None:
        if not self._qdrant:
            return
        try:
            from qdrant_client.http import models as qmodels

            text = self._semantic_text_from_value(value)
            self._qdrant.upsert(
                collection_name=self._semantic_collection,
                points=[
                    qmodels.PointStruct(
                        id=self._semantic_point_id(user_id, key),
                        vector=self._embed_text(text),
                        payload={
                            "user_id": user_id,
                            "key": key,
                            "text": text,
                            "value": value,
                            "project_id": project_id,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                ],
                wait=False,
            )
        except Exception as exc:
            logger.warning(
                "memory.semantic_upsert_failed",
                error=str(exc),
                user_id=user_id,
                key=key,
            )

    def _delete_semantic_entries(self, *, user_id: str, keys: list[str]) -> None:
        if not self._qdrant or not keys:
            return
        try:
            from qdrant_client.http import models as qmodels

            point_ids = [self._semantic_point_id(user_id, key) for key in keys]
            self._qdrant.delete(
                collection_name=self._semantic_collection,
                points_selector=qmodels.PointIdsList(points=point_ids),
                wait=False,
            )
        except Exception as exc:
            logger.warning("memory.semantic_delete_failed", error=str(exc), user_id=user_id)

    @staticmethod
    def _text_overlap_score(query: str, candidate: str) -> float:
        query_tokens = set(re.findall(r"[a-z0-9_]{2,}", query.lower()))
        if not query_tokens:
            return 0.0
        candidate_tokens = set(re.findall(r"[a-z0-9_]{2,}", candidate.lower()))
        if not candidate_tokens:
            return 0.0
        overlap = query_tokens.intersection(candidate_tokens)
        return len(overlap) / len(query_tokens)

    def _init_redis_client(self):
        try:
            client = redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True,
            )
            client.ping()
            return client
        except Exception as exc:
            logger.warning("memory.redis_unavailable", error=str(exc))
            return None

    def _get_conn(self):
        return psycopg2.connect(**self._db_config)

    def _cache_get_json(self, key: str):
        if not self._redis:
            return None
        raw = self._redis.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _cache_set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        if not self._redis:
            return
        self._redis.setex(key, ttl_seconds, json.dumps(value))

    def _cache_delete(self, key: str) -> None:
        if self._redis:
            self._redis.delete(key)

    def _cache_delete_pattern(self, pattern: str) -> None:
        if not self._redis:
            return
        for cache_key in self._redis.scan_iter(pattern):
            self._redis.delete(cache_key)

    def _resolve_user_for_scope(self, user_id: str | None, scope: MemoryScope) -> str:
        if scope == MemoryScope.GLOBAL:
            return _GLOBAL_MEMORY_USER
        return user_id or _GLOBAL_MEMORY_USER

    @staticmethod
    def _normalize_memory_type(memory_type: MemoryType | str) -> MemoryType:
        if isinstance(memory_type, MemoryType):
            return memory_type
        return MemoryType(memory_type.lower().strip())

    @staticmethod
    def _to_iso_or_none(value: datetime | None) -> str | None:
        if not value:
            return None
        return value.isoformat()

    @staticmethod
    def _is_expired(expires_at: str | None) -> bool:
        if not expires_at:
            return False
        try:
            return datetime.fromisoformat(expires_at) < datetime.now(timezone.utc)
        except ValueError:
            return False

    @staticmethod
    def _was_redacted(original: Any, redacted: Any) -> bool:
        try:
            return json.dumps(original, sort_keys=True, default=str) != json.dumps(
                redacted,
                sort_keys=True,
                default=str,
            )
        except Exception:
            return original != redacted

    def _record_audit(
        self,
        action: str,
        memory_type: MemoryType,
        user_id: str,
        key: str,
        scope: MemoryScope,
        project_id: str | None,
        redacted: bool,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        event = MemoryAuditEvent(
            action=action,
            memory_type=memory_type,
            user_id=user_id,
            key=key,
            scope=scope,
            project_id=project_id,
            redacted=redacted,
            outcome=outcome,
            details=details or {},
        )
        self.audit.record(event)
        self._persist_audit_event(event)

    def _persist_audit_event(self, event: MemoryAuditEvent) -> None:
        payload = {
            "timestamp": event.timestamp,
            "action": event.action,
            "memory_type": event.memory_type.value,
            "user_id": event.user_id,
            "key": event.key,
            "scope": event.scope.value,
            "project_id": event.project_id,
            "redacted": event.redacted,
            "outcome": event.outcome,
            "details": event.details,
        }

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO memory_audit_log (
                    event_ts, action, memory_type, user_id, memory_key,
                    scope, project_id, redacted, outcome, details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event.timestamp,
                    event.action,
                    event.memory_type.value,
                    event.user_id,
                    event.key,
                    event.scope.value,
                    event.project_id,
                    event.redacted,
                    event.outcome,
                    Json(event.details),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("memory.audit_persist_fallback_local", error=str(exc))
            self._local_audit_buffer.append(payload)

    def _enforce_retention_limit(self, *, target_user: str, memory_type: MemoryType) -> int:
        limit = self.policy.retention_for(memory_type)
        deleted = 0
        deleted_keys: list[str] = []

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, key
                FROM agent_memory
                WHERE user_id = %s AND memory_type = %s
                ORDER BY updated_at DESC
                OFFSET %s
                """,
                (target_user, memory_type.value, limit),
            )
            rows = cur.fetchall()
            to_delete = [row["id"] for row in rows]
            deleted_keys = [row.get("key") for row in rows if row.get("key")]
            if to_delete:
                cur.execute("DELETE FROM agent_memory WHERE id = ANY(%s)", (to_delete,))
                conn.commit()
                deleted = len(to_delete)
            conn.close()
        except Exception:
            per_type = self._local_typed.get(target_user, {}).get(memory_type, {})
            if len(per_type) > limit:
                ordered = sorted(
                    per_type.items(),
                    key=lambda item: item[1].get("updated_at", ""),
                    reverse=True,
                )
                keep = dict(ordered[:limit])
                deleted = max(0, len(per_type) - len(keep))
                deleted_keys = [entry_key for entry_key in per_type if entry_key not in keep]
                self._local_typed.setdefault(target_user, {})[memory_type] = keep

        if deleted:
            self._cache_delete_pattern(f"typed_memory:{target_user}:{memory_type.value}:*")
            if memory_type == MemoryType.SEMANTIC and deleted_keys:
                self._delete_semantic_entries(user_id=target_user, keys=deleted_keys)
            logger.info(
                "memory.retention_pruned",
                user_id=target_user,
                memory_type=memory_type.value,
                deleted=deleted,
                retention_limit=limit,
            )
        return deleted

    def list_memory_audit(
        self, user_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return memory audit events from PostgreSQL or local fallback."""
        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            if user_id:
                cur.execute(
                    """
                    SELECT event_ts, action, memory_type, user_id, memory_key,
                           scope, project_id, redacted, outcome, details
                    FROM memory_audit_log
                    WHERE user_id = %s
                    ORDER BY event_ts DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT event_ts, action, memory_type, user_id, memory_key,
                           scope, project_id, redacted, outcome, details
                    FROM memory_audit_log
                    ORDER BY event_ts DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
            conn.close()
            return [
                {
                    "timestamp": self._to_iso_or_none(row.get("event_ts")),
                    "action": row.get("action"),
                    "memory_type": row.get("memory_type"),
                    "user_id": row.get("user_id"),
                    "key": row.get("memory_key"),
                    "scope": row.get("scope"),
                    "project_id": row.get("project_id"),
                    "redacted": bool(row.get("redacted")),
                    "outcome": row.get("outcome"),
                    "details": row.get("details") or {},
                }
                for row in rows
            ]
        except Exception:
            data = self._local_audit_buffer
            if user_id:
                data = [item for item in data if item.get("user_id") == user_id]
            return data[-limit:]

    def cleanup_old_audit_events(self, older_than_days: int = 90) -> int:
        """Cleanup old audit events from persistent and local buffers."""
        deleted = 0
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM memory_audit_log WHERE event_ts < NOW() - (%s * INTERVAL '1 day')",
                (older_than_days,),
            )
            deleted = cur.rowcount
            conn.commit()
            conn.close()
        except Exception:
            threshold = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            keep = []
            for event in self._local_audit_buffer:
                try:
                    ts = datetime.fromisoformat(event.get("timestamp", ""))
                except Exception:
                    ts = datetime.now(timezone.utc)
                if ts >= threshold:
                    keep.append(event)
            deleted = max(0, len(self._local_audit_buffer) - len(keep))
            self._local_audit_buffer = keep
        return deleted

    # --- New typed memory API (Phase 1 foundation) ---

    def save_typed_memory(
        self,
        *,
        user_id: str,
        key: str,
        value: Any,
        memory_type: MemoryType | str,
        scope: MemoryScope | str | None = None,
        project_id: str | None = None,
        confidence: float = 1.0,
        ttl_seconds: int | None = None,
        source: str = "agent",
    ) -> dict[str, Any]:
        typed = self._normalize_memory_type(memory_type)
        resolved_scope = scope or self.policy.scope_for(typed)
        if isinstance(resolved_scope, str):
            resolved_scope = MemoryScope(resolved_scope)

        redacted_value = self.policy.redact_value(value)
        effective_ttl = self.policy.ttl_for(typed) if ttl_seconds is None else ttl_seconds
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=effective_ttl)
            if effective_ttl is not None
            else None
        )

        payload = {
            "value": redacted_value,
            "scope": resolved_scope.value,
            "project_id": project_id,
            "expires_at": self._to_iso_or_none(expires_at),
            "source": source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        target_user = self._resolve_user_for_scope(user_id, resolved_scope)
        outcome = "success"

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO agent_memory (user_id, memory_type, key, value, confidence)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, memory_type, key)
                DO UPDATE SET value = EXCLUDED.value, confidence = EXCLUDED.confidence
                """,
                (target_user, typed.value, key, Json(payload), confidence),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            outcome = "fallback_local"
            logger.warning(
                "memory.save_typed_fallback_local",
                error=str(exc),
                user_id=user_id,
                memory_type=typed.value,
                key=key,
            )
            per_user = self._local_typed.setdefault(target_user, {})
            per_type = per_user.setdefault(typed, {})
            per_type[key] = payload

        self._cache_delete_pattern(f"typed_memory:{target_user}:{typed.value}:*")
        self._enforce_retention_limit(target_user=target_user, memory_type=typed)
        if typed == MemoryType.SEMANTIC:
            self._upsert_semantic_memory(
                user_id=target_user,
                key=key,
                value=redacted_value,
                project_id=project_id,
            )
        self._record_audit(
            action="save",
            memory_type=typed,
            user_id=user_id,
            key=key,
            scope=resolved_scope,
            project_id=project_id,
            redacted=self._was_redacted(value, redacted_value),
            outcome=outcome,
            details={"ttl_seconds": effective_ttl, "source": source},
        )

        return payload

    def get_typed_memory(
        self,
        *,
        user_id: str,
        memory_type: MemoryType | str,
        limit: int = 20,
        scope: MemoryScope | str | None = None,
        project_id: str | None = None,
        include_expired: bool = False,
    ) -> list[dict[str, Any]]:
        typed = self._normalize_memory_type(memory_type)
        resolved_scope: MemoryScope | None
        if scope is None:
            resolved_scope = None
        elif isinstance(scope, MemoryScope):
            resolved_scope = scope
        else:
            resolved_scope = MemoryScope(scope)

        target_user = self._resolve_user_for_scope(user_id, resolved_scope or MemoryScope.USER)
        cache_scope = resolved_scope.value if resolved_scope else "any"
        cache_key = f"typed_memory:{target_user}:{typed.value}:{cache_scope}:{project_id}:{limit}"
        cached = self._cache_get_json(cache_key)
        if cached is not None:
            return cached

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT key, value, confidence, created_at, updated_at
                FROM agent_memory
                WHERE user_id = %s AND memory_type = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (target_user, typed.value, limit),
            )
            rows = cur.fetchall()
            conn.close()

            output = []
            for row in rows:
                entry = self._typed_row_to_entry(row)
                if resolved_scope and entry["scope"] != resolved_scope.value:
                    continue
                if project_id and entry.get("project_id") != project_id:
                    continue
                if not include_expired and self._is_expired(entry.get("expires_at")):
                    continue
                output.append(entry)

        except Exception as exc:
            logger.warning(
                "memory.get_typed_fallback_local",
                error=str(exc),
                user_id=user_id,
                memory_type=typed.value,
            )
            output = []
            per_type = self._local_typed.get(target_user, {}).get(typed, {})
            for item_key, payload in per_type.items():
                entry = {
                    "key": item_key,
                    "value": payload.get("value"),
                    "scope": payload.get("scope", MemoryScope.USER.value),
                    "project_id": payload.get("project_id"),
                    "expires_at": payload.get("expires_at"),
                    "updated_at": payload.get("updated_at"),
                    "confidence": 1.0,
                }
                if resolved_scope and entry["scope"] != resolved_scope.value:
                    continue
                if project_id and entry.get("project_id") != project_id:
                    continue
                if not include_expired and self._is_expired(entry.get("expires_at")):
                    continue
                output.append(entry)
            output = output[:limit]

        self._cache_set_json(cache_key, output, ttl_seconds=60)
        return output

    def cleanup_expired_typed_memory(self) -> int:
        """Remove expired typed memory entries from persistent/local storage."""
        deleted = 0
        target_types = [
            mem_type for mem_type in MemoryType if self.policy.ttl_for(mem_type) is not None
        ]

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, user_id, memory_type, key, value
                FROM agent_memory
                WHERE memory_type = ANY(%s)
                """,
                ([mem_type.value for mem_type in target_types],),
            )
            rows = cur.fetchall()
            to_delete_ids = []
            to_delete_semantic: dict[str, list[str]] = {}
            for row in rows:
                payload = row.get("value") or {}
                expires_at = payload.get("expires_at") if isinstance(payload, dict) else None
                if self._is_expired(expires_at):
                    to_delete_ids.append(row["id"])
                    if row.get("memory_type") == MemoryType.SEMANTIC.value:
                        to_delete_semantic.setdefault(row.get("user_id"), []).append(row.get("key"))

            if to_delete_ids:
                cur.execute("DELETE FROM agent_memory WHERE id = ANY(%s)", (to_delete_ids,))
                conn.commit()
                deleted += len(to_delete_ids)
                for sem_user_id, sem_keys in to_delete_semantic.items():
                    self._delete_semantic_entries(
                        user_id=sem_user_id,
                        keys=[key for key in sem_keys if key],
                    )
            conn.close()
        except Exception as exc:
            logger.warning("memory.cleanup_expired_db_failed", error=str(exc))

        for _, per_user in self._local_typed.items():
            for mem_type in target_types:
                entries = per_user.get(mem_type, {})
                for entry_key in list(entries.keys()):
                    if self._is_expired(entries[entry_key].get("expires_at")):
                        del entries[entry_key]
                        deleted += 1

        if deleted:
            self._cache_delete_pattern("typed_memory:*")

        return deleted

    def prepare_for_delegation(
        self,
        context: dict[str, Any] | None,
        allowed_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        """Apply least privilege and redaction before external delegation."""
        return self.policy.sanitize_context(context, allowed_keys=allowed_keys)

    def search_semantic_memory(
        self,
        *,
        user_id: str,
        query_text: str,
        project_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        effective_limit = (
            self._semantic_recall_default_limit if limit is None else max(1, int(limit))
        )
        if not query_text.strip():
            return []

        if self._qdrant:
            try:
                from qdrant_client.http import models as qmodels

                conditions = [
                    qmodels.FieldCondition(
                        key="user_id",
                        match=qmodels.MatchValue(value=user_id),
                    )
                ]
                if project_id:
                    conditions.append(
                        qmodels.FieldCondition(
                            key="project_id",
                            match=qmodels.MatchValue(value=project_id),
                        )
                    )

                points = self._qdrant.search(
                    collection_name=self._semantic_collection,
                    query_vector=self._embed_text(query_text),
                    query_filter=qmodels.Filter(must=conditions),
                    limit=effective_limit,
                    with_payload=True,
                )
                output = []
                for point in points:
                    payload = point.payload or {}
                    output.append(
                        {
                            "key": payload.get("key"),
                            "value": payload.get("value"),
                            "text": payload.get("text"),
                            "project_id": payload.get("project_id"),
                            "score": float(getattr(point, "score", 0.0)),
                        }
                    )
                if output:
                    return output
            except Exception as exc:
                logger.warning(
                    "memory.semantic_search_qdrant_failed", error=str(exc), user_id=user_id
                )

        entries = self.get_typed_memory(
            user_id=user_id,
            memory_type=MemoryType.SEMANTIC,
            limit=max(effective_limit * 20, 50),
            project_id=project_id,
        )
        ranked = []
        for entry in entries:
            text = self._semantic_text_from_value(entry.get("value"))
            score = self._text_overlap_score(query_text, text)
            if score <= 0:
                continue
            ranked.append(
                {
                    "key": entry.get("key"),
                    "value": entry.get("value"),
                    "text": text,
                    "project_id": entry.get("project_id"),
                    "score": score,
                }
            )
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:effective_limit]

    def _typed_row_to_entry(self, row: dict[str, Any]) -> dict[str, Any]:
        raw_value = row.get("value")
        if isinstance(raw_value, dict) and "value" in raw_value:
            payload = raw_value
            value = payload.get("value")
            scope = payload.get("scope", MemoryScope.USER.value)
            project_id = payload.get("project_id")
            expires_at = payload.get("expires_at")
        else:
            value = raw_value
            scope = MemoryScope.USER.value
            project_id = None
            expires_at = None

        return {
            "key": row.get("key"),
            "value": value,
            "scope": scope,
            "project_id": project_id,
            "expires_at": expires_at,
            "confidence": row.get("confidence", 1.0),
            "created_at": self._to_iso_or_none(row.get("created_at")),
            "updated_at": self._to_iso_or_none(row.get("updated_at")),
        }

    # --- Backwards compatible API ---

    def get_user_facts(self, user_id: str) -> dict:
        """Retrieve known user facts (legacy API)."""
        cache_key = f"user_facts:{user_id}"
        cached = self._cache_get_json(cache_key)
        if cached is not None:
            return cached

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT key, value, confidence FROM agent_memory "
                "WHERE user_id = %s AND memory_type = 'fact' "
                "ORDER BY confidence DESC",
                (user_id,),
            )
            rows = cur.fetchall()
            conn.close()
            facts = {row["key"]: row["value"] for row in rows}
        except Exception as exc:
            logger.warning("memory.get_user_facts_fallback_local", error=str(exc), user_id=user_id)
            facts = self._local_facts.get(user_id, {}).copy()

        self._cache_set_json(cache_key, facts, ttl_seconds=300)
        return facts

    def save_fact(self, user_id: str, key: str, value: dict, confidence: float = 1.0):
        """Save or update one user fact (legacy API)."""
        redacted_value = self.policy.redact_value(value)
        outcome = "success"
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO agent_memory (user_id, memory_type, key, value, confidence)
                VALUES (%s, 'fact', %s, %s, %s)
                ON CONFLICT (user_id, memory_type, key)
                DO UPDATE SET value = EXCLUDED.value, confidence = EXCLUDED.confidence
                """,
                (user_id, key, Json(redacted_value), confidence),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            outcome = "fallback_local"
            logger.warning(
                "memory.save_fact_fallback_local", error=str(exc), user_id=user_id, key=key
            )
            facts = self._local_facts.setdefault(user_id, {})
            facts[key] = redacted_value

        self._cache_delete(f"user_facts:{user_id}")
        self._record_audit(
            action="save_fact",
            memory_type=MemoryType.PROFILE,
            user_id=user_id,
            key=key,
            scope=MemoryScope.USER,
            project_id=None,
            redacted=self._was_redacted(value, redacted_value),
            outcome=outcome,
            details={"legacy_memory_type": "fact"},
        )

    def get_conversation_history(self, user_id: str, limit: int = 10) -> list:
        """Retrieve recent conversation turns (legacy API)."""
        cache_key = f"conv_history:{user_id}:{limit}"
        cached = self._cache_get_json(cache_key)
        if cached is not None:
            return cached

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT role, content, created_at as timestamp FROM conversation_log "
                "WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
            conn.close()
            history = [
                {
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": self._to_iso_or_none(row.get("timestamp")),
                }
                for row in rows
            ]
            history.reverse()
        except Exception as exc:
            logger.warning(
                "memory.get_conversation_history_fallback_local",
                error=str(exc),
                user_id=user_id,
            )
            history = self._local_history.get(user_id, [])[-limit:]

        self._cache_set_json(cache_key, history, ttl_seconds=60)
        return history

    def save_conversation(self, user_id: str, role: str, content: str):
        """Persist one conversation message (legacy API)."""
        redacted_content = self.policy.redact_value(content)
        timestamp = datetime.now(timezone.utc).isoformat()
        outcome = "success"

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO conversation_log (user_id, role, content)
                VALUES (%s, %s, %s)
                """,
                (user_id, role, redacted_content),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            outcome = "fallback_local"
            logger.warning(
                "memory.save_conversation_fallback_local",
                error=str(exc),
                user_id=user_id,
            )
            self._local_history.setdefault(user_id, []).append(
                {
                    "role": role,
                    "content": redacted_content,
                    "timestamp": timestamp,
                }
            )

        # Keep episodic mirror in typed memory for cross-runtime retrieval.
        self.save_typed_memory(
            user_id=user_id,
            key=f"turn:{timestamp}:{role}",
            value={"role": role, "content": redacted_content},
            memory_type=MemoryType.EPISODIC,
            scope=MemoryScope.USER,
            source="conversation_log",
        )
        if role == "user":
            # Semantic mirror feeds Qdrant-backed recall for delegated runtimes.
            self.save_typed_memory(
                user_id=user_id,
                key=f"semantic:{timestamp}",
                value={
                    "text": redacted_content,
                    "role": role,
                    "source": "conversation_log",
                },
                memory_type=MemoryType.SEMANTIC,
                scope=MemoryScope.USER,
                source="conversation_semantic",
            )

        self._cache_delete_pattern(f"conv_history:{user_id}:*")
        self._record_audit(
            action="save_conversation",
            memory_type=MemoryType.EPISODIC,
            user_id=user_id,
            key=f"turn:{role}",
            scope=MemoryScope.USER,
            project_id=None,
            redacted=self._was_redacted(content, redacted_content),
            outcome=outcome,
        )

    def get_system_state(self) -> dict:
        """Retrieve global system state snapshot."""
        cached = self._cache_get_json("system_state")
        if cached is not None:
            return cached

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT component, state, updated_at FROM system_state")
            rows = cur.fetchall()
            conn.close()
            state = {
                row["component"]: {
                    "state": row["state"],
                    "updated_at": self._to_iso_or_none(row.get("updated_at")),
                }
                for row in rows
            }
        except Exception as exc:
            logger.warning("memory.get_system_state_fallback_local", error=str(exc))
            state = self._local_system_state.copy()

        self._cache_set_json("system_state", state, ttl_seconds=60)
        return state

    def set_system_state(self, key: str, value: dict):
        """Update one global system state entry."""
        redacted_value = self.policy.redact_value(value)
        outcome = "success"
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO system_state (component, state)
                VALUES (%s, %s)
                ON CONFLICT (component) DO UPDATE SET state = EXCLUDED.state
                """,
                (key, Json(redacted_value)),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            outcome = "fallback_local"
            logger.warning("memory.set_system_state_fallback_local", error=str(exc), key=key)
            self._local_system_state[key] = {
                "state": redacted_value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        self._cache_delete("system_state")
        self._record_audit(
            action="set_system_state",
            memory_type=MemoryType.PROCEDURAL,
            user_id=_GLOBAL_MEMORY_USER,
            key=key,
            scope=MemoryScope.GLOBAL,
            project_id=None,
            redacted=self._was_redacted(value, redacted_value),
            outcome=outcome,
        )

    def close(self):
        """Close memory connections."""
        if self._redis:
            self._redis.close()
