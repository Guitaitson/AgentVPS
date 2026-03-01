"""
Hook System — pre/post execution hooks para skills.

Inspirado no OpenClaw hook-runner-global.ts.
Permite logging, metricas, e feedback loop
sem modificar os skills individuais.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class HookContext:
    """Contexto passado para cada hook."""

    skill_name: str
    args: Dict[str, Any]
    user_id: str
    timestamp: float = field(default_factory=time.time)
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class HookRunner:
    """Executa hooks pre/post execution."""

    def __init__(self):
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []

    def register_pre(self, hook: Callable):
        """Registra hook pre-execucao."""
        self._pre_hooks.append(hook)

    def register_post(self, hook: Callable):
        """Registra hook pos-execucao."""
        self._post_hooks.append(hook)

    async def run_pre(self, ctx: HookContext) -> bool:
        """Roda hooks pre-execucao. Retorna False para cancelar."""
        for hook in self._pre_hooks:
            try:
                result = await hook(ctx)
                if result is False:
                    logger.info("hook_vetoed", hook=hook.__name__, skill=ctx.skill_name)
                    return False
            except Exception as e:
                logger.error("pre_hook_error", hook=hook.__name__, error=str(e))
        return True

    async def run_post(self, ctx: HookContext):
        """Roda hooks pos-execucao."""
        for hook in self._post_hooks:
            try:
                await hook(ctx)
            except Exception as e:
                logger.error("post_hook_error", hook=hook.__name__, error=str(e))


# ============================================
# Builtin Hooks
# ============================================


async def logging_hook(ctx: HookContext):
    """Hook: Logging estruturado completo de execucoes (para auto-diagnostico)."""
    logger.info(
        "skill_executed",
        skill=ctx.skill_name,
        args=str(ctx.args)[:200],
        duration_ms=ctx.duration_ms,
        success=ctx.error is None,
        user_id=ctx.user_id,
        result_preview=str(ctx.result)[:300] if ctx.result else None,
        error=ctx.error,
        warning=ctx.metadata.get("warning"),
    )


async def feedback_pre_hook(ctx: HookContext):
    """Hook: Consulta learnings antes de executar (feedback loop)."""
    try:
        from ..vps_langgraph.learnings import learnings_manager

        recent_failures = learnings_manager.search_learnings(ctx.skill_name, limit=5)
        # Filtrar apenas erros de execucao recentes
        errors = [
            entry
            for entry in recent_failures
            if entry.get("category") == "execution_error" and not entry.get("success", True)
        ]
        if len(errors) >= 3:
            ctx.metadata["warning"] = f"Este skill falhou {len(errors)}x recentemente"
            logger.warning(
                "feedback_warning",
                skill=ctx.skill_name,
                failures=len(errors),
            )
    except Exception as e:
        logger.debug("feedback_pre_hook_skip", reason=str(e))
    return True  # Warning, nao veto


async def learning_hook(ctx: HookContext):
    """Hook: Registra erros no sistema de learnings."""
    if ctx.error:
        try:
            from ..vps_langgraph.learnings import learnings_manager

            learnings_manager.add_learning(
                category="execution_error",
                trigger=ctx.skill_name,
                lesson=f"Erro ao executar {ctx.skill_name}: {ctx.error}",
                success=False,
                metadata={"args": str(ctx.args)[:200], "user_id": ctx.user_id},
            )
        except Exception as e:
            logger.debug("learning_hook_skip", reason=str(e))


# ============================================
# Singleton
# ============================================

_hook_runner: Optional[HookRunner] = None


def get_hook_runner() -> HookRunner:
    """Retorna instancia singleton do HookRunner com hooks builtin."""
    global _hook_runner
    if _hook_runner is None:
        _hook_runner = HookRunner()
        _hook_runner.register_pre(feedback_pre_hook)
        _hook_runner.register_post(logging_hook)
        _hook_runner.register_post(learning_hook)
        logger.info("hook_runner_initialized", hooks=3)
    return _hook_runner
