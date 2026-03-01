"""
Skill: FleetIntel — Dados de emplacamentos de veículos pesados do Brasil.

Conecta-se ao servidor MCP FleetIntel via HTTPS e executa consultas
sobre a base de dados de emplacamentos (~1M registros, ~170k empresas).

Variáveis de ambiente necessárias:
    FLEETINTEL_MCP_URL   — URL do MCP server (ex: https://mcp.gtaitson.space/mcp)
    FLEETINTEL_MCP_TOKEN — Bearer token de autenticação
"""

import json
import os
import re
from typing import Any, Dict, Optional, Tuple

import httpx
import structlog

from core.skills.base import SkillBase

logger = structlog.get_logger()

FLEETINTEL_MCP_URL = os.getenv("FLEETINTEL_MCP_URL", "https://mcp.gtaitson.space/mcp")
FLEETINTEL_MCP_TOKEN = os.getenv("FLEETINTEL_MCP_TOKEN", "")

# Limite de caracteres para resposta no Telegram
MAX_CHARS = 3000


class FleetIntelSkill(SkillBase):
    """
    Skill para consultas de dados de frota de veículos pesados.

    Roteia automaticamente a pergunta do usuário para a tool MCP correta:
    - get_stats            → estatísticas gerais do banco
    - get_market_share     → market share por marca
    - top_empresas_by_registrations → ranking de maiores compradores
    - count_empresa_registrations   → volume de uma empresa específica
    - search_empresas      → busca de empresa por nome/CNPJ
    - search_vehicles      → busca de veículo por marca/modelo/chassi
    - search_registrations → busca de emplacamentos por período/estado/preço
    """

    async def execute(self, args: Dict[str, Any] = None) -> str:
        args = args or {}
        raw_input = args.get("raw_input", args.get("query", ""))

        if not raw_input:
            return "❓ Qual dado de frota você quer consultar? Ex: 'market share de caminhões em 2024'"

        logger.info("fleetintel_execute", query=raw_input[:100])

        if not FLEETINTEL_MCP_TOKEN:
            return "❌ FLEETINTEL_MCP_TOKEN não configurado. Verifique o arquivo .env."

        # Rotear para a tool correta
        tool_name, tool_args = self._route(raw_input)

        logger.info("fleetintel_routing", tool=tool_name, args=tool_args)

        try:
            result = await self._call_mcp(tool_name, tool_args)
            return self._format_response(tool_name, result, raw_input)
        except Exception as e:
            logger.error("fleetintel_error", error=str(e))
            return f"❌ Erro ao consultar dados de frota: {e}"

    # ─────────────────────────────────────────────
    # Roteamento por padrões de linguagem natural
    # ─────────────────────────────────────────────

    def _route(self, message: str) -> Tuple[str, Dict]:
        """Roteia a mensagem para a tool MCP correta."""
        msg = message.lower().strip()

        # 1. Estatísticas gerais
        if any(p in msg for p in [
            "estatística", "estatistica", "quantos veículo", "quantos veiculo",
            "total de ", "quantos no banco", "quantos registro", "resumo geral",
            "quantas empresa", "quantos emplacamento", "total geral", "stats"
        ]):
            # Se menciona empresa específica, vai para count_empresa
            empresa = self._extract_empresa(msg)
            if empresa and any(p in msg for p in ["emplacou", "emplacaram", "comprou", "comprou", "adquiriu", "quantos da"]):
                return "count_empresa_registrations", self._build_count_empresa_args(msg, empresa)
            return "get_stats", {}

        # 2. Market share / participação de mercado
        if any(p in msg for p in [
            "market share", "participação de mercado", "participacao de mercado",
            "cota de mercado", "fatia de mercado", "share", "percentual de mercado"
        ]):
            return "get_market_share", self._build_market_share_args(msg)

        # 3. Top empresas / Ranking de compradores
        if any(p in msg for p in [
            "top ", "ranking", "maiores compradores", "quem mais comprou",
            "maiores frotas", "maiores clientes", "top 10", "top 5",
            "quais empresas mais", "empresas que mais"
        ]):
            return "top_empresas_by_registrations", self._build_top_empresas_args(msg)

        # 4. Count de uma empresa específica
        empresa = self._extract_empresa(msg)
        if empresa and any(p in msg for p in [
            "emplacou", "emplacaram", "comprou", "adquiriu", "quantos da",
            "quantas da", "quantos caminhões da", "quantos caminh"
        ]):
            return "count_empresa_registrations", self._build_count_empresa_args(msg, empresa)

        # 5. Busca de empresa por nome
        if any(p in msg for p in [
            "encontre a empresa", "busca a empresa", "dados da empresa",
            "informações da empresa", "informacoes da empresa", "cnpj",
            "procure a empresa", "pesquise a empresa"
        ]):
            return "search_empresas", self._build_search_empresas_args(msg)

        # 6. Busca de veículo específico
        if any(p in msg for p in [
            "chassi", "placa", "buscar veículo", "buscar veiculo",
            "encontrar caminhão", "encontrar caminhao"
        ]):
            return "search_vehicles", self._build_search_vehicles_args(msg)

        # 7. Busca de emplacamentos por período/estado/preço
        if any(p in msg for p in [
            "emplacamentos em ", "emplacados em ", "emplacado em ",
            "emplacamentos do mês", "emplacamentos de ", "em janeiro", "em fevereiro",
            "em março", "em abril", "em maio", "em junho", "em julho",
            "em agosto", "em setembro", "em outubro", "em novembro", "em dezembro",
            "no paraná", "em são paulo", "no rio", "em minas", "no rs", "em sp",
            "em sc", "no rj", "acima de r$", "abaixo de r$", "entre r$"
        ]):
            return "search_registrations", self._build_search_registrations_args(msg)

        # 8. Fallback: se menciona empresa, tenta count; senão tenta stats
        if empresa:
            return "count_empresa_registrations", self._build_count_empresa_args(msg, empresa)

        # Fallback final: get_stats
        return "get_stats", {}

    # ─────────────────────────────────────────────
    # Extração de parâmetros
    # ─────────────────────────────────────────────

    def _extract_year(self, msg: str) -> Optional[int]:
        """Extrai ano da mensagem (2020-2026)."""
        match = re.search(r'\b(20[0-2][0-9])\b', msg)
        return int(match.group(1)) if match else None

    def _extract_uf(self, msg: str) -> Optional[str]:
        """Extrai UF da mensagem."""
        uf_map = {
            "são paulo": "SP", "sao paulo": "SP", " sp ": "SP",
            "rio de janeiro": "RJ", " rj ": "RJ",
            "minas gerais": "MG", "minas ": "MG", " mg ": "MG",
            "paraná": "PR", "parana": "PR", " pr ": "PR",
            "rio grande do sul": "RS", " rs ": "RS",
            "santa catarina": "SC", " sc ": "SC",
            "bahia": "BA", " ba ": "BA",
            "goiás": "GO", "goias": "GO", " go ": "GO",
            "mato grosso do sul": "MS", " ms ": "MS",
            "mato grosso": "MT", " mt ": "MT",
            "pernambuco": "PE", " pe ": "PE",
            "ceará": "CE", "ceara": "CE", " ce ": "CE",
            "amazonas": "AM", " am ": "AM",
            "pará": "PA", "para ": "PA", " pa ": "PA",
            "espírito santo": "ES", "espirito santo": "ES", " es ": "ES",
        }
        msg_padded = f" {msg} "
        for state_name, uf_code in uf_map.items():
            if state_name in msg_padded:
                return uf_code
        return None

    def _extract_empresa(self, msg: str) -> Optional[str]:
        """Tenta extrair nome de empresa da mensagem."""
        # Padrões: "a empresa X", "a X", "da empresa X", "da X"
        patterns = [
            r'a empresa ([A-Za-zÀ-ÖØ-öø-ÿ0-9\s&\.\-]+?) (?:em|de|no|na|comprou|emplacou|emplacaram)',
            r'da empresa ([A-Za-zÀ-ÖØ-öø-ÿ0-9\s&\.\-]+?) (?:em|de|no|na|comprou|emplacou)',
            r'da ([A-Za-zÀ-ÖØ-öø-ÿ0-9\s&\.\-]+?) (?:em|de|no|na|comprou|emplacou|emplacaram)',
            r'a ([A-Za-zÀ-ÖØ-öø-ÿ0-9\s&\.\-]+?) (?:emplacou|emplacaram|comprou|adquiriu)',
        ]
        for pattern in patterns:
            match = re.search(pattern, msg, re.IGNORECASE)
            if match:
                empresa = match.group(1).strip()
                # Filtrar artigos e preposições soltos
                if len(empresa) > 2 and empresa.lower() not in ['que', 'qual', 'quem', 'quanto']:
                    return empresa
        return None

    def _extract_limit(self, msg: str, default: int = 10) -> int:
        """Extrai número de resultados desejados."""
        match = re.search(r'top\s+(\d+)', msg)
        if match:
            return min(int(match.group(1)), 50)
        match = re.search(r'(\d+)\s+(?:maiores|principais|empresas|primeiros)', msg)
        if match:
            return min(int(match.group(1)), 50)
        return default

    def _build_market_share_args(self, msg: str) -> Dict:
        args = {}
        year = self._extract_year(msg)
        if year:
            args["year"] = year
        else:
            args["year"] = 2024  # default sensato
        uf = self._extract_uf(msg)
        if uf:
            args["uf"] = uf
        # Segmento
        for seg in ["caminhão", "caminhao", "onibus", "ônibus", "implemento"]:
            if seg in msg:
                args["segmento"] = seg.replace("ã", "a").replace("ô", "o")
                break
        return args

    def _build_top_empresas_args(self, msg: str) -> Dict:
        args = {"limit": self._extract_limit(msg)}
        year = self._extract_year(msg)
        args["year"] = year if year else 2024
        uf = self._extract_uf(msg)
        if uf:
            args["uf"] = uf
        return args

    def _build_count_empresa_args(self, msg: str, empresa: str) -> Dict:
        args = {"empresa_nome": empresa}
        year = self._extract_year(msg)
        if year:
            args["year"] = year
        return args

    def _build_search_empresas_args(self, msg: str) -> Dict:
        args = {}
        empresa = self._extract_empresa(msg)
        if empresa:
            args["razao_social"] = empresa
        uf = self._extract_uf(msg)
        if uf:
            args["uf"] = uf
        args["limit"] = 5
        return args

    def _build_search_vehicles_args(self, msg: str) -> Dict:
        args = {}
        # Chassi (17 chars alfanuméricos)
        chassi_match = re.search(r'\b([A-HJ-NPR-Z0-9]{17})\b', msg.upper())
        if chassi_match:
            args["chassi"] = chassi_match.group(1)
        # Placa (ABC-1234 ou ABC1D23)
        placa_match = re.search(r'\b([A-Z]{3}[\-\s]?[0-9][A-Z0-9][0-9]{2})\b', msg.upper())
        if placa_match:
            args["placa"] = placa_match.group(1).replace("-", "").replace(" ", "")
        # Marca
        for marca in ["scania", "volvo", "mercedes", "volkswagen", "iveco", "ford", "daf", "hyundai"]:
            if marca in msg:
                args["marca"] = marca.upper()
                break
        year = self._extract_year(msg)
        if year:
            args["ano_min"] = year
            args["ano_max"] = year
        args["limit"] = 10
        return args

    def _build_search_registrations_args(self, msg: str) -> Dict:
        args = {}
        year = self._extract_year(msg)
        if year:
            args["data_inicio"] = f"{year}-01-01"
            args["data_fim"] = f"{year}-12-31"
        uf = self._extract_uf(msg)
        if uf:
            args["uf"] = uf
        # Preço mínimo
        preco_match = re.search(r'acima de r\$\s*([\d\.]+)', msg)
        if preco_match:
            args["preco_min"] = float(preco_match.group(1).replace(".", ""))
        args["limit"] = 50
        return args

    # ─────────────────────────────────────────────
    # Chamada ao MCP server via HTTPS
    # ─────────────────────────────────────────────

    async def _call_mcp(self, tool_name: str, tool_args: Dict) -> Any:
        """Chama uma tool no FleetIntel MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_args,
            },
        }

        headers = {
            "Authorization": f"Bearer {FLEETINTEL_MCP_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(FLEETINTEL_MCP_URL, json=payload, headers=headers)

        if resp.status_code != 200:
            raise RuntimeError(f"MCP server retornou HTTP {resp.status_code}: {resp.text[:200]}")

        # O MCP pode retornar SSE ou JSON puro
        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(resp.text)
        else:
            data = resp.json()
            return self._extract_mcp_result(data)

    def _parse_sse(self, sse_text: str) -> Any:
        """Extrai o resultado de uma resposta SSE do MCP."""
        for line in sse_text.splitlines():
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    return self._extract_mcp_result(data)
                except json.JSONDecodeError:
                    continue
        return None

    def _extract_mcp_result(self, data: dict) -> Any:
        """Extrai o conteúdo de uma resposta JSON-RPC MCP."""
        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")
        result = data.get("result", {})
        content = result.get("content", [])
        if content and isinstance(content, list):
            # Pegar o primeiro bloco de texto
            for block in content:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    # Tentar deserializar como JSON para formatar melhor
                    try:
                        return json.loads(text)
                    except Exception:
                        return text
        return result

    # ─────────────────────────────────────────────
    # Formatação de respostas
    # ─────────────────────────────────────────────

    def _format_response(self, tool_name: str, result: Any, original_query: str) -> str:
        """Formata a resposta do MCP para exibição no Telegram."""
        if result is None:
            return "⚠️ Nenhum dado encontrado para esta consulta."

        try:
            if tool_name == "get_stats":
                return self._fmt_stats(result)
            elif tool_name == "get_market_share":
                return self._fmt_market_share(result)
            elif tool_name == "top_empresas_by_registrations":
                return self._fmt_top_empresas(result)
            elif tool_name == "count_empresa_registrations":
                return self._fmt_count_empresa(result)
            elif tool_name == "search_empresas":
                return self._fmt_search_empresas(result)
            elif tool_name == "search_vehicles":
                return self._fmt_search_vehicles(result)
            elif tool_name == "search_registrations":
                return self._fmt_search_registrations(result)
            else:
                # Fallback genérico
                if isinstance(result, str):
                    return f"📊 **FleetIntel**\n\n{result[:MAX_CHARS]}"
                return f"📊 **FleetIntel**\n\n```\n{json.dumps(result, ensure_ascii=False, indent=2)[:MAX_CHARS]}\n```"
        except Exception as e:
            logger.error("fleetintel_format_error", error=str(e))
            return f"📊 Dados recebidos:\n{str(result)[:MAX_CHARS]}"

    def _fmt_stats(self, r: Any) -> str:
        if isinstance(r, str):
            return f"📊 **Estatísticas FleetIntel**\n\n{r}"
        r = r if isinstance(r, dict) else {}
        lines = ["📊 **Estatísticas — Base de Frota**\n"]
        if "total_vehicles" in r:
            lines.append(f"🚛 Veículos: **{r['total_vehicles']:,}**".replace(",", "."))
        if "total_empresas" in r:
            lines.append(f"🏢 Empresas: **{r['total_empresas']:,}**".replace(",", "."))
        if "total_registrations" in r:
            lines.append(f"📋 Emplacamentos: **{r['total_registrations']:,}**".replace(",", "."))
        if "total_marcas" in r:
            lines.append(f"🔖 Marcas: **{r['total_marcas']}**")
        if "total_modelos" in r:
            lines.append(f"📐 Modelos: **{r['total_modelos']}**")
        return "\n".join(lines) if len(lines) > 1 else f"📊 {r}"

    def _fmt_market_share(self, r: Any) -> str:
        if isinstance(r, str):
            return f"📈 **Market Share**\n\n{r}"
        items = r if isinstance(r, list) else r.get("market_share", r.get("data", []))
        if not items:
            return "⚠️ Sem dados de market share para este período."
        lines = [f"📈 **Market Share — Caminhões**\n"]
        for i, item in enumerate(items[:15], 1):
            marca = item.get("marca", item.get("brand", "?"))
            total = item.get("total", item.get("count", 0))
            share = item.get("share_pct", item.get("share", 0))
            lines.append(f"{i}. **{marca}**: {total:,} un. ({share:.1f}%)".replace(",", "."))
        return "\n".join(lines)

    def _fmt_top_empresas(self, r: Any) -> str:
        if isinstance(r, str):
            return f"🏆 **Top Empresas**\n\n{r}"
        items = r if isinstance(r, list) else r.get("empresas", r.get("data", []))
        if not items:
            return "⚠️ Sem dados de ranking para este período."
        lines = ["🏆 **Top Empresas — Emplacamentos**\n"]
        for i, item in enumerate(items[:15], 1):
            nome = item.get("razao_social", item.get("nome", item.get("empresa", "?")))
            total = item.get("total", item.get("count", item.get("registrations", 0)))
            lines.append(f"{i}. **{nome[:40]}**: {total:,} un.".replace(",", "."))
        return "\n".join(lines)

    def _fmt_count_empresa(self, r: Any) -> str:
        if isinstance(r, str):
            return f"🚛 **Emplacamentos da Empresa**\n\n{r}"
        count = r.get("total", r.get("count", r.get("registrations", "?")))
        empresa = r.get("empresa", r.get("razao_social", r.get("nome", "empresa")))
        year = r.get("year", "")
        year_str = f" em {year}" if year else ""
        return f"🚛 **{empresa}**{year_str}\n\n📋 Emplacamentos: **{count}**"

    def _fmt_search_empresas(self, r: Any) -> str:
        if isinstance(r, str):
            return f"🏢 **Empresas encontradas**\n\n{r}"
        items = r if isinstance(r, list) else r.get("empresas", r.get("data", []))
        if not items:
            return "⚠️ Nenhuma empresa encontrada."
        lines = ["🏢 **Empresas encontradas**\n"]
        for item in items[:5]:
            nome = item.get("razao_social", item.get("nome", "?"))
            cnpj = item.get("cnpj", "")
            seg = item.get("segmento_cliente", item.get("segmento", ""))
            uf = item.get("uf", "")
            lines.append(f"• **{nome}**")
            if cnpj:
                lines.append(f"  CNPJ: {cnpj}")
            if seg:
                lines.append(f"  Segmento: {seg}")
            if uf:
                lines.append(f"  UF: {uf}")
            lines.append("")
        return "\n".join(lines)

    def _fmt_search_vehicles(self, r: Any) -> str:
        if isinstance(r, str):
            return f"🚛 **Veículos encontrados**\n\n{r}"
        items = r if isinstance(r, list) else r.get("vehicles", r.get("data", []))
        if not items:
            return "⚠️ Nenhum veículo encontrado."
        lines = [f"🚛 **{len(items)} veículo(s) encontrado(s)**\n"]
        for item in items[:10]:
            marca = item.get("marca", item.get("marca_nome", "?"))
            modelo = item.get("modelo", item.get("modelo_nome", "?"))
            ano = item.get("ano_fabricacao", "?")
            placa = item.get("placa", "")
            lines.append(f"• **{marca} {modelo}** ({ano}){f' — {placa}' if placa else ''}")
        return "\n".join(lines)

    def _fmt_search_registrations(self, r: Any) -> str:
        if isinstance(r, str):
            return f"📋 **Emplacamentos**\n\n{r}"
        items = r if isinstance(r, list) else r.get("registrations", r.get("data", []))
        count = len(items) if isinstance(items, list) else r.get("count", "?")
        if not items:
            return "⚠️ Nenhum emplacamento encontrado para os filtros informados."
        lines = [f"📋 **{count} emplacamento(s) encontrado(s)**\n"]
        for item in (items if isinstance(items, list) else [])[:10]:
            data = item.get("data_emplacamento", "?")
            empresa = item.get("razao_social", item.get("empresa", "?"))
            marca = item.get("marca", item.get("marca_nome", ""))
            uf = item.get("uf", item.get("uf_emplacamento", ""))
            preco = item.get("preco", None)
            preco_str = f" — R$ {preco:,.0f}".replace(",", ".") if preco else ""
            lines.append(f"• {data} | {empresa[:30]} | {marca} | {uf}{preco_str}")
        return "\n".join(lines)
