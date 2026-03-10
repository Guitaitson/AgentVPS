import pytest

from core.skills._builtin.execute_scheduled.handler import ExecuteScheduledSkill
from core.skills.base import SkillConfig


def _skill() -> ExecuteScheduledSkill:
    return ExecuteScheduledSkill(config=SkillConfig(name="execute_scheduled", description="test"))


@pytest.mark.asyncio
async def test_execute_scheduled_marks_task_completed(monkeypatch):
    skill = _skill()
    called = {"status": None}

    async def _fake_run(_payload):
        return "ok"

    def _fake_mark(_task_id, *, status, note=None):
        called["status"] = status
        called["note"] = note

    monkeypatch.setattr(skill, "_run_payload_action", _fake_run)
    monkeypatch.setattr(skill, "_mark_task_status", _fake_mark)

    output = await skill.execute({"task": {"id": 123}, "payload": {"action": "noop"}})

    assert "Scheduled task executed" in output
    assert called["status"] == "completed"
    assert called["note"] is None


@pytest.mark.asyncio
async def test_execute_scheduled_marks_task_failed_on_exception(monkeypatch):
    skill = _skill()
    called = {"status": None}

    async def _fake_run(_payload):
        raise RuntimeError("boom")

    def _fake_mark(_task_id, *, status, note=None):
        called["status"] = status
        called["note"] = note

    monkeypatch.setattr(skill, "_run_payload_action", _fake_run)
    monkeypatch.setattr(skill, "_mark_task_status", _fake_mark)

    output = await skill.execute({"task": {"id": 123}, "payload": {"action": "noop"}})

    assert output.startswith("Failed to execute scheduled task")
    assert called["status"] == "failed"
    assert called["note"] == "boom"


@pytest.mark.asyncio
async def test_execute_scheduled_rejects_unknown_action():
    skill = _skill()

    with pytest.raises(ValueError):
        await skill._run_payload_action({"action": "not_supported"})


@pytest.mark.asyncio
async def test_execute_scheduled_voice_context_sync(monkeypatch):
    skill = _skill()

    class FakeService:
        async def sync_inbox(self, source="scheduled"):
            return {
                "success": True,
                "processed_files": 1,
                "auto_committed": 2,
                "pending_review": 1,
            }

    monkeypatch.setattr(
        "core.voice_context.VoiceContextService",
        lambda: FakeService(),
    )

    output = await skill._run_payload_action({"action": "voice_context_sync"})

    assert "voice context sync done" in output
