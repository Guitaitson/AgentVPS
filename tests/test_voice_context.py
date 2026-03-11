from types import SimpleNamespace

import pytest

from core.config import get_settings
from core.voice_context.extraction import VoiceContextExtractor
from core.voice_context.service import VoiceContextService


@pytest.fixture(autouse=True)
def _reset_settings_cache(monkeypatch):
    monkeypatch.setenv("VOICE_CONTEXT_EXTRACT_WITH_LLM", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_voice_context_extractor_detects_preferences_and_commitments():
    extractor = VoiceContextExtractor()
    result = await extractor.extract_structured_context(
        "Hoje foquei no projeto AgentVPS e precisei organizar a rotina. "
        "Eu prefiro trabalhar cedo quando tenho mais energia. "
        "Amanha vou ligar para o cliente e pagar a fatura do cartao."
    )

    assert result["summary"]
    assert any(item["domain"] == "trabalho_criacao" for item in result["episodes"])
    assert any(item["key"].startswith("pref_") for item in result["preferences"])
    assert any(item.get("due_hint") == "amanha" for item in result["commitments"])


@pytest.mark.asyncio
async def test_voice_context_extractor_chunks_long_transcripts_with_llm(monkeypatch):
    monkeypatch.setenv("VOICE_CONTEXT_EXTRACT_WITH_LLM", "true")
    get_settings.cache_clear()

    calls = []

    class DummyProvider:
        api_key = "test-key"

        async def generate(self, *, user_message, system_prompt, json_mode):
            calls.append(user_message)
            index = len(calls)
            payload = {
                "summary": f"parte {index}",
                "episodes": [
                    {
                        "text": f"episodio parte {index}",
                        "domain": "trabalho_criacao",
                        "confidence": 0.9,
                    }
                ],
                "facts": [
                    {
                        "text": f"fato parte {index}",
                        "domain": "operacoes_dia_a_dia",
                        "confidence": 0.8,
                    }
                ],
                "preferences": [],
                "commitments": [],
            }
            return SimpleNamespace(success=True, content=__import__("json").dumps(payload))

    monkeypatch.setattr("core.voice_context.extraction.get_llm_provider", lambda: DummyProvider())

    extractor = VoiceContextExtractor()
    sentence = "Hoje avancei no AgentVPS e documentei o fluxo de voz. "
    transcript = sentence * 400

    result = await extractor.extract_structured_context(transcript)

    assert len(calls) > 1
    assert "parte 1" in result["summary"]
    assert len(result["episodes"]) >= 2
    assert any(item["text"] == "fato parte 1" for item in result["facts"])


def test_voice_context_service_assess_item_decision(monkeypatch):
    service = VoiceContextService(memory=SimpleNamespace())
    monkeypatch.setattr(service, "has_pending_files", lambda: True)

    low_risk = service.assess_item_decision(
        {
            "memory_target": "episodic",
            "domain": "operacoes_dia_a_dia",
            "confidence": 0.9,
        }
    )
    assert low_risk.auto_commit is True
    assert low_risk.risk_level == "low"

    profile_item = service.assess_item_decision(
        {
            "memory_target": "profile",
            "domain": "operacoes_dia_a_dia",
            "confidence": 0.95,
        }
    )
    assert profile_item.auto_commit is False
    assert profile_item.risk_level == "medium"

    finance_item = service.assess_item_decision(
        {
            "memory_target": "semantic",
            "domain": "financas",
            "confidence": 0.95,
        }
    )
    assert finance_item.auto_commit is False
    assert finance_item.risk_level == "high"
