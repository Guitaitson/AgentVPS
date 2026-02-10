"""
Grafo principal do agente LangGraph.
Define o fluxo de decisão completo com Self-Improvement.
"""

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

from .memory import AgentMemory
from .nodes import (
    node_check_capabilities,
    node_classify_intent,
    node_execute,
    node_generate_response,
    node_implement_capability,
    node_load_context,
    node_plan,
    node_save_memory,
    node_security_check,
    node_self_improve,
)
from .state import AgentState

logger = structlog.get_logger()
memory = AgentMemory()


def get_checkpointer():
    """
    Retorna o checkpointer para persistência de estado.
    
    Tenta usar PostgreSQL, se falhar usa MemorySaver (memória em RAM).
    """
    try:
        from .checkpoint import get_checkpointer as get_pg_checkpointer
        
        checkpointer = get_pg_checkpointer()
        if checkpointer:
            logger.info("checkpointer_postgres_ativo")
            return checkpointer
    except Exception as e:
        logger.warning("checkpointer_postgres_falhou", error=str(e))
    
    # Fallback para MemorySaver (não persiste entre restarts, mas funciona)
    logger.info("checkpointer_memory_fallback")
    return MemorySaver()


def build_agent_graph():
    """Constrói e retorna o grafo do agente com checkpointing."""
    workflow = StateGraph(AgentState)

    # Nós do workflow (alguns são async)
    workflow.add_node("classify", node_classify_intent)
    workflow.add_node("load_context", node_load_context)
    workflow.add_node("plan", node_plan)
    workflow.add_node("security_check", node_security_check)
    workflow.add_node("execute", node_execute)
    workflow.add_node("respond", node_generate_response)
    workflow.add_node("save_memory", node_save_memory)
    workflow.add_node("check_capabilities", node_check_capabilities)
    workflow.add_node("self_improve", node_self_improve)
    workflow.add_node("implement_capability", node_implement_capability)

    # Ponto de entrada
    workflow.set_entry_point("classify")

    # Fluxo principal: classify → load_context → plan
    workflow.add_edge("classify", "load_context")
    workflow.add_edge("load_context", "plan")

    # Planejamento → Execução ou Resposta (baseado no intent e action_required)
    def route_after_plan(state):
        """Roteia baseado na intenção e se requer ação."""
        intent = state.get("intent", "unknown")
        action_required = state.get("action_required", False)
        tool_suggestion = state.get("tool_suggestion", "")
        
        logger.info(
            "route_after_plan",
            intent=intent,
            action_required=action_required,
            tool_suggestion=tool_suggestion,
        )
        
        # Perguntas que requerem ação vão para security_check → execute
        if intent in ["command", "task"]:
            return "security_check"
        elif intent == "question" and action_required:
            # Perguntas sobre sistema (RAM, status) vão para execução
            return "security_check"
        elif intent == "self_improve":
            return "check_capabilities"
        else:
            # Chat e perguntas informativas vão direto para resposta
            return "respond"

    workflow.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "security_check": "security_check",
            "check_capabilities": "check_capabilities",
            "respond": "respond",
        },
    )

    # Segurança → Execução/Resposta (baseado no resultado)
    def route_after_security(state):
        """Roteia após verificação de segurança."""
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

    # Execução → Responder (mostrar resultados)
    workflow.add_edge("execute", "respond")

    # Self-improve: check_capabilities → self_improve → respond
    def route_after_capabilities(state):
        """Roteia após verificação de capacidades."""
        needs_improvement = state.get("needs_improvement", False)
        logger.info("route_after_capabilities", needs_improvement=needs_improvement)
        
        return "self_improve" if needs_improvement else "respond"

    workflow.add_conditional_edges(
        "check_capabilities",
        route_after_capabilities,
        {
            "self_improve": "self_improve",
            "respond": "respond",
        },
    )
    workflow.add_edge("self_improve", "respond")

    # Responder → Salvar memória → END
    workflow.add_edge("respond", "save_memory")
    workflow.set_finish_point("save_memory")

    # Compilar com checkpointer para persistência de estado
    checkpointer = get_checkpointer()
    compiled_graph = workflow.compile(checkpointer=checkpointer)
    
    logger.info("grafo_compilado_com_checkpointer")
    
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