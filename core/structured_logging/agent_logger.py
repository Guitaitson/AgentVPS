"""
Agente Logger - Sistema de logging estruturado para debug.

Logs todos os passos do processamento de mensagens para facilitar debug.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

# Configuração do diretório de log
LOG_DIR = os.getenv("VPS_AGENT_LOG_DIR", "/var/log/vps-agent")
LOG_FILE = os.path.join(LOG_DIR, "agent.jsonl")


def _ensure_log_dir():
    """Garante que o diretório de log existe."""
    try:
        Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback para /tmp se não conseguir criar
        global LOG_DIR, LOG_FILE
        LOG_DIR = "/tmp/vps-agent-logs"
        LOG_FILE = os.path.join(LOG_DIR, "agent.jsonl")
        Path(LOG_DIR).mkdir(parents=True, exist_ok=True)


class AgentLogger:
    """
    Logger estruturado que salva cada request em JSON Lines.
    
    Útil para debug do fluxo: intent → plan → execute → response
    """

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or str(uuid.uuid4())[:8]
        self.started_at = datetime.now(timezone.utc)
        self.events: list[Dict] = []

    def log(
        self,
        step: str,
        input_data: Any = None,
        output_data: Any = None,
        metadata: Dict = None,
        error: str = None,
    ):
        """Registra um evento no log."""
        event = {
            "request_id": self.request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": step,
        }

        if input_data is not None:
            # Truncar dados grandes
            input_str = str(input_data)
            if len(input_str) > 500:
                input_str = input_str[:500] + "..."
            event["input"] = input_str

        if output_data is not None:
            output_str = str(output_data)
            if len(output_str) > 500:
                output_str = output_str[:500] + "..."
            event["output"] = output_str

        if metadata:
            event["metadata"] = metadata

        if error:
            event["error"] = error[:200] if len(error) > 200 else error

        self.events.append(event)

        # Log para stdout também
        logger = structlog.get_logger()
        logger.info(
            f"[{self.request_id}] {step}",
            input=event.get("input", "")[:100],
            output=event.get("output", "")[:100] if "output" in event else None,
            error=error,
        )

        # Salvar em arquivo
        self._write_to_file(event)

    def _write_to_file(self, event: Dict):
        """Escreve evento no arquivo JSONL."""
        try:
            _ensure_log_dir()
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Silencioso se falhar

    def finalize(self, success: bool = True):
        """Finaliza o log do request."""
        duration_ms = int((datetime.now(timezone.utc) - self.started_at).total_seconds() * 1000)

        self.log(
            step="request_complete",
            metadata={
                "success": success,
                "duration_ms": duration_ms,
                "events_count": len(self.events),
            }
        )


# ============================================
# Context manager para logging automático
# ============================================

class log_agent_flow:
    """Context manager para logging automático do fluxo do agente."""

    def __init__(self, request_id: Optional[str] = None):
        self.logger = AgentLogger(request_id)

    def __enter__(self):
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.log(
                step="request_error",
                error=f"{exc_type.__name__}: {exc_val}",
            )
            self.logger.finalize(success=False)
        else:
            self.logger.finalize(success=True)


# ============================================
# Funções de convenience
# ============================================

def log_intentclassification(message: str, result: Dict):
    """Log do resultado de classificação de intent."""
    logger = AgentLogger()
    logger.log(
        step="classify_intent",
        input_data=message[:100],
        output_data=f"intent={result.get('intent')}, tool={result.get('tool_suggestion')}",
        metadata={
            "confidence": result.get("confidence"),
            "action_required": result.get("action_required"),
        },
    )
    logger.finalize()


def log_plan_creation(plan: Dict):
    """Log da criação do plano."""
    logger = AgentLogger()
    logger.log(
        step="create_plan",
        output_data=str(plan),
    )
    logger.finalize()


def log_skill_execution(skill_name: str, args: Dict, result: str):
    """Log da execução de um skill."""
    logger = AgentLogger()
    logger.log(
        step="execute_skill",
        input_data=f"{skill_name}({args})",
        output_data=result[:200] if result else "None",
    )
    logger.finalize()


def log_llm_call(prompt: str, response: str, model: str, tokens: int = None):
    """Log de chamada ao LLM."""
    logger = AgentLogger()
    logger.log(
        step="llm_call",
        input_data=prompt[:200],
        output_data=response[:200] if response else "None",
        metadata={
            "model": model,
            "tokens": tokens,
        },
    )
    logger.finalize()


__all__ = [
    "AgentLogger",
    "log_agent_flow",
    "log_intentclassification",
    "log_plan_creation",
    "log_skill_execution",
    "log_llm_call",
]
