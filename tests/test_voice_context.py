from types import SimpleNamespace

import pytest

from core.config import get_settings
from core.voice_context.extraction import VoiceContextExtractor
from core.voice_context.service import VoiceContextService
from core.voice_context.transcription import TranscriptResult


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

    long_audio_item = service.assess_item_decision(
        {
            "memory_target": "episodic",
            "domain": "operacoes_dia_a_dia",
            "confidence": 0.99,
            "payload": {"force_review": True},
        }
    )
    assert long_audio_item.auto_commit is False
    assert long_audio_item.risk_level == "low"


def test_voice_context_service_discard_job(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._rows = [
                {
                    "id": 10,
                    "memory_target": "episodic",
                    "memory_key": "voice:summary:2:e195cc299eb1",
                    "proposal_id": 33,
                },
                {
                    "id": 11,
                    "memory_target": "semantic",
                    "memory_key": None,
                    "proposal_id": None,
                },
            ]
            self.rowcount = 0

        def execute(self, query, params=None):
            normalized = " ".join(str(query).split())
            if "SELECT id, memory_target, memory_key, proposal_id" in normalized:
                self.rowcount = len(self._rows)
            elif "UPDATE agent_proposals" in normalized:
                self.rowcount = 1
            elif "UPDATE voice_context_items" in normalized:
                self.rowcount = 2
            elif "UPDATE voice_ingestion_jobs" in normalized:
                self.rowcount = 1
            else:
                self.rowcount = 0

        def fetchall(self):
            return self._rows

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_obj

        def commit(self):
            return None

        def close(self):
            return None

    deleted = []
    fake_memory = SimpleNamespace(
        delete_typed_memory=lambda **kwargs: deleted.append(kwargs) or True,
    )
    service = VoiceContextService(memory=fake_memory)
    monkeypatch.setattr(service, "_get_conn", lambda: FakeConn())
    monkeypatch.setattr(service, "resolve_user_id", lambda user_id=None: "u1")

    result = service.discard_job(job_id=2, actor="test")

    assert result["success"] is True
    assert result["discarded_items"] == 2
    assert result["deleted_memories"] == 1
    assert result["rejected_proposals"] == 1
    assert deleted[0]["key"] == "voice:summary:2:e195cc299eb1"


def test_voice_context_quality_report_flags_noisy_long_audio():
    service = VoiceContextService(memory=SimpleNamespace())
    transcript = TranscriptResult(
        text=("E ai? achei que era cabeca\nta bom?\nnao e o pago\neu gosto de um pouco\n") * 120,
        duration_seconds=5 * 60 * 60,
        model="faster-whisper:tiny",
    )

    report = service.evaluate_transcript_quality(transcript)

    assert report.status in {"warn", "discard"}
    assert report.score < 0.65
    assert report.reasons


def test_voice_context_feedback_mentions_memory_targets_and_discard_reason():
    service = VoiceContextService(memory=SimpleNamespace())

    text = service._format_job_feedback(  # noqa: SLF001 - targeted regression coverage
        {
            "job_id": 9,
            "status": "completed",
            "processed_files": 1,
            "duplicates_skipped": 0,
            "discarded_low_quality": 1,
            "auto_committed": 2,
            "pending_review": 1,
            "committed_targets": {"episodic": 1, "semantic": 1},
            "pending_targets": {"goals": 1},
            "proposal_ids": [41],
            "files": [
                {
                    "file_name": "morning.wav",
                    "status": "discarded_quality",
                    "quality_score": 0.31,
                    "quality_status": "discard",
                    "duration_minutes": 52.0,
                    "reason": "review_required; quality_discard:0.31",
                    "quality_reasons": ["baixa estabilidade lexical na transcricao"],
                }
            ],
        }
    )

    assert "memory_committed: episodic=1, semantic=1" in text
    assert "memory_review: goals=1" in text
    assert "disposition: review_required; quality_discard:0.31" in text
    assert "/contextdiscard 9" in text


@pytest.mark.asyncio
async def test_voice_context_inspect_inbox_reports_review_without_committing(tmp_path):
    inbox_dir = tmp_path / "inbox"
    processing_dir = tmp_path / "processing"
    archive_dir = tmp_path / "archive"
    failed_dir = tmp_path / "failed"
    transcripts_dir = tmp_path / "transcripts"
    inbox_dir.mkdir()
    (inbox_dir / "sample.mp3").write_bytes(b"fake-audio")

    settings = SimpleNamespace(
        file_extensions=".mp3,.wav",
        inbox_dir=str(inbox_dir),
        processing_dir=str(processing_dir),
        archive_dir=str(archive_dir),
        failed_dir=str(failed_dir),
        transcripts_dir=str(transcripts_dir),
        max_files_per_run=12,
        auto_commit_max_duration_minutes=30,
        quality_warn_score=0.65,
        quality_min_score=0.35,
        create_daily_summary=True,
        auto_commit_threshold=0.75,
    )

    class FakeTranscriber:
        def transcribe_file(self, file_path, language="pt"):  # noqa: ARG002
            return TranscriptResult(
                text=(
                    "Hoje avancei no AgentVPS e documentei o fluxo de voz para reduzir ruido. "
                    "Revisei o lote da manha, conferi os arquivos, organizei os blocos por contexto, "
                    "separei trechos curtos, removi pausas longas e mantive um ritmo de fala mais claro. "
                    "Tambem anotei que prefiro revisar os lotes antes de subir qualquer arquivo para a VPS. "
                    "No periodo da tarde continuei o ajuste de calibracao, comparei os resultados do gravador "
                    "e deixei um resumo operacional do dia para a memoria episodica."
                ),
                duration_seconds=12 * 60,
                model="fake",
            )

    class FakeExtractor:
        async def extract_structured_context(self, transcript, source_name=None):  # noqa: ARG002
            return {
                "summary": "Resumo util",
                "episodes": [
                    {
                        "text": "Avancei no AgentVPS",
                        "domain": "trabalho_criacao",
                        "confidence": 0.91,
                    }
                ],
                "facts": [],
                "preferences": [
                    {
                        "key": "pref_review",
                        "value": "Prefiro revisar lotes antes de subir",
                        "evidence": "Eu prefiro revisar os lotes antes de subir.",
                        "domain": "operacoes_dia_a_dia",
                        "confidence": 0.84,
                    }
                ],
                "commitments": [],
            }

    service = VoiceContextService(
        settings=settings,
        memory=SimpleNamespace(),
        extractor=FakeExtractor(),
        transcriber=FakeTranscriber(),
    )

    result = await service.inspect_inbox(max_files=5)

    assert result["success"] is True
    assert result["status"] == "inspected"
    assert result["processed_files"] == 1
    assert result["auto_committed"] == 2
    assert result["pending_review"] == 1
    assert result["review_required_files"] == 1
    assert result["batch_recommendation"] == "review_before_send"
    assert "Segregue os arquivos" in result["calibration_advice"]
    assert result["green_gate"]["passed"] is False
    assert "review_dominates_batch" in result["green_gate"]["failed_reasons"]
    assert result["files"][0]["recommended_action"] == "hold"
    assert result["files"][0]["would_require_review"] == 1


@pytest.mark.asyncio
async def test_voice_context_inspect_inbox_filters_explicit_batch_file_names(tmp_path):
    inbox_dir = tmp_path / "inbox"
    processing_dir = tmp_path / "processing"
    archive_dir = tmp_path / "archive"
    failed_dir = tmp_path / "failed"
    transcripts_dir = tmp_path / "transcripts"
    inbox_dir.mkdir()
    (inbox_dir / "older.mp3").write_bytes(b"old")
    (inbox_dir / "batch.mp3").write_bytes(b"batch")

    settings = SimpleNamespace(
        file_extensions=".mp3,.wav",
        inbox_dir=str(inbox_dir),
        processing_dir=str(processing_dir),
        archive_dir=str(archive_dir),
        failed_dir=str(failed_dir),
        transcripts_dir=str(transcripts_dir),
        max_files_per_run=12,
        auto_commit_max_duration_minutes=30,
        quality_warn_score=0.65,
        quality_min_score=0.35,
        create_daily_summary=True,
        auto_commit_threshold=0.75,
    )

    class FakeTranscriber:
        def transcribe_file(self, file_path, language="pt"):  # noqa: ARG002
            name = getattr(file_path, "name", str(file_path))
            return TranscriptResult(
                text=(
                    f"Arquivo {name} com resumo do dia no AgentVPS e detalhes claros do que foi feito. "
                    "Organizei o lote de voz, revisei a captacao, mantive o raciocinio continuo, "
                    "e deixei contexto suficiente para memoria episodica sem ruido excessivo. "
                )
                * 8,
                duration_seconds=12 * 60,
                model="fake",
            )

    class FakeExtractor:
        async def extract_structured_context(self, transcript, source_name=None):  # noqa: ARG002
            return {
                "summary": f"Resumo util de {source_name}",
                "episodes": [
                    {
                        "text": "Organizei o lote de voz",
                        "domain": "trabalho_criacao",
                        "confidence": 0.93,
                    }
                ],
                "facts": [],
                "preferences": [],
                "commitments": [],
            }

    service = VoiceContextService(
        settings=settings,
        memory=SimpleNamespace(),
        extractor=FakeExtractor(),
        transcriber=FakeTranscriber(),
    )

    result = await service.inspect_inbox(file_names=["batch.mp3"])

    assert result["processed_files"] == 1
    assert result["matched_files"] == ["batch.mp3"]
    assert result["missing_requested_files"] == []
    assert result["files"][0]["file_name"] == "batch.mp3"
    assert result["green_gate"]["passed"] is True


@pytest.mark.asyncio
async def test_voice_context_inspect_inbox_reports_missing_requested_files(tmp_path, monkeypatch):
    inbox_dir = tmp_path / "inbox"
    processing_dir = tmp_path / "processing"
    archive_dir = tmp_path / "archive"
    failed_dir = tmp_path / "failed"
    transcripts_dir = tmp_path / "transcripts"
    inbox_dir.mkdir()

    settings = SimpleNamespace(
        file_extensions=".mp3,.wav",
        inbox_dir=str(inbox_dir),
        processing_dir=str(processing_dir),
        archive_dir=str(archive_dir),
        failed_dir=str(failed_dir),
        transcripts_dir=str(transcripts_dir),
        max_files_per_run=12,
        auto_commit_max_duration_minutes=30,
        quality_warn_score=0.65,
        quality_min_score=0.35,
        create_daily_summary=True,
        auto_commit_threshold=0.75,
    )

    service = VoiceContextService(
        settings=settings,
        memory=SimpleNamespace(),
        extractor=SimpleNamespace(),
        transcriber=SimpleNamespace(),
    )
    monkeypatch.setattr(service, "count_pending_review", lambda: 0)

    result = await service.inspect_inbox(file_names=["missing.mp3"])

    assert result["status"] == "no_files"
    assert result["requested_files"] == ["missing.mp3"]
    assert result["missing_requested_files"] == ["missing.mp3"]
