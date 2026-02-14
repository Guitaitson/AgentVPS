"""
Autonomous Loop Engine - Sistema de execução autônoma

Gerencia triggers e execução automática de tarefas.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import psycopg2
import redis
import structlog
from dotenv import load_dotenv

load_dotenv("/opt/vps-agent/core/.env")

logger = structlog.get_logger()


class Trigger:
    """Representa um trigger que pode executar automaticamente."""

    def __init__(
        self,
        name: str,
        condition: Callable[[], bool],
        action: Callable[[], Any],
        interval: int = 60,
        enabled: bool = True,
    ):
        self.name = name
        self.condition = condition
        self.action = action
        self.interval = interval  # segundos
        self.enabled = enabled
        self._task: Optional[asyncio.Task] = None

    async def run(self):
        """Executa o trigger."""
        if not self.enabled:
            return

        try:
            if self.condition():
                logger.info("trigger_executing", name=self.name)
                result = await self.action()
                logger.info("trigger_completed", name=self.name, result=result)
        except Exception as e:
            logger.error("trigger_error", name=self.name, error=str(e))


class AutonomousLoop:
    """Motor de execução autônoma."""

    def __init__(self):
        self._triggers: dict[str, Trigger] = {}
        self._running = False
        self._db_config = {
            "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "port": int(os.getenv("POSTGRES_PORT", 5432)),
            "dbname": os.getenv("POSTGRES_DB", "vps_agent"),
            "user": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD"),
        }
        self._redis = redis.Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )

    def register_trigger(self, trigger: Trigger):
        """Registra um trigger."""
        self._triggers[trigger.name] = trigger
        logger.info("trigger_registered", name=trigger.name, interval=trigger.interval)

    async def start(self):
        """Inicia o loop de execução."""
        if self._running:
            return

        self._running = True
        logger.info("autonomous_loop_started", triggers=len(self._triggers))

        while self._running:
            try:
                tasks = []
                for trigger in self._triggers.values():
                    if trigger.enabled:
                        tasks.append(trigger.run())

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                await asyncio.sleep(1)
            except Exception as e:
                logger.error("loop_error", error=str(e))
                await asyncio.sleep(5)

    def stop(self):
        """Para o loop."""
        self._running = False
        logger.info("autonomous_loop_stopped")

    def _get_conn(self):
        return psycopg2.connect(**self._db_config)


# ============================================
# FACTORY
# ============================================

_autonomous_loop: Optional[AutonomousLoop] = None


def get_autonomous_loop() -> AutonomousLoop:
    """Retorna instância singleton do loop."""
    global _autonomous_loop
    if _autonomous_loop is None:
        _autonomous_loop = AutonomousLoop()

        # Registrar triggers iniciais (S4-03)
        
        # Trigger 1: Health Check
        async def health_check_action():
            import docker
            try:
                client = docker.from_env()
                containers = client.containers.list()
                critical = ["postgres", "redis", "qdrant"]
                status = {}
                for c in containers:
                    if any(name in c.name for name in critical):
                        status[c.name] = "running" if c.status == "running" else "stopped"
                _autonomous_loop._redis.setex("health:containers", 60, json.dumps(status))
                return status
            except Exception as e:
                logger.error("health_check_error", error=str(e))
                return {}

        _autonomous_loop.register_trigger(
            Trigger(
                name="health_check",
                condition=lambda: True,
                action=health_check_action,
                interval=60,
                enabled=True,
            )
        )

        # Trigger 2: Memory Cleanup
        async def memory_cleanup_action():
            try:
                conn = _autonomous_loop._get_conn()
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM conversation_log WHERE created_at < NOW() - INTERVAL '7 days'"
                )
                deleted = cur.rowcount
                conn.commit()
                conn.close()
                if deleted > 0:
                    logger.info("memory_cleaned", deleted=deleted)
                return {"deleted": deleted}
            except Exception as e:
                logger.error("memory_cleanup_error", error=str(e))
                return {"deleted": 0}

        _autonomous_loop.register_trigger(
            Trigger(
                name="memory_cleanup",
                condition=lambda: True,
                action=memory_cleanup_action,
                interval=3600,
                enabled=True,
            )
        )

        # Trigger 3: Skill Stats
        async def skill_stats_action():
            try:
                skills = ["get_ram", "list_containers", "get_system_status", 
                          "check_postgres", "check_redis", "shell_exec", 
                          "file_manager", "memory_query", "web_search", "self_edit"]
                stats = {}
                for skill in skills:
                    count = _autonomous_loop._redis.get(f"skill_usage:{skill}")
                    stats[skill] = int(count) if count else 0

                conn = _autonomous_loop._get_conn()
                cur = conn.cursor()
                for skill, count in stats.items():
                    if count > 0:
                        cur.execute(
                            """INSERT INTO agent_skills (skill_name, success_count)
                               VALUES (%s, %s)
                               ON CONFLICT (skill_name) 
                               DO UPDATE SET success_count = agent_skills.success_count + EXCLUDED.success_count""",
                            (skill, count),
                        )
                conn.commit()
                conn.close()

                for skill in skills:
                    _autonomous_loop._redis.delete(f"skill_usage:{skill}")

                return stats
            except Exception as e:
                logger.error("skill_stats_error", error=str(e))
                return {}

        _autonomous_loop.register_trigger(
            Trigger(
                name="skill_stats",
                condition=lambda: True,
                action=skill_stats_action,
                interval=300,
                enabled=True,
            )
        )

    return _autonomous_loop


__all__ = ["AutonomousLoop", "Trigger", "get_autonomous_loop"]
