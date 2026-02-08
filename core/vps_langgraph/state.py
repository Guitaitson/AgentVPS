"""
Estado compartilhado do agente LangGraph.
Tudo que o agente "sabe" em um dado momento.
"""
from typing import TypedDict, Optional


class AgentState(TypedDict):
    """Estado que flui pelo grafo do agente."""
    
    # Input
    user_id: str
    user_message: str
    
    # Classificação da intenção
    intent: Optional[str]  # 'command', 'question', 'task', 'chat'
    intent_confidence: Optional[float]
    
    # Contexto recuperado da memória
    user_context: Optional[dict]  # Fatos sobre o usuário
    conversation_history: Optional[list]  # Últimas N mensagens
    
    # Planejamento
    plan: Optional[list]  # Lista de passos a executar
    current_step: Optional[int]
    
    # Ferramentas
    tools_needed: Optional[list]  # Quais ferramentas o passo requer
    tools_available: Optional[list]  # Quais estão rodando agora
    
    # Execução
    execution_result: Optional[str]
    error: Optional[str]
    
    # Output
    response: Optional[str]
    should_save_memory: Optional[bool]
    memory_updates: Optional[list]  # Novos fatos para salvar
    
    # Meta
    timestamp: Optional[str]
    ram_available_mb: Optional[int]
    
    # Self-Improvement
    missing_capabilities: Optional[list]
    needs_improvement: Optional[bool]
    improvement_summary: Optional[str]
    improvement_plan: Optional[list]
    should_improve: Optional[bool]
    implementation_result: Optional[str]
    new_capability: Optional[str]
