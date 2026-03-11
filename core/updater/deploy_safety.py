"""Shared deploy safety snapshot for release and acervo update decisions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import psycopg2


@dataclass(slots=True)
class DeploySafetySnapshot:
    """Current runtime activity that can block disruptive updates."""

    voice_jobs_running: int = 0
    voice_files_processing: int = 0
    running_missions: int = 0
    executing_proposals: int = 0
    running_tasks: int = 0
    manual_blockers: int = 0

    @property
    def blockers(self) -> dict[str, int]:
        return {
            "voice_jobs_running": int(self.voice_jobs_running),
            "voice_files_processing": int(self.voice_files_processing),
            "running_missions": int(self.running_missions),
            "executing_proposals": int(self.executing_proposals),
            "running_tasks": int(self.running_tasks),
            "manual_blockers": int(self.manual_blockers),
        }

    @property
    def safe_to_deploy(self) -> bool:
        return all(value == 0 for value in self.blockers.values())


def collect_deploy_safety_snapshot(*, app_dir: str | None = None) -> DeploySafetySnapshot:
    """Collects live update blockers from DB and runtime filesystem."""

    resolved_app_dir = app_dir or os.getenv("APP_DIR", "/opt/vps-agent")
    blocker_dir = Path(resolved_app_dir) / "runtime" / "deploy-blockers"
    processing_dir = Path(resolved_app_dir) / "data" / "voice" / "processing"

    snapshot = DeploySafetySnapshot(
        voice_files_processing=_count_files(processing_dir),
        manual_blockers=_count_files(blocker_dir),
    )

    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "vps_agent"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
        )
        cur = conn.cursor()
        snapshot.voice_jobs_running = _sql_count(
            cur,
            "SELECT COUNT(*) FROM voice_ingestion_jobs WHERE status = 'running'",
        )
        snapshot.running_missions = _sql_count(
            cur,
            "SELECT COUNT(*) FROM agent_missions WHERE status = 'running'",
        )
        snapshot.executing_proposals = _sql_count(
            cur,
            "SELECT COUNT(*) FROM agent_proposals WHERE status = 'executing'",
        )
        snapshot.running_tasks = _sql_count(
            cur,
            "SELECT COUNT(*) FROM scheduled_tasks WHERE status = 'running'",
        )
    except Exception:
        # Best-effort snapshot. Filesystem blockers still apply.
        return snapshot
    finally:
        if conn is not None:
            conn.close()

    return snapshot


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.iterdir() if item.is_file())


def _sql_count(cur, query: str) -> int:
    try:
        cur.execute(query)
        row = cur.fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0
