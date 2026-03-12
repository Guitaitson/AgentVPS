"""FleetIntel skill backed by the external FleetIntel MCP server."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Tuple

import structlog

from core.integrations import RemoteMCPClient
from core.skills.base import SkillBase

logger = structlog.get_logger()

FLEETINTEL_MCP_URL = os.getenv("FLEETINTEL_MCP_URL", "https://agent-fleet.gtaitson.space/mcp")
FLEETINTEL_CF_ACCESS_CLIENT_ID = os.getenv("FLEETINTEL_CF_ACCESS_CLIENT_ID", "")
FLEETINTEL_CF_ACCESS_CLIENT_SECRET = os.getenv("FLEETINTEL_CF_ACCESS_CLIENT_SECRET", "")

MAX_CHARS = 3000


class FleetIntelSkill(SkillBase):
    """Skill para consultas de dados de frota de veiculos pesados."""

    async def execute(self, args: Dict[str, Any] | None = None) -> str:
        args = args or {}
        raw_input = args.get("raw_input", args.get("query", ""))

        if not raw_input:
            return "Qual dado de frota voce quer consultar? Ex: 'market share de caminhoes em 2024'"

        logger.info("fleetintel_execute", query=str(raw_input)[:100])

        client = RemoteMCPClient(
            base_url=FLEETINTEL_MCP_URL,
            access_client_id=FLEETINTEL_CF_ACCESS_CLIENT_ID,
            access_client_secret=FLEETINTEL_CF_ACCESS_CLIENT_SECRET,
            client_name="agentvps-fleetintel",
            server_name="fleetintel",
        )
        if not client.is_configured:
            return (
                "FleetIntel MCP nao configurado. Ajuste FLEETINTEL_MCP_URL, "
                "FLEETINTEL_CF_ACCESS_CLIENT_ID e FLEETINTEL_CF_ACCESS_CLIENT_SECRET."
            )

        tool_name, tool_args = self._route(str(raw_input))
        logger.info("fleetintel_routing", tool=tool_name, args=tool_args)

        try:
            result = await self._call_mcp(client, tool_name, tool_args)
            return self._format_response(tool_name, result, str(raw_input))
        except Exception as exc:
            logger.error("fleetintel_error", error=str(exc))
            return f"Erro ao consultar dados de frota: {exc}"

    def _route(self, message: str) -> Tuple[str, Dict[str, Any]]:
        msg = message.lower().strip()

        if any(
            p in msg
            for p in [
                "estatistica",
                "quantos veiculo",
                "total de ",
                "quantos no banco",
                "quantos registro",
                "resumo geral",
                "quantas empresa",
                "quantos emplacamento",
                "total geral",
                "stats",
            ]
        ):
            empresa = self._extract_empresa(msg)
            if empresa and any(
                p in msg for p in ["emplacou", "emplacaram", "comprou", "adquiriu", "quantos da"]
            ):
                return "count_empresa_registrations", self._build_count_empresa_args(msg, empresa)
            return "get_stats", {}

        if any(
            p in msg
            for p in [
                "market share",
                "participacao de mercado",
                "cota de mercado",
                "fatia de mercado",
                "share",
                "percentual de mercado",
            ]
        ):
            return "get_market_share", self._build_market_share_args(msg)

        if any(
            p in msg
            for p in [
                "top ",
                "ranking",
                "maiores compradores",
                "quem mais comprou",
                "maiores frotas",
                "maiores clientes",
                "top 10",
                "top 5",
                "quais empresas mais",
                "empresas que mais",
            ]
        ):
            return "top_empresas_by_registrations", self._build_top_empresas_args(msg)

        empresa = self._extract_empresa(msg)
        if empresa and any(
            p in msg
            for p in [
                "emplacou",
                "emplacaram",
                "comprou",
                "adquiriu",
                "quantos da",
                "quantas da",
                "quantos caminhoes da",
                "quantos caminh",
            ]
        ):
            return "count_empresa_registrations", self._build_count_empresa_args(msg, empresa)

        if any(
            p in msg
            for p in [
                "encontre a empresa",
                "busca a empresa",
                "dados da empresa",
                "informacoes da empresa",
                "cnpj",
                "procure a empresa",
                "pesquise a empresa",
            ]
        ):
            return "search_empresas", self._build_search_empresas_args(msg)

        if any(
            p in msg
            for p in [
                "chassi",
                "placa",
                "buscar veiculo",
                "encontrar caminhao",
            ]
        ):
            return "search_vehicles", self._build_search_vehicles_args(msg)

        if any(
            p in msg
            for p in [
                "emplacamentos em ",
                "emplacados em ",
                "emplacado em ",
                "emplacamentos do mes",
                "emplacamentos de ",
                "em janeiro",
                "em fevereiro",
                "em marco",
                "em abril",
                "em maio",
                "em junho",
                "em julho",
                "em agosto",
                "em setembro",
                "em outubro",
                "em novembro",
                "em dezembro",
                "no parana",
                "em sao paulo",
                "no rio",
                "em minas",
                "no rs",
                "em sp",
                "em sc",
                "no rj",
                "acima de r$",
                "abaixo de r$",
                "entre r$",
            ]
        ):
            return "search_registrations", self._build_search_registrations_args(msg)

        if empresa:
            return "count_empresa_registrations", self._build_count_empresa_args(msg, empresa)
        return "get_stats", {}

    def _extract_year(self, msg: str) -> Optional[int]:
        match = re.search(r"\b(20[0-2][0-9])\b", msg)
        return int(match.group(1)) if match else None

    def _extract_uf(self, msg: str) -> Optional[str]:
        uf_map = {
            "sao paulo": "SP",
            " sp ": "SP",
            "rio de janeiro": "RJ",
            " rj ": "RJ",
            "minas gerais": "MG",
            "minas ": "MG",
            " mg ": "MG",
            "parana": "PR",
            " pr ": "PR",
            "rio grande do sul": "RS",
            " rs ": "RS",
            "santa catarina": "SC",
            " sc ": "SC",
            "bahia": "BA",
            " ba ": "BA",
            "goias": "GO",
            " go ": "GO",
            "mato grosso do sul": "MS",
            " ms ": "MS",
            "mato grosso": "MT",
            " mt ": "MT",
            "pernambuco": "PE",
            " pe ": "PE",
            "ceara": "CE",
            " ce ": "CE",
            "amazonas": "AM",
            " am ": "AM",
            "para ": "PA",
            " pa ": "PA",
            "espirito santo": "ES",
            " es ": "ES",
        }
        msg_padded = f" {msg} "
        for state_name, uf_code in uf_map.items():
            if state_name in msg_padded:
                return uf_code
        return None

    def _extract_empresa(self, msg: str) -> Optional[str]:
        patterns = [
            r"a empresa ([A-Za-z0-9\s&\.\-]+?) (?:em|de|no|na|comprou|emplacou|emplacaram)",
            r"da empresa ([A-Za-z0-9\s&\.\-]+?) (?:em|de|no|na|comprou|emplacou)",
            r"da ([A-Za-z0-9\s&\.\-]+?) (?:em|de|no|na|comprou|emplacou|emplacaram)",
            r"a ([A-Za-z0-9\s&\.\-]+?) (?:emplacou|emplacaram|comprou|adquiriu)",
        ]
        for pattern in patterns:
            match = re.search(pattern, msg, re.IGNORECASE)
            if not match:
                continue
            empresa = match.group(1).strip()
            if len(empresa) > 2 and empresa.lower() not in ["que", "qual", "quem", "quanto"]:
                return empresa
        return None

    def _extract_limit(self, msg: str, default: int = 10) -> int:
        match = re.search(r"top\s+(\d+)", msg)
        if match:
            return min(int(match.group(1)), 50)
        match = re.search(r"(\d+)\s+(?:maiores|principais|empresas|primeiros)", msg)
        if match:
            return min(int(match.group(1)), 50)
        return default

    def _build_market_share_args(self, msg: str) -> Dict[str, Any]:
        year = self._extract_year(msg)
        args: Dict[str, Any] = {"ano": year if year else 2024}
        uf = self._extract_uf(msg)
        if uf:
            args["uf"] = uf
        limit = self._extract_limit(msg, default=0)
        if limit:
            args["top_n"] = limit
        return args

    def _build_top_empresas_args(self, msg: str) -> Dict[str, Any]:
        year = self._extract_year(msg)
        args: Dict[str, Any] = {"ano": year if year else 2024}
        args["top_n"] = self._extract_limit(msg, default=10)
        uf = self._extract_uf(msg)
        if uf:
            args["uf"] = uf
        return args

    def _build_count_empresa_args(self, msg: str, empresa: str) -> Dict[str, Any]:
        args: Dict[str, Any] = {"razao_social": empresa}
        year = self._extract_year(msg)
        if year:
            args["ano"] = year
        return args

    def _build_search_empresas_args(self, msg: str) -> Dict[str, Any]:
        args: Dict[str, Any] = {"limit": 5}
        empresa = self._extract_empresa(msg)
        if empresa:
            args["razao_social"] = empresa
        return args

    def _build_search_vehicles_args(self, msg: str) -> Dict[str, Any]:
        args: Dict[str, Any] = {}
        chassi_match = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", msg.upper())
        if chassi_match:
            args["chassi"] = chassi_match.group(1)
        placa_match = re.search(r"\b([A-Z]{3}[\-\s]?[0-9][A-Z0-9][0-9]{2})\b", msg.upper())
        if placa_match:
            args["placa"] = placa_match.group(1).replace("-", "").replace(" ", "")
        for marca in [
            "scania",
            "volvo",
            "mercedes",
            "volkswagen",
            "iveco",
            "ford",
            "daf",
            "hyundai",
            "vw",
        ]:
            if marca in msg:
                args["marca"] = marca.upper().replace("VW", "VW")
                break
        year = self._extract_year(msg)
        if year:
            args["ano_fabricacao_min"] = year
            args["ano_fabricacao_max"] = year
        args["limit"] = 10
        return args

    def _build_search_registrations_args(self, msg: str) -> Dict[str, Any]:
        args: Dict[str, Any] = {"limit": 50}
        year = self._extract_year(msg)
        if year:
            args["data_emplacamento_inicio"] = f"{year}-01-01"
            args["data_emplacamento_fim"] = f"{year}-12-31"
        uf = self._extract_uf(msg)
        if uf:
            args["uf_emplacamento"] = uf
        preco_match = re.search(r"acima de r\$\s*([\d\.]+)", msg)
        if preco_match:
            args["preco_min"] = float(preco_match.group(1).replace(".", ""))
        return args

    async def _call_mcp(
        self, client: RemoteMCPClient, tool_name: str, tool_args: Dict[str, Any]
    ) -> Any:
        return await client.call_tool(tool_name, tool_args)

    def _format_response(self, tool_name: str, result: Any, original_query: str) -> str:
        if result is None:
            return "Nenhum dado encontrado para esta consulta."

        try:
            if tool_name == "get_stats":
                return self._fmt_stats(result)
            if tool_name == "get_market_share":
                return self._fmt_market_share(result)
            if tool_name == "top_empresas_by_registrations":
                return self._fmt_top_empresas(result)
            if tool_name == "count_empresa_registrations":
                return self._fmt_count_empresa(result)
            if tool_name == "search_empresas":
                return self._fmt_search_empresas(result)
            if tool_name == "search_vehicles":
                return self._fmt_search_vehicles(result)
            if tool_name == "search_registrations":
                return self._fmt_search_registrations(result)
            if isinstance(result, str):
                return f"FleetIntel\n\n{result[:MAX_CHARS]}"
            return (
                "FleetIntel\n\n```\n"
                f"{json.dumps(result, ensure_ascii=False, indent=2)[:MAX_CHARS]}\n```"
            )
        except Exception as exc:
            logger.error("fleetintel_format_error", error=str(exc), query=original_query[:80])
            return f"FleetIntel\n\n{str(result)[:MAX_CHARS]}"

    def _fmt_stats(self, data: Any) -> str:
        if isinstance(data, str):
            return f"Estatisticas FleetIntel\n\n{data}"
        payload = data if isinstance(data, dict) else {}
        stats = payload.get("stats", payload)
        lines = ["Estatisticas - Base de Frota", ""]
        vehicles = stats.get("vehicles", stats.get("total_vehicles"))
        empresas = stats.get("empresas", stats.get("total_empresas"))
        registrations = stats.get("registrations", stats.get("total_registrations"))
        marcas = stats.get("marcas", stats.get("total_marcas"))
        modelos = stats.get("modelos", stats.get("total_modelos"))
        if vehicles is not None:
            lines.append(f"Veiculos: {int(vehicles):,}".replace(",", "."))
        if empresas is not None:
            lines.append(f"Empresas: {int(empresas):,}".replace(",", "."))
        if registrations is not None:
            lines.append(f"Emplacamentos: {int(registrations):,}".replace(",", "."))
        if marcas is not None:
            lines.append(f"Marcas: {marcas}")
        if modelos is not None:
            lines.append(f"Modelos: {modelos}")
        if payload.get("timestamp"):
            lines.append("")
            lines.append(f"Atualizado: {payload['timestamp'][:10]}")
        return "\n".join(lines) if len(lines) > 2 else f"FleetIntel\n\n{payload}"

    def _fmt_market_share(self, data: Any) -> str:
        if isinstance(data, str):
            return f"Market Share\n\n{data}"
        items = (
            data
            if isinstance(data, list)
            else data.get("marcas", data.get("market_share", data.get("data", [])))
        )
        ano = data.get("ano", "") if isinstance(data, dict) else ""
        uf = data.get("uf", "") if isinstance(data, dict) else ""
        title = f"Market Share - Caminhoes{f' {ano}' if ano else ''}{f' ({uf})' if uf else ''}"
        if not items:
            return f"{title}\n\nSem dados de market share para este periodo."
        lines = [title, ""]
        for index, item in enumerate(items[:15], 1):
            marca = item.get("marca", item.get("brand", "?"))
            total = item.get("total_emplacamentos", item.get("total", item.get("count", 0)))
            share = item.get("market_share_pct", item.get("share_pct", item.get("share", 0)))
            lines.append(f"{index}. {marca}: {int(total):,} un. ({share:.1f}%)".replace(",", "."))
        return "\n".join(lines)

    def _fmt_top_empresas(self, data: Any) -> str:
        if isinstance(data, str):
            return f"Top Empresas\n\n{data}"
        items = data if isinstance(data, list) else data.get("empresas", data.get("data", []))
        ano = data.get("ano", "") if isinstance(data, dict) else ""
        uf = data.get("uf", "") if isinstance(data, dict) else ""
        title = f"Top Empresas - Emplacamentos{f' {ano}' if ano else ''}{f' ({uf})' if uf else ''}"
        if not items:
            return f"{title}\n\nSem dados de ranking para este periodo."
        lines = [title, ""]
        for index, item in enumerate(items[:15], 1):
            nome = item.get("razao_social", item.get("nome", item.get("empresa", "?")))
            total = item.get("total_registrations", item.get("total", item.get("count", 0)))
            lines.append(f"{index}. {nome[:45]}: {int(total):,} un.".replace(",", "."))
        return "\n".join(lines)

    def _fmt_count_empresa(self, data: Any) -> str:
        if isinstance(data, str):
            return f"Emplacamentos da Empresa\n\n{data}"
        count = data.get("total", data.get("count", data.get("total_registrations", "?")))
        empresa = data.get("razao_social", data.get("empresa", data.get("nome", "empresa")))
        year = data.get("ano", data.get("year", ""))
        year_str = f" em {year}" if year else ""
        return f"{empresa}{year_str}\n\nEmplacamentos: {count}"

    def _fmt_search_empresas(self, data: Any) -> str:
        if isinstance(data, str):
            return f"Empresas encontradas\n\n{data}"
        items = data if isinstance(data, list) else data.get("empresas", data.get("data", []))
        if not items:
            return "Nenhuma empresa encontrada."
        lines = ["Empresas encontradas", ""]
        for item in items[:5]:
            nome = item.get("razao_social", item.get("nome", "?"))
            cnpj = item.get("cnpj", "")
            seg = item.get("segmento_cliente", item.get("segmento", ""))
            uf = item.get("uf", "")
            lines.append(f"- {nome}")
            if cnpj:
                lines.append(f"  CNPJ: {cnpj}")
            if seg:
                lines.append(f"  Segmento: {seg}")
            if uf:
                lines.append(f"  UF: {uf}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _fmt_search_vehicles(self, data: Any) -> str:
        if isinstance(data, str):
            return f"Veiculos encontrados\n\n{data}"
        items = data if isinstance(data, list) else data.get("vehicles", data.get("data", []))
        if not items:
            return "Nenhum veiculo encontrado."
        lines = [f"{len(items)} veiculo(s) encontrado(s)", ""]
        for item in items[:10]:
            marca = item.get("marca", item.get("marca_nome", "?"))
            modelo = item.get("modelo", item.get("modelo_nome", "?"))
            ano = item.get("ano_fabricacao", "?")
            placa = item.get("placa", "")
            suffix = f" - {placa}" if placa else ""
            lines.append(f"- {marca} {modelo} ({ano}){suffix}")
        return "\n".join(lines)

    def _fmt_search_registrations(self, data: Any) -> str:
        if isinstance(data, str):
            return f"Emplacamentos\n\n{data}"
        items = data if isinstance(data, list) else data.get("registrations", data.get("data", []))
        count = len(items) if isinstance(items, list) else data.get("count", "?")
        if not items:
            return "Nenhum emplacamento encontrado para os filtros informados."
        lines = [f"{count} emplacamento(s) encontrado(s)", ""]
        for item in (items if isinstance(items, list) else [])[:10]:
            data_emplacamento = item.get("data_emplacamento", "?")
            empresa = item.get("razao_social", item.get("empresa", "?"))
            marca = item.get("marca", item.get("marca_nome", ""))
            uf = item.get("uf", item.get("uf_emplacamento", ""))
            preco = item.get("preco")
            preco_str = f" - R$ {preco:,.0f}".replace(",", ".") if preco else ""
            lines.append(f"- {data_emplacamento} | {empresa[:30]} | {marca} | {uf}{preco_str}")
        return "\n".join(lines)
