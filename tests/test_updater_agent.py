import pytest

from core.updater import UpdateCheckResult, UpdaterAgent


class _StaticJob:
    def __init__(self, result: UpdateCheckResult, name: str = "job"):
        self.name = name
        self._result = result

    async def check(self) -> UpdateCheckResult:
        return self._result


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
