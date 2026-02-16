"""
Skill: Web Search - Pesquisa na web usando Brave Search API.
"""

import os
from typing import Any, Dict

import httpx
import structlog

from core.skills.base import SkillBase

logger = structlog.get_logger()

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")


class WebSearchSkill(SkillBase):
    """Pesquisa na web usando Brave Search."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        args = args or {}

        raw_input = args.get("raw_input", "")

        # Extrair query
        query = args.get("query", "").strip()
        if not query:
            query = self._extract_query(raw_input)

        if not query:
            return "❌ Forneça um termo de busca. Ex: 'pesquise python tutorials'"

        if not BRAVE_API_KEY:
            logger.error("web_search_no_api_key")
            return "❌ BRAVE_API_KEY não configurada no servidor."

        try:
            return await self._search(query)
        except httpx.TimeoutException:
            logger.error("web_search_timeout", query=query)
            return f"❌ Busca expirou (timeout de 15s). Query: {query}"
        except httpx.HTTPError as e:
            logger.error("web_search_http_error", error=str(e), query=query)
            return f"❌ Erro HTTP na busca: {e}"
        except Exception as e:
            logger.error(
                "web_search_error",
                error=str(e),
                error_type=type(e).__name__,
                query=query,
            )
            return f"❌ Erro na busca ({type(e).__name__}): {e}"

    def _extract_query(self, text: str) -> str:
        """Extrai query do texto."""
        text = text.lower()

        # Remover prefixos comuns
        for prefix in ["pesquise ", "busque ", "procure ", "search ", "buscar "]:
            if text.startswith(prefix):
                return text[len(prefix) :].strip()

        # Pegar tudo após trigger words
        triggers = ["sobre ", "de ", "sobre "]
        for trigger in triggers:
            if trigger in text:
                idx = text.find(trigger)
                return text[idx + len(trigger) :].strip()

        return text.strip()

    async def _search(self, query: str) -> str:
        """Executa a busca na Brave API."""
        url = "https://api.search.brave.com/res/v1/web/search"

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": BRAVE_API_KEY,
        }

        params = {
            "q": query,
            "count": 5,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params=params, timeout=15.0)
            if resp.status_code != 200:
                logger.error(
                    "web_search_api_error",
                    status=resp.status_code,
                    body=resp.text[:300],
                    query=query,
                )
                return f"❌ Erro da API Brave Search: HTTP {resp.status_code}"

            data = resp.json()
            logger.info(
                "web_search_success",
                query=query,
                results_count=len(data.get("web", {}).get("results", [])),
            )
            return self._format_results(query, data)

    def _format_results(self, query: str, data: dict) -> str:
        """Formata resultados da busca."""
        results = data.get("web", {}).get("results", [])

        if not results:
            return f"🔍 Nenhum resultado encontrado para: **{query}**"

        lines = [f"🔍 **Resultados para:** {query}\n"]

        for i, result in enumerate(results[:5], 1):
            title = result.get("title", "Sem título")
            url = result.get("url", "")
            desc = result.get("description", "")

            lines.append(f"**{i}. {title}**")
            if desc:
                lines.append(f"   {desc[:150]}...")
            if url:
                lines.append(f"   🔗 {url}")
            lines.append("")

        return "\n".join(lines)
