from core.llm import agent_identity


class _FakeSoulManager:
    def render_prompt_extensions(self):
        return "## Alma Versionada\n- teste"

    def render_condensed_identity_extension(self):
        return " Challenge mode ativo."


def test_full_prompt_includes_soul_extension(monkeypatch):
    monkeypatch.setattr("core.identity.get_soul_manager", lambda: _FakeSoulManager())
    prompt = agent_identity.get_full_system_prompt()
    assert "Alma Versionada" in prompt


def test_condensed_prompt_includes_challenge_extension(monkeypatch):
    monkeypatch.setattr("core.identity.get_soul_manager", lambda: _FakeSoulManager())
    prompt = agent_identity.get_identity_prompt_condensed()
    assert "Challenge mode ativo" in prompt
