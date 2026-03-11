"""Structured extraction of daily context from long-form voice transcripts."""

from __future__ import annotations

import json
import re
from typing import Any

from core.config import get_settings
from core.llm.unified_provider import get_llm_provider

SUPPORTED_DOMAINS = (
    "saude_energia",
    "trabalho_criacao",
    "financas",
    "relacionamentos",
    "aprendizagem",
    "valores_proposito",
    "operacoes_dia_a_dia",
    "lazer_contribuicao",
)

LLM_TRANSCRIPT_MAX_CHARS = 12000
LLM_CHUNK_TARGET_CHARS = 8000
LLM_MAX_CHUNKS = 24


class VoiceContextExtractor:
    """Turns transcripts into structured context with LLM-first, heuristic fallback."""

    DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
        "saude_energia": (
            "saude",
            "energia",
            "sono",
            "academia",
            "treino",
            "medico",
            "alimentacao",
            "dormir",
            "cansado",
        ),
        "trabalho_criacao": (
            "cliente",
            "projeto",
            "codigo",
            "produto",
            "agentvps",
            "fleetintel",
            "reuniao",
            "entregar",
            "negocio",
            "venda",
        ),
        "financas": (
            "dinheiro",
            "financeiro",
            "orcamento",
            "pagar",
            "receber",
            "nota fiscal",
            "cobranca",
            "banco",
            "cartao",
            "investimento",
        ),
        "relacionamentos": (
            "familia",
            "amigo",
            "esposa",
            "namorada",
            "filho",
            "conversar",
            "relacionamento",
        ),
        "aprendizagem": (
            "estudar",
            "aprendi",
            "ler",
            "curso",
            "pesquisa",
            "conhecimento",
            "ideia",
        ),
        "valores_proposito": (
            "proposito",
            "missao",
            "valor",
            "sentido",
            "importante",
            "quero ser",
            "legado",
        ),
        "operacoes_dia_a_dia": (
            "mercado",
            "comprar",
            "ligar",
            "mandar",
            "agenda",
            "documento",
            "resolver",
            "organizar",
            "rotina",
        ),
        "lazer_contribuicao": (
            "descansar",
            "viagem",
            "filme",
            "musica",
            "jogo",
            "ajudar",
            "comunidade",
            "doar",
            "lazer",
        ),
    }

    PREFERENCE_PATTERNS = (
        re.compile(r"\b(prefiro|gosto de|nao gosto de|odeio|curto)\b", re.IGNORECASE),
    )
    COMMITMENT_PATTERNS = (
        re.compile(
            r"\b(vou|preciso|tenho que|lembrar de|nao esquecer de|combinar de|marcar de)\b",
            re.IGNORECASE,
        ),
    )

    def __init__(self):
        self.settings = get_settings().voice_context

    async def extract_structured_context(
        self,
        transcript: str,
        *,
        source_name: str | None = None,
    ) -> dict[str, Any]:
        cleaned = self._normalize_text(transcript)
        if not cleaned:
            return self._empty_output()

        if self.settings.extract_with_llm:
            llm_output = await self._extract_with_llm(cleaned, source_name=source_name)
            if llm_output:
                return self._normalize_output(llm_output)

        return self._heuristic_extract(cleaned)

    async def _extract_with_llm(
        self,
        transcript: str,
        *,
        source_name: str | None = None,
    ) -> dict[str, Any] | None:
        chunks = self._chunk_transcript_for_llm(transcript)
        if not chunks:
            return None

        if len(chunks) == 1:
            return await self._extract_llm_chunk(chunks[0], source_name=source_name)

        merged_outputs: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks, start=1):
            chunk_source = source_name
            if chunk_source:
                chunk_source = f"{chunk_source} [parte {index}/{len(chunks)}]"
            else:
                chunk_source = f"parte {index}/{len(chunks)}"
            chunk_output = await self._extract_llm_chunk(chunk, source_name=chunk_source)
            if chunk_output:
                merged_outputs.append(chunk_output)

        if not merged_outputs:
            return None
        return self._merge_llm_outputs(merged_outputs)

    async def _extract_llm_chunk(
        self,
        transcript: str,
        *,
        source_name: str | None = None,
    ) -> dict[str, Any] | None:
        provider = get_llm_provider()
        if not provider.api_key:
            return None

        prompt = (
            "Voce vai transformar uma transcricao de voz longa em memoria estruturada.\n"
            "Retorne APENAS JSON valido no formato:\n"
            "{"
            '"summary":"...",'
            '"episodes":[{"text":"...","domain":"trabalho_criacao","confidence":0.8}],'
            '"facts":[{"text":"...","domain":"operacoes_dia_a_dia","confidence":0.8}],'
            '"preferences":[{"key":"...","value":"...","evidence":"...","domain":"...","confidence":0.7}],'
            '"commitments":[{"text":"...","due_hint":"...","domain":"...","confidence":0.8}]'
            "}\n"
            f"Use apenas estes domains: {', '.join(SUPPORTED_DOMAINS)}.\n"
            "Regras:\n"
            "- Foque no que ajuda um agente pessoal no dia a dia.\n"
            "- Nao invente fatos.\n"
            "- Se algo for ambiguo, reduza a confianca.\n"
            "- Seja conciso e sem duplicatas."
        )
        if source_name:
            prompt += f"\nOrigem: {source_name}"

        response = await provider.generate(
            user_message=transcript[:LLM_TRANSCRIPT_MAX_CHARS],
            system_prompt=prompt,
            json_mode=True,
        )
        if not response.success or not response.content:
            return None

        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except Exception:
            return None

    def _chunk_transcript_for_llm(self, transcript: str) -> list[str]:
        cleaned = self._normalize_text(transcript)
        if not cleaned:
            return []
        if len(cleaned) <= LLM_TRANSCRIPT_MAX_CHARS:
            return [cleaned]

        sentences = self._split_sentences(cleaned)
        if not sentences:
            return [
                cleaned[i : i + LLM_CHUNK_TARGET_CHARS]
                for i in range(0, len(cleaned), LLM_CHUNK_TARGET_CHARS)
            ][:LLM_MAX_CHUNKS]

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence) + (1 if current else 0)
            if current and current_len + sentence_len > LLM_CHUNK_TARGET_CHARS:
                chunks.append(" ".join(current).strip())
                current = [sentence]
                current_len = len(sentence)
            else:
                current.append(sentence)
                current_len += sentence_len

        if current:
            chunks.append(" ".join(current).strip())

        return chunks[:LLM_MAX_CHUNKS]

    def _merge_llm_outputs(self, outputs: list[dict[str, Any]]) -> dict[str, Any]:
        merged = self._empty_output()
        normalized_outputs = [self._normalize_output(output) for output in outputs]

        summary_parts: list[str] = []
        for output in normalized_outputs:
            summary = str(output.get("summary", "")).strip()
            if summary and summary not in summary_parts:
                summary_parts.append(summary)

        merged["summary"] = " ".join(summary_parts[:4])[:1000]

        caps = {
            "episodes": 8,
            "facts": 12,
            "preferences": 6,
            "commitments": 8,
        }
        for key, limit in caps.items():
            deduped = self._dedupe_items(normalized_outputs, key)
            merged[key] = deduped[:limit]
        return merged

    @staticmethod
    def _dedupe_items(outputs: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for output in outputs:
            for item in output.get(key, []) or []:
                if key == "preferences":
                    stable = f"{item.get('key','')}|{item.get('value','')}".strip().lower()
                else:
                    stable = str(item.get("text") or item.get("value") or "").strip().lower()
                if not stable or stable in seen:
                    continue
                seen.add(stable)
                deduped.append(item)
        deduped.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)
        return deduped

    def _heuristic_extract(self, transcript: str) -> dict[str, Any]:
        sentences = self._split_sentences(transcript)
        if not sentences:
            return self._empty_output()

        preferences: list[dict[str, Any]] = []
        commitments: list[dict[str, Any]] = []
        episodes: list[dict[str, Any]] = []
        facts: list[dict[str, Any]] = []

        for sentence in sentences:
            domain = self.classify_domain(sentence)
            if self._looks_like_preference(sentence):
                preferences.append(
                    {
                        "key": self._preference_key(sentence),
                        "value": sentence,
                        "evidence": sentence,
                        "domain": domain,
                        "confidence": 0.72,
                    }
                )
                continue
            if self._looks_like_commitment(sentence):
                commitments.append(
                    {
                        "text": sentence,
                        "due_hint": self._detect_due_hint(sentence),
                        "domain": domain,
                        "confidence": 0.79,
                    }
                )
                continue

            target = episodes if len(episodes) < 5 else facts
            target.append(
                {
                    "text": sentence,
                    "domain": domain,
                    "confidence": 0.78 if target is episodes else 0.74,
                }
            )

        if not facts:
            facts = episodes[1:6]

        summary = self._build_summary(
            episodes=episodes,
            facts=facts,
            preferences=preferences,
            commitments=commitments,
        )

        return self._normalize_output(
            {
                "summary": summary,
                "episodes": episodes[:5],
                "facts": facts[:8],
                "preferences": preferences[:5],
                "commitments": commitments[:5],
            }
        )

    def classify_domain(self, text: str) -> str:
        lowered = text.lower()
        best_domain = "operacoes_dia_a_dia"
        best_score = 0
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in lowered)
            if score > best_score:
                best_domain = domain
                best_score = score
        return best_domain

    @staticmethod
    def _normalize_text(transcript: str) -> str:
        cleaned = re.sub(r"\s+", " ", (transcript or "")).strip()
        return cleaned

    @staticmethod
    def _split_sentences(transcript: str) -> list[str]:
        raw_parts = re.split(r"(?<=[\.\!\?])\s+|\s*\n\s*", transcript)
        output = []
        for part in raw_parts:
            text = re.sub(r"\s+", " ", part).strip(" -")
            if len(text) >= 18:
                output.append(text)
        return output

    @classmethod
    def _looks_like_preference(cls, sentence: str) -> bool:
        return any(pattern.search(sentence) for pattern in cls.PREFERENCE_PATTERNS)

    @classmethod
    def _looks_like_commitment(cls, sentence: str) -> bool:
        return any(pattern.search(sentence) for pattern in cls.COMMITMENT_PATTERNS)

    @staticmethod
    def _preference_key(sentence: str) -> str:
        lowered = re.sub(r"[^a-z0-9]+", "_", sentence.lower()).strip("_")
        return f"pref_{lowered[:48] or 'voice'}"

    @staticmethod
    def _detect_due_hint(sentence: str) -> str | None:
        lowered = sentence.lower()
        hints = (
            "hoje",
            "amanha",
            "semana que vem",
            "segunda",
            "terca",
            "quarta",
            "quinta",
            "sexta",
            "sabado",
            "domingo",
        )
        for hint in hints:
            if hint in lowered:
                return hint
        return None

    @staticmethod
    def _build_summary(
        *,
        episodes: list[dict[str, Any]],
        facts: list[dict[str, Any]],
        preferences: list[dict[str, Any]],
        commitments: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = []
        if episodes:
            parts.append(episodes[0]["text"])
        elif facts:
            parts.append(facts[0]["text"])
        if commitments:
            parts.append(f"Compromissos citados: {len(commitments)}")
        if preferences:
            parts.append(f"Preferencias observadas: {len(preferences)}")
        summary = " ".join(parts).strip()
        return summary[:500]

    def _normalize_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._empty_output()
        normalized["summary"] = str(payload.get("summary", "")).strip()[:1000]
        for key in ("episodes", "facts", "preferences", "commitments"):
            raw_items = payload.get(key) or []
            if not isinstance(raw_items, list):
                continue
            items: list[dict[str, Any]] = []
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                text = str(
                    item.get("text")
                    or item.get("value")
                    or item.get("evidence")
                    or item.get("summary")
                    or ""
                ).strip()
                if key == "preferences":
                    if not text and not item.get("value"):
                        continue
                elif not text:
                    continue
                domain = item.get("domain") or self.classify_domain(text)
                if domain not in SUPPORTED_DOMAINS:
                    domain = self.classify_domain(text)
                normalized_item = {
                    "domain": domain,
                    "confidence": max(0.0, min(float(item.get("confidence", 0.7)), 1.0)),
                }
                if key == "preferences":
                    normalized_item.update(
                        {
                            "key": str(item.get("key") or self._preference_key(text)).strip(),
                            "value": str(item.get("value") or text).strip()[:500],
                            "evidence": str(item.get("evidence") or text).strip()[:500],
                        }
                    )
                elif key == "commitments":
                    normalized_item.update(
                        {
                            "text": text[:500],
                            "due_hint": item.get("due_hint"),
                        }
                    )
                else:
                    normalized_item["text"] = text[:500]
                items.append(normalized_item)
            normalized[key] = items
        return normalized

    @staticmethod
    def _empty_output() -> dict[str, Any]:
        return {
            "summary": "",
            "episodes": [],
            "facts": [],
            "preferences": [],
            "commitments": [],
        }
