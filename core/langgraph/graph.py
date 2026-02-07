"""
Grafo principal do agente LangGraph.
Define o fluxo de decisão: input → classificar → contexto → planejar → executar/CLI → responder.
"""
from langgraph.graph import StateGraph, END
from .state import AgentState
from .memory import AgentMemory
from .nodes import (
    node_classify_intent,
    node_load_context,
    node_plan,
    node_execute,
    node_call_cli,
    node_generate_response,
    node_save_memory,
)

memory = AgentMemory()


def build_agent_graph():
    """Constrói e retorna o grafo do agente."""
    
    graph = StateGraph(AgentState)
    
    # Adicionar nós
    graph.add_node("classify", node_classify_intent)
    graph.add_node("load_context", node_load_context)
    graph.add_node("plan", node_plan)
    graph.add_node("execute", node_execute)
    graph.add_node("call_cli", node_call_cli)
    graph.add_node("respond", node_generate_response)
    graph.add_node("save_memory", node_save_memory)
    
    # Definir fluxo
    graph.set_entry_point("classify")
    
    # classify → load_context → plan
    graph.add_edge("classify", "load_context")
    graph.add_edge("load_context", "plan")
    
    # plan → execute (comandos diretos) OU plan → call_cli (tarefas)
    graph.add_conditional_edges(
        "plan",
        lambda state: "execute" if state.get("plan") and state.get("plan", [{}])[0].get("action") in ["run_command", "start_tool", "stop_tool"] else "call_cli",
        {
            "execute": "execute",
            "call_cli": "call_cli",
        }
    )
    
    # execute → respond
    graph.add_edge("execute", "respond")
    
    # call_cli → respond (CLIs always go to response)
    graph.add_edge("call_cli", "respond")
    
    # Condicional: salvar memória se necessário
    graph.add_conditional_edges(
        "respond",
        lambda state: "save_memory" if state.get("should_save_memory") else "end",
        {
            "save_memory": "save_memory",
            "end": END,
        }
    )
    
    graph.add_edge("save_memory", END)
    
    return graph.compile()
