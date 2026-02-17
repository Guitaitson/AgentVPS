"""
Skill: Web Search - Pesquisa na web usando Brave Search API com fallback DuckDuckGo.
"""

import os
import re
from typing import Any, Dict

import httpx
import structlog

from core.skills.base import SkillBase

logger = structlog.get_logger()

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")


class WebSearchSkill(SkillBase):
    """Pesquisa na web usando Brave Search com fallback DuckDuckGo."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        args = args or {}

        raw_input = args.get("raw_input", "")

        # Extrair query
        query = args.get("query", "").strip()
        if not query:
            query = self._extract_query(raw_input)

        if not query:
            return "Forneca um termo de busca. Ex: 'pesquise python tutorials'"

        # Tentar Brave primeiro (se API key configurada)
        if BRAVE_API_KEY:
            try:
                result = await self._search_brave(query)
                if not result.startswith("ERRO_BRAVE:"):
                    return result
                logger.warning("web_search_brave_failed", error=result, falling_back="ddg")
            except Exception as e:
                logger.warning("web_search_brave_exception", error=str(e), falling_back="ddg")
        else:
            logger.info("web_search_no_brave_key", falling_back="ddg")

        # Fallback: DuckDuckGo (sem API key)
        try:
            return await self._search_ddg(query)
        except Exception as e:
            logger.error("web_search_ddg_failed", error=str(e), query=query)
            return f"Nao consegui buscar '{query}' — Brave e DuckDuckGo falharam. Erro: {e}"

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

    async def _search_brave(self, query: str) -> str:
        """Executa busca na Brave API. Retorna 'ERRO_BRAVE:...' em caso de falha."""
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
                    "web_search_brave_api_error",
                    status=resp.status_code,
                    body=resp.text[:300],
                    query=query,
                )
                return f"ERRO_BRAVE: HTTP {resp.status_code} - {resp.text[:200]}"

            data = resp.json()
            logger.info(
                "web_search_brave_success",
                query=query,
                results_count=len(data.get("web", {}).get("results", [])),
            )
            return self._format_results(query, data)

    async def _search_ddg(self, query: str) -> str:
        """Fallback: DuckDuckGo HTML search (sem API key necessaria)."""
        url = "https://html.duckduckgo.com/html/"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={"q": query},
                timeout=15.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )

            if resp.status_code != 200:
                logger.error("web_search_ddg_http_error", status=resp.status_code, query=query)
                return f"Busca DuckDuckGo falhou com HTTP {resp.status_code}"

            results = self._parse_ddg_html(resp.text, query)
            logger.info("web_search_ddg_success", query=query, results_count=len(results))

            if not results:
                return f"Nenhum resultado encontrado para: {query}"

            lines = [f"Resultados para: {query}\n"]
            for i, r in enumerate(results[:5], 1):
                lines.append(f"**{i}. {r['title']}**")
                if r.get("snippet"):
                    lines.append(f"   {r['snippet']}")
                if r.get("url"):
                    lines.append(f"   {r['url']}")
                lines.append("")

            return "\n".join(lines)

    def _parse_ddg_html(self, html: str, query: str) -> list:
        """Parseia resultados do DuckDuckGo HTML search."""
        results = []

        # Extrair blocos de resultado — cada resultado está em <div class="result">
        # Titulo em <a class="result__a"> e snippet em <a class="result__snippet">
        title_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL
        )
        snippet_pattern = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)

        # Dividir por blocos de resultado
        result_blocks = re.split(r'<div[^>]*class="[^"]*result[^"]*"', html)

        for block in result_blocks[1:]:  # skip primeiro (antes do primeiro resultado)
            title_match = title_pattern.search(block)
            snippet_match = snippet_pattern.search(block)

            if title_match:
                url = title_match.group(1)
                title = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()
                snippet = ""
                if snippet_match:
                    snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()

                # DuckDuckGo usa redirects — extrair URL real se possível
                if "uddg=" in url:
                    real_url_match = re.search(r"uddg=([^&]+)", url)
                    if real_url_match:
                        from urllib.parse import unquote

                        url = unquote(real_url_match.group(1))

                if title:
                    results.append(
                        {
                            "title": title[:100],
                            "snippet": snippet[:200],
                            "url": url,
                        }
                    )

            if len(results) >= 5:
                break

        return results

    def _format_results(self, query: str, data: dict) -> str:
        """Formata resultados da busca Brave."""
        results = data.get("web", {}).get("results", [])

        if not results:
            return f"Nenhum resultado encontrado para: {query}"

        lines = [f"Resultados para: {query}\n"]

        for i, result in enumerate(results[:5], 1):
            title = result.get("title", "Sem titulo")
            url = result.get("url", "")
            desc = result.get("description", "")

            lines.append(f"**{i}. {title}**")
            if desc:
                lines.append(f"   {desc[:150]}")
            if url:
                lines.append(f"   {url}")
            lines.append("")

        return "\n".join(lines)
