"""
Autonomous Loop Engine - Sistema de execução autônomo (T4-02)

Implementa o Blueprint de 6 passos:
1. DETECT → Trigger identifica condição
2. PROPOSE → Cria proposal no PostgreSQL
3. FILTER → Cap Gates verificam recursos/segurança
4. EXECUTE → Worker executa via Skill
5. COMPLETE → Emite evento com resultado
6. RE-TRIGGER → Evento gera novas proposals
"""

import asyncio
import json
import os
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
        self.interval = interval
        self.enabled = enabled

    async def run(self, engine: "AutonomousLoop"):
        """Executa o trigger com acesso ao engine."""
        if not self.enabled:
            return

        try:
            if self.condition():
                logger.info("trigger_executing", name=self.name)
                result = await self.action(engine)
                logger.info("trigger_completed", name=self.name, result=result)
        except Exception as e:
            logger.error("trigger_error", name=self.name, error=str(e))


class CapGate:
    """Cap Gates - verificações antes de executar uma proposal."""

    @staticmethod
    async def check_rate_limit(engine: "AutonomousLoop", proposal_id: int) -> dict:
        """Verifica rate limit: max_proposals_per_hour."""
        try:
            conn = engine._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT COUNT(*) FROM agent_proposals
                WHERE created_at > NOW() - INTERVAL '1 hour'
                AND status IN ('pending', 'approved', 'executing')"""
            )
            count = cur.fetchone()[0]
            conn.close()

            policy_limit = 10
            if count >= policy_limit:
                return {"blocked": True, "reason": f"rate_limit: {count}/{policy_limit}"}
            return {"blocked": False}
        except Exception as e:
            logger.error("cap_gate_rate_limit_error", error=str(e))
            return {"blocked": False}

    @staticmethod
    async def check_ram_threshold(engine: "AutonomousLoop", proposal_id: int) -> dict:
        """Verifica se há RAM suficiente."""
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()

            values = {}
            for line in meminfo.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    values[key.strip()] = int(val.strip().split()[0])

            values.get("MemTotal", 0) // 1024  # noqa: F841
            available = values.get("MemAvailable", 0) // 1024

            min_required = 200
            if available < min_required:
                return {"blocked": True, "reason": f"ram_low: {available}MB < {min_required}MB"}
            return {"blocked": False, "available_mb": available}
        except Exception as e:
            logger.error("cap_gate_ram_error", error=str(e))
            return {"blocked": False}

    @staticmethod
    async def check_security_level(engine: "AutonomousLoop", proposal_id: int, action: str) -> dict:
        """Verifica se ação perigosa requer aprovação."""
        dangerous_actions = ["systemctl", "rm -rf", "kill", "docker stop", "docker rm"]
        requires_approval = any(d in action for d in dangerous_actions)

        if requires_approval:
            try:
                conn = engine._get_conn()
                cur = conn.cursor()
                cur.execute(
                    """UPDATE agent_proposals
                    SET requires_approval = TRUE, status = 'pending'
                    WHERE id = %s""",
                    (proposal_id,),
                )
                conn.commit()
                conn.close()
                return {"blocked": True, "reason": "requires_approval", "action": action}
            except Exception as e:
                logger.error("cap_gate_security_error", error=str(e))

        return {"blocked": False}


class AutonomousLoop:
    """Motor de execução autônoma com PostgreSQL."""

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
                        tasks.append(trigger.run(self))

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                # Processar proposals pendentes
                await self._process_proposals()

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

    async def _process_proposals(self):
        """Processa proposals pendentes (DETECT → FILTER → EXECUTE → COMPLETE)."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT id, trigger_name, suggested_action, status
                FROM agent_proposals
                WHERE status = 'approved'
                ORDER BY priority ASC, created_at ASC
                LIMIT 1"""
            )
            proposal = cur.fetchone()
            conn.close()

            if not proposal:
                return

            proposal_id, trigger_name, suggested_action_json, status = proposal
            suggested_action = json.loads(suggested_action_json)

            # EXECUTE: executar a ação
            await self._execute_mission(proposal_id, suggested_action)

        except Exception as e:
            logger.error("process_proposals_error", error=str(e))

    async def _execute_mission(self, proposal_id: int, suggested_action: dict):
        """Executa uma missão."""
        try:
            action = suggested_action.get("action")
            args = suggested_action.get("args", {})

            logger.info("executing_mission", proposal_id=proposal_id, action=action)

            # Criar missão
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO agent_missions (proposal_id, mission_type, execution_plan, status, started_at)
                VALUES (%s, %s, %s, 'running', NOW())""",
                (proposal_id, action, json.dumps(suggested_action)),
            )
            mission_id = cur.lastrowid
            cur.execute(
                """UPDATE agent_proposals SET status = 'executing' WHERE id = %s""",
                (proposal_id,),
            )
            conn.commit()
            conn.close()

            # Executar via skill registry
            result = {"status": "completed"}
            from core.skills.registry import get_skill_registry

            registry = get_skill_registry()
            if action == "shell_exec":
                skill_result = await registry.execute_skill("shell_exec", args)
                result = {"output": skill_result}

            # Atualizar missão
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE agent_missions
                SET status = 'completed', result = %s, completed_at = NOW()
                WHERE id = %s""",
                (json.dumps(result), mission_id),
            )
            cur.execute(
                """UPDATE agent_proposals SET status = 'completed', executed_at = NOW() WHERE id = %s""",
                (proposal_id,),
            )
            conn.commit()
            conn.close()

            logger.info("mission_completed", proposal_id=proposal_id, mission_id=mission_id)

        except Exception as e:
            logger.error("mission_error", proposal_id=proposal_id, error=str(e))
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE agent_proposals SET status = 'failed' WHERE id = %s""",
                (proposal_id,),
            )
            conn.commit()
            conn.close()

    async def create_proposal(
        self, trigger_name: str, condition_data: dict, suggested_action: dict, priority: int = 5
    ) -> int:
        """Cria uma proposal no PostgreSQL (PROPOSE step)."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO agent_proposals
                (trigger_name, condition_data, suggested_action, status, priority)
                VALUES (%s, %s, %s, 'pending', %s)
                RETURNING id""",
                (trigger_name, json.dumps(condition_data), json.dumps(suggested_action), priority),
            )
            proposal_id = cur.fetchone()[0]
            conn.commit()
            conn.close()

            logger.info("proposal_created", trigger=trigger_name, proposal_id=proposal_id)

            # FILTER: verificar cap gates
            await self._check_cap_gates(proposal_id, suggested_action)

            return proposal_id

        except Exception as e:
            logger.error("create_proposal_error", error=str(e))
            return -1

    async def _check_cap_gates(self, proposal_id: int, suggested_action: dict):
        """Executa as verificações de cap gates."""
        action = suggested_action.get("action", "")

        # Rate limit
        result = await CapGate.check_rate_limit(self, proposal_id)
        if result.get("blocked"):
            self._reject_proposal(proposal_id, result["reason"])
            return

        # RAM threshold
        result = await CapGate.check_ram_threshold(self, proposal_id)
        if result.get("blocked"):
            self._reject_proposal(proposal_id, result["reason"])
            return

        # Security
        result = await CapGate.check_security_level(self, proposal_id, action)
        if result.get("blocked"):
            # Já marcado para aprovação na função
            return

        # Aprovar automaticamente
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """UPDATE agent_proposals SET status = 'approved' WHERE id = %s""",
            (proposal_id,),
        )
        conn.commit()
        conn.close()

    def _reject_proposal(self, proposal_id: int, reason: str):
        """Rejeita uma proposal."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE agent_proposals SET status = 'rejected', approval_note = %s WHERE id = %s""",
                (reason, proposal_id),
            )
            conn.commit()
            conn.close()
            logger.info("proposal_rejected", proposal_id=proposal_id, reason=reason)
        except Exception as e:
            logger.error("reject_proposal_error", error=str(e))


