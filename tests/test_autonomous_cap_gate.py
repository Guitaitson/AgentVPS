import pytest

from core.autonomous.engine import CapGate


@pytest.mark.asyncio
async def test_check_explicit_approval_ignores_when_flag_not_set(monkeypatch):
    called = {"value": False}

    def _fake_mark(*args, **kwargs):
        called["value"] = True
        return {"blocked": True}

    monkeypatch.setattr(CapGate, "_mark_requires_approval", _fake_mark)

    result = await CapGate.check_explicit_approval(
        engine=object(),
        proposal_id=1,
        suggested_action={"action": "skills_catalog_sync"},
    )

    assert result["blocked"] is False
    assert called["value"] is False


@pytest.mark.asyncio
async def test_check_explicit_approval_marks_when_flag_set(monkeypatch):
    def _fake_mark(engine, proposal_id, action, reason):
        return {
            "blocked": True,
            "reason": reason,
            "action": action,
            "proposal_id": proposal_id,
        }

    monkeypatch.setattr(CapGate, "_mark_requires_approval", _fake_mark)

    result = await CapGate.check_explicit_approval(
        engine=object(),
        proposal_id=42,
        suggested_action={"action": "skills_catalog_sync", "requires_approval": True},
    )

    assert result["blocked"] is True
    assert result["reason"] == "explicit_approval_required"
    assert result["action"] == "skills_catalog_sync"
