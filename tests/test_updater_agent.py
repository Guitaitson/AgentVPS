import pytest

from core.updater import SkillsCatalogUpdateJob, UpdateCheckResult, UpdaterAgent


class _StaticJob:
    def __init__(self, result: UpdateCheckResult, name: str = "job"):
        self.name = name
        self._result = result

    async def check(self) -> UpdateCheckResult:
        return self._result


class _AutoApplyJob(_StaticJob):
    auto_apply_enabled = True

    def __init__(self, result: UpdateCheckResult, summary: dict, name: str = "skills_catalog"):
        super().__init__(result, name=name)
        self._summary = summary

    async def auto_apply(self, check: UpdateCheckResult) -> dict:
        assert check is self._result
        return self._summary


class _FakeEngine:
    def __init__(self, has_open: bool = False):
        self._has_open = has_open
        self.created: list[dict] = []

    def has_open_proposal(self, trigger_name: str) -> bool:
        return self._has_open

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
async def test_updater_agent_creates_proposal_when_changes_detected():
    result = UpdateCheckResult(
        job_name="skills_catalog",
        trigger_name="catalog_update_available",
        success=True,
        changes_detected=3,
        condition_data={"added": 1},
        suggested_action={"action": "skills_catalog_sync"},
    )
    agent = UpdaterAgent(jobs=[_StaticJob(result, name="skills_catalog")])
    engine = _FakeEngine(has_open=False)

    summary = await agent.check_and_propose(engine)

    assert summary[0]["status"] == "proposal_created"
    assert len(engine.created) == 1
    assert engine.created[0]["trigger_name"] == "catalog_update_available"


@pytest.mark.asyncio
async def test_updater_agent_auto_applies_when_job_is_eligible():
    result = UpdateCheckResult(
        job_name="skills_catalog",
        trigger_name="catalog_update_available",
        success=True,
        changes_detected=2,
    )
    job = _AutoApplyJob(result, {"job": "skills_catalog", "status": "auto_applied"})
    agent = UpdaterAgent(jobs=[job])
    engine = _FakeEngine(has_open=False)

    summary = await agent.check_and_propose(engine)

    assert summary == [{"job": "skills_catalog", "status": "auto_applied"}]
    assert engine.created == []


@pytest.mark.asyncio
async def test_updater_agent_skips_when_proposal_already_open():
    result = UpdateCheckResult(
        job_name="skills_catalog",
        trigger_name="catalog_update_available",
        success=True,
        changes_detected=2,
    )
    agent = UpdaterAgent(jobs=[_StaticJob(result, name="skills_catalog")])
    engine = _FakeEngine(has_open=True)

    summary = await agent.check_and_propose(engine)

    assert summary[0]["status"] == "proposal_already_open"
    assert engine.created == []


@pytest.mark.asyncio
async def test_updater_agent_reports_failed_check():
    result = UpdateCheckResult(
        job_name="skills_catalog",
        success=False,
        error="network_error",
    )
    agent = UpdaterAgent(jobs=[_StaticJob(result, name="skills_catalog")])
    engine = _FakeEngine(has_open=False)

    summary = await agent.check_and_propose(engine)

    assert summary[0]["status"] == "check_failed"
    assert summary[0]["error"] == "network_error"
    assert engine.created == []


@pytest.mark.asyncio
async def test_skills_catalog_job_check_targets_live_source(monkeypatch):
    captured = {}

    async def fake_sync(self, *, mode="check", source_name=None):
        captured["mode"] = mode
        captured["source_name"] = source_name
        return {
            "success": True,
            "changes_detected": 1,
            "added": 1,
            "updated": 0,
            "removed": 0,
            "changed_keys": ["fleetintel-orchestrator:fleetintel_skillpack_repo"],
        }

    monkeypatch.setattr("core.updater.agent.SkillsCatalogSyncEngine.sync", fake_sync)

    job = SkillsCatalogUpdateJob(
        approval_required_for_apply=False,
        source_name="fleetintel_skillpack_repo",
        auto_apply_enabled=True,
        smoke_enabled=True,
        auto_rollback_on_failure=True,
    )

    result = await job.check()

    assert captured == {"mode": "check", "source_name": "fleetintel_skillpack_repo"}
    assert result.condition_data["source_name"] == "fleetintel_skillpack_repo"
    assert result.suggested_action["args"] == {
        "mode": "apply",
        "source": "fleetintel_skillpack_repo",
    }


