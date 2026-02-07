"""
Grafo principal do agente LangGraph.
Define o fluxo de decisão: input → classificar → contexto → planejar → executar → responder.
"""
from langgraph.graph import StateGraph, END
from vps_langgraph.state import AgentState
from vps_langgraph.memory import AgentMemory
from vps_langgraph.nodes import (
    node_classify_intent,
    node_load_context,
    node_plan,
    node_execute,
    node_generate_response,
    node_save_memory,
    node_check_capabilities,
    node_self_improve,
    node_implement_capability,
)

memory = AgentMemory()


def build_agent_graph():
    """Constrói e retorna o grafo do agente."""
    workflow = StateGraph(AgentState)
    
    # Nós do workflow
    workflow.add_node("classify", node_classify_intent)
    workflow.add_node("load_context", node_load_context)
    workflow.add_node("plan", node_plan)
    workflow.add_node("execute", node_execute)
    workflow.add_node("respond", node_generate_response)
    workflow.add_node("save_memory", node_save_memory)
    workflow.add_node("check_capabilities", node_check_capabilities)
    workflow.add_node("self_improve", node_self_improve)
    workflow.add_node("implement_capability", node_implement_capability)
    
    # Ponto de entrada
    workflow.set_entry_point("classify")
    
    # Classificação de intenção
    workflow.add_edge("classify", "load_context")
    
    # Carregar contexto
    workflow.add_edge("load_context", "plan")
    
    # Planejamento
    workflow.add_conditional_edges(
        "plan",
        lambda state: state.get("intent_type", "unknown"),
        {
            "command": "execute",
            "task": "execute",
            "question": "respond",
            "chat": "respond",
            "unknown": "respond",
        }
    )
    
    # Execução
    workflow.add_edge("execute", "save_memory")
    
    # Salvar memória
    workflow.add_edge("save_memory", "respond")
    
    # Verificar capacidades após execução
    workflow.add_conditional_edges(
        "respond",
        lambda state: state.get("needs_capability_check", False),
        {
            True: "check_capabilities",
            False: END,
        }
    )
    
    # Verificar se precisa de self-improvement
    workflow.add_conditional_edges(
        "check_capabilities",
        lambda state: state.get("capability_status", "ok"),
        {
            "needs_improvement": "self_improve",
            "ok": END,
            "implementing": "implement_capability",
        }
    )
    
    # Self-improvement
    workflow.add_edge("self_improve", "implement_capability")
    
    # Implementar capacidade
    workflow.add_edge("implement_capability", END)
    
    return workflow.compile()


# Instância global do grafo
_agent_graph = None


def get_agent_graph():
    """Retorna a instância do grafo do agente (lazy loading)."""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph
