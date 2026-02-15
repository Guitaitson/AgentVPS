"""Skill: Check Redis — Verifica conexão Redis."""

import os
from typing import Any, Dict

import redis

from core.skills.base import SkillBase


class RedisSkill(SkillBase):
    """Verifica conexão e status do Redis."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        try:
            r = redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD") or None,
                socket_timeout=5,
                socket_connect_timeout=5,
            )

            # Test connection
            r.ping()

            # Get info
            info = r.info()
            version = info.get("redis_version", "unknown")
            used_memory = info.get("used_memory_human", "unknown")
            keys_count = r.dbsize()

            return (
                f"✅ **Redis**\n\n"
                f"Status: Online\n"
                f"Versão: {version}\n"
                f"Memória usada: {used_memory}\n"
                f"Chaves: {keys_count}"
            )

        except redis.ConnectionError:
            return "❌ **Redis**\n\nNão conecta: Connection refused"
        except redis.TimeoutError:
            return "❌ **Redis**\n\nTimeout na conexão"
        except Exception as e:
            return f"❌ **Redis**\n\nErro: {str(e)}"