# ============================================
# FACTORY
# ============================================

_autonomous_loop: Optional[AutonomousLoop] = None


def get_autonomous_loop() -> AutonomousLoop:
    """Retorna instância singleton do loop."""
    global _autonomous_loop
    if _autonomous_loop is None:
        _autonomous_loop = AutonomousLoop()

        # ============================================
        # TRIGGERS COM CONDIÇÕES REAIS
        # ============================================

        # Trigger 1: Health Check
        async def health_check_action(engine: AutonomousLoop):
            import docker

            try:
                client = docker.from_env()
                containers = client.containers.list()
                critical = ["postgres", "redis", "qdrant"]
                status = {}
                for c in containers:
                    if any(name in c.name for name in critical):
                        status[c.name] = "running" if c.status == "running" else "stopped"
                engine._redis.setex("health:containers", 60, json.dumps(status))
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
        async def memory_cleanup_action(engine: AutonomousLoop):
            try:
                conn = engine._get_conn()
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
        async def skill_stats_action(engine: AutonomousLoop):
            try:
                skills = [
                    "get_ram",
                    "list_containers",
                    "get_system_status",
                    "check_postgres",
                    "check_redis",
                    "shell_exec",
                    "file_manager",
                    "memory_query",
                    "web_search",
                    "self_edit",
                ]
                stats = {}
                for skill in skills:
                    count = engine._redis.get(f"skill_usage:{skill}")
                    stats[skill] = int(count) if count else 0

                conn = engine._get_conn()
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
                    engine._redis.delete(f"skill_usage:{skill}")

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

        # Trigger 4: RAM > 80% → criar proposal
        def check_ram_condition() -> bool:
            try:
                with open("/proc/meminfo", "r") as f:
                    meminfo = f.read()

                values = {}
                for line in meminfo.split("\n"):
                    if ":" in line:
                        key, val = line.split(":", 1)
                        values[key.strip()] = int(val.strip().split()[0])

                total = values.get("MemTotal", 0) // 1024
                available = values.get("MemAvailable", 0) // 1024

                if total > 0:
                    used_percent = ((total - available) / total) * 100
                    return used_percent > 80
            except Exception:
                pass
            return False

        async def ram_high_action(engine: AutonomousLoop):
            suggested_action = {
                "action": "shell_exec",
                "args": {
                    "command": "docker ps -a --filter 'status=exited' --format '{{.ID}}' | head -5"
                },
                "description": "Limpar containers Docker inativos",
            }
            await engine.create_proposal(
                trigger_name="ram_high",
                condition_data={"ram_percent": 80},
                suggested_action=suggested_action,
                priority=3,
            )
            return {"status": "proposal_created"}

        _autonomous_loop.register_trigger(
            Trigger(
                name="ram_high",
                condition=check_ram_condition,
                action=ram_high_action,
                interval=300,
                enabled=True,
            )
        )

        # Trigger 5: Error repeated → criar proposal
        async def error_repeated_action(engine: AutonomousLoop):
            try:
                conn = engine._get_conn()
                cur = conn.cursor()
                cur.execute(
                    """SELECT trigger, COUNT(*) as count
                    FROM learnings
                    WHERE category = 'execution_error'
                    AND created_at > NOW() - INTERVAL '1 hour'
                    GROUP BY trigger
                    HAVING COUNT(*) > 3"""
                )
                errors = cur.fetchall()
                conn.close()

                if errors:
                    error_triggers = [e[0] for e in errors]
                    logger.warning("trigger_error_repeated", errors=error_triggers)

                    suggested_action = {
                        "action": "investigate_errors",
                        "args": {"error_triggers": error_triggers},
                        "description": "Investigar erros repetidos",
                    }
                    await engine.create_proposal(
                        trigger_name="error_repeated",
                        condition_data={"errors": error_triggers},
                        suggested_action=suggested_action,
                        priority=2,
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
                interval=600,
                enabled=True,
            )
        )

        # Trigger 6: Schedule due → criar proposal
        async def schedule_due_action(engine: AutonomousLoop):
            try:
                conn = engine._get_conn()
                cur = conn.cursor()
                cur.execute(
                    """SELECT id, task_name, scheduled_time
                    FROM scheduled_tasks
                    WHERE status = 'pending'
                    AND scheduled_time <= NOW()
                    LIMIT 5"""
                )
                tasks = cur.fetchall()
                conn.close()

                if tasks:
                    task_list = [{"id": t[0], "name": t[1], "time": str(t[2])} for t in tasks]
                    logger.info("trigger_schedule_due", tasks=task_list)

                    suggested_action = {
                        "action": "execute_scheduled",
                        "args": {"tasks": task_list},
                        "description": "Executar tarefas agendadas",
                    }
                    await engine.create_proposal(
                        trigger_name="schedule_due",
                        condition_data={"tasks": task_list},
                        suggested_action=suggested_action,
                        priority=4,
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
                interval=60,
                enabled=True,
            )
        )

    return _autonomous_loop


__all__ = ["AutonomousLoop", "Trigger", "get_autonomous_loop", "CapGate"]