@pytest.mark.asyncio
async def test_skills_catalog_job_auto_apply_smoke_success(monkeypatch):
    async def fake_sync(self, *, mode="check", source_name=None):
        assert mode == "apply"
        return {
            "success": True,
            "changes_detected": 2,
            "added": 0,
            "updated": 2,
            "removed": 0,
            "changed_keys": [
                "fleetintel-orchestrator:fleetintel_skillpack_repo",
                "brazilcnpj-enricher:fleetintel_skillpack_repo",
            ],
        }

    async def fake_smoke(self, external_skill_names):
        assert sorted(external_skill_names) == ["brazilcnpj-enricher", "fleetintel-orchestrator"]
        return {"success": True, "skipped": False, "results": []}

    async def fake_notify(self, summary):
        summary["notified"] = True

    monkeypatch.setattr("core.updater.agent.SkillsCatalogSyncEngine.sync", fake_sync)
    monkeypatch.setattr("core.updater.agent.ExternalSkillsSmokeRunner.run", fake_smoke)
    monkeypatch.setattr("core.updater.agent.SkillsCatalogUpdateJob._notify", fake_notify)

    job = SkillsCatalogUpdateJob(
        approval_required_for_apply=False,
        source_name="fleetintel_skillpack_repo",
        auto_apply_enabled=True,
        smoke_enabled=True,
        auto_rollback_on_failure=True,
    )
    check = UpdateCheckResult(
        job_name="skills_catalog",
        success=True,
        changes_detected=2,
        condition_data={"source_name": "fleetintel_skillpack_repo"},
    )

    summary = await job.auto_apply(check)

    assert summary["status"] == "auto_applied"
    assert summary["smoke"]["success"] is True


@pytest.mark.asyncio
async def test_skills_catalog_job_auto_apply_rolls_back_when_smoke_fails(monkeypatch):
    async def fake_sync(self, *, mode="check", source_name=None):
        assert mode == "apply"
        return {
            "success": True,
            "changes_detected": 1,
            "added": 0,
            "updated": 1,
            "removed": 0,
            "changed_keys": ["fleetintel-orchestrator:fleetintel_skillpack_repo"],
        }

    async def fake_smoke(self, external_skill_names):
        return {
            "success": False,
            "skipped": False,
            "results": [
                {
                    "external_skill": "fleetintel-orchestrator",
                    "success": False,
                    "failure_reason": "missing_marker:Operacao FleetIntel: status=",
                }
            ],
        }

    async def fake_rollback(
        self, *, skill_name, source_name=None, actor=None, reason=None, target_version=None
    ):
        assert skill_name == "fleetintel-orchestrator"
        assert source_name == "fleetintel_skillpack_repo"
        return {
            "success": True,
            "skill_name": skill_name,
            "rolled_back_to_version": "1.2.3",
        }

    async def fake_notify(self, summary):
        summary["notified"] = True

    monkeypatch.setattr("core.updater.agent.SkillsCatalogSyncEngine.sync", fake_sync)
    monkeypatch.setattr("core.updater.agent.ExternalSkillsSmokeRunner.run", fake_smoke)
    monkeypatch.setattr("core.updater.agent.SkillsCatalogSyncEngine.rollback", fake_rollback)
    monkeypatch.setattr("core.updater.agent.SkillsCatalogUpdateJob._notify", fake_notify)

    job = SkillsCatalogUpdateJob(
        approval_required_for_apply=False,
        source_name="fleetintel_skillpack_repo",
        auto_apply_enabled=True,
        smoke_enabled=True,
        auto_rollback_on_failure=True,
    )
    check = UpdateCheckResult(
        job_name="skills_catalog",
        success=True,
        changes_detected=1,
        condition_data={"source_name": "fleetintel_skillpack_repo"},
    )

    summary = await job.auto_apply(check)

    assert summary["status"] == "auto_rollback_completed"
    assert summary["rollback"]["success"] is True
    assert summary["rollback"]["rolled_back"][0]["version"] == "1.2.3"
