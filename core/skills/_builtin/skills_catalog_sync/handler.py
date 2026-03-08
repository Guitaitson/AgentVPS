"""
Skill: skills_catalog_sync

Runs check/apply sync for external skill catalog sources.
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
        result = await engine.sync(mode=mode, source_name=source)
        if not result.get("success"):
            return f"❌ Falha no sync de catálogo: {result.get('error', 'erro desconhecido')}"

        lines = [
            "📚 Sync de catálogo concluído",
            f"- modo: {result.get('mode')}",
            f"- fontes verificadas: {result.get('sources_checked', 0)}",
            f"- skills descobertas: {result.get('skills_discovered', 0)}",
            f"- mudanças: {result.get('changes_detected', 0)}",
            f"- adicionadas: {result.get('added', 0)}",
            f"- atualizadas: {result.get('updated', 0)}",
            f"- removidas: {result.get('removed', 0)}",
        ]
        changed = result.get("changed_keys", [])
        if changed:
            preview = ", ".join(changed[:10])
            lines.append(f"- exemplos alterados: {preview}")
        return "\n".join(lines)
