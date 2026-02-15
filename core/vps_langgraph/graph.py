"""
Grafo principal do agente LangGraph — Sprint 03.

Fluxo ReAct com function calling:
  load_context → react → [security_check → execute → format_response] → respond → save_memory

O react_node substitui classify_intent + plan em uma unica chamada LLM.
O LLM recebe tool schemas e decide qual tool usar (ou responde diretamente).
"""

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

from .nodes import (
    node_execute,
    node_generate_response,
    node_load_context,
    node_save_memory,
    node_security_check,
)
from .react_node import node_format_response, node_react, route_after_react
from .state import AgentState

logger = structlog.get_logger()


def get_checkpointer():
    """Retorna o checkpointer para persistencia de estado."""
    logger.info("checkpointer_memory_ativo")
    return MemorySaver()


def build_agent_graph():
    """Constroi grafo ReAct com function calling (7 nos)."""
    workflow = StateGraph(AgentState)

    # 7 nos (vs 10 antigos)
    workflow.add_node("load_context", node_load_context)
    workflow.add_node("react", node_react)
    workflow.add_node("security_check", node_security_check)
    workflow.add_node("execute", node_execute)
    workflow.add_node("format_response", node_format_response)
    workflow.add_node("respond", node_generate_response)
    workflow.add_node("save_memory", node_save_memory)

    # Ponto de entrada
    workflow.set_entry_point("load_context")

    # load_context → react
    workflow.add_edge("load_context", "react")

    # React decide: tool (→ security_check) ou resposta direta (→ respond)
    workflow.add_conditional_edges(
        "react",
        route_after_react,
        {
            "security_check": "security_check",
            "respond": "respond",
        },
    )

    # Seguranca → execute ou respond (se bloqueado)
    def route_after_security(state):
        """Roteia apos verificacao de seguranca."""
        blocked = state.get("blocked_by_security", False)
        logger.info("route_after_security", blocked=blocked)
        if blocked:
            return "respond"
        return "execute"

    workflow.add_conditional_edges(
        "security_check",
        route_after_security,
        {
            "execute": "execute",
            "respond": "respond",
        },
    )

    # execute → format_response (LLM formata resultado) → respond → save_memory
    workflow.add_edge("execute", "format_response")
    workflow.add_edge("format_response", "respond")
    workflow.add_edge("respond", "save_memory")
    workflow.set_finish_point("save_memory")

    # Compilar com checkpointer
    checkpointer = get_checkpointer()
    compiled_graph = workflow.compile(checkpointer=checkpointer)

    logger.info("grafo_react_compilado", nodes=7)

    return compiled_graph


# Instância global do grafo (singleton)
_agent_graph = None


def get_agent_graph():
    """Retorna a instância do grafo do agente (lazy loading)."""
    global _agent_graph
    if _agent_graph is None:
        logger.info("criando_instancia_grafo")
        _agent_graph = build_agent_graph()
    return _agent_graph
