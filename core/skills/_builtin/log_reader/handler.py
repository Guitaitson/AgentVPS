"""
Skill: Log Reader - Auto-observabilidade do agente.

Permite ao agente ler seus próprios logs de erros, execuções e
estatísticas para auto-diagnóstico autônomo.
"""

import os
from typing import Any, Dict

import structlog

from core.skills.base import SkillBase

logger = structlog.get_logger()


class LogReaderSkill(SkillBase):
    """Lê logs internos do agente para auto-diagnóstico."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        args = args or {}
        query_type = args.get("query_type", "all_recent")
        limit = int(args.get("limit", 10))

        try:
            if query_type == "recent_errors":
                return self._read_errors(limit)
            elif query_type == "skill_stats":
                return self._read_skill_stats(limit)
            else:
                return self._read_all(limit)
        except Exception as e:
            logger.error("log_reader_error", error=str(e))
            return f"Erro ao ler logs: {e}"

    def _read_errors(self, limit: int) -> str:
        """Lê erros recentes da tabela learnings."""
        from core.vps_langgraph.learnings import LearningsManager

        mgr = LearningsManager()
        results = mgr.search_learnings("", limit=limit)

        # Filtrar apenas erros
        errors = [r for r in results if r.get("category") == "execution_error"]

        if not errors:
            return "Nenhum erro recente registrado. O sistema está operando normalmente."

        lines = [f"**Erros Recentes** ({len(errors)} encontrados)\n"]
        for err in errors[:limit]:
            trigger = err.get("trigger", "?")
            lesson = err.get("lesson", "?")[:150]
            created = str(err.get("created_at", "?"))[:19]
            lines.append(f"- [{created}] **{trigger}**: {lesson}")

        return "\n".join(lines)

    def _read_skill_stats(self, limit: int) -> str:
        """Lê estatísticas de uso de skills do Redis."""
        import redis

        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )

        stats = []
        for key in r.scan_iter("skill_usage:*"):
            skill_name = key.replace("skill_usage:", "")
            count = r.get(key)
            stats.append((skill_name, int(count or 0)))

        r.close()

        if not stats:
            return "Nenhuma estatística de skills registrada ainda."

        stats.sort(key=lambda x: x[1], reverse=True)

        lines = ["**Estatísticas de Skills**\n"]
        for name, count in stats[:limit]:
            lines.append(f"- **{name}**: {count} execuções")

        return "\n".join(lines)

    def _read_all(self, limit: int) -> str:
        """Retorna resumo geral: erros + stats."""
        parts = []

        # Erros recentes
        errors_section = self._read_errors(min(limit, 5))
        parts.append(errors_section)

        parts.append("")  # Separador

        # Stats de skills
        stats_section = self._read_skill_stats(min(limit, 5))
        parts.append(stats_section)

        # Contagem de conversas
        try:
            import psycopg2

            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                dbname=os.getenv("POSTGRES_DB", "vps_agent"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
            )
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM conversation_log")
            count = cur.fetchone()[0]
            conn.close()
            parts.append(f"\n**Conversas registradas**: {count} mensagens no total")
        except Exception:
            pass

        return "\n".join(parts)
