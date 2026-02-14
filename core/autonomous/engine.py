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

        # ============================================
        # TRIGGERS PLANEJADOS (S4-03 original)
        # ============================================

        # Trigger 4: RAM > 80% → propor limpeza de containers inativos
        def check_ram_condition() -> bool:
            """Verifica se RAM está acima de 80%."""
            try:
                with open("/proc/meminfo", "r") as f:
                    meminfo = f.read()
                
                values = {}
                for line in meminfo.split("\n"):
                    if ":" in line:
                        key, val = line.split(":", 1)
                        values[key.strip()] = int(val.strip().split()[0])
                
                total = values.get("MemTotal", 0) // 1024  # MB
                available = values.get("MemAvailable", 0) // 1024  # MB
                
                if total > 0:
                    used_percent = ((total - available) / total) * 100
                    return used_percent > 80
            except Exception:
                pass
            return False

        async def ram_high_action():
            """Dispara quando RAM > 80%."""
            logger.warning("trigger_ram_high", message="RAM acima de 80%, propomos limpeza de containers inativos")
            # Salvar proposta no Redis para notificação
            _autonomous_loop._redis.setex(
                "proposal:ram_high",
                3600,
                json.dumps({
                    "trigger": "ram_high",
                    "action": "shell_exec",
                    "args": {"command": "docker ps -a --filter 'status=exited' --format '{{.ID}}' | head -5"},
                    "description": "Limpar containers Docker inativos"
                })
            )
            return {"status": "proposal_created", "type": "ram_high"}

        _autonomous_loop.register_trigger(
            Trigger(
                name="ram_high",
                condition=check_ram_condition,
                action=ram_high_action,
                interval=300,  # 5 min
                enabled=True,
            )
        )

        # Trigger 5: Erro repetido (>3x em 1 hora) → propor investigação
        async def error_repeated_action():
            """Detecta erros repetidos nos aprendizados."""
            try:
                conn = _autonomous_loop._get_conn()
                cur = conn.cursor()
                cur.execute("""
                    SELECT trigger, COUNT(*) as count 
                    FROM learnings 
                    WHERE category = 'execution_error' 
                    AND created_at > NOW() - INTERVAL '1 hour'
                    GROUP BY trigger 
                    HAVING COUNT(*) > 3
                """)
                errors = cur.fetchall()
                conn.close()
                
                if errors:
                    error_triggers = [e[0] for e in errors]
                    logger.warning("trigger_error_repeated", errors=error_triggers)
                    
                    _autonomous_loop._redis.setex(
                        "proposal:error_repeated",
                        3600,
                        json.dumps({
                            "trigger": "error_repeated",
                            "action": "investigate_errors",
                            "args": {"error_triggers": error_triggers},
                            "description": f"Investigar erros repetidos: {error_triggers}"
                        })
                    )
                    return {"status": "proposal_created", "errors": error_triggers}
            except Exception as e:
                logger.error("error_repeated_check_error", error=str(e))
            return {"status": "no_errors"}

        _autonomous_loop.register_trigger(
            Trigger(
                name="error_repeated",
                condition=lambda: True,
                action=error_repeated_action,
                interval=600,  # 10 min
                enabled=True,
            )
        )

        # Trigger 6: Tarefa agendada vencida → propor execução
        async def schedule_due_action():
            """Verifica tarefas agendadas pendentes."""
            try:
                conn = _autonomous_loop._get_conn()
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, task_name, scheduled_time 
                    FROM scheduled_tasks 
                    WHERE status = 'pending' 
                    AND scheduled_time <= NOW()
                    LIMIT 5
                """)
                tasks = cur.fetchall()
                conn.close()
                
                if tasks:
                    task_list = [{"id": t[0], "name": t[1], "time": str(t[2])} for t in tasks]
                    logger.info("trigger_schedule_due", tasks=task_list)
                    
                    _autonomous_loop._redis.setex(
                        "proposal:schedule_due",
                        3600,
                        json.dumps({
                            "trigger": "schedule_due",
                            "action": "execute_scheduled",
                            "args": {"tasks": task_list},
                            "description": f"Executar tarefas agendadas: {[t['name'] for t in task_list]}"
                        })
                    )
                    return {"status": "proposal_created", "tasks": task_list}
            except Exception as e:
                logger.error("schedule_due_check_error", error=str(e))
            return {"status": "no_tasks"}

        _autonomous_loop.register_trigger(
            Trigger(
                name="schedule_due",
                condition=lambda: True,
                action=schedule_due_action,
                interval=60,  # 1 min
                enabled=True,
            )
        )

    return _autonomous_loop


__all__ = ["AutonomousLoop", "Trigger", "get_autonomous_loop"]
