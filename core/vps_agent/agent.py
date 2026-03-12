from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict

import structlog
from langchain_core.messages import HumanMessage

from core.progress import bind_progress_callback, emit_progress

logger = structlog.get_logger()

ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None] | None]


def _get_request_logger():
    """Return the structured debug logger when available."""
    try:
        from core.structured_logging.agent_logger import AgentLogger

        return AgentLogger()
    except Exception:
        return None


def get_agent_graph():
    """Return the singleton graph instance."""
    from core.vps_langgraph.graph import get_agent_graph as _get_graph

    return _get_graph()


async def process_message_async(
    user_id: str,
    message: str,
    progress_callback: ProgressCallback | None = None,
) -> str:
    """Process a user message through the LangGraph pipeline."""
    debug_logger = _get_request_logger()
    if debug_logger:
        debug_logger.log(
            step="receive_message",
            input_data=message[:100],
            metadata={"user_id": user_id},
        )

    logger.info("processando_mensagem", user_id=user_id, message=message[:100])

    initial_state = {
        "user_id": user_id,
        "user_message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "messages": [HumanMessage(content=message)],
        "response": "",
        "execution_result": None,
        "blocked_by_security": False,
        "error": None,
        "security_check": {},
        "plan": None,
        "current_step": 0,
        "tool_suggestion": None,
        "tools_needed": [],
        "action_required": False,
        "intent": "",
        "should_save_memory": False,
        "memory_updates": [],
    }

    with bind_progress_callback(progress_callback):
        await emit_progress("received", user_id=user_id, message=message[:100])

        try:
            graph = get_agent_graph()
            logger.info(
                "grafico_obtido",
                nodes=list(graph.nodes.keys()) if hasattr(graph, "nodes") else "N/A",
            )

            config = {
                "configurable": {
                    "thread_id": f"user_{user_id}",
                    "checkpoint_ns": "telegram_bot",
                }
            }

            logger.info("iniciando_ainvoke", thread_id=config["configurable"]["thread_id"])
            await emit_progress("routing", user_id=user_id)

            if debug_logger:
                debug_logger.log(step="invoke_graph", input_data="LangGraph invoke")

            result = await graph.ainvoke(initial_state, config=config)

            if debug_logger:
                debug_logger.log(
                    step="graph_result",
                    output_data=f"keys: {list(result.keys())}",
                )

            logger.info("resultado_grafo", result_keys=list(result.keys()))
            response = result.get(
                "response", "Desculpe, ocorreu um erro ao processar sua mensagem."
            )

            logger.info(
                "resposta_gerada",
                user_id=user_id,
                response=response[:100] if response else "None",
            )
            await emit_progress("done", user_id=user_id)

            if debug_logger:
                debug_logger.log(
                    step="response_ready",
                    output_data=response[:200] if response else "None",
                )
                debug_logger.finalize(success=True)

            return response

        except Exception as exc:
            import traceback

            logger.error("erro_processamento", error=str(exc), user_id=user_id)
            logger.error("traceback", traceback=traceback.format_exc())
            await emit_progress("error", user_id=user_id, error=str(exc))

            if debug_logger:
                debug_logger.log(step="error", error=str(exc)[:200])
                debug_logger.finalize(success=False)

            return f"Erro ao processar mensagem: {str(exc)}"


def get_agent_status() -> Dict[str, Any]:
    """Return current agent status."""
    from core.capabilities import capabilities_registry

    summary = capabilities_registry.get_summary()

    return {
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "capabilities": summary,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_message = " ".join(sys.argv[1:])
        print(f"Processando: {test_message}")
        response = asyncio.run(process_message_async("test_user", test_message))
        print(f"Resposta: {response}")
    else:
        print("Uso: python agent.py <mensagem>")
