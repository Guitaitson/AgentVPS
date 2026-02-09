# VPS Agent - Interface principal entre Telegram Bot e LangGraph

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

import structlog

from core.vps_langgraph.graph import build_agent_graph
from core.vps_langgraph.state import AgentState

logger = structlog.get_logger()


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
    logger.info("processando_mensagem", user_id=user_id, message=message[:100])

    # Criar estado inicial
    initial_state: AgentState = {
        "user_id": user_id,
        "user_message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Construir e executar o grafo
        graph = build_agent_graph()
        logger.info("grafico_criado", nodes=list(graph.nodes.keys()))
        result = await graph.ainvoke(initial_state)
        logger.info("resultado_grafo", result_keys=list(result.keys()))

        # Extrair resposta
        response = result.get("response", "Desculpe, ocorreu um erro ao processar sua mensagem.")

        logger.info("resposta_gerada", user_id=user_id, response=response[:100])

        return response

    except Exception as e:
        import traceback
        logger.error("erro_processamento", error=str(e), user_id=user_id)
        logger.error("traceback", traceback=traceback.format_exc())
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
        "capabilities": summary
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
