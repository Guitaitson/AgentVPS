"""
Soul manager: versioned identity artifacts + approval workflow.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import Any

import psycopg2
import structlog
from psycopg2.extras import Json, RealDictCursor

from core.config import get_settings
from core.env import load_project_env

load_project_env()
logger = structlog.get_logger(__name__)


class SoulArtifactType(str, Enum):
    CORE_IDENTITY = "core_identity"
    PERSONAL_VOICE = "personal_voice"
    BEHAVIOR_CONTRACT = "behavior_contract"


class SoulImpactLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(slots=True)
class SoulArtifact:
    artifact_type: SoulArtifactType
    version: int
    content: str
    metadata: dict[str, Any]
    created_by: str
    created_at: str


@dataclass(slots=True)
class SoulChangeProposal:
    proposal_id: int
    artifact_type: SoulArtifactType
    proposed_content: str
    rationale: str
    impact_level: SoulImpactLevel
    requires_approval: bool
    status: str
    requested_by: str
    reviewer: str | None
    review_note: str | None
    created_at: str
    reviewed_at: str | None = None
    applied_at: str | None = None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_soul(owner_name: str) -> dict[SoulArtifactType, SoulArtifact]:
    now = _utcnow()
    return {
        SoulArtifactType.CORE_IDENTITY: SoulArtifact(
            artifact_type=SoulArtifactType.CORE_IDENTITY,
            version=1,
            content=(
                f"Voce e o VPS-Agent, criado por {owner_name}, orquestrador soberano de memoria, "
                "politicas e execucao de ferramentas."
            ),
            metadata={"immutable": True},
            created_by="system_bootstrap",
            created_at=now,
        ),
        SoulArtifactType.PERSONAL_VOICE: SoulArtifact(
            artifact_type=SoulArtifactType.PERSONAL_VOICE,
            version=1,
            content="Responda em portugues brasileiro, de forma direta, tecnica e pragmatica.",
            metadata={"tone": "direct"},
            created_by="system_bootstrap",
            created_at=now,
        ),
        SoulArtifactType.BEHAVIOR_CONTRACT: SoulArtifact(
            artifact_type=SoulArtifactType.BEHAVIOR_CONTRACT,
            version=1,
            content=(
                "Antes de planos complexos ou decisoes de alto impacto, desafie premissas frageis, "
                "explique riscos tecnicos e proponha alternativa mais segura."
            ),
            metadata={"challenge_mode": True},
            created_by="system_bootstrap",
            created_at=now,
        ),
    }


class SoulManager:
    """Manages versioned identity artifacts with proposal/approval workflow."""

    def __init__(self):
        settings = get_settings()
        self._challenge_mode_enabled = settings.identity.challenge_mode_enabled
        self._owner_name = settings.identity.owner_name
        self._db_config = {
            "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "port": int(os.getenv("POSTGRES_PORT", 5432)),
            "dbname": os.getenv("POSTGRES_DB", "vps_agent"),
            "user": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD"),
        }
        self._local_artifacts = _default_soul(owner_name=self._owner_name)
        self._local_proposals: dict[int, SoulChangeProposal] = {}
        self._local_proposal_seq = 0

    def _get_conn(self):
        return psycopg2.connect(**self._db_config)

    @property
    def challenge_mode_enabled(self) -> bool:
        return self._challenge_mode_enabled

    def get_artifact(self, artifact_type: SoulArtifactType) -> SoulArtifact:
        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT artifact_type, version, content, metadata, created_by, created_at
                FROM agent_soul_artifacts
                WHERE artifact_type = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (artifact_type.value,),
            )
            row = cur.fetchone()
            conn.close()
            if row:
                return SoulArtifact(
                    artifact_type=SoulArtifactType(row["artifact_type"]),
                    version=int(row["version"]),
                    content=row["content"],
                    metadata=row.get("metadata") or {},
                    created_by=row.get("created_by") or "unknown",
                    created_at=row["created_at"].isoformat()
                    if row.get("created_at")
                    else _utcnow(),
                )
        except Exception as exc:
            logger.debug("soul.get_artifact_fallback_local", error=str(exc))
        return self._local_artifacts[artifact_type]

    def get_all_artifacts(self) -> dict[SoulArtifactType, SoulArtifact]:
        return {
            artifact_type: self.get_artifact(artifact_type) for artifact_type in SoulArtifactType
        }

    def propose_change(
        self,
        *,
        artifact_type: SoulArtifactType | str,
        proposed_content: str,
        rationale: str,
        requested_by: str = "system",
        impact_level: SoulImpactLevel | str = SoulImpactLevel.MEDIUM,
    ) -> SoulChangeProposal:
        if isinstance(artifact_type, str):
            artifact_type = SoulArtifactType(artifact_type)
        if isinstance(impact_level, str):
            impact_level = SoulImpactLevel(impact_level)

        requires_approval = impact_level == SoulImpactLevel.HIGH or artifact_type in {
            SoulArtifactType.CORE_IDENTITY,
            SoulArtifactType.BEHAVIOR_CONTRACT,
        }
        created_at = _utcnow()

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                INSERT INTO agent_soul_change_proposals (
                    artifact_type, proposed_content, rationale, impact_level,
                    requires_approval, status, requested_by, created_at
                )
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, NOW())
                RETURNING id, created_at
                """,
                (
                    artifact_type.value,
                    proposed_content,
                    rationale,
                    impact_level.value,
                    requires_approval,
                    requested_by,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            conn.close()
            proposal_id = int(row["id"])
            created_at = row["created_at"].isoformat()
        except Exception as exc:
            logger.warning("soul.propose_fallback_local", error=str(exc))
            self._local_proposal_seq += 1
            proposal_id = self._local_proposal_seq

        proposal = SoulChangeProposal(
            proposal_id=proposal_id,
            artifact_type=artifact_type,
            proposed_content=proposed_content,
            rationale=rationale,
            impact_level=impact_level,
            requires_approval=requires_approval,
            status="pending",
            requested_by=requested_by,
            reviewer=None,
            review_note=None,
            created_at=created_at,
        )
        self._local_proposals[proposal.proposal_id] = proposal
        return proposal

    def approve_proposal(
        self,
        proposal_id: int,
        *,
        reviewer: str,
        review_note: str | None = None,
    ) -> bool:
        proposal = self._local_proposals.get(proposal_id)
        if not proposal:
            proposal = self._load_proposal_from_db(proposal_id)
            if not proposal:
                return False

        proposal.status = "approved"
        proposal.reviewer = reviewer
        proposal.review_note = review_note
        proposal.reviewed_at = _utcnow()

        applied = self._apply_artifact_change(proposal, created_by=reviewer)
        if not applied:
            return False
        proposal.status = "applied"
        proposal.applied_at = _utcnow()
        self._local_proposals[proposal_id] = proposal
        self._sync_proposal_to_db(proposal)
        return True

    def reject_proposal(self, proposal_id: int, *, reviewer: str, review_note: str) -> bool:
        proposal = self._local_proposals.get(proposal_id)
        if not proposal:
            proposal = self._load_proposal_from_db(proposal_id)
            if not proposal:
                return False

        proposal.status = "rejected"
        proposal.reviewer = reviewer
        proposal.review_note = review_note
        proposal.reviewed_at = _utcnow()
        self._local_proposals[proposal_id] = proposal
        self._sync_proposal_to_db(proposal)
        return True

    def list_pending_proposals(self, limit: int = 20) -> list[SoulChangeProposal]:
        local_pending = [
            proposal for proposal in self._local_proposals.values() if proposal.status == "pending"
        ]
        if local_pending:
            return sorted(local_pending, key=lambda proposal: proposal.proposal_id, reverse=True)[
                :limit
            ]

        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, artifact_type, proposed_content, rationale, impact_level,
                       requires_approval, status, requested_by, reviewer, review_note,
                       created_at, reviewed_at, applied_at
                FROM agent_soul_change_proposals
                WHERE status = 'pending'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            conn.close()
            proposals = [self._row_to_proposal(row) for row in rows]
            for proposal in proposals:
                self._local_proposals[proposal.proposal_id] = proposal
            return proposals
        except Exception:
            return []

    def render_prompt_extensions(self) -> str:
        artifacts = self.get_all_artifacts()
        challenge_mode = self.challenge_mode_enabled
        behavior_metadata = artifacts[SoulArtifactType.BEHAVIOR_CONTRACT].metadata or {}
        if "challenge_mode" in behavior_metadata:
            challenge_mode = bool(behavior_metadata.get("challenge_mode"))

        parts = [
            "## Alma Versionada",
            f"- Core Identity v{artifacts[SoulArtifactType.CORE_IDENTITY].version}: {artifacts[SoulArtifactType.CORE_IDENTITY].content}",
            f"- Personal Voice v{artifacts[SoulArtifactType.PERSONAL_VOICE].version}: {artifacts[SoulArtifactType.PERSONAL_VOICE].content}",
            f"- Behavior Contract v{artifacts[SoulArtifactType.BEHAVIOR_CONTRACT].version}: {artifacts[SoulArtifactType.BEHAVIOR_CONTRACT].content}",
        ]
        if challenge_mode:
            parts.extend(
                [
                    "## Challenge Mode (Ativo)",
                    "- Antes de executar planos complexos, desafie premissas tecnicamente frageis.",
                    "- Aponte riscos e tradeoffs com objetividade.",
                    "- Proponha alternativa mais segura quando houver fragilidade arquitetural.",
                ]
            )
        return "\n".join(parts)

    def render_condensed_identity_extension(self) -> str:
        if not self.challenge_mode_enabled:
            return ""
        return (
            " Challenge mode ativo: questione premissas frageis em planos complexos "
            "antes de executar."
        )

    def _apply_artifact_change(self, proposal: SoulChangeProposal, created_by: str) -> bool:
        current = self.get_artifact(proposal.artifact_type)
        new_version = current.version + 1
        now = _utcnow()
        artifact = SoulArtifact(
            artifact_type=proposal.artifact_type,
            version=new_version,
            content=proposal.proposed_content,
            metadata={
                "from_proposal_id": proposal.proposal_id,
                "impact": proposal.impact_level.value,
            },
            created_by=created_by,
            created_at=now,
        )
        self._local_artifacts[proposal.artifact_type] = artifact

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO agent_soul_artifacts (artifact_type, version, content, metadata, created_by)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    artifact.artifact_type.value,
                    artifact.version,
                    artifact.content,
                    Json(artifact.metadata),
                    artifact.created_by,
                ),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as exc:
            logger.warning("soul.apply_change_fallback_local", error=str(exc))
            return True

    def _load_proposal_from_db(self, proposal_id: int) -> SoulChangeProposal | None:
        try:
            conn = self._get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, artifact_type, proposed_content, rationale, impact_level,
                       requires_approval, status, requested_by, reviewer, review_note,
                       created_at, reviewed_at, applied_at
                FROM agent_soul_change_proposals
                WHERE id = %s
                """,
                (proposal_id,),
            )
            row = cur.fetchone()
            conn.close()
            if not row:
                return None
            proposal = self._row_to_proposal(row)
            self._local_proposals[proposal.proposal_id] = proposal
            return proposal
        except Exception:
            return None

    def _sync_proposal_to_db(self, proposal: SoulChangeProposal) -> None:
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE agent_soul_change_proposals
                SET status = %s,
                    reviewer = %s,
                    review_note = %s,
                    reviewed_at = %s,
                    applied_at = %s
                WHERE id = %s
                """,
                (
                    proposal.status,
                    proposal.reviewer,
                    proposal.review_note,
                    proposal.reviewed_at,
                    proposal.applied_at,
                    proposal.proposal_id,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("soul.sync_proposal_db_skipped", error=str(exc))

    @staticmethod
    def _row_to_proposal(row: dict[str, Any]) -> SoulChangeProposal:
        return SoulChangeProposal(
            proposal_id=int(row["id"]),
            artifact_type=SoulArtifactType(row["artifact_type"]),
            proposed_content=row["proposed_content"],
            rationale=row["rationale"],
            impact_level=SoulImpactLevel(row.get("impact_level", SoulImpactLevel.MEDIUM.value)),
            requires_approval=bool(row.get("requires_approval", True)),
            status=row.get("status", "pending"),
            requested_by=row.get("requested_by", "unknown"),
            reviewer=row.get("reviewer"),
            review_note=row.get("review_note"),
            created_at=row["created_at"].isoformat() if row.get("created_at") else _utcnow(),
            reviewed_at=row["reviewed_at"].isoformat() if row.get("reviewed_at") else None,
            applied_at=row["applied_at"].isoformat() if row.get("applied_at") else None,
        )

    def export_state(self) -> dict[str, Any]:
        return {
            "artifacts": {
                artifact_type.value: asdict(artifact)
                for artifact_type, artifact in self.get_all_artifacts().items()
            },
            "pending_proposals": [asdict(proposal) for proposal in self.list_pending_proposals()],
        }


@lru_cache(maxsize=1)
def get_soul_manager() -> SoulManager:
    return SoulManager()
