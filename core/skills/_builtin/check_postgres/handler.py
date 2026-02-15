"""Skill: Check PostgreSQL — Verifica conexão PostgreSQL."""

import os
from typing import Any, Dict

import psycopg2

from core.skills.base import SkillBase


class PostgresSkill(SkillBase):
    """Verifica conexão e status do PostgreSQL."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        try:
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                dbname=os.getenv("POSTGRES_DB", "vps_agent"),
                user=os.getenv("POSTGRES_USER", "vps_agent"),
                password=os.getenv("POSTGRES_PASSWORD", "postgres"),
                connect_timeout=5,
            )

            # Get version
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0].split()[1]

            # Get database size
            cursor.execute(
                """
                SELECT pg_size_pretty(pg_database_size(%s));
            """,
                (os.getenv("POSTGRES_DB", "vps_agent"),),
            )
            size = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            return f"✅ **PostgreSQL**\n\nStatus: Online\nVersão: {version}\nTamanho: {size}"

        except psycopg2.OperationalError as e:
            return f"❌ **PostgreSQL**\n\nNão conecta: {str(e)}"
        except Exception as e:
            return f"❌ **PostgreSQL**\n\nErro: {str(e)}"
