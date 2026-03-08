from core.identity import SoulArtifactType, SoulImpactLevel
from core.identity.soul import SoulManager


def _raise_db_unavailable():
    raise RuntimeError("db unavailable for test")


def test_core_identity_change_always_requires_approval(monkeypatch):
    manager = SoulManager()
    monkeypatch.setattr(manager, "_get_conn", _raise_db_unavailable)

    proposal = manager.propose_change(
        artifact_type=SoulArtifactType.CORE_IDENTITY,
        proposed_content="Nova identidade.",
        rationale="Ajuste constitucional",
        requested_by="owner",
        impact_level=SoulImpactLevel.LOW,
    )

    assert proposal.requires_approval is True
    assert proposal.status == "pending"


def test_approve_personal_voice_proposal_increments_version(monkeypatch):
    manager = SoulManager()
    monkeypatch.setattr(manager, "_get_conn", _raise_db_unavailable)

    before = manager.get_artifact(SoulArtifactType.PERSONAL_VOICE)
    proposal = manager.propose_change(
        artifact_type=SoulArtifactType.PERSONAL_VOICE,
        proposed_content="Fale de forma objetiva e com bullets curtos.",
        rationale="Melhorar consistencia de resposta.",
        requested_by="owner",
        impact_level=SoulImpactLevel.LOW,
    )

    approved = manager.approve_proposal(proposal.proposal_id, reviewer="owner")
    after = manager.get_artifact(SoulArtifactType.PERSONAL_VOICE)

    assert approved is True
    assert after.version == before.version + 1
    assert "objetiva" in after.content


def test_prompt_extensions_include_challenge_mode(monkeypatch):
    manager = SoulManager()
    monkeypatch.setattr(manager, "_get_conn", _raise_db_unavailable)

    prompt = manager.render_prompt_extensions()

    assert "Alma Versionada" in prompt
    assert "Challenge Mode" in prompt
