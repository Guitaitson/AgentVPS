"""Voice context ingestion pipeline built on top of AgentVPS memory and proposals."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg2
import structlog
from psycopg2.extras import Json, RealDictCursor

from core.config import get_settings
from core.memory import MemoryScope, MemoryType
from core.vps_langgraph.memory import AgentMemory

from .extraction import SUPPORTED_DOMAINS, VoiceContextExtractor
from .transcription import TranscriptResult, WhisperTranscriber

logger = structlog.get_logger(__name__)

SENSITIVE_DOMAINS = {
    "saude_energia",
    "financas",
    "relacionamentos",
    "valores_proposito",
}


@dataclass(slots=True)
class VoiceContextItemDecision:
    """Decision for one extracted context item."""

    auto_commit: bool
    risk_level: str
    memory_target: str


class VoiceContextService:
    """Coordinates voice ingestion, extraction, memory commit, and review proposals."""

    def __init__(
        self,
        *,
        settings=None,
        memory: AgentMemory | None = None,
        extractor: VoiceContextExtractor | None = None,
        transcriber: WhisperTranscriber | None = None,
    ):
        app_settings = get_settings()
        self.settings = settings or app_settings.voice_context
        self.telegram_settings = app_settings.telegram
        self.memory = memory or AgentMemory()
        self.extractor = extractor or VoiceContextExtractor()
        self.transcriber = transcriber or WhisperTranscriber()
        self._db_config = {
            "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "port": int(os.getenv("POSTGRES_PORT", 5432)),
            "dbname": os.getenv("POSTGRES_DB", "vps_agent"),
            "user": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD"),
        }

    def _get_conn(self):
        return psycopg2.connect(**self._db_config)

    @property
    def supported_extensions(self) -> set[str]:
        raw = self.settings.file_extensions or ""
        return {item.strip().lower() for item in raw.split(",") if item.strip()}

    def ensure_directories(self) -> None:
        for path_str in (
            self.settings.inbox_dir,
            self.settings.processing_dir,
            self.settings.archive_dir,
            self.settings.failed_dir,
            self.settings.transcripts_dir,
        ):
            Path(path_str).mkdir(parents=True, exist_ok=True)

    def resolve_user_id(self, user_id: str | None = None) -> str:
        if user_id:
            return str(user_id)
        if self.settings.user_id:
            return str(self.settings.user_id)
        if self.telegram_settings.allowed_user_ids:
            return str(self.telegram_settings.allowed_user_ids[0])
        return "__global__"

    def list_pending_files(self) -> list[Path]:
        inbox = Path(self.settings.inbox_dir)
        if not inbox.exists():
            return []
        items = []
        for path in inbox.rglob("*"):
            if path.is_file() and path.suffix.lower() in self.supported_extensions:
                items.append(path)
        return sorted(items, key=lambda item: item.stat().st_mtime)

    def has_pending_files(self) -> bool:
        return bool(self.list_pending_files())

    async def sync_inbox(
        self,
        *,
        user_id: str | None = None,
        source: str = "manual",
        max_files: int | None = None,
    ) -> dict[str, Any]:
        self.ensure_directories()
        self.cleanup_expired_transcripts()

        resolved_user_id = self.resolve_user_id(user_id)
        pending = self.list_pending_files()
        limit = max_files or int(self.settings.max_files_per_run)
        selected = pending[: max(1, limit)] if pending else []

        if not selected:
            return {
                "success": True,
                "status": "no_files",
                "processed_files": 0,
                "pending_review": self.count_pending_review(),
                "inbox_files": 0,
            }

        job_id = self._create_job(source=source, batch_date=datetime.utcnow().date().isoformat())
        stats = {
            "processed_files": 0,
            "duplicates_skipped": 0,
            "failed_files": 0,
            "context_items": 0,
            "auto_committed": 0,
            "pending_review": 0,
        }

        try:
            for path in selected:
                file_result = await self._process_one_file(
                    job_id=job_id,
                    source_path=path,
                    user_id=resolved_user_id,
                )
                stats["processed_files"] += 1
                stats["duplicates_skipped"] += int(file_result.get("duplicate", False))
                stats["failed_files"] += int(not file_result.get("success", False))
                stats["context_items"] += int(file_result.get("context_items", 0))
                stats["auto_committed"] += int(file_result.get("auto_committed", 0))
                stats["pending_review"] += int(file_result.get("pending_review", 0))

            self._finish_job(job_id, status="completed", stats=stats)
            status = self.get_status()
            status.update({"success": True, "job_id": job_id, **stats})
            return status
        except Exception as exc:
            logger.error("voice_context.sync_error", error=str(exc), job_id=job_id)
            self._finish_job(job_id, status="failed", stats=stats, error=str(exc))
            return {
                "success": False,
                "status": "failed",
                "job_id": job_id,
                "error": str(exc),
                **stats,
            }

    async def _process_one_file(
        self,
        *,
        job_id: int,
        source_path: Path,
        user_id: str,
    ) -> dict[str, Any]:
        sha256 = self._compute_sha256(source_path)
        if self._sha_already_processed(sha256):
            self._archive_duplicate(source_path, sha256)
            self._record_duplicate_file(job_id=job_id, sha256=sha256, source_path=source_path)
            return {"success": True, "duplicate": True, "context_items": 0}

        processing_path = (
            Path(self.settings.processing_dir) / f"{sha256}{source_path.suffix.lower()}"
        )
        shutil.move(str(source_path), processing_path)
        file_id = self._register_file(
            job_id=job_id,
            sha256=sha256,
            filename=source_path.name,
            status="processing",
        )

        try:
            transcript = self.transcriber.transcribe_file(processing_path)
            force_review = (
                float(transcript.duration_seconds)
                >= float(self.settings.auto_commit_max_duration_minutes) * 60.0
            )
            transcript_path = self._write_transcript(sha256=sha256, transcript=transcript)
            extracted = await self.extractor.extract_structured_context(
                transcript.text,
                source_name=source_path.name,
            )
            items = self._build_context_items(
                extraction=extracted,
                job_id=job_id,
                file_id=file_id,
                batch_date=datetime.utcnow().date().isoformat(),
                transcript_duration_seconds=float(transcript.duration_seconds),
                force_review=force_review,
            )
            commit_stats = self._persist_context_items(
                job_id=job_id,
                file_id=file_id,
                user_id=user_id,
                items=items,
            )
            archive_path = Path(self.settings.archive_dir) / processing_path.name
            shutil.move(str(processing_path), archive_path)
            self._update_file_status(
                file_id=file_id,
                status="completed",
                duration_seconds=transcript.duration_seconds,
                transcript_path=str(transcript_path),
                archive_path=str(archive_path),
                error=("long_audio_force_review" if force_review else None),
            )
            return {"success": True, **commit_stats}
        except Exception as exc:
            failed_path = Path(self.settings.failed_dir) / processing_path.name
            if processing_path.exists():
                shutil.move(str(processing_path), failed_path)
            self._update_file_status(
                file_id=file_id,
                status="failed",
                error=str(exc),
                archive_path=str(failed_path),
            )
            logger.error("voice_context.file_failed", file=str(source_path), error=str(exc))
            return {"success": False, "context_items": 0, "auto_committed": 0, "pending_review": 0}

    def _build_context_items(
        self,
        *,
        extraction: dict[str, Any],
        job_id: int,
        file_id: int,
        batch_date: str,
        transcript_duration_seconds: float,
        force_review: bool,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        summary = str(extraction.get("summary", "")).strip()
        if summary and self.settings.create_daily_summary:
            items.append(
                {
                    "item_type": "summary",
                    "memory_target": MemoryType.EPISODIC.value,
                    "domain": "operacoes_dia_a_dia",
                    "confidence": 0.82,
                    "payload": {
                        "text": summary,
                        "job_id": job_id,
                        "file_id": file_id,
                        "batch_date": batch_date,
                        "transcript_duration_seconds": transcript_duration_seconds,
                        "force_review": force_review,
                    },
                }
            )

        mapping = {
            "episodes": ("episode", MemoryType.EPISODIC.value),
            "facts": ("fact", MemoryType.SEMANTIC.value),
            "preferences": ("preference", MemoryType.PROFILE.value),
            "commitments": ("commitment", MemoryType.GOALS.value),
        }

        for key, (item_type, memory_target) in mapping.items():
            for entry in extraction.get(key, []) or []:
                domain = str(entry.get("domain") or "operacoes_dia_a_dia")
                if domain not in SUPPORTED_DOMAINS:
                    domain = "operacoes_dia_a_dia"
                confidence = max(0.0, min(float(entry.get("confidence", 0.7)), 1.0))
                payload = dict(entry)
                payload.update(
                    {
                        "job_id": job_id,
                        "file_id": file_id,
                        "batch_date": batch_date,
                        "transcript_duration_seconds": transcript_duration_seconds,
                        "force_review": force_review,
                    }
                )
                items.append(
                    {
                        "item_type": item_type,
                        "memory_target": memory_target,
                        "domain": domain,
                        "confidence": confidence,
                        "payload": payload,
                    }
                )
        return items

    def assess_item_decision(self, item: dict[str, Any]) -> VoiceContextItemDecision:
        memory_target = str(item.get("memory_target") or MemoryType.SEMANTIC.value)
        domain = str(item.get("domain") or "operacoes_dia_a_dia")
        confidence = float(item.get("confidence", 0.0))
        payload = item.get("payload") or {}
        force_review = bool(payload.get("force_review"))

        risk_level = "low"
        if memory_target in {MemoryType.PROFILE.value, MemoryType.GOALS.value}:
            risk_level = "medium"
        if domain in SENSITIVE_DOMAINS:
            risk_level = "high"

        auto_commit = (
            memory_target in {MemoryType.EPISODIC.value, MemoryType.SEMANTIC.value}
            and risk_level == "low"
            and confidence >= float(self.settings.auto_commit_threshold)
            and not force_review
        )
        return VoiceContextItemDecision(
            auto_commit=auto_commit,
            risk_level=risk_level,
            memory_target=memory_target,
        )

    def _persist_context_items(
        self,
        *,
        job_id: int,
        file_id: int,
        user_id: str,
        items: list[dict[str, Any]],
    ) -> dict[str, int]:
        if not items:
            return {"context_items": 0, "auto_committed": 0, "pending_review": 0}

        auto_committed = 0
        pending_review = 0
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            for item in items:
                decision = self.assess_item_decision(item)
                item_id = self._insert_context_item(
                    cur,
                    job_id=job_id,
                    file_id=file_id,
                    item=item,
                    risk_level=decision.risk_level,
                )
                conn.commit()
                if decision.auto_commit:
                    self._commit_item(
                        item_id=item_id, user_id=user_id, item=item, actor="voice_context"
                    )
                    auto_committed += 1
                else:
                    proposal_id = self._create_review_proposal(cur, item_id=item_id, item=item)
                    cur.execute(
                        """
                        UPDATE voice_context_items
                        SET commit_status = 'pending_review', proposal_id = %s
                        WHERE id = %s
                        """,
                        (proposal_id, item_id),
                    )
                    conn.commit()
                    pending_review += 1
        finally:
            conn.close()

        return {
            "context_items": len(items),
            "auto_committed": auto_committed,
            "pending_review": pending_review,
        }

    def _insert_context_item(
        self,
        cur,
        *,
        job_id: int,
        file_id: int,
        item: dict[str, Any],
        risk_level: str,
    ) -> int:
        cur.execute(
            """
            INSERT INTO voice_context_items (
                job_id, file_id, item_type, memory_target, domain, risk_level,
                confidence, payload_json, commit_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'extracted')
            RETURNING id
            """,
            (
                job_id,
                file_id,
                item.get("item_type"),
                item.get("memory_target"),
                item.get("domain"),
                risk_level,
                item.get("confidence", 0.0),
                Json(item.get("payload") or {}),
            ),
        )
        return int(cur.fetchone()[0])

    def _create_review_proposal(self, cur, *, item_id: int, item: dict[str, Any]) -> int:
        preview = (
            item.get("payload", {}).get("text")
            or item.get("payload", {}).get("value")
            or item.get("payload", {}).get("evidence")
            or item.get("item_type")
        )
        cur.execute(
            """
            INSERT INTO agent_proposals (
                trigger_name, condition_data, suggested_action, status, priority, requires_approval
            )
            VALUES (%s, %s, %s, 'pending', %s, TRUE)
            RETURNING id
            """,
            (
                "voice_memory_commit",
                Json({"voice_context_item_id": item_id, "domain": item.get("domain")}),
                Json(
                    {
                        "action": "voice_context_sync",
                        "args": {"mode": "commit_review_item", "item_id": item_id},
                        "description": f"Commit voice context item #{item_id}: {str(preview)[:160]}",
                        "requires_approval": True,
                    }
                ),
                4,
            ),
        )
        return int(cur.fetchone()[0])

    def _commit_item(
        self,
        *,
        item_id: int,
        user_id: str,
        item: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        payload = item.get("payload") or {}
        memory_target = MemoryType(str(item.get("memory_target")))
        memory_key = self._memory_key_for_item(item_id=item_id, item=item)

        stored_payload = dict(payload)
        stored_payload.update(
            {
                "source": "voice_context",
                "context_item_id": item_id,
                "committed_by": actor,
                "committed_at": datetime.utcnow().isoformat(),
            }
        )

        self.memory.save_typed_memory(
            user_id=user_id,
            key=memory_key,
            value=stored_payload,
            memory_type=memory_target,
            scope=MemoryScope.USER if memory_target != MemoryType.GOALS else MemoryScope.PROJECT,
            project_id=payload.get("domain") or item.get("domain"),
            confidence=float(item.get("confidence", 0.8)),
            source="voice_context",
        )

        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE voice_context_items
                SET commit_status = 'committed', memory_key = %s, committed_at = NOW()
                WHERE id = %s
                """,
                (memory_key, item_id),
            )
            conn.commit()
        finally:
            conn.close()

        return {"success": True, "memory_key": memory_key}

    def commit_review_item(self, *, item_id: int, actor: str = "system") -> dict[str, Any]:
        row = self.get_context_item(item_id)
        if not row:
            return {"success": False, "error": "item not found"}
        if row.get("commit_status") == "rejected":
            return {"success": False, "error": "item rejected"}
        if row.get("commit_status") == "committed":
            return {"success": True, "memory_key": row.get("memory_key"), "already_committed": True}

        item = {
            "item_type": row.get("item_type"),
            "memory_target": row.get("memory_target"),
            "confidence": row.get("confidence", 0.0),
            "domain": row.get("domain"),
            "payload": row.get("payload_json") or {},
        }
        user_id = self.resolve_user_id()
        result = self._commit_item(item_id=item_id, user_id=user_id, item=item, actor=actor)
        return {"success": True, **result}

    def reject_review_item(
        self,
        *,
        item_id: int,
        actor: str = "system",
        note: str | None = None,
    ) -> dict[str, Any]:
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE voice_context_items
                SET commit_status = 'rejected', review_note = %s
                WHERE id = %s
                """,
                (note or f"rejected by {actor}", item_id),
            )
            updated = cur.rowcount
            conn.commit()
        finally:
            conn.close()
        return {"success": updated > 0, "updated": updated}

    def discard_job(
        self, *, job_id: int, actor: str = "system", note: str | None = None
    ) -> dict[str, Any]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        deleted_memories = 0
        affected_items = 0
        affected_proposals = 0

        try:
            cur.execute(
                """
                SELECT id, memory_target, memory_key, proposal_id
                FROM voice_context_items
                WHERE job_id = %s
                ORDER BY id
                """,
                (job_id,),
            )
            items = cur.fetchall()
            user_id = self.resolve_user_id()

            for item in items:
                memory_key = item.get("memory_key")
                memory_target = item.get("memory_target")
                if memory_key and memory_target:
                    deleted = self.memory.delete_typed_memory(
                        user_id=user_id,
                        key=str(memory_key),
                        memory_type=str(memory_target),
                        scope=(
                            MemoryScope.PROJECT
                            if str(memory_target) == MemoryType.GOALS.value
                            else MemoryScope.USER
                        ),
                    )
                    deleted_memories += int(deleted)

                proposal_id = item.get("proposal_id")
                if proposal_id:
                    cur.execute(
                        """
                        UPDATE agent_proposals
                        SET status = 'rejected'
                        WHERE id = %s AND status = 'pending'
                        """,
                        (proposal_id,),
                    )
                    affected_proposals += cur.rowcount

            review_note = note or f"discarded by {actor}"
            cur.execute(
                """
                UPDATE voice_context_items
                SET commit_status = 'discarded', review_note = %s, memory_key = NULL
                WHERE job_id = %s
                """,
                (review_note, job_id),
            )
            affected_items = cur.rowcount
            cur.execute(
                """
                UPDATE voice_ingestion_jobs
                SET status = 'discarded', error_message = %s
                WHERE id = %s
                """,
                (review_note, job_id),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "success": True,
            "job_id": job_id,
            "discarded_items": affected_items,
            "deleted_memories": deleted_memories,
            "rejected_proposals": affected_proposals,
        }

    def sync_proposal_state(
        self, *, proposal_id: int, decision: str, actor: str = "telegram"
    ) -> dict[str, Any]:
        item = self.get_context_item_by_proposal(proposal_id)
        if not item:
            return {"success": False, "updated": 0}
        if decision == "approved":
            new_status = "approved"
            note = f"approved by {actor}"
        elif decision == "rejected":
            new_status = "rejected"
            note = f"rejected by {actor}"
        else:
            return {"success": False, "updated": 0}

        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE voice_context_items
                SET commit_status = %s, review_note = %s
                WHERE proposal_id = %s
                """,
                (new_status, note, proposal_id),
            )
            updated = cur.rowcount
            conn.commit()
        finally:
            conn.close()
        return {"success": updated > 0, "updated": updated}

    def get_context_item(self, item_id: int) -> dict[str, Any] | None:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SELECT * FROM voice_context_items WHERE id = %s LIMIT 1", (item_id,))
            return cur.fetchone()
        finally:
            conn.close()

    def get_context_item_by_proposal(self, proposal_id: int) -> dict[str, Any] | None:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                "SELECT * FROM voice_context_items WHERE proposal_id = %s LIMIT 1",
                (proposal_id,),
            )
            return cur.fetchone()
        finally:
            conn.close()

    def get_status(self) -> dict[str, Any]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT id, source, batch_date, status, started_at, finished_at, stats_json, error_message
                FROM voice_ingestion_jobs
                ORDER BY id DESC
                LIMIT 1
                """
            )
            last_job = cur.fetchone()
            cur.execute(
                """
                SELECT commit_status, COUNT(*) AS count
                FROM voice_context_items
                GROUP BY commit_status
                """
            )
            grouped = {row["commit_status"]: int(row["count"]) for row in cur.fetchall()}
            inbox_files = len(self.list_pending_files())
            payload = {
                "status": "ok",
                "pending_review": grouped.get("pending_review", 0),
                "approved_review": grouped.get("approved", 0),
                "committed_items": grouped.get("committed", 0),
                "rejected_items": grouped.get("rejected", 0),
                "inbox_files": inbox_files,
            }
            if last_job:
                payload["last_job"] = {
                    "id": last_job.get("id"),
                    "source": last_job.get("source"),
                    "batch_date": str(last_job.get("batch_date")),
                    "status": last_job.get("status"),
                    "started_at": self._to_iso(last_job.get("started_at")),
                    "finished_at": self._to_iso(last_job.get("finished_at")),
                    "stats": last_job.get("stats_json") or {},
                    "error": last_job.get("error_message"),
                }
            return payload
        finally:
            conn.close()

    def count_pending_review(self) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT COUNT(*) FROM voice_context_items WHERE commit_status = 'pending_review'"
            )
            return int(cur.fetchone()[0])
        finally:
            conn.close()

    def cleanup_expired_transcripts(self) -> int:
        transcripts_dir = Path(self.settings.transcripts_dir)
        if not transcripts_dir.exists():
            return 0
        threshold = datetime.utcnow() - timedelta(days=int(self.settings.transcript_ttl_days))
        deleted = 0
        for path in transcripts_dir.glob("*.txt"):
            modified = datetime.utcfromtimestamp(path.stat().st_mtime)
            if modified < threshold:
                path.unlink(missing_ok=True)
                deleted += 1
        return deleted

    def should_run_daily_batch(self, *, now: datetime, last_run_date: str | None) -> bool:
        if not bool(self.settings.enabled):
            return False
        if now.hour < int(self.settings.batch_hour):
            return False
        if last_run_date == now.date().isoformat():
            return False
        return self.has_pending_files()

    def _create_job(self, *, source: str, batch_date: str) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO voice_ingestion_jobs (source, batch_date, status, started_at, stats_json)
                VALUES (%s, %s, 'running', NOW(), %s)
                RETURNING id
                """,
                (source, batch_date, Json({})),
            )
            job_id = int(cur.fetchone()[0])
            conn.commit()
            return job_id
        finally:
            conn.close()

    def _finish_job(
        self, job_id: int, *, status: str, stats: dict[str, Any], error: str | None = None
    ) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE voice_ingestion_jobs
                SET status = %s, finished_at = NOW(), stats_json = %s, error_message = %s
                WHERE id = %s
                """,
                (status, Json(stats), error, job_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _register_file(
        self,
        *,
        job_id: int,
        sha256: str,
        filename: str,
        status: str,
    ) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO voice_audio_files (job_id, sha256, filename, status)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (job_id, sha256, filename, status),
            )
            file_id = int(cur.fetchone()[0])
            conn.commit()
            return file_id
        finally:
            conn.close()

    def _record_duplicate_file(self, *, job_id: int, sha256: str, source_path: Path) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO voice_audio_files (job_id, sha256, filename, status)
                VALUES (%s, %s, %s, 'duplicate')
                ON CONFLICT (sha256) DO NOTHING
                """,
                (job_id, sha256, source_path.name),
            )
            conn.commit()
        finally:
            conn.close()

    def _update_file_status(
        self,
        *,
        file_id: int,
        status: str,
        duration_seconds: float | None = None,
        transcript_path: str | None = None,
        archive_path: str | None = None,
        error: str | None = None,
    ) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE voice_audio_files
                SET status = %s,
                    duration_seconds = COALESCE(%s, duration_seconds),
                    transcript_path = COALESCE(%s, transcript_path),
                    archive_path = COALESCE(%s, archive_path),
                    error = COALESCE(%s, error),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, duration_seconds, transcript_path, archive_path, error, file_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _sha_already_processed(self, sha256: str) -> bool:
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM voice_audio_files
                WHERE sha256 = %s AND status IN ('processing', 'completed', 'duplicate')
                """,
                (sha256,),
            )
            return int(cur.fetchone()[0]) > 0
        finally:
            conn.close()

    def _write_transcript(self, *, sha256: str, transcript: TranscriptResult) -> Path:
        path = Path(self.settings.transcripts_dir) / f"{sha256}.txt"
        lines = [
            f"model={transcript.model}",
            f"language={transcript.language}",
            f"duration_seconds={transcript.duration_seconds}",
            "",
            transcript.text,
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _archive_duplicate(self, source_path: Path, sha256: str) -> None:
        destination = (
            Path(self.settings.archive_dir) / f"duplicate_{sha256}{source_path.suffix.lower()}"
        )
        shutil.move(str(source_path), destination)

    @staticmethod
    def _compute_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _to_iso(value) -> str | None:
        if not value:
            return None
        return value.isoformat()

    @staticmethod
    def _memory_key_for_item(*, item_id: int, item: dict[str, Any]) -> str:
        payload = item.get("payload") or {}
        item_type = str(item.get("item_type") or "voice")
        stable = (
            payload.get("key")
            or payload.get("text")
            or payload.get("value")
            or json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
        )
        digest = hashlib.sha1(str(stable).encode("utf-8")).hexdigest()[:12]
        return f"voice:{item_type}:{item_id}:{digest}"
