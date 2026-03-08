"""
Skill: execute_scheduled

Executes a scheduled task payload and marks task state in PostgreSQL.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg2
import structlog

from core.catalog import SkillsCatalogSyncEngine
from core.skills.base import SkillBase

logger = structlog.get_logger()


class ExecuteScheduledSkill(SkillBase):
    """Executes scheduled task payload actions."""

    async def execute(self, args: dict[str, Any] = None) -> str:
        args = args or {}
        task = args.get("task") or {}
        payload = args.get("payload") or {}
        task_id = task.get("id")

        try:
            message = await self._run_payload_action(payload)
            if task_id is not None:
                self._mark_task_status(int(task_id), status="completed")
            return f"Scheduled task executed: {message}"
        except Exception as exc:
            if task_id is not None:
                self._mark_task_status(int(task_id), status="failed", note=str(exc)[:500])
            logger.error("execute_scheduled_error", task_id=task_id, error=str(exc))
            return f"Failed to execute scheduled task: {str(exc)}"

    async def _run_payload_action(self, payload: dict[str, Any]) -> str:
        action = str(payload.get("action", "")).strip().lower()
        if action == "notify":
            message = str(payload.get("message", "Scheduled notification"))
            from telegram_bot.bot import send_notification

            await send_notification(message)
            return "notification sent"

        if action == "catalog_sync_apply":
            source = payload.get("source")
            source_name = str(source).strip() if source else None
            result = await SkillsCatalogSyncEngine().sync(mode="apply", source_name=source_name)
            if not result.get("success"):
                raise RuntimeError(result.get("error", "catalog sync apply failed"))
            return (
                f"catalog apply done (changes={result.get('changes_detected', 0)}, "
                f"added={result.get('added', 0)}, updated={result.get('updated', 0)}, "
                f"removed={result.get('removed', 0)})"
            )

        if action == "approve_update_proposals":
            limit = int(payload.get("limit", 20))
            include_manual = bool(payload.get("include_requires_approval", False))
            approved = self._approve_update_proposals(limit=limit, include_manual=include_manual)
            return f"approved {approved} update proposal(s)"

        raise ValueError(f"unsupported scheduled action: {action or 'empty'}")

    @staticmethod
    def _get_conn():
        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "vps_agent"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
        )

    def _mark_task_status(self, task_id: int, *, status: str, note: str | None = None) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        if note:
            cur.execute(
                """
                UPDATE scheduled_tasks
                SET status = %s, last_run = NOW(), payload = jsonb_set(payload, '{note}', to_jsonb(%s::text), true)
                WHERE id = %s
                """,
                (status, note, task_id),
            )
        else:
            cur.execute(
                """
                UPDATE scheduled_tasks
                SET status = %s, last_run = NOW()
                WHERE id = %s
                """,
                (status, task_id),
            )
        conn.commit()
        conn.close()

    def _approve_update_proposals(self, *, limit: int, include_manual: bool) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        if include_manual:
            cur.execute(
                """
                WITH target AS (
                    SELECT id
                    FROM agent_proposals
                    WHERE status = 'pending'
                    AND trigger_name LIKE %s
                    ORDER BY priority ASC, created_at ASC
                    LIMIT %s
                )
                UPDATE agent_proposals p
                SET status = 'approved', approval_note = 'Approved by scheduled maintenance window'
                FROM target
                WHERE p.id = target.id
                RETURNING p.id
                """,
                ("%_update_available", limit),
            )
        else:
            cur.execute(
                """
                WITH target AS (
                    SELECT id
                    FROM agent_proposals
                    WHERE status = 'pending'
                    AND trigger_name LIKE %s
                    AND COALESCE(requires_approval, FALSE) = FALSE
                    ORDER BY priority ASC, created_at ASC
                    LIMIT %s
                )
                UPDATE agent_proposals p
                SET status = 'approved', approval_note = 'Approved by scheduled maintenance window'
                FROM target
                WHERE p.id = target.id
                RETURNING p.id
                """,
                ("%_update_available", limit),
            )
        approved = len(cur.fetchall())
        conn.commit()
        conn.close()
        return approved

