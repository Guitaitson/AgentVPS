"""Voice context ingestion pipeline built on top of AgentVPS memory and proposals."""

from __future__ import annotations

import hashlib
import json
import os
import re
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


@dataclass(slots=True)
class TranscriptQualityReport:
    """Heuristic quality signal for one transcript."""

    score: float
    status: str
    reasons: list[str]
    metrics: dict[str, Any]


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
            "discarded_low_quality": 0,
            "context_items": 0,
            "auto_committed": 0,
            "pending_review": 0,
            "committed_targets": {},
            "pending_targets": {},
            "proposal_ids": [],
            "files": [],
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
                stats["discarded_low_quality"] += int(file_result.get("discarded_low_quality", 0))
                stats["context_items"] += int(file_result.get("context_items", 0))
                stats["auto_committed"] += int(file_result.get("auto_committed", 0))
                stats["pending_review"] += int(file_result.get("pending_review", 0))
                self._merge_counter(
                    stats["committed_targets"],
                    file_result.get("committed_targets") or {},
                )
                self._merge_counter(
                    stats["pending_targets"],
                    file_result.get("pending_targets") or {},
                )
                stats["proposal_ids"].extend(file_result.get("proposal_ids") or [])
                report = file_result.get("report")
                if report:
                    stats["files"].append(report)

            self._finish_job(job_id, status="completed", stats=stats)
            status = self.get_status()
            feedback = self.build_job_feedback(job_id=job_id)
            if self.settings.notify_on_job_completion:
                status["notification_sent"] = await self._notify_job_feedback(
                    user_id=resolved_user_id,
                    feedback=feedback,
                )
            status.update({"success": True, "job_id": job_id, "feedback": feedback, **stats})
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
            quality = self.evaluate_transcript_quality(transcript)
            force_review = (
                float(transcript.duration_seconds)
                >= float(self.settings.auto_commit_max_duration_minutes) * 60.0
            ) or quality.score < float(self.settings.quality_warn_score)
            transcript_path = self._write_transcript(sha256=sha256, transcript=transcript)
            if quality.score < float(self.settings.quality_min_score):
                archive_path = Path(self.settings.archive_dir) / processing_path.name
                shutil.move(str(processing_path), archive_path)
                reason = "; ".join(quality.reasons) or "low transcript quality"
                self._update_file_status(
                    file_id=file_id,
                    status="discarded_quality",
                    duration_seconds=transcript.duration_seconds,
                    transcript_path=str(transcript_path),
                    archive_path=str(archive_path),
                    error=f"quality_score={quality.score:.2f}; {reason}",
                )
                return {
                    "success": True,
                    "discarded_low_quality": 1,
                    "context_items": 0,
                    "auto_committed": 0,
                    "pending_review": 0,
                    "report": self._build_file_report(
                        file_name=source_path.name,
                        transcript=transcript,
                        quality=quality,
                        status="discarded_quality",
                        reason=reason,
                    ),
                }
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
                quality=quality,
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
                error=self._file_status_reason(force_review=force_review, quality=quality),
            )
            return {
                "success": True,
                **commit_stats,
                "report": self._build_file_report(
                    file_name=source_path.name,
                    transcript=transcript,
                    quality=quality,
                    status="completed",
                    reason=self._file_status_reason(force_review=force_review, quality=quality),
                    committed_targets=commit_stats.get("committed_targets"),
                    pending_targets=commit_stats.get("pending_targets"),
                ),
            }
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
        quality: TranscriptQualityReport,
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
                        "quality_score": quality.score,
                        "quality_status": quality.status,
                        "quality_reasons": quality.reasons,
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
                        "quality_score": quality.score,
                        "quality_status": quality.status,
                        "quality_reasons": quality.reasons,
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
            return {
                "context_items": 0,
                "auto_committed": 0,
                "pending_review": 0,
                "committed_targets": {},
                "pending_targets": {},
                "proposal_ids": [],
            }

        auto_committed = 0
        pending_review = 0
        committed_targets: dict[str, int] = {}
        pending_targets: dict[str, int] = {}
        proposal_ids: list[int] = []
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
                    target = str(item.get("memory_target") or "unknown")
                    committed_targets[target] = committed_targets.get(target, 0) + 1
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
                    proposal_ids.append(proposal_id)
                    target = str(item.get("memory_target") or "unknown")
                    pending_targets[target] = pending_targets.get(target, 0) + 1
        finally:
            conn.close()

        return {
            "context_items": len(items),
            "auto_committed": auto_committed,
            "pending_review": pending_review,
            "committed_targets": committed_targets,
            "pending_targets": pending_targets,
            "proposal_ids": proposal_ids,
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

    def build_job_feedback(self, *, job_id: int) -> dict[str, Any]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT id, source, status, batch_date, started_at, finished_at, stats_json, error_message
                FROM voice_ingestion_jobs
                WHERE id = %s
                LIMIT 1
                """,
                (job_id,),
            )
            job = cur.fetchone()
            if not job:
                return {"job_id": job_id, "status": "missing"}

            cur.execute(
                """
                SELECT proposal_id
                FROM voice_context_items
                WHERE job_id = %s AND proposal_id IS NOT NULL AND commit_status = 'pending_review'
                ORDER BY proposal_id
                """,
                (job_id,),
            )
            proposal_ids = [int(row["proposal_id"]) for row in cur.fetchall()]

            stats = job.get("stats_json") or {}
            files = stats.get("files") or []
            return {
                "job_id": int(job["id"]),
                "status": str(job.get("status") or "unknown"),
                "source": str(job.get("source") or "unknown"),
                "batch_date": str(job.get("batch_date")),
                "started_at": self._to_iso(job.get("started_at")),
                "finished_at": self._to_iso(job.get("finished_at")),
                "processed_files": int(stats.get("processed_files", 0)),
                "duplicates_skipped": int(stats.get("duplicates_skipped", 0)),
                "failed_files": int(stats.get("failed_files", 0)),
                "discarded_low_quality": int(stats.get("discarded_low_quality", 0)),
                "context_items": int(stats.get("context_items", 0)),
                "auto_committed": int(stats.get("auto_committed", 0)),
                "pending_review": int(stats.get("pending_review", 0)),
                "committed_targets": dict(stats.get("committed_targets") or {}),
                "pending_targets": dict(stats.get("pending_targets") or {}),
                "files": files,
                "proposal_ids": proposal_ids,
                "error": job.get("error_message"),
            }
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
                "discarded_items": grouped.get("discarded", 0),
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
    def _merge_counter(target: dict[str, int], values: dict[str, int]) -> None:
        for key, value in values.items():
            target[str(key)] = target.get(str(key), 0) + int(value)

    def evaluate_transcript_quality(self, transcript: TranscriptResult) -> TranscriptQualityReport:
        body = (transcript.text or "").strip()
        tokens = re.findall(r"\b\w+\b", body.lower(), flags=re.UNICODE)
        alpha_tokens = [token for token in tokens if any(ch.isalpha() for ch in token)]
        lines = [line.strip() for line in body.splitlines() if line.strip()]

        short_ratio = sum(1 for token in alpha_tokens if len(token) <= 2) / max(
            1, len(alpha_tokens)
        )
        unique_ratio = len(set(alpha_tokens)) / max(1, len(alpha_tokens))
        avg_words_per_line = sum(len(re.findall(r"\b\w+\b", line)) for line in lines) / max(
            1, len(lines)
        )

        score = 1.0
        reasons: list[str] = []
        if len(alpha_tokens) < 80:
            score -= 0.2
            reasons.append("pouca fala util detectada")
        if short_ratio > 0.30:
            score -= 0.2
            reasons.append("muitos trechos curtos e fragmentados")
        if unique_ratio < 0.22:
            score -= 0.3
            reasons.append("baixa estabilidade lexical na transcricao")
        if avg_words_per_line < 6.0:
            score -= 0.1
            reasons.append("linhas muito curtas, possivel segmentacao ruidosa")
        if transcript.duration_seconds >= 60 * 60 and unique_ratio < 0.25:
            score -= 0.15
            reasons.append("audio longo com vocabulario pouco consistente")

        score = max(0.0, min(round(score, 2), 1.0))
        if score < float(self.settings.quality_min_score):
            status = "discard"
        elif score < float(self.settings.quality_warn_score):
            status = "warn"
        else:
            status = "good"

        metrics = {
            "alpha_tokens": len(alpha_tokens),
            "short_ratio": round(short_ratio, 3),
            "unique_ratio": round(unique_ratio, 3),
            "avg_words_per_line": round(avg_words_per_line, 2),
            "duration_seconds": round(float(transcript.duration_seconds), 2),
        }
        return TranscriptQualityReport(
            score=score,
            status=status,
            reasons=reasons,
            metrics=metrics,
        )

    def _build_file_report(
        self,
        *,
        file_name: str,
        transcript: TranscriptResult,
        quality: TranscriptQualityReport,
        status: str,
        reason: str | None = None,
        committed_targets: dict[str, int] | None = None,
        pending_targets: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        return {
            "file_name": file_name,
            "status": status,
            "duration_minutes": round(float(transcript.duration_seconds) / 60.0, 1),
            "quality_score": quality.score,
            "quality_status": quality.status,
            "quality_reasons": quality.reasons,
            "reason": reason,
            "committed_targets": dict(committed_targets or {}),
            "pending_targets": dict(pending_targets or {}),
        }

    def _file_status_reason(
        self, *, force_review: bool, quality: TranscriptQualityReport
    ) -> str | None:
        reasons: list[str] = []
        if force_review:
            reasons.append("review_required")
        if quality.status != "good":
            reasons.append(f"quality_{quality.status}:{quality.score:.2f}")
        return "; ".join(reasons) or None

    async def _notify_job_feedback(self, *, user_id: str, feedback: dict[str, Any]) -> bool:
        token = self.telegram_settings.bot_token
        if not token:
            return False
        try:
            chat_id = int(str(user_id))
        except Exception:
            return False

        try:
            from telegram import Bot

            bot = Bot(token=token)
            await bot.send_message(chat_id=chat_id, text=self._format_job_feedback(feedback))
            return True
        except Exception as exc:
            logger.warning("voice_context.feedback_notification_failed", error=str(exc))
            return False

    def _format_job_feedback(self, feedback: dict[str, Any]) -> str:
        lines = [
            f"voice context job #{feedback.get('job_id')}",
            f"- status: {feedback.get('status')}",
            f"- processed_files: {feedback.get('processed_files', 0)}",
            f"- duplicates_skipped: {feedback.get('duplicates_skipped', 0)}",
            f"- discarded_low_quality: {feedback.get('discarded_low_quality', 0)}",
            f"- auto_committed: {feedback.get('auto_committed', 0)}",
            f"- pending_review: {feedback.get('pending_review', 0)}",
        ]
        committed_targets = feedback.get("committed_targets") or {}
        if committed_targets:
            lines.append(f"- memory_committed: {self._format_targets(committed_targets)}")
        pending_targets = feedback.get("pending_targets") or {}
        if pending_targets:
            lines.append(f"- memory_review: {self._format_targets(pending_targets)}")

        files = feedback.get("files") or []
        if files:
            lines.append("")
            lines.append("files:")
            for report in files[:5]:
                lines.append(
                    f"- {report.get('file_name')}: {report.get('status')} | "
                    f"quality={report.get('quality_score', 0):.2f}/{report.get('quality_status')} | "
                    f"duration={report.get('duration_minutes', 0)}m"
                )
                if report.get("reason"):
                    lines.append(f"  disposition: {report.get('reason')}")
                reasons = report.get("quality_reasons") or []
                if reasons:
                    lines.append(f"  reasons: {', '.join(reasons[:3])}")

        proposal_ids = feedback.get("proposal_ids") or []
        if proposal_ids:
            proposal_preview = ", ".join(str(item) for item in proposal_ids[:10])
            lines.extend(
                [
                    "",
                    f"approvals_needed: {proposal_preview}",
                    "use: /approve <id> | /reject <id> | /proposal <id>",
                ]
            )

        if feedback.get("discarded_low_quality", 0) or any(
            (file.get("quality_status") in {"warn", "discard"} for file in files)
        ):
            lines.extend(
                [
                    "",
                    "feedback_needed:",
                    f"- if this lote parece ruim, use /contextdiscard {feedback.get('job_id')}",
                    "- se estiver bom, aprove os itens pendentes que fizerem sentido",
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _format_targets(values: dict[str, int]) -> str:
        return ", ".join(f"{key}={int(value)}" for key, value in sorted(values.items()))

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
