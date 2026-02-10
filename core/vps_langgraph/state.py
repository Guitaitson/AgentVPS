"""
Estado compartilhado do agente LangGraph - Versão Moderna (Fase 5).

Usa TypedDict com Annotated para type safety e reducers automáticos.
Compatível com LangGraph 0.2+ com checkpointing.
"""

from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph import add_messages


class AgentState(TypedDict):
    """
    Estado que flui pelo grafo do agente.
    
    Usa Annotated para:
    - add_messages: Acumula mensagens automaticamente
    - Reducers personalizados para outros campos
    """

    # ============ Input ============
    user_id: str
    user_message: str
    
    # Mensagens (acumulam automaticamente)
    messages: Annotated[list, add_messages]

    # ============ Classificação ============
    intent: str  # 'command', 'question', 'task', 'chat', 'self_improve'
    intent_confidence: float
    intent_details: dict[str, Any]  # Metadados da classificação

    # ============ Contexto ============
    user_context: dict[str, Any]  # Fatos sobre o usuário
    conversation_history: list[dict]  # Últimas N mensagens

    # ============ Planejamento ============
    plan: list[dict]  # Lista de passos a executar
    current_step: int
    tools_needed: list[str]  # Quais ferramentas o passo requer
    tools_available: list[str]  # Quais estão rodando agora

    # ============ Execução ============
    execution_result: Optional[str]
    error: Optional[dict]  # Structured error info

    # ============ Segurança ============
    security_check: dict[str, Any]  # Resultado da verificação
    blocked_by_security: bool

    # ============ Output ============
    response: str
    should_save_memory: bool
    memory_updates: list[dict]  # Novos fatos para salvar

    # ============ Meta ============
    timestamp: str
    ram_available_mb: Optional[int]

    # ============ Self-Improvement ============
    missing_capabilities: list[dict]
    needs_improvement: bool
    improvement_summary: Optional[str]
    improvement_plan: Optional[list[dict]]
    should_improve: bool
    implementation_result: Optional[str]
    new_capability: Optional[str]
    implementation_status: Optional[str]


def merge_dicts(left: dict, right: dict) -> dict:
    """Reducer para merge de dicionários."""
    merged = left.copy()
    merged.update(right)
    return merged


def append_to_list(left: list, right: list) -> list:
    """Reducer para concatenar listas."""
    return left + right if left else right


class AgentStateModern(TypedDict):
    """
    Versão experimental com reducers personalizados.
    
    Use esta versão quando migrar completamente para o novo formato.
    """

    # Input
    user_id: str
    user_message: str
    
    # Mensagens com reducer automático
    messages: Annotated[list, add_messages]
    
    # Contexto com merge
    user_context: Annotated[dict, merge_dicts]
    
    # Histórico com append
    conversation_history: Annotated[list, append_to_list]
    
    # Resto igual ao AgentState
    intent: str
    intent_confidence: float
    plan: list[dict]
    current_step: int
    execution_result: Optional[str]
    response: str


# Mantém compatibilidade com código antigo
__all__ = ["AgentState", "AgentStateModern"]
