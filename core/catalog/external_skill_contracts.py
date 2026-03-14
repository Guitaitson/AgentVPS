"""Runtime helper for external skill contracts synced from the catalog."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from core.config import get_settings


@dataclass(frozen=True, slots=True)
class ExternalSkillContract:
    local_name: str
    external_name: str
    source_name: str
    version: str
    execution_mode: str
    response_owner: str
    raw_output_policy: str
    description: str
    instructions_markdown: str
    metadata: dict[str, Any]


_LOCAL_TO_EXTERNAL = {
    "fleetintel_orchestrator": "fleetintel-orchestrator",
    "fleetintel_analyst": "fleetintel-analyst",
    "brazilcnpj": "brazilcnpj-enricher",
}


def get_external_skill_contract(local_skill_name: str) -> ExternalSkillContract | None:
    external_name = _LOCAL_TO_EXTERNAL.get(local_skill_name)
    if not external_name:
        return None

    record = _load_catalog_record(external_name)
    if not record:
        return _default_contract(local_skill_name, external_name, payload={})

    payload = record.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    instructions = str(payload.get("instructions_markdown") or "").strip()
    execution_mode = str(metadata.get("execution_mode") or "").strip()
    response_owner = str(metadata.get("response_owner") or "").strip()
    raw_output_policy = str(metadata.get("raw_output_policy") or "").strip()

    inferred_execution_mode, inferred_owner, inferred_raw_policy = _infer_defaults(
        external_name=external_name,
        instructions_markdown=instructions,
    )

    return ExternalSkillContract(
        local_name=local_skill_name,
        external_name=external_name,
        source_name=str(record.get("source_name") or ""),
        version=str(record.get("version") or ""),
        execution_mode=execution_mode or inferred_execution_mode,
        response_owner=response_owner or inferred_owner,
        raw_output_policy=raw_output_policy or inferred_raw_policy,
        description=str(payload.get("description") or ""),
        instructions_markdown=instructions,
        metadata=metadata,
    )


def _load_catalog_record(external_name: str) -> dict[str, Any] | None:
    row = _load_from_db(external_name)
    if row:
        return row
    return _load_from_cache(external_name)


def _load_from_db(external_name: str) -> dict[str, Any] | None:
    db_config = {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_PORT", 5432)),
        "dbname": os.getenv("POSTGRES_DB", "vps_agent"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT skill_name, source_name, version, payload
            FROM skills_catalog
            WHERE skill_name = %s AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (external_name,),
        )
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def _load_from_cache(external_name: str) -> dict[str, Any] | None:
    settings = get_settings()
    path = Path(settings.catalog.fallback_cache_file)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    items = payload.get("skills") or []
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("skill_name") == external_name and item.get("status", "active") == "active":
            return item
    return None


def _default_contract(
    local_skill_name: str,
    external_name: str,
    payload: dict[str, Any],
) -> ExternalSkillContract:
    execution_mode, response_owner, raw_output_policy = _infer_defaults(
        external_name=external_name,
        instructions_markdown=str(payload.get("instructions_markdown") or ""),
    )
    return ExternalSkillContract(
        local_name=local_skill_name,
        external_name=external_name,
        source_name="",
        version=str(payload.get("version") or ""),
        execution_mode=execution_mode,
        response_owner=response_owner,
        raw_output_policy=raw_output_policy,
        description=str(payload.get("description") or ""),
        instructions_markdown=str(payload.get("instructions_markdown") or ""),
        metadata={},
    )


def _infer_defaults(
    *,
    external_name: str,
    instructions_markdown: str,
) -> tuple[str, str, str]:
    if external_name in {"fleetintel-orchestrator", "fleetintel-analyst"}:
        return ("specialist_response", "specialist", "on_user_request")
    if "Response Contract" in instructions_markdown:
        return ("specialist_response", "specialist", "on_user_request")
    return ("tool_first", "agentvps", "on_user_request")
