"""
Catalog sync engine for external skills metadata sources.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import psycopg2
import structlog
from psycopg2.extras import Json, RealDictCursor

from core.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class CatalogSource:
    name: str
    source_type: str
    location: str
    enabled: bool = True


class SkillsCatalogSyncEngine:
    """Synchronizes skill metadata catalog from configured sources."""

    def __init__(self, sources_file: str | None = None):
        settings = get_settings()
        self.settings = settings.catalog
        self.sources_file = sources_file or self.settings.sources_file
        self._fallback_cache_path = self.settings.fallback_cache_file
        self._db_config = {
            "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "port": int(os.getenv("POSTGRES_PORT", 5432)),
            "dbname": os.getenv("POSTGRES_DB", "vps_agent"),
            "user": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD"),
        }

    def _get_conn(self):
        return psycopg2.connect(**self._db_config)

    def load_sources(self) -> list[CatalogSource]:
        path = Path(self.sources_file)
        if not path.is_file():
            logger.warning("catalog.sources_file_missing", path=str(path))
            return []

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_sources = payload.get("sources", [])
            sources = []
            for raw in raw_sources:
                source = CatalogSource(
                    name=str(raw.get("name", "")).strip(),
                    source_type=str(raw.get("type", "")).strip(),
                    location=str(raw.get("location", "")).strip(),
                    enabled=bool(raw.get("enabled", True)),
                )
                if source.name and source.source_type and source.location:
                    sources.append(source)
            return sources
        except Exception as exc:
            logger.error("catalog.sources_parse_error", error=str(exc), path=str(path))
            return []

    async def sync(self, *, mode: str = "check", source_name: str | None = None) -> dict[str, Any]:
        """Run one sync cycle. mode: 'check' or 'apply'."""
        mode = mode.lower().strip()
        if mode not in {"check", "apply"}:
            return {"success": False, "error": "mode must be 'check' or 'apply'"}

        sources = [source for source in self.load_sources() if source.enabled]
        if source_name:
            sources = [source for source in sources if source.name == source_name]

        if not sources:
            return {
                "success": True,
                "mode": mode,
                "sources_checked": 0,
                "skills_discovered": 0,
                "changes_detected": 0,
                "added": 0,
                "updated": 0,
                "removed": 0,
                "message": "No enabled sources configured",
            }

        try:
            discovered = await self._discover_all_sources(sources)
            existing = self._load_existing_catalog()
            diff = self._diff_catalog(existing, discovered)

            if mode == "apply":
                self._apply_catalog(diff, discovered)

            result = {
                "success": True,
                "mode": mode,
                "sources_checked": len(sources),
                "skills_discovered": len(discovered),
                "changes_detected": diff["added"] + diff["updated"] + diff["removed"],
                "added": diff["added"],
                "updated": diff["updated"],
                "removed": diff["removed"],
                "changed_keys": diff["changed_keys"][:50],
            }
            self._persist_run(status="success", run_mode=mode, stats=result)
            return result
        except Exception as exc:
            logger.error("catalog.sync_error", error=str(exc))
            self._persist_run(
                status="failed",
                run_mode=mode,
                stats={},
                error_message=str(exc),
            )
            return {"success": False, "mode": mode, "error": str(exc)}

    async def _discover_all_sources(self, sources: list[CatalogSource]) -> dict[str, dict[str, Any]]:
        catalog: dict[str, dict[str, Any]] = {}
        for source in sources:
            raw_skills = await self._fetch_source_skills(source)
            for raw_skill in raw_skills:
                normalized = self._normalize_skill(raw_skill, source_name=source.name)
                if not normalized:
                    continue
                key = self._catalog_key(normalized["skill_name"], normalized["source_name"])
                catalog[key] = normalized
        return catalog

    async def _fetch_source_skills(self, source: CatalogSource) -> list[dict[str, Any]]:
        if source.source_type == "local_json":
            path = Path(source.location)
            if not path.is_file():
                logger.warning("catalog.local_source_missing", source=source.name, path=str(path))
                return []
            payload = json.loads(path.read_text(encoding="utf-8"))
            return self._extract_skills(payload)

        if source.source_type == "url_json":
            async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
                response = await client.get(source.location)
                response.raise_for_status()
                payload = response.json()
                return self._extract_skills(payload)

        if source.source_type == "langchain_skills_local_json":
            path = Path(source.location)
            if not path.is_file():
                logger.warning("catalog.local_source_missing", source=source.name, path=str(path))
                return []
            payload = json.loads(path.read_text(encoding="utf-8"))
            return self._extract_langchain_skills(payload)

        if source.source_type == "langchain_skills_url_json":
            async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
                response = await client.get(source.location)
                response.raise_for_status()
                payload = response.json()
                return self._extract_langchain_skills(payload)

        logger.warning(
            "catalog.unsupported_source_type",
            source=source.name,
            source_type=source.source_type,
        )
        return []

    @staticmethod
    def _extract_skills(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            raw = payload.get("skills", [])
            return [item for item in raw if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_langchain_skills(payload: Any) -> list[dict[str, Any]]:
        """
        Extracts skill-like items from flexible LangChain/LangGraph catalogs.
        """
        candidates: list[dict[str, Any]] = []

        def collect(items: Any):
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        candidates.append(item)
            elif isinstance(items, dict):
                # Handle nested package/source payloads recursively.
                for key in ("skills", "tools", "items", "entries"):
                    nested = items.get(key)
                    if isinstance(nested, list):
                        collect(nested)
                for key in ("packages", "sources", "catalogs"):
                    nested_groups = items.get(key)
                    if isinstance(nested_groups, list):
                        for group in nested_groups:
                            if isinstance(group, dict):
                                collect(group)

        if isinstance(payload, dict):
            collect(payload)
        elif isinstance(payload, list):
            collect(payload)

        normalized_like = []
        for item in candidates:
            function = item.get("function")
            if isinstance(function, dict):
                function_name = function.get("name")
                if function_name and "name" not in item:
                    item = {**item, "name": function_name}
                function_params = function.get("parameters")
                if function_params and "parameters_schema" not in item:
                    item = {**item, "parameters_schema": function_params}
            normalized_like.append(item)
        return normalized_like

    def _normalize_skill(self, raw_skill: dict[str, Any], *, source_name: str) -> dict[str, Any] | None:
        skill_name = self._pick_name(raw_skill)
        if not skill_name:
            return None

        version = self._pick_version(raw_skill)
        description = self._pick_description(raw_skill)
        security_level = self._pick_security_level(raw_skill)
        if security_level not in {"safe", "moderate", "dangerous", "forbidden"}:
            security_level = "safe"

        triggers = self._pick_triggers(raw_skill)
        parameters_schema = self._pick_parameters_schema(raw_skill)
        payload = {
            "name": skill_name,
            "description": description,
            "version": version,
            "security_level": security_level,
            "triggers": triggers,
            "parameters_schema": parameters_schema,
            "metadata": self._build_metadata(raw_skill),
        }
        schema_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()

        return {
            "skill_name": skill_name,
            "source_name": source_name,
            "version": version,
            "schema_hash": schema_hash,
            "payload": payload,
            "status": "active",
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }

    def _load_existing_catalog(self) -> dict[str, dict[str, Any]]:
        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT skill_name, source_name, version, schema_hash, payload, status, last_seen_at
                FROM skills_catalog
                """
            )
            rows = cur.fetchall()
            conn.close()
            existing = {}
            for row in rows:
                key = self._catalog_key(row["skill_name"], row["source_name"])
                existing[key] = dict(row)
            return existing
        except Exception as exc:
            logger.warning("catalog.load_existing_fallback_file", error=str(exc))
            return self._load_existing_from_file()

    def _load_existing_from_file(self) -> dict[str, dict[str, Any]]:
        path = Path(self._fallback_cache_path)
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = payload.get("skills", [])
            catalog = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                key = self._catalog_key(item.get("skill_name", ""), item.get("source_name", ""))
                if key != ":":
                    catalog[key] = item
            return catalog
        except Exception:
            return {}

    def _diff_catalog(
        self,
        existing: dict[str, dict[str, Any]],
        discovered: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        added = 0
        updated = 0
        removed = 0
        changed_keys: list[str] = []

        for key, item in discovered.items():
            if key not in existing:
                added += 1
                changed_keys.append(key)
                continue
            if existing[key].get("schema_hash") != item.get("schema_hash"):
                updated += 1
                changed_keys.append(key)

        for key in existing:
            if key not in discovered and existing[key].get("status", "active") == "active":
                removed += 1
                changed_keys.append(key)

        return {
            "added": added,
            "updated": updated,
            "removed": removed,
            "changed_keys": changed_keys,
        }

    def _apply_catalog(self, diff: dict[str, Any], discovered: dict[str, dict[str, Any]]) -> None:
        try:
            conn = self._get_conn()
            cur = conn.cursor()

            for item in discovered.values():
                cur.execute(
                    """
                    INSERT INTO skills_catalog (
                        skill_name, source_name, version, schema_hash, payload, status, last_seen_at
                    )
                    VALUES (%s, %s, %s, %s, %s, 'active', NOW())
                    ON CONFLICT (skill_name, source_name)
                    DO UPDATE SET
                        version = EXCLUDED.version,
                        schema_hash = EXCLUDED.schema_hash,
                        payload = EXCLUDED.payload,
                        status = 'active',
                        last_seen_at = NOW(),
                        updated_at = NOW()
                    """,
                    (
                        item["skill_name"],
                        item["source_name"],
                        item["version"],
                        item["schema_hash"],
                        Json(item["payload"]),
                    ),
                )

            if discovered:
                pairs = [(item["skill_name"], item["source_name"]) for item in discovered.values()]
                cur.execute(
                    """
                    SELECT skill_name, source_name
                    FROM skills_catalog
                    WHERE status = 'active'
                    """
                )
                rows = cur.fetchall()
                known = {(row[0], row[1]) for row in rows}
                discovered_set = set(pairs)
                removed_set = known - discovered_set
                for skill_name, source_name in removed_set:
                    cur.execute(
                        """
                        UPDATE skills_catalog
                        SET status = 'inactive', updated_at = NOW()
                        WHERE skill_name = %s AND source_name = %s
                        """,
                        (skill_name, source_name),
                    )

            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("catalog.apply_fallback_file", error=str(exc))
            path = Path(self._fallback_cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "skills": list(discovered.values()),
                "diff": diff,
            }
            path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _persist_run(
        self,
        *,
        status: str,
        run_mode: str,
        stats: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO skills_catalog_sync_runs (run_mode, status, source_count, stats, error_message)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    run_mode,
                    status,
                    int(stats.get("sources_checked", 0)),
                    Json(stats),
                    error_message,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            # Non-critical telemetry write.
            return

    @staticmethod
    def _catalog_key(skill_name: str, source_name: str) -> str:
        return f"{skill_name}:{source_name}"

    @staticmethod
    def _pick_name(raw_skill: dict[str, Any]) -> str:
        candidates = [
            raw_skill.get("name"),
            raw_skill.get("id"),
            raw_skill.get("slug"),
            raw_skill.get("skill_name"),
            raw_skill.get("tool_name"),
        ]
        function = raw_skill.get("function")
        if isinstance(function, dict):
            candidates.append(function.get("name"))
        for value in candidates:
            if value:
                name = str(value).strip()
                if name:
                    return name
        return ""

    @staticmethod
    def _pick_description(raw_skill: dict[str, Any]) -> str:
        candidates = [
            raw_skill.get("description"),
            raw_skill.get("summary"),
            raw_skill.get("help"),
            raw_skill.get("docs"),
        ]
        function = raw_skill.get("function")
        if isinstance(function, dict):
            candidates.append(function.get("description"))
        for value in candidates:
            if value:
                text = str(value).strip()
                if text:
                    return text
        return "No description"

    @staticmethod
    def _pick_version(raw_skill: dict[str, Any]) -> str:
        candidates = [
            raw_skill.get("version"),
            raw_skill.get("semver"),
            raw_skill.get("skill_version"),
            raw_skill.get("release"),
        ]
        for value in candidates:
            if value:
                return str(value).strip()
        return "0.0.0"

    @staticmethod
    def _pick_security_level(raw_skill: dict[str, Any]) -> str:
        value = (
            raw_skill.get("security_level")
            or raw_skill.get("risk_level")
            or raw_skill.get("trust_level")
            or "safe"
        )
        level = str(value).strip().lower()
        aliases = {
            "low": "safe",
            "read_only": "safe",
            "medium": "moderate",
            "high": "dangerous",
            "critical": "forbidden",
        }
        return aliases.get(level, level)

    @staticmethod
    def _pick_triggers(raw_skill: dict[str, Any]) -> list[str]:
        value = raw_skill.get("triggers") or raw_skill.get("keywords") or raw_skill.get("tags") or []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []
        return []

    @staticmethod
    def _pick_parameters_schema(raw_skill: dict[str, Any]) -> dict[str, Any]:
        for key in ("parameters_schema", "input_schema", "json_schema", "schema"):
            value = raw_skill.get(key)
            if isinstance(value, dict):
                return value
        function = raw_skill.get("function")
        if isinstance(function, dict):
            params = function.get("parameters")
            if isinstance(params, dict):
                return params
        return {}

    @staticmethod
    def _build_metadata(raw_skill: dict[str, Any]) -> dict[str, Any]:
        metadata = raw_skill.get("metadata")
        base = metadata.copy() if isinstance(metadata, dict) else {}
        for key in ("provider", "package", "author", "repository", "homepage"):
            if key in raw_skill and key not in base:
                base[key] = raw_skill.get(key)
        return base
