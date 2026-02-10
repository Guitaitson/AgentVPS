"""
Intent Classifier via LLM - Classificação inteligente com structured output.

Fase 6: Substitui regex por LLM com function calling.
"""

from typing import Any

try:
    from pydantic.v1 import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field


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


INTENT_CLASSIFICATION_PROMPT = """Você é um classificador de intenções para o VPS-Agent, um agente autônomo que gerencia VPS.

## Intenções Possíveis:

1. **command** - Comandos diretos do sistema (/status, /ram, comandos técnicos)
   - Exemplos: "/ram", "/status", "reinicie o serviço", "pare o container"
   
2. **task** - Tarefas a executar (ações concretas na VPS)
   - Exemplos: "liste containers", "faça backup", "atualize o sistema"
   
3. **question** - Perguntas sobre o sistema (solicita informações)
   - Exemplos: "quanta RAM?", "como está o servidor?", "quantos containers?"
   
4. **chat** - Conversa natural (saudações, agradecimentos)
   - Exemplos: "oi", "tudo bem?", "obrigado", "como funciona?"
   
5. **self_improve** - Pedidos para criar/implementar algo novo
   - Exemplos: "crie um agente", "integre com GitHub", "adicionar feature"

## Entidades Comuns:
- ram, memory, memória
- cpu, processador
- docker, container, containers
- postgres, redis, database
- github, git, repositório
- backup, log, arquivo

## Responda com:
- intent: uma das opções acima
- confidence: 0.0 a 1.0
- entities: lista de entidades encontradas
- action_required: true se precisa executar algo na VPS
- tool_suggestion: nome da tool sugerida (get_ram, list_containers, etc.)
- reasoning: breve explicação

## Mensagem do usuário:
{message}

## Contexto da conversa:
{context}
"""


async def classify_intent_llm(
    message: str,
    conversation_history: list[dict] = None,
    llm_client=None
) -> dict[str, Any]:
    """
    Classifica intent usando LLM com structured output.
    
    Args:
        message: Mensagem do usuário
        conversation_history: Histórico opcional
        llm_client: Cliente LLM (OpenRouter, etc.)
        
    Returns:
        Dicionário com classificação estruturada
    """
    try:
        # Fallback: importar cliente padrão se não fornecido
        if llm_client is None:
            from ..llm.openrouter_client import generate_response
            
            # Construir prompt
            context = format_context(conversation_history) if conversation_history else "Nenhum contexto"
            prompt = INTENT_CLASSIFICATION_PROMPT.format(
                message=message,
                context=context
            )
            
            # Chamar LLM (sem structured output por enquanto - fallback)
            response = await generate_response(
                user_message=prompt,
                system_message="Você é um classificador de intenções. Responda apenas com JSON válido."
            )
            
            # Parse manual do JSON (fallback)
            return parse_fallback_response(response, message)
        
        # TODO: Implementar com structured output quando migrar para LangChain
        # result = await llm_client.with_structured_output(IntentClassification).ainvoke(...)
        
    except Exception as e:
        # Fallback para regex em caso de erro
        from .intent_classifier import classify_intent
        
        intent, confidence, details = classify_intent(message)
        return {
            "intent": intent.value,
            "confidence": confidence,
            "entities": details.get("keywords", []),
            "action_required": intent.value in ["command", "task"],
            "tool_suggestion": suggest_tool(intent.value, details),
            "reasoning": f"Fallback para regex devido a erro: {e}",
            "error": str(e)
        }


def format_context(history: list[dict]) -> str:
    """Formata histórico para contexto."""
    if not history:
        return "Nenhum histórico"
    
    recent = history[-3:]  # Últimas 3 mensagens
    formatted = []
    for msg in recent:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:100]  # Limita tamanho
        formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted)


def parse_fallback_response(response: str, message: str) -> dict[str, Any]:
    """Parse da resposta LLM quando structured output não disponível."""
    import json
    import re
    
    try:
        # Tentar extrair JSON da resposta
        json_match = re.search(r'\{[^}]+\}', response)
        if json_match:
            data = json.loads(json_match.group())
            return {
                "intent": data.get("intent", "chat"),
                "confidence": data.get("confidence", 0.7),
                "entities": data.get("entities", []),
                "action_required": data.get("action_required", False),
                "tool_suggestion": data.get("tool_suggestion", ""),
                "reasoning": data.get("reasoning", "Classificado via LLM")
            }
    except:
        pass
    
    # Fallback: inferir da mensagem
    return infer_intent_from_message(message)


def infer_intent_from_message(message: str) -> dict[str, Any]:
    """Inferência básica quando LLM falha."""
    msg_lower = message.lower()
    
    # Detectar comandos
    if msg_lower.startswith("/"):
        return {
            "intent": "command",
            "confidence": 0.9,
            "entities": [],
            "action_required": True,
            "tool_suggestion": msg_lower[1:].split()[0],
            "reasoning": "Comando direto detectado"
        }
    
    # Detectar perguntas
    question_words = ["quanto", "quantos", "qual", "quais", "como", "onde", "?"]
    if any(w in msg_lower for w in question_words):
        entities = []
        if any(w in msg_lower for w in ["ram", "memória", "memory"]):
            entities.append("ram")
        if any(w in msg_lower for w in ["docker", "container"]):
            entities.append("docker")
            
        return {
            "intent": "question",
            "confidence": 0.8,
            "entities": entities,
            "action_required": True,  # Perguntas sobre sistema requerem ação
            "tool_suggestion": "get_ram" if "ram" in msg_lower else "system_info",
            "reasoning": "Pergunta detectada"
        }
    
    # Default: chat
    return {
        "intent": "chat",
        "confidence": 0.6,
        "entities": [],
        "action_required": False,
        "tool_suggestion": "",
        "reasoning": "Conversa natural"
    }


def suggest_tool(intent: str, details: dict) -> str:
    """Sugere tool baseado no intent e entidades."""
    keywords = details.get("keywords", [])
    msg = " ".join(keywords).lower()
    
    if "ram" in msg or "memória" in msg:
        return "get_ram"
    if "docker" in msg or "container" in msg:
        return "list_containers"
    if "status" in msg:
        return "get_system_status"
    if "postgres" in msg:
        return "check_postgres"
    if "redis" in msg:
        return "check_redis"
    
    return ""


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
