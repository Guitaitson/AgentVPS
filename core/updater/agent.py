"""
Updater agent orchestration for periodic system updates.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import redis
import structlog

from core.catalog import SkillsCatalogSyncEngine
from core.updater.skills_smoke import ExternalSkillsSmokeRunner

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class UpdateCheckResult:
    """Standard result contract for updater jobs."""

    job_name: str
    success: bool
    trigger_name: str | None = None
    changes_detected: int = 0
    condition_data: dict[str, Any] | None = None
    suggested_action: dict[str, Any] | None = None
    error: str | None = None


class UpdaterJob(Protocol):
    """Contract for update-check jobs."""

    name: str

    async def check(self) -> UpdateCheckResult:
        """Checks if updates are available."""


class SkillsCatalogUpdateJob:
    """Checks and optionally auto-applies updates for external skills catalog sources."""

    name = "skills_catalog"

    def __init__(
        self,
        *,
        approval_required_for_apply: bool,
        source_name: str,
        auto_apply_enabled: bool,
        smoke_enabled: bool,
        auto_rollback_on_failure: bool,
    ):
        self._approval_required_for_apply = bool(approval_required_for_apply)
        self._source_name = str(source_name).strip()
        self._auto_apply_enabled = bool(auto_apply_enabled)
        self._smoke_enabled = bool(smoke_enabled)
        self._auto_rollback_on_failure = bool(auto_rollback_on_failure)
        self._sync_engine = SkillsCatalogSyncEngine()
        self._smoke_runner = ExternalSkillsSmokeRunner()

    @property
    def auto_apply_enabled(self) -> bool:
        return self._auto_apply_enabled and not self._approval_required_for_apply

    async def check(self) -> UpdateCheckResult:
        result = await self._sync_engine.sync(mode="check", source_name=self._source_name)
        if not result.get("success"):
            return UpdateCheckResult(
                job_name=self.name,
                success=False,
                error=str(result.get("error", "unknown_error")),
            )

        changes = int(result.get("changes_detected", 0))
        return UpdateCheckResult(
            job_name=self.name,
            success=True,
            trigger_name="catalog_update_available",
            changes_detected=changes,
            condition_data={
                "source_name": self._source_name,
                "changes_detected": changes,
                "added": result.get("added", 0),
                "updated": result.get("updated", 0),
                "removed": result.get("removed", 0),
                "changed_keys": result.get("changed_keys", []),
            },
            suggested_action={
                "action": "skills_catalog_sync",
                "args": {"mode": "apply", "source": self._source_name},
                "description": "Aplicar atualizacoes detectadas no catalogo de skills",
                "requires_approval": self._approval_required_for_apply,
            },
        )

    async def auto_apply(self, check: UpdateCheckResult) -> dict[str, Any]:
        source_name = str((check.condition_data or {}).get("source_name") or self._source_name)
        apply_result = await self._sync_engine.sync(mode="apply", source_name=source_name)
        if not apply_result.get("success"):
            summary = {
                "job": self.name,
                "status": "auto_apply_failed",
                "source": source_name,
                "error": str(apply_result.get("error", "unknown_error")),
            }
            await self._notify(summary)
            return summary

        changed_keys = [str(key) for key in apply_result.get("changed_keys", [])]
        external_skill_names = [key.split(":", 1)[0] for key in changed_keys]
        smoke_result: dict[str, Any] = {
            "success": True,
            "skipped": True,
            "results": [],
        }
        if self._smoke_enabled:
            smoke_result = await self._smoke_runner.run(external_skill_names)

        summary: dict[str, Any] = {
            "job": self.name,
            "status": "auto_applied",
            "source": source_name,
            "changes": int(apply_result.get("changes_detected", 0)),
            "added": int(apply_result.get("added", 0)),
            "updated": int(apply_result.get("updated", 0)),
            "removed": int(apply_result.get("removed", 0)),
            "changed_keys": changed_keys[:20],
            "smoke": smoke_result,
        }

        if smoke_result.get("success"):
            await self._notify(summary)
            return summary

        summary["status"] = "smoke_failed"
        if self._auto_rollback_on_failure:
            summary["rollback"] = await self._rollback_changed(
                changed_keys, source_name=source_name
            )
            summary["status"] = (
                "auto_rollback_completed"
                if summary["rollback"].get("success")
                else "auto_rollback_failed"
            )

        await self._notify(summary)
        return summary

    async def _rollback_changed(
        self, changed_keys: list[str], *, source_name: str
    ) -> dict[str, Any]:
        rolled_back: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for key in changed_keys:
            skill_name, _, key_source = key.partition(":")
            if key_source and key_source != source_name:
                continue
            result = await self._sync_engine.rollback(
                skill_name=skill_name,
                source_name=source_name,
                actor="updater:auto_rollback",
                reason="smoke failure after auto apply",
            )
            if result.get("success"):
                rolled_back.append(
                    {
                        "skill_name": skill_name,
                        "version": result.get("rolled_back_to_version"),
                    }
                )
            else:
                errors.append(
                    {
                        "skill_name": skill_name,
                        "error": result.get("error", "unknown_error"),
                    }
                )

        return {
            "success": not errors,
            "rolled_back": rolled_back,
            "errors": errors,
        }

    async def _notify(self, summary: dict[str, Any]) -> None:
        try:
            from telegram_bot.bot import send_notification

            lines = [
                "Updater auto-apply",
                f"- job: {summary.get('job')}",
                f"- status: {summary.get('status')}",
                f"- source: {summary.get('source')}",
                f"- changes: {summary.get('changes', 0)}",
            ]
            smoke = summary.get("smoke")
            if isinstance(smoke, dict):
                lines.append(f"- smoke_success: {str(bool(smoke.get('success'))).lower()}")
                for item in smoke.get("results", [])[:3]:
                    lines.append(
                        f"- smoke {item.get('external_skill')}: "
                        f"{'ok' if item.get('success') else item.get('failure_reason')}"
                    )
            rollback = summary.get("rollback")
            if isinstance(rollback, dict):
                lines.append(f"- rollback_success: {str(bool(rollback.get('success'))).lower()}")
                for item in rollback.get("rolled_back", [])[:5]:
                    lines.append(
                        f"- rolled_back {item.get('skill_name')} -> v{item.get('version')}"
                    )
                for item in rollback.get("errors", [])[:5]:
                    lines.append(f"- rollback_error {item.get('skill_name')}: {item.get('error')}")
            if summary.get("error"):
                lines.append(f"- error: {summary.get('error')}")

            await send_notification("\n".join(lines))
        except Exception as exc:  # pragma: no cover - notification is best effort
            logger.error("updater.skills_catalog_notify_failed", error=str(exc))


class ManifestDigestUpdateJob:
    """
    Detects updates by comparing content hash of a manifest file over time.
    """

    _local_state: dict[str, str] = {}

    def __init__(
        self,
        *,
        name: str,
        trigger_name: str,
        manifest_file: str,
        description: str,
        suggested_action: str,
        approval_required: bool = True,
    ):
        self.name = name
        self._trigger_name = trigger_name
        self._manifest_file = manifest_file
        self._description = description
        self._suggested_action = suggested_action
        self._approval_required = bool(approval_required)
        self._redis = self._init_redis_client()

    def _init_redis_client(self):
        try:
            client = redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True,
            )
            client.ping()
            return client
        except Exception:
            return None

    @classmethod
    def reset_local_state_for_tests(cls) -> None:
        cls._local_state = {}

    def _state_key(self) -> str:
        return f"updater:manifest_digest:{self.name}"

    def _read_last_digest(self) -> str | None:
        key = self._state_key()
        if self._redis:
            try:
                value = self._redis.get(key)
                if value:
                    return str(value)
            except Exception:
                pass
        return self._local_state.get(key)

    def _write_last_digest(self, digest: str) -> None:
        key = self._state_key()
        if self._redis:
            try:
                self._redis.set(key, digest)
                return
            except Exception:
                pass
        self._local_state[key] = digest

    def _manifest_digest(self) -> tuple[str, dict[str, Any]]:
        path = Path(self._manifest_file)
        if not path.is_file():
            raise FileNotFoundError(f"manifest_not_found:{path}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return digest, payload

    async def check(self) -> UpdateCheckResult:
        try:
            current_digest, payload = self._manifest_digest()
            previous_digest = self._read_last_digest()
            self._write_last_digest(current_digest)
            changed = bool(previous_digest and previous_digest != current_digest)
            changes = 1 if changed else 0

            return UpdateCheckResult(
                job_name=self.name,
                success=True,
                trigger_name=self._trigger_name,
                changes_detected=changes,
                condition_data={
                    "manifest_file": self._manifest_file,
                    "previous_digest": previous_digest,
                    "current_digest": current_digest,
                    "version": payload.get("version"),
                    "changes_detected": changes,
                },
                suggested_action={
                    "action": self._suggested_action,
                    "args": {"manifest_file": self._manifest_file},
                    "description": self._description,
                    "requires_approval": self._approval_required,
                },
            )
        except Exception as exc:
            return UpdateCheckResult(
                job_name=self.name,
                success=False,
                trigger_name=self._trigger_name,
                error=str(exc),
            )


class ProtocolMappingsUpdateJob(ManifestDigestUpdateJob):
    name = "protocol_mappings"

    def __init__(self):
        super().__init__(
            name=self.name,
            trigger_name="protocol_mappings_update_available",
            manifest_file="configs/updater-protocol-mappings.json",
            description="Revisar e aplicar atualizacao de protocol mappings",
            suggested_action="self_edit",
            approval_required=True,
        )


class PolicyBundleUpdateJob(ManifestDigestUpdateJob):
    name = "policy_bundle"

    def __init__(self):
        super().__init__(
            name=self.name,
            trigger_name="policy_bundle_update_available",
            manifest_file="configs/updater-policy-bundle.json",
            description="Revisar e aplicar atualizacao de policies",
            suggested_action="self_edit",
            approval_required=True,
        )


class RunbookUpdateJob(ManifestDigestUpdateJob):
    name = "runbook_bundle"

    def __init__(self):
        super().__init__(
            name=self.name,
            trigger_name="runbook_update_available",
            manifest_file="configs/updater-runbooks.json",
            description="Revisar e aplicar atualizacao de runbooks operacionais",
            suggested_action="self_edit",
            approval_required=True,
        )


class UpdaterAgent:
    """Runs update jobs and opens proposals when updates are detected."""

    def __init__(self, jobs: list[UpdaterJob]):
        self._jobs = jobs

    async def run_checks(self) -> list[UpdateCheckResult]:
        results: list[UpdateCheckResult] = []
        for job in self._jobs:
            try:
                results.append(await job.check())
            except Exception as exc:  # pragma: no cover - defensive path
                logger.error("updater.job_check_error", job=job.name, error=str(exc))
                results.append(
                    UpdateCheckResult(
                        job_name=job.name,
                        success=False,
                        error=str(exc),
                    )
                )
        return results

    async def check_and_propose(self, engine: Any) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        checks = await self.run_checks()
        for job, check in zip(self._jobs, checks):
            trigger_name = check.trigger_name or f"{check.job_name}_update_available"
            if not check.success:
                summaries.append(
                    {
                        "job": check.job_name,
                        "status": "check_failed",
                        "error": check.error or "unknown_error",
                    }
                )
                continue
            if check.changes_detected <= 0:
                summaries.append(
                    {
                        "job": check.job_name,
                        "status": "up_to_date",
                        "changes": 0,
                    }
                )
                continue
            if hasattr(job, "auto_apply") and getattr(job, "auto_apply_enabled", False):
                summaries.append(await job.auto_apply(check))
                continue
            if engine.has_open_proposal(trigger_name):
                summaries.append(
                    {
                        "job": check.job_name,
                        "status": "proposal_already_open",
                        "changes": check.changes_detected,
                    }
                )
                continue

            await engine.create_proposal(
                trigger_name=trigger_name,
                condition_data=check.condition_data or {},
                suggested_action=check.suggested_action or {},
                priority=4,
            )
            summaries.append(
                {
                    "job": check.job_name,
                    "status": "proposal_created",
                    "changes": check.changes_detected,
                }
            )
        return summaries
