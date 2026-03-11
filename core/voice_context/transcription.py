"""Operational audio transcription helpers for voice context ingestion."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from core.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class TranscriptChunk:
    """One transcript chunk with timing metadata."""

    start_seconds: float
    end_seconds: float
    text: str


@dataclass(slots=True)
class TranscriptResult:
    """Normalized transcription output."""

    text: str
    language: str = "pt"
    duration_seconds: float = 0.0
    model: str = ""
    chunks: list[TranscriptChunk] = field(default_factory=list)


class WhisperTranscriber:
    """Transcribes audio files locally using faster-whisper when available."""

    _model_cache: dict[tuple[str, str], object] = {}

    def __init__(self, *, model_size: str | None = None, device: str | None = None):
        settings = get_settings().voice_context
        self.model_size = model_size or getattr(settings, "whisper_model_size", None) or "tiny"
        self.device = device or getattr(settings, "whisper_device", None) or "cpu"
        self.segment_seconds = 15 * 60

    @staticmethod
    def is_available() -> bool:
        try:
            import faster_whisper  # noqa: F401
        except Exception:
            return False
        return True

    def transcribe_file(self, file_path: str | Path, *, language: str = "pt") -> TranscriptResult:
        if not self.is_available():
            raise RuntimeError(
                "faster-whisper nao instalado. Instale a dependencia para habilitar transcricao local."
            )

        source = Path(file_path)
        if not source.is_file():
            raise FileNotFoundError(str(source))

        prepared = self._prepare_audio_file(source)
        chunk_paths = self._split_audio_file(prepared) or [prepared]
        model = self._get_model()

        chunks: list[TranscriptChunk] = []
        full_text: list[str] = []
        duration = 0.0
        current_offset = 0.0

        try:
            total_chunks = len(chunk_paths)
            for index, chunk_path in enumerate(chunk_paths, start=1):
                logger.info(
                    "voice_context.transcription_chunk_started",
                    chunk_index=index,
                    total_chunks=total_chunks,
                    chunk_path=str(chunk_path),
                )
                segments, info = model.transcribe(
                    str(chunk_path),
                    language=language,
                    vad_filter=True,
                    beam_size=1,
                    condition_on_previous_text=False,
                )
                chunk_duration = self._get_audio_duration_seconds(chunk_path)
                duration += chunk_duration
                for segment in segments:
                    text = str(getattr(segment, "text", "")).strip()
                    if not text:
                        continue
                    start_seconds = float(getattr(segment, "start", 0.0)) + current_offset
                    end_seconds = float(getattr(segment, "end", 0.0)) + current_offset
                    chunks.append(
                        TranscriptChunk(
                            start_seconds=start_seconds,
                            end_seconds=end_seconds,
                            text=text,
                        )
                    )
                    full_text.append(text)
                current_offset += chunk_duration
                logger.info(
                    "voice_context.transcription_chunk_finished",
                    chunk_index=index,
                    total_chunks=total_chunks,
                    chunk_duration_seconds=round(chunk_duration, 2),
                    accumulated_duration_seconds=round(current_offset, 2),
                )

            detected_language = (
                getattr(info, "language", language) if "info" in locals() else language
            )
            final_text = "\n".join(full_text).strip()
            return TranscriptResult(
                text=final_text,
                language=str(detected_language or language),
                duration_seconds=round(duration, 2),
                model=f"faster-whisper:{self.model_size}",
                chunks=chunks,
            )
        finally:
            for chunk_path in chunk_paths:
                if chunk_path != prepared:
                    chunk_path.unlink(missing_ok=True)
            if prepared != source and prepared.exists():
                prepared.unlink(missing_ok=True)

    def transcribe_bytes(
        self,
        audio_data: bytes,
        *,
        suffix: str = ".ogg",
        language: str = "pt",
    ) -> TranscriptResult:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_data)
            temp_path = Path(temp_file.name)

        try:
            return self.transcribe_file(temp_path, language=language)
        finally:
            temp_path.unlink(missing_ok=True)

    def _get_model(self):
        cache_key = (self.model_size, self.device)
        if cache_key not in self._model_cache:
            from faster_whisper import WhisperModel

            self._model_cache[cache_key] = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="int8" if self.device == "cpu" else "auto",
            )
        return self._model_cache[cache_key]

    def _prepare_audio_file(self, source: Path) -> Path:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return source

        prepared = Path(tempfile.mkstemp(prefix="voice_ctx_", suffix=".wav")[1])
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(prepared),
        ]
        self._run_command(cmd, "ffmpeg prepare")
        return prepared

    def _split_audio_file(self, source: Path) -> list[Path]:
        duration = self._get_audio_duration_seconds(source)
        if duration <= 0 or duration <= self.segment_seconds:
            return []

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return []

        output_dir = Path(tempfile.mkdtemp(prefix="voice_ctx_chunks_"))
        output_pattern = output_dir / "chunk_%03d.wav"
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-f",
            "segment",
            "-segment_time",
            str(self.segment_seconds),
            "-c",
            "copy",
            str(output_pattern),
        ]
        self._run_command(cmd, "ffmpeg split")
        return sorted(output_dir.glob("chunk_*.wav"))

    @staticmethod
    def _run_command(cmd: list[str], label: str) -> None:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"{label} failed: {stderr[:300]}")

    @staticmethod
    def _get_audio_duration_seconds(source: Path) -> float:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return 0.0
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return 0.0
        try:
            return float((result.stdout or "0").strip())
        except ValueError:
            return 0.0
