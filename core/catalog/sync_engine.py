"""
Catalog sync engine for external skills metadata sources.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import psycopg2
import structlog
import yaml
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
        self._history_file_path = self.settings.history_file
        self._pins_file_path = self.settings.pins_file
        self._github_token = (
            os.getenv("CATALOG_GITHUB_TOKEN")
            or os.getenv("GITHUB_TOKEN")
            or os.getenv("GH_TOKEN")
            or ""
        )
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
                "pinned_skipped": 0,
                "message": "No enabled sources configured",
            }

        try:
            discovered = await self._discover_all_sources(sources)
            existing = self._load_existing_catalog()
            self._apply_pins_to_discovered(discovered)
            diff = self._diff_catalog(existing, discovered)

            if mode == "apply":
                self._apply_catalog(diff, discovered, existing)
                self._persist_history_snapshot(discovered, diff)

            result = {
                "success": True,
                "mode": mode,
                "sources_checked": len(sources),
                "skills_discovered": len(discovered),
                "changes_detected": diff["added"] + diff["updated"] + diff["removed"],
                "added": diff["added"],
                "updated": diff["updated"],
                "removed": diff["removed"],
                "pinned_skipped": diff.get("pinned_skipped", 0),
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

    async def pin(
        self,
        *,
        skill_name: str,
        source_name: str | None = None,
        version: str | None = None,
        reason: str | None = None,
        pinned_by: str = "system",
    ) -> dict[str, Any]:
        """Pins one catalog entry to prevent version drift on apply sync."""
        skill_name = skill_name.strip()
        source_name = source_name.strip() if source_name else None
        version = version.strip() if version else None
        if not skill_name:
            return {"success": False, "error": "skill_name is required"}

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            if source_name:
                cur.execute(
                    """
                    SELECT skill_name, source_name, version
                    FROM skills_catalog
                    WHERE skill_name = %s AND source_name = %s
                    LIMIT 1
                    """,
                    (skill_name, source_name),
                )
            else:
                cur.execute(
                    """
                    SELECT skill_name, source_name, version
                    FROM skills_catalog
                    WHERE skill_name = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (skill_name,),
                )
            row = cur.fetchone()
            if not row:
                conn.close()
                return {"success": False, "error": "skill not found in catalog"}

            source = source_name or row["source_name"]
            pin_version = version or row["version"]
            cur.execute(
                """
                UPDATE skills_catalog
                SET pinned = TRUE,
                    pinned_version = %s,
                    pin_reason = %s,
                    pinned_at = NOW(),
                    pinned_by = %s
                WHERE skill_name = %s AND source_name = %s
                """,
                (pin_version, reason, pinned_by, skill_name, source),
            )
            conn.commit()
            conn.close()
            return {
                "success": True,
                "skill_name": skill_name,
                "source_name": source,
                "pinned_version": pin_version,
            }
        except Exception:
            return self._pin_in_file(
                skill_name=skill_name,
                source_name=source_name,
                version=version,
                reason=reason,
                pinned_by=pinned_by,
            )

    async def unpin(self, *, skill_name: str, source_name: str | None = None) -> dict[str, Any]:
        skill_name = skill_name.strip()
        source_name = source_name.strip() if source_name else None
        if not skill_name:
            return {"success": False, "error": "skill_name is required"}

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            if source_name:
                cur.execute(
                    """
                    UPDATE skills_catalog
                    SET pinned = FALSE,
                        pinned_version = NULL,
                        pin_reason = NULL,
                        pinned_at = NULL,
                        pinned_by = NULL
                    WHERE skill_name = %s AND source_name = %s
                    """,
                    (skill_name, source_name),
                )
            else:
                cur.execute(
                    """
                    UPDATE skills_catalog
                    SET pinned = FALSE,
                        pinned_version = NULL,
                        pin_reason = NULL,
                        pinned_at = NULL,
                        pinned_by = NULL
                    WHERE skill_name = %s
                    """,
                    (skill_name,),
                )
            updated = int(cur.rowcount)
            conn.commit()
            conn.close()
            return {"success": True, "updated": updated}
        except Exception:
            pins = self._load_pins_from_file()
            keys = [key for key in pins if key.startswith(f"{skill_name}:")]
            if source_name:
                keys = (
                    [f"{skill_name}:{source_name}"] if f"{skill_name}:{source_name}" in pins else []
                )
            for key in keys:
                pins.pop(key, None)
            self._save_pins_to_file(pins)
            return {"success": True, "updated": len(keys)}

    async def provenance(
        self,
        *,
        skill_name: str,
        source_name: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        skill_name = skill_name.strip()
        source_name = source_name.strip() if source_name else None
        if not skill_name:
            return {"success": False, "error": "skill_name is required"}

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            if source_name:
                cur.execute(
                    """
                    SELECT skill_name, source_name, version, schema_hash, status, last_seen_at,
                           pinned, pinned_version, pin_reason, pinned_at, pinned_by
                    FROM skills_catalog
                    WHERE skill_name = %s AND source_name = %s
                    LIMIT 1
                    """,
                    (skill_name, source_name),
                )
            else:
                cur.execute(
                    """
                    SELECT skill_name, source_name, version, schema_hash, status, last_seen_at,
                           pinned, pinned_version, pin_reason, pinned_at, pinned_by
                    FROM skills_catalog
                    WHERE skill_name = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (skill_name,),
                )
            current = cur.fetchone()
            if not current:
                conn.close()
                return {"success": False, "error": "skill not found in catalog"}

            cur.execute(
                """
                SELECT version, schema_hash, status, changed_at, change_type, changed_by
                FROM skills_catalog_history
                WHERE skill_name = %s AND source_name = %s
                ORDER BY changed_at DESC
                LIMIT %s
                """,
                (current["skill_name"], current["source_name"], max(1, int(limit))),
            )
            history = cur.fetchall()
            conn.close()

            return {
                "success": True,
                "current": self._serialize_catalog_row(current),
                "history": [self._serialize_catalog_row(row) for row in history],
            }
        except Exception:
            return self._provenance_from_files(
                skill_name=skill_name, source_name=source_name, limit=limit
            )

    async def rollback(
        self,
        *,
        skill_name: str,
        source_name: str | None = None,
        target_version: str | None = None,
        actor: str = "system",
        reason: str | None = None,
    ) -> dict[str, Any]:
        skill_name = skill_name.strip()
        source_name = source_name.strip() if source_name else None
        target_version = target_version.strip() if target_version else None
        if not skill_name:
            return {"success": False, "error": "skill_name is required"}

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            if source_name:
                cur.execute(
                    """
                    SELECT skill_name, source_name, version
                    FROM skills_catalog
                    WHERE skill_name = %s AND source_name = %s
                    LIMIT 1
                    """,
                    (skill_name, source_name),
                )
            else:
                cur.execute(
                    """
                    SELECT skill_name, source_name, version
                    FROM skills_catalog
                    WHERE skill_name = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (skill_name,),
                )
            current = cur.fetchone()
            if not current:
                conn.close()
                return {"success": False, "error": "skill not found in catalog"}

            params: list[Any] = [current["skill_name"], current["source_name"]]
            where_version = ""
            if target_version:
                where_version = "AND version = %s"
                params.append(target_version)

            cur.execute(
                f"""
                SELECT skill_name, source_name, version, schema_hash, payload, status
                FROM skills_catalog_history
                WHERE skill_name = %s AND source_name = %s
                  {where_version}
                ORDER BY changed_at DESC
                LIMIT 1
                """,
                tuple(params),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return {"success": False, "error": "no rollback candidate in history"}

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
                    row["skill_name"],
                    row["source_name"],
                    row["version"],
                    row["schema_hash"],
                    Json(row["payload"]),
                ),
            )

            detail = {"reason": reason} if reason else {}
            cur.execute(
                """
                INSERT INTO skills_catalog_history (
                    skill_name, source_name, version, schema_hash, payload, status, change_type, changed_by, details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["skill_name"],
                    row["source_name"],
                    row["version"],
                    row["schema_hash"],
                    Json(row["payload"]),
                    "active",
                    "rollback_applied",
                    actor,
                    Json(detail),
                ),
            )
            conn.commit()
            conn.close()
            return {
                "success": True,
                "skill_name": row["skill_name"],
                "source_name": row["source_name"],
                "rolled_back_to_version": row["version"],
            }
        except Exception:
            return self._rollback_from_files(
                skill_name=skill_name,
                source_name=source_name,
                target_version=target_version,
            )

    async def _discover_all_sources(
        self, sources: list[CatalogSource]
    ) -> dict[str, dict[str, Any]]:
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

        if source.source_type == "langchain_skills_github_repo":
            return await self._fetch_langchain_skills_github_repo(source.location)

        logger.warning(
            "catalog.unsupported_source_type",
            source=source.name,
            source_type=source.source_type,
        )
        return []

    async def _fetch_langchain_skills_github_repo(self, location: str) -> list[dict[str, Any]]:
        owner, repo, ref = self._parse_github_repo_location(location)
        if not owner or not repo:
            logger.warning("catalog.github_repo_invalid_location", location=location)
            return []

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AgentVPS-CatalogSync/1.0",
        }
        if self._github_token:
            headers["Authorization"] = f"Bearer {self._github_token}"
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
            commit_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits/{ref}",
                headers=headers,
            )
            if commit_resp.status_code == 404 and not self._github_token:
                raise RuntimeError(
                    "GitHub repository not accessible without token. "
                    "Set CATALOG_GITHUB_TOKEN, GITHUB_TOKEN, or GH_TOKEN."
                )
            commit_resp.raise_for_status()
            commit_sha = str(commit_resp.json().get("sha", ref))

            tree_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1",
                headers=headers,
            )
            tree_resp.raise_for_status()
            tree_payload = tree_resp.json()

            skills: list[dict[str, Any]] = []
            for item in tree_payload.get("tree", []):
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path", ""))
                if not re.fullmatch(r"skills/[^/]+/SKILL\.md", path):
                    continue
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
                raw_resp = await client.get(raw_url, headers=headers)
                raw_resp.raise_for_status()
                parsed = self._parse_langchain_skill_markdown(raw_resp.text)
                if not parsed:
                    continue
                parsed.setdefault("name", path.split("/")[1])
                parsed.setdefault("version", commit_sha[:12])
                parsed.setdefault("metadata", {})
                parsed["metadata"].setdefault("repository", f"https://github.com/{owner}/{repo}")
                parsed["metadata"].setdefault("homepage", f"https://github.com/{owner}/{repo}")
                parsed["metadata"].setdefault("git_ref", ref)
                parsed["metadata"].setdefault("git_commit", commit_sha)
                parsed["metadata"].setdefault("skill_path", path)
                skills.append(parsed)
            return skills

    @staticmethod
    def _parse_github_repo_location(location: str) -> tuple[str, str, str]:
        value = location.strip()
        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlparse(value)
            parts = [part for part in parsed.path.strip("/").split("/") if part]
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1].removesuffix(".git")
                ref = "main"
                if len(parts) >= 4 and parts[2] == "tree":
                    ref = parts[3]
                return owner, repo, ref
            return "", "", "main"

        ref = "main"
        repo_part = value
        if "@" in value:
            repo_part, ref = value.split("@", 1)
        parts = [part for part in repo_part.strip("/").split("/") if part]
        if len(parts) != 2:
            return "", "", ref or "main"
        return parts[0], parts[1].removesuffix(".git"), ref or "main"

    @staticmethod
    def _parse_langchain_skill_markdown(content: str) -> dict[str, Any] | None:
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
        if not match:
            return None
        try:
            payload = yaml.safe_load(match.group(1))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        body = content[match.end() :].strip()
        if "description" not in payload:
            if body:
                payload["description"] = body.splitlines()[0][:300]
        if body:
            payload["_skill_body"] = body
        return payload

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

    def _normalize_skill(
        self, raw_skill: dict[str, Any], *, source_name: str
    ) -> dict[str, Any] | None:
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
            "instructions_markdown": str(raw_skill.get("_skill_body", "")).strip(),
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
            try:
                cur.execute(
                    """
                    SELECT skill_name, source_name, version, schema_hash, payload, status, last_seen_at,
                           pinned, pinned_version, pin_reason, pinned_at, pinned_by
                    FROM skills_catalog
                    """
                )
            except Exception:
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
        pinned_skipped = 0
        changed_keys: list[str] = []

        for key, item in discovered.items():
            if key not in existing:
                added += 1
                changed_keys.append(key)
                continue
            pinned_version = existing[key].get("pinned_version")
            if (
                existing[key].get("pinned")
                and pinned_version
                and item.get("version") != pinned_version
            ):
                pinned_skipped += 1
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
            "pinned_skipped": pinned_skipped,
            "changed_keys": changed_keys,
        }

    def _apply_catalog(
        self,
        diff: dict[str, Any],
        discovered: dict[str, dict[str, Any]],
        existing: dict[str, dict[str, Any]],
    ) -> None:
        try:
            conn = self._get_conn()
            cur = conn.cursor()

            for key, item in discovered.items():
                current = existing.get(key)
                pinned_version = current.get("pinned_version") if current else None
                if (
                    current
                    and current.get("pinned")
                    and pinned_version
                    and item.get("version") != pinned_version
                ):
                    # Keep pinned version stable, only refresh heartbeat.
                    cur.execute(
                        """
                        UPDATE skills_catalog
                        SET status = 'active', last_seen_at = NOW(), updated_at = NOW()
                        WHERE skill_name = %s AND source_name = %s
                        """,
                        (item["skill_name"], item["source_name"]),
                    )
                    continue

                cur.execute(
                    """
                    INSERT INTO skills_catalog (
                        skill_name, source_name, version, schema_hash, payload, status, last_seen_at,
                        pinned, pinned_version, pin_reason, pinned_at, pinned_by
                    )
                    VALUES (%s, %s, %s, %s, %s, 'active', NOW(), FALSE, NULL, NULL, NULL, NULL)
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

                self._insert_history_row(
                    cur,
                    item=item,
                    status="active",
                    change_type="applied",
                )

            if discovered:
                pairs = [(item["skill_name"], item["source_name"]) for item in discovered.values()]
                cur.execute(
                    """
                    SELECT skill_name, source_name, version, schema_hash, payload
                    FROM skills_catalog
                    WHERE status = 'active'
                    """
                )
                rows = cur.fetchall()
                known = {(row[0], row[1]): row for row in rows}
                discovered_set = set(pairs)
                removed_set = set(known.keys()) - discovered_set
                for skill_name, source_name in removed_set:
                    cur.execute(
                        """
                        UPDATE skills_catalog
                        SET status = 'inactive', updated_at = NOW()
                        WHERE skill_name = %s AND source_name = %s
                        """,
                        (skill_name, source_name),
                    )
                    row = known[(skill_name, source_name)]
                    self._insert_history_row(
                        cur,
                        item={
                            "skill_name": row[0],
                            "source_name": row[1],
                            "version": row[2],
                            "schema_hash": row[3],
                            "payload": row[4],
                        },
                        status="inactive",
                        change_type="removed",
                    )

            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("catalog.apply_fallback_file", error=str(exc))
            self._write_catalog_cache_file(discovered, diff)

    def _apply_pins_to_discovered(self, discovered: dict[str, dict[str, Any]]) -> None:
        pins = self._load_pins_from_file()
        if not pins:
            return
        for key, item in discovered.items():
            pin = pins.get(key)
            if not isinstance(pin, dict):
                continue
            pin_version = pin.get("version")
            if pin_version:
                item["pinned"] = True
                item["pinned_version"] = str(pin_version)
                item.setdefault("payload", {}).setdefault("metadata", {})["pinned"] = True

    def _insert_history_row(
        self,
        cur,
        *,
        item: dict[str, Any],
        status: str,
        change_type: str,
        changed_by: str = "sync_engine",
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            cur.execute(
                """
                INSERT INTO skills_catalog_history (
                    skill_name, source_name, version, schema_hash, payload, status, change_type, changed_by, details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    item["skill_name"],
                    item["source_name"],
                    item.get("version", "0.0.0"),
                    item.get("schema_hash", ""),
                    Json(item.get("payload", {})),
                    status,
                    change_type,
                    changed_by,
                    Json(details or {}),
                ),
            )
        except Exception:
            return

    def _write_catalog_cache_file(
        self,
        discovered: dict[str, dict[str, Any]],
        diff: dict[str, Any],
    ) -> None:
        path = Path(self._fallback_cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "skills": list(discovered.values()),
            "diff": diff,
        }
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _persist_history_snapshot(
        self,
        discovered: dict[str, dict[str, Any]],
        diff: dict[str, Any],
    ) -> None:
        path = Path(self._history_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    history = raw
            except Exception:
                history = []
        history.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "skills": list(discovered.values()),
                "diff": diff,
            }
        )
        history = history[-100:]
        path.write_text(json.dumps(history, ensure_ascii=True, indent=2), encoding="utf-8")

    def _load_pins_from_file(self) -> dict[str, dict[str, Any]]:
        path = Path(self._pins_file_path)
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return {
                    str(key): value for key, value in payload.items() if isinstance(value, dict)
                }
            return {}
        except Exception:
            return {}

    def _save_pins_to_file(self, pins: dict[str, dict[str, Any]]) -> None:
        path = Path(self._pins_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pins, ensure_ascii=True, indent=2), encoding="utf-8")

    def _pin_in_file(
        self,
        *,
        skill_name: str,
        source_name: str | None,
        version: str | None,
        reason: str | None,
        pinned_by: str,
    ) -> dict[str, Any]:
        catalog = self._load_existing_from_file()
        candidate_key = None
        if source_name:
            key = self._catalog_key(skill_name, source_name)
            if key in catalog:
                candidate_key = key
        else:
            for key, item in catalog.items():
                if item.get("skill_name") == skill_name:
                    candidate_key = key
                    break
        if not candidate_key:
            return {"success": False, "error": "skill not found in cache"}

        item = catalog[candidate_key]
        pin_version = version or str(item.get("version", "0.0.0"))
        pins = self._load_pins_from_file()
        pins[candidate_key] = {
            "version": pin_version,
            "reason": reason,
            "pinned_by": pinned_by,
            "pinned_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_pins_to_file(pins)
        return {
            "success": True,
            "skill_name": item.get("skill_name"),
            "source_name": item.get("source_name"),
            "pinned_version": pin_version,
        }

    def _provenance_from_files(
        self,
        *,
        skill_name: str,
        source_name: str | None,
        limit: int,
    ) -> dict[str, Any]:
        catalog = self._load_existing_from_file()
        current = None
        if source_name:
            current = catalog.get(self._catalog_key(skill_name, source_name))
        else:
            for item in catalog.values():
                if item.get("skill_name") == skill_name:
                    current = item
                    break
        if not current:
            return {"success": False, "error": "skill not found in cache"}

        history_path = Path(self._history_file_path)
        history_rows: list[dict[str, Any]] = []
        if history_path.is_file():
            try:
                snapshots = json.loads(history_path.read_text(encoding="utf-8"))
                if isinstance(snapshots, list):
                    for snapshot in reversed(snapshots):
                        for item in snapshot.get("skills", []):
                            if not isinstance(item, dict):
                                continue
                            if item.get("skill_name") != current.get("skill_name"):
                                continue
                            if item.get("source_name") != current.get("source_name"):
                                continue
                            history_rows.append(
                                {
                                    "version": item.get("version"),
                                    "schema_hash": item.get("schema_hash"),
                                    "status": item.get("status", "active"),
                                    "changed_at": snapshot.get("ts"),
                                    "change_type": "snapshot",
                                    "changed_by": "sync_engine",
                                }
                            )
                            if len(history_rows) >= max(1, int(limit)):
                                break
                        if len(history_rows) >= max(1, int(limit)):
                            break
            except Exception:
                history_rows = []

        return {
            "success": True,
            "current": self._serialize_catalog_row(current),
            "history": [self._serialize_catalog_row(row) for row in history_rows],
        }

    def _rollback_from_files(
        self,
        *,
        skill_name: str,
        source_name: str | None,
        target_version: str | None,
    ) -> dict[str, Any]:
        history_path = Path(self._history_file_path)
        if not history_path.is_file():
            return {"success": False, "error": "history unavailable"}
        try:
            snapshots = json.loads(history_path.read_text(encoding="utf-8"))
            if not isinstance(snapshots, list):
                return {"success": False, "error": "invalid history format"}

            candidate = None
            for snapshot in reversed(snapshots):
                for item in snapshot.get("skills", []):
                    if not isinstance(item, dict):
                        continue
                    if item.get("skill_name") != skill_name:
                        continue
                    if source_name and item.get("source_name") != source_name:
                        continue
                    if target_version and str(item.get("version")) != target_version:
                        continue
                    candidate = item
                    break
                if candidate:
                    break

            if not candidate:
                return {"success": False, "error": "rollback candidate not found in history"}

            catalog = self._load_existing_from_file()
            key = self._catalog_key(
                candidate.get("skill_name", ""), candidate.get("source_name", "")
            )
            if key == ":":
                return {"success": False, "error": "invalid candidate key"}
            catalog[key] = candidate
            self._write_catalog_cache_file(catalog, {"rollback": True})
            return {
                "success": True,
                "skill_name": candidate.get("skill_name"),
                "source_name": candidate.get("source_name"),
                "rolled_back_to_version": candidate.get("version"),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def _serialize_catalog_row(row: dict[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in row.items():
            if hasattr(value, "isoformat"):
                output[key] = value.isoformat()
            else:
                output[key] = value
        return output

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
        value = (
            raw_skill.get("triggers") or raw_skill.get("keywords") or raw_skill.get("tags") or []
        )
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
