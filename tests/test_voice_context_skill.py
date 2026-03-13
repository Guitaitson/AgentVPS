import pytest

from core.skills._builtin.voice_context_sync.handler import VoiceContextSyncSkill
from core.skills.base import SkillConfig


@pytest.mark.asyncio
async def test_voice_context_sync_skill_runs_sync(monkeypatch):
    class FakeService:
        async def sync_inbox(self, source="skill", max_files=None):
            return {
                "success": True,
                "status": "ok",
                "processed_files": 2,
                "duplicates_skipped": 1,
                "failed_files": 0,
                "context_items": 5,
                "auto_committed": 3,
                "pending_review": 2,
            }

    monkeypatch.setattr(
        "core.skills._builtin.voice_context_sync.handler.VoiceContextService",
        lambda: FakeService(),
    )
    skill = VoiceContextSyncSkill(config=SkillConfig(name="voice_context_sync", description="test"))

    output = await skill.execute({"mode": "sync"})

    assert "voice context sync" in output
    assert "processed_files: 2" in output


@pytest.mark.asyncio
async def test_voice_context_sync_skill_commits_item(monkeypatch):
    class FakeService:
        def commit_review_item(self, *, item_id, actor="x"):
            return {"success": True, "memory_key": f"voice:item:{item_id}"}

    monkeypatch.setattr(
        "core.skills._builtin.voice_context_sync.handler.VoiceContextService",
        lambda: FakeService(),
    )
    skill = VoiceContextSyncSkill(config=SkillConfig(name="voice_context_sync", description="test"))

    output = await skill.execute({"mode": "commit_review_item", "item_id": 7})

    assert "voice context item committed: 7" in output


@pytest.mark.asyncio
async def test_voice_context_sync_skill_discards_job(monkeypatch):
    class FakeService:
        def discard_job(self, *, job_id, actor="x", note=None):
            return {
                "success": True,
                "discarded_items": 5,
                "deleted_memories": 2,
                "rejected_proposals": 3,
            }

    monkeypatch.setattr(
        "core.skills._builtin.voice_context_sync.handler.VoiceContextService",
        lambda: FakeService(),
    )
    skill = VoiceContextSyncSkill(config=SkillConfig(name="voice_context_sync", description="test"))

    output = await skill.execute({"mode": "discard_job", "job_id": 2})

    assert "voice context job discarded: 2" in output


@pytest.mark.asyncio
async def test_voice_context_sync_skill_reports_low_quality_count(monkeypatch):
    class FakeService:
        async def sync_inbox(self, source="skill", max_files=None):
            return {
                "success": True,
                "status": "ok",
                "processed_files": 1,
                "duplicates_skipped": 0,
                "failed_files": 0,
                "discarded_low_quality": 1,
                "context_items": 0,
                "auto_committed": 0,
                "pending_review": 0,
            }

    monkeypatch.setattr(
        "core.skills._builtin.voice_context_sync.handler.VoiceContextService",
        lambda: FakeService(),
    )
    skill = VoiceContextSyncSkill(config=SkillConfig(name="voice_context_sync", description="test"))

    output = await skill.execute({"mode": "sync"})

    assert "discarded_low_quality: 1" in output


@pytest.mark.asyncio
async def test_voice_context_sync_skill_passes_max_files(monkeypatch):
    calls = []

    class FakeService:
        async def sync_inbox(self, source="skill", max_files=None):
            calls.append({"source": source, "max_files": max_files})
            return {
                "success": True,
                "status": "ok",
                "processed_files": 2,
                "duplicates_skipped": 0,
                "failed_files": 0,
                "discarded_low_quality": 0,
                "context_items": 2,
                "auto_committed": 1,
                "pending_review": 1,
            }

    monkeypatch.setattr(
        "core.skills._builtin.voice_context_sync.handler.VoiceContextService",
        lambda: FakeService(),
    )
    skill = VoiceContextSyncSkill(config=SkillConfig(name="voice_context_sync", description="test"))

    output = await skill.execute({"mode": "sync", "max_files": 3})

    assert calls == [{"source": "skill", "max_files": 3}]
    assert "requested_max_files: 3" in output
