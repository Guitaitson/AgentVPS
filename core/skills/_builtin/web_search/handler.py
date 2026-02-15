"""
Skill: Web Search - Pesquisa na web usando Brave Search API.
"""

import os
from typing import Any, Dict

import httpx

from core.skills.base import SkillBase

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

        try:
            return await self._search(query)
        except Exception as e:
            return f"❌ Erro na busca: {e}"

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
                return f"❌ Erro da API: {resp.status_code}"

            data = resp.json()
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
