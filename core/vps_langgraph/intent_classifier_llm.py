"""
Intent Classifier via LLM - Classificação inteligente com structured output.

Fase 6: Substitui regex por LLM com function calling.
"""

from typing import Any

import structlog

try:
    from pydantic.v1 import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field

logger = structlog.get_logger()


class IntentClassification(BaseModel):
    """Schema para classificação de intent via LLM."""
    
    intent: str = Field(
        ...,
        enum=["command", "task", "question", "chat", "self_improve"],
        description="Tipo de intenção do usuário"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confiança da classificação (0-1)"
    )
    entities: list[str] = Field(
        default=[],
        description="Entidades detectadas (ex: ['ram', 'docker']"
    )
    action_required: bool = Field(
        default=False,
        description="Se requer ação/execução na VPS"
    )
    tool_suggestion: str = Field(
        default="",
        description="Tool sugerida para executar (ex: 'get_ram', 'list_containers')"
    )
    reasoning: str = Field(
        ...,
        description="Explicação breve da classificação"
    )


async def classify_intent_llm(
    message: str,
    conversation_history: list[dict] = None,
    llm_client=None
) -> dict[str, Any]:
    """
    Classifica intent usando LLM com structured output.
    
    Tenta usar o LLM unificado primeiro, se falhar usa regex como fallback.
    
    Args:
        message: Mensagem do usuário
        conversation_history: Histórico opcional
        llm_client: Cliente LLM (legado, não usado)
        
    Returns:
        Dicionário com classificação estruturada
    """
    try:
        # Tentar usar o novo LLM Provider unificado
        from ..llm.unified_provider import classify_intent_with_llm
        
        result = await classify_intent_with_llm(message, conversation_history)
        
        # Verificar se o LLM retornou resultado válido
        if result.get("intent") and result.get("confidence", 0) > 0.5:
            logger.info(
                "intent_classified_by_llm",
                intent=result["intent"],
                confidence=result["confidence"],
                tool_suggestion=result.get("tool_suggestion", ""),
            )
            return result
        
        # Se confidence baixo, usar fallback
        logger.warning(
            "llm_low_confidence",
            confidence=result.get("confidence", 0),
            fallback="regex",
        )
        
    except Exception as e:
        logger.error("llm_classification_error", error=str(e), fallback="regex")
    
    # Fallback para regex local
    return infer_intent_from_message(message)


def infer_intent_from_message(message: str) -> dict[str, Any]:
    """Inferência baseada em regex para classificar intenções."""
    msg_lower = message.lower().strip()
    
    # Detectar comandos diretos (/comando)
    if msg_lower.startswith("/"):
        cmd = msg_lower[1:].split()[0]
        return {
            "intent": "command",
            "confidence": 0.95,
            "entities": [],
            "action_required": True,
            "tool_suggestion": cmd,
            "reasoning": "Comando direto detectado"
        }
    
    # Detectar perguntas sobre sistema (question)
    question_patterns = [
        "quanta ram", "quantas ram", "uso da ram", "memoria",
        "quanto memória", "quanta memória",
        "quantos containers", "quantos docker",
        "como está", "status do", "estado do",
        "quanto espaço", "quanto disco",
        "quantos serviços", "quais serviços"
    ]
    
    for pattern in question_patterns:
        if pattern in msg_lower:
            entities = []
            tool = "system_info"
            
            if any(w in msg_lower for w in ["ram", "memória", "memoria", "memory"]):
                entities.append("ram")
                tool = "get_ram"
            elif any(w in msg_lower for w in ["container", "docker", "containers"]):
                entities.append("docker")
                tool = "list_containers"
            elif any(w in msg_lower for w in ["status", "estado", "como está"]):
                entities.append("status")
                tool = "get_system_status"
            elif any(w in msg_lower for w in ["postgres", "banco", "database"]):
                entities.append("postgres")
                tool = "check_postgres"
            elif any(w in msg_lower for w in ["redis"]):
                entities.append("redis")
                tool = "check_redis"
            
            return {
                "intent": "question",
                "confidence": 0.9,
                "entities": entities,
                "action_required": True,
                "tool_suggestion": tool,
                "reasoning": f"Pergunta sobre sistema detectada: {pattern}"
            }
    
    # Detectar tarefas (task)
    task_patterns = [
        "liste", "mostre", "exiba", "verifique", "check",
        "inicie", "pare", "reinicie", "restart", "stop", "start",
        "faça", "execute", "rode", "run",
        "crie", "add", "adicione", "remova", "delete"
    ]
    
    for pattern in task_patterns:
        if msg_lower.startswith(pattern):
            return {
                "intent": "task",
                "confidence": 0.85,
                "entities": [],
                "action_required": True,
                "tool_suggestion": "",
                "reasoning": "Tarefa a executar detectada"
            }
    
    # Detectar self-improve
    improve_patterns = [
        "crie um agente", "novo agente", "adicionar funcionalidade",
        "integre com", "implemente", "desenvolva"
    ]
    
    for pattern in improve_patterns:
        if pattern in msg_lower:
            return {
                "intent": "self_improve",
                "confidence": 0.8,
                "entities": [],
                "action_required": False,
                "tool_suggestion": "",
                "reasoning": "Pedido de auto-melhoria detectado"
            }
    
    # Default: chat (conversa natural)
    return {
        "intent": "chat",
        "confidence": 0.7,
        "entities": [],
        "action_required": False,
        "tool_suggestion": "",
        "reasoning": "Conversa natural"
    }


# Compatibilidade com código antigo
def classify_intent_with_llm(message: str, **kwargs) -> tuple:
    """
    Wrapper compatível com interface antiga (síncrono).
    
    Retorna: (intent_str, confidence, details_dict)
    """
    import asyncio
    
    try:
        result = asyncio.run(classify_intent_llm(message, **kwargs))
        return (
            result["intent"],
            result["confidence"],
            {
                "entities": result["entities"],
                "action_required": result["action_required"],
                "tool_suggestion": result["tool_suggestion"],
                "reasoning": result["reasoning"]
            }
        )
    except:
        # Fallback total
        from .intent_classifier import classify_intent
        return classify_intent(message)


__all__ = [
    "IntentClassification",
    "classify_intent_llm",
    "classify_intent_with_llm",
]
