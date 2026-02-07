"""
Agente LangGraph principal.
Entry point para processar mensagens através do grafo.
"""
from datetime import datetime
from typing import Optional

from .graph import build_agent_graph
from .memory import AgentMemory
from .state import AgentState

# Build graph once at module load
agent_graph = build_agent_graph()
memory = AgentMemory()


def process_message(user_id: str, message: str) -> str:
    """
    Processa uma mensagem do usuário através do agente LangGraph.
    
    Args:
        user_id: ID do usuário no Telegram
        message: Mensagem enviada pelo usuário
    
    Returns:
        Resposta gerada pelo agente
    """
    # Criar estado inicial
    initial_state: AgentState = {
        "user_id": user_id,
        "user_message": message,
        "intent": None,
        "intent_confidence": None,
        "user_context": None,
        "conversation_history": None,
        "plan": None,
        "current_step": None,
        "tools_needed": None,
        "tools_available": None,
        "execution_result": None,
        "error": None,
        "response": None,
        "should_save_memory": False,
        "memory_updates": None,
        "timestamp": datetime.now().isoformat(),
        "ram_available_mb": None,
    }
    
    # Executar grafo
    final_state = agent_graph.invoke(initial_state)
    
    # Retornar resposta
    return final_state.get("response", "Erro ao processar mensagem")


async def process_message_async(user_id: str, message: str) -> str:
    """
    Versão assíncrona do process_message.
    Útil para integração com Telegram Bot async.
    """
    return process_message(user_id, message)
