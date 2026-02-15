# VPS Agent - Interface principal entre Telegram Bot e LangGraph

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

import structlog

logger = structlog.get_logger()


def _get_request_logger():
    """Retorna o logger de debug se disponível."""
    try:
        from core.structured_logging.agent_logger import AgentLogger
        return AgentLogger()
    except Exception:
        return None


def get_agent_graph():
    """
    Retorna a instância singleton do grafo do agente.
    
    Lazy loading para garantir que o grafo é criado uma única vez.
    """
    from core.vps_langgraph.graph import get_agent_graph as _get_graph

    return _get_graph()


async def process_message_async(user_id: str, message: str) -> str:
    """
    Processa mensagem do usuário através do LangGraph.

    Esta é a função principal que conecta o Telegram Bot ao agente LangGraph.

    Args:
        user_id: ID do usuário no Telegram
        message: Mensagem enviada pelo usuário

    Returns:
        Resposta gerada pelo agente
    """
    # Logger de debug (para arquivo JSON)
    debug_logger = _get_request_logger()
    if debug_logger:
        debug_logger.log(
            step="receive_message",
            input_data=message[:100],
            metadata={"user_id": user_id},
        )

    logger.info("processando_mensagem", user_id=user_id, message=message[:100])

    # Criar estado inicial
    initial_state = {
        "user_id": user_id,
        "user_message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Usar singleton do grafo (não reconstruir a cada mensagem)
        graph = get_agent_graph()
        logger.info("grafico_obtido", nodes=list(graph.nodes.keys()) if hasattr(graph, 'nodes') else "N/A")

        # CORREÇÃO: Usar user_id como thread_id para manter contexto da conversa
        # Isso permite que o agente lembre de interações anteriores
        config = {
            "configurable": {
                "thread_id": f"user_{user_id}",
                "checkpoint_ns": "telegram_bot",
            }
        }

        logger.info("iniciando_ainvoke", thread_id=config["configurable"]["thread_id"])

        if debug_logger:
            debug_logger.log(step="invoke_graph", input_data="LangGraph invoke")

        result = await graph.ainvoke(initial_state, config=config)

        if debug_logger:
            debug_logger.log(
                step="graph_result",
                output_data=f"keys: {list(result.keys())}",
            )

        logger.info("resultado_grafo", result_keys=list(result.keys()))

        # Extrair resposta
        response = result.get("response", "Desculpe, ocorreu um erro ao processar sua mensagem.")

        logger.info("resposta_gerada", user_id=user_id, response=response[:100] if response else "None")

        if debug_logger:
            debug_logger.log(step="response_ready", output_data=response[:200] if response else "None")
            debug_logger.finalize(success=True)

        return response

    except Exception as e:
        import traceback

        logger.error("erro_processamento", error=str(e), user_id=user_id)
        logger.error("traceback", traceback=traceback.format_exc())

        if debug_logger:
            debug_logger.log(step="error", error=str(e)[:200])
            debug_logger.finalize(success=False)

        return f"❌ Erro ao processar mensagem: {str(e)}"


def get_agent_status() -> Dict[str, Any]:
    """
    Retorna status atual do agente.

    Returns:
        Dicionário com informações sobre o agente
    """
    from core.capabilities import capabilities_registry

    summary = capabilities_registry.get_summary()

    return {
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "capabilities": summary,
    }


if __name__ == "__main__":
    # Teste local
    import sys

    if len(sys.argv) > 1:
        test_message = " ".join(sys.argv[1:])
        print(f"Processando: {test_message}")
        response = asyncio.run(process_message_async("test_user", test_message))
        print(f"Resposta: {response}")
    else:
        print("Uso: python agent.py <mensagem>")
