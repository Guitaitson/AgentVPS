import json

import pytest

from core.updater import UpdaterAgent
from core.updater.agent import ManifestDigestUpdateJob


class _FakeEngine:
    def __init__(self):
        self.created: list[dict] = []

    def has_open_proposal(self, trigger_name: str) -> bool:  # noqa: ARG002
        return False

    async def create_proposal(
        self, trigger_name: str, condition_data: dict, suggested_action: dict, priority: int = 5
    ) -> int:
        self.created.append(
            {
                "trigger_name": trigger_name,
                "condition_data": condition_data,
                "suggested_action": suggested_action,
                "priority": priority,
            }
        )
        return 1


@pytest.mark.asyncio
async def test_manifest_job_first_run_sets_baseline_without_changes(tmp_path, monkeypatch):
    manifest = tmp_path / "bundle.json"
    manifest.write_text(json.dumps({"version": "1", "items": [{"name": "a"}]}), encoding="utf-8")

    ManifestDigestUpdateJob.reset_local_state_for_tests()
    monkeypatch.setattr(ManifestDigestUpdateJob, "_init_redis_client", lambda self: None)
    job = ManifestDigestUpdateJob(
        name="test_bundle",
        trigger_name="test_bundle_update_available",
        manifest_file=str(manifest),
        description="Teste",
        suggested_action="self_edit",
        approval_required=True,
    )

    result = await job.check()

    assert result.success is True
    assert result.changes_detected == 0
    assert result.trigger_name == "test_bundle_update_available"


@pytest.mark.asyncio
async def test_manifest_job_detects_change_and_creates_proposal(tmp_path, monkeypatch):
    manifest = tmp_path / "bundle.json"
    manifest.write_text(json.dumps({"version": "1", "items": [{"name": "a"}]}), encoding="utf-8")

    ManifestDigestUpdateJob.reset_local_state_for_tests()
    monkeypatch.setattr(ManifestDigestUpdateJob, "_init_redis_client", lambda self: None)
    job = ManifestDigestUpdateJob(
        name="test_bundle",
        trigger_name="test_bundle_update_available",
        manifest_file=str(manifest),
        description="Teste",
        suggested_action="self_edit",
        approval_required=True,
    )

    # Baseline
    first = await job.check()
    assert first.changes_detected == 0

    # Change detected
    manifest.write_text(json.dumps({"version": "2", "items": [{"name": "a"}, {"name": "b"}]}), encoding="utf-8")
    agent = UpdaterAgent(jobs=[job])
    engine = _FakeEngine()
    summary = await agent.check_and_propose(engine)

    assert summary[0]["status"] == "proposal_created"
    assert summary[0]["changes"] == 1
    assert len(engine.created) == 1
    assert engine.created[0]["trigger_name"] == "test_bundle_update_available"
