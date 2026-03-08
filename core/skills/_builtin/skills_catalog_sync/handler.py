"""
Skill: skills_catalog_sync

Runs check/apply sync for external skill catalog sources and supports pin/rollback/provenance.
"""

from __future__ import annotations

from typing import Any

from core.catalog import SkillsCatalogSyncEngine
from core.skills.base import SkillBase


class SkillsCatalogSyncSkill(SkillBase):
    """Syncs external skills catalog metadata."""

    async def execute(self, args: dict[str, Any] = None) -> str:
        args = args or {}
        mode = str(args.get("mode", "check")).strip().lower()
        source = args.get("source")
        source = str(source).strip() if source else None

        engine = SkillsCatalogSyncEngine()

        if mode in {"check", "apply"}:
            result = await engine.sync(mode=mode, source_name=source)
            if not result.get("success"):
                return f"ERROR: catalog sync failed: {result.get('error', 'unknown')}"
            lines = [
                "catalog sync completed",
                f"- mode: {result.get('mode')}",
                f"- sources_checked: {result.get('sources_checked', 0)}",
                f"- skills_discovered: {result.get('skills_discovered', 0)}",
                f"- changes: {result.get('changes_detected', 0)}",
                f"- added: {result.get('added', 0)}",
                f"- updated: {result.get('updated', 0)}",
                f"- removed: {result.get('removed', 0)}",
                f"- pinned_skipped: {result.get('pinned_skipped', 0)}",
            ]
            changed = result.get("changed_keys", [])
            if changed:
                lines.append(f"- changed_keys: {', '.join(changed[:10])}")
            return "\n".join(lines)

        if mode == "pin":
            skill_name = str(args.get("skill_name", "")).strip()
            if not skill_name:
                return "ERROR: mode=pin requires skill_name"
            version = str(args.get("version", "")).strip() or None
            result = await engine.pin(
                skill_name=skill_name,
                source_name=source,
                version=version,
                reason=str(args.get("reason", "")).strip() or None,
                pinned_by=str(args.get("pinned_by", "skills_catalog_sync")),
            )
            if not result.get("success"):
                return f"ERROR: pin failed: {result.get('error', 'unknown')}"
            return (
                f"pin applied: {result.get('skill_name')}@{result.get('source_name')} "
                f"v{result.get('pinned_version')}"
            )

        if mode == "unpin":
            skill_name = str(args.get("skill_name", "")).strip()
            if not skill_name:
                return "ERROR: mode=unpin requires skill_name"
            result = await engine.unpin(skill_name=skill_name, source_name=source)
            if not result.get("success"):
                return f"ERROR: unpin failed: {result.get('error', 'unknown')}"
            return f"unpin completed (updated={result.get('updated', 0)})"

        if mode == "rollback":
            skill_name = str(args.get("skill_name", "")).strip()
            if not skill_name:
                return "ERROR: mode=rollback requires skill_name"
            target_version = str(args.get("target_version", "")).strip() or None
            result = await engine.rollback(
                skill_name=skill_name,
                source_name=source,
                target_version=target_version,
                actor=str(args.get("actor", "skills_catalog_sync")),
                reason=str(args.get("reason", "")).strip() or None,
            )
            if not result.get("success"):
                return f"ERROR: rollback failed: {result.get('error', 'unknown')}"
            return (
                f"rollback completed: {result.get('skill_name')}@{result.get('source_name')} "
                f"v{result.get('rolled_back_to_version')}"
            )

        if mode == "provenance":
            skill_name = str(args.get("skill_name", "")).strip()
            if not skill_name:
                return "ERROR: mode=provenance requires skill_name"
            limit = int(args.get("limit", 5))
            result = await engine.provenance(skill_name=skill_name, source_name=source, limit=limit)
            if not result.get("success"):
                return f"ERROR: provenance failed: {result.get('error', 'unknown')}"
            current = result.get("current", {})
            history = result.get("history", [])
            lines = [
                "provenance",
                f"- skill: {current.get('skill_name')}",
                f"- source: {current.get('source_name')}",
                f"- current_version: {current.get('version')}",
                f"- status: {current.get('status')}",
                f"- pinned: {current.get('pinned', False)}",
            ]
            for row in history[:limit]:
                lines.append(
                    f"- {row.get('changed_at', '?')} | v{row.get('version')} | "
                    f"{row.get('change_type', row.get('status', '?'))}"
                )
            return "\n".join(lines)

        return "ERROR: invalid mode. Use check, apply, pin, unpin, rollback, provenance."
