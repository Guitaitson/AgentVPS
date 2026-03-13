"""Skill: voice_context_sync."""

from __future__ import annotations

from typing import Any

from core.skills.base import SkillBase
from core.voice_context import VoiceContextService


class VoiceContextSyncSkill(SkillBase):
    """Processes voice context inbox and review workflow."""

    async def execute(self, args: dict[str, Any] = None) -> str:
        args = args or {}
        mode = str(args.get("mode", "sync")).strip().lower()
        service = VoiceContextService()

        if mode == "sync":
            max_files = args.get("max_files")
            result = await service.sync_inbox(
                source=str(args.get("source", "skill")),
                max_files=int(max_files) if max_files is not None else None,
            )
            if not result.get("success"):
                return f"ERROR: voice context sync failed: {result.get('error', 'unknown')}"
            return (
                "voice context sync\n"
                f"- status: {result.get('status', 'ok')}\n"
                f"- requested_max_files: {max_files if max_files is not None else 'default'}\n"
                f"- processed_files: {result.get('processed_files', 0)}\n"
                f"- duplicates_skipped: {result.get('duplicates_skipped', 0)}\n"
                f"- failed_files: {result.get('failed_files', 0)}\n"
                f"- discarded_low_quality: {result.get('discarded_low_quality', 0)}\n"
                f"- context_items: {result.get('context_items', 0)}\n"
                f"- auto_committed: {result.get('auto_committed', 0)}\n"
                f"- pending_review: {result.get('pending_review', 0)}"
            )

        if mode == "status":
            result = service.get_status()
            last_job = result.get("last_job") or {}
            return (
                "voice context status\n"
                f"- inbox_files: {result.get('inbox_files', 0)}\n"
                f"- pending_review: {result.get('pending_review', 0)}\n"
                f"- approved_review: {result.get('approved_review', 0)}\n"
                f"- committed_items: {result.get('committed_items', 0)}\n"
                f"- discarded_items: {result.get('discarded_items', 0)}\n"
                f"- last_job_id: {last_job.get('id', '-')}\n"
                f"- last_job_status: {last_job.get('status', '-')}"
            )

        if mode == "commit_review_item":
            item_id = int(args.get("item_id", 0))
            result = service.commit_review_item(
                item_id=item_id,
                actor=str(args.get("actor", "voice_context_sync")),
            )
            if not result.get("success"):
                return f"ERROR: commit failed: {result.get('error', 'unknown')}"
            return f"voice context item committed: {item_id} ({result.get('memory_key', '-')})"

        if mode == "reject_review_item":
            item_id = int(args.get("item_id", 0))
            result = service.reject_review_item(
                item_id=item_id,
                actor=str(args.get("actor", "voice_context_sync")),
                note=str(args.get("note", "")).strip() or None,
            )
            if not result.get("success"):
                return "ERROR: reject failed"
            return f"voice context item rejected: {item_id}"

        if mode == "discard_job":
            job_id = int(args.get("job_id", 0))
            result = service.discard_job(
                job_id=job_id,
                actor=str(args.get("actor", "voice_context_sync")),
                note=str(args.get("note", "")).strip() or None,
            )
            if not result.get("success"):
                return "ERROR: discard failed"
            return (
                f"voice context job discarded: {job_id} "
                f"(items={result.get('discarded_items', 0)}, "
                f"memories={result.get('deleted_memories', 0)}, "
                f"proposals={result.get('rejected_proposals', 0)})"
            )

        return "ERROR: invalid mode. Use sync, status, commit_review_item, reject_review_item or discard_job."
