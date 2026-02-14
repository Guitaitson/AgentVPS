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


# Mensagens curtas que DEVEM ser classificadas como chat
_FORCE_CHAT_MESSAGES = {
    "oi", "olá", "ola", "hi", "hello", "hey", "e ai", "eai",
    "bom dia", "boa tarde", "boa noite", "td bem", "tudo bem",
    "blz", "blz?", "salve", "alô", "alo", "oi?", "ola?"
}


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
    # ============ GUARD CLAUSE: Mensagens curtas = CHAT ============
    # Isso corrige o bug de "oi" retornando containers
    msg_lower = message.lower().strip()
    
    # Se é uma saudação curta (≤15 chars), FORÇAR chat
    if len(message) <= 15 and any(
        msg_lower == sauda or sauda in msg_lower 
        for sauda in _FORCE_CHAT_MESSAGES
    ):
        logger.info(
            "intent_forced_chat",
            message=message,
            reason="saudacao_curta"
        )
        return {
            "intent": "chat",
            "confidence": 0.95,
            "entities": [],
            "action_required": False,
            "tool_suggestion": "",
            "reasoning": "Saudação curta detectada - forçar chat"
        }
    
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
    
    # ========================================
    # PRIORIDADE 1: Comandos diretos (/comando)
    # ========================================
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
    
    # ========================================
    # PRIORIDADE 2: Ações que requerem execução (TASK)
    # ========================================
    # Padrões mais comuns que indicam tasks
    task_starters = [
        "execute ", "executa ", "executar ", "rode ", "roda ", "rodar ",
        "rode ", "roda ", "run ", "rode ",
        "pesquise ", "busque ", "buscar ", "search ", "procure ",
        "liste ", "listar ", "mostre ", "mostrar ", "exiba ", "exibir ",
        "leia ", "ler ", "abri ", "abrir ",
        "crie ", "criar ", "criar ", "adicione ", "add ",
        "verifique ", "check ", "verifica ",
        "inicie ", "pare ", "pare ", "reinicie ", "restart ", "start ", "stop ",
    ]
    
    for pattern in task_starters:
        if msg_lower.startswith(pattern):
            # Detectar tipo de task pelo padrão
            if pattern.strip() in ["pesquise", "busque", "buscar", "search", "procure"]:
                return {
                    "intent": "task",
                    "confidence": 0.95,
                    "entities": ["web_search"],
                    "action_required": True,
                    "tool_suggestion": "web_search",
                    "reasoning": f"Task de busca detectada: {pattern.strip()}"
                }
            elif pattern.strip() in ["execute", "executa", "executar", "rode", "roda", "rodar", "run"]:
                return {
                    "intent": "task",
                    "confidence": 0.95,
                    "entities": ["shell_exec"],
                    "action_required": True,
                    "tool_suggestion": "shell_exec",
                    "reasoning": f"Task de execução detectada: {pattern.strip()}"
                }
            elif pattern.strip() in ["leia", "ler", "abri", "abrir"]:
                return {
                    "intent": "task",
                    "confidence": 0.95,
                    "entities": ["file_manager"],
                    "action_required": True,
                    "tool_suggestion": "file_manager",
                    "reasoning": f"Task de leitura de arquivo: {pattern.strip()}"
                }
            elif pattern.strip() in ["liste", "listar", "mostre", "mostrar", "exiba", "exibir"]:
                return {
                    "intent": "task",
                    "confidence": 0.9,
                    "entities": ["shell_exec"],
                    "action_required": True,
                    "tool_suggestion": "shell_exec",
                    "reasoning": f"Task de listagem: {pattern.strip()}"
                }
            else:
                return {
                    "intent": "task",
                    "confidence": 0.85,
                    "entities": [],
                    "action_required": True,
                    "tool_suggestion": "",
                    "reasoning": f"Task detectada: {pattern.strip()}"
                }
    
    # Detectar tarefas no meio da frase
    task_keywords = [
        ("pesquise", "web_search"), ("busque", "web_search"), ("pesquisar", "web_search"),
        ("execute", "shell_exec"), ("executar", "shell_exec"), ("rode", "shell_exec"),
        ("rode ", "shell_exec"), ("roda ", "shell_exec"),
        ("leia", "file_manager"), ("ler", "file_manager"), ("arquivo", "file_manager"),
        ("crie", "shell_exec"), ("criar", "shell_exec"),
    ]
    
    for keyword, tool in task_keywords:
        if keyword in msg_lower:
            return {
                "intent": "task",
                "confidence": 0.9,
                "entities": [tool],
                "action_required": True,
                "tool_suggestion": tool,
                "reasoning": f"Keyword de task detectado: {keyword}"
            }
    
    # ========================================
    # PRIORIDADE 3: Perguntas sobre sistema (QUESTION) - COM ACTION REQUIRED
    # ========================================
    # Perguntas que DEVEM executar ação (action_required=True)
    question_with_action = [
        # Memória
        "memoria", "memória", "memory",
        # Containers
        "quantos containers", "quantos docker",
        # Status
        "como está", "estado do",
        # Disco
        "quanto espaço", "quanto disco",
        # Serviços
        "quantos serviços", "quais serviços",
        # Instalação - ESTE É O CASO CRÍTICO!
        "tem instalado", "o que tem instalado", "quais programas", "tem o",
        "tem o claude", "tem o docker", "tem o postgres", "tem o redis",
        "esta instalado", "está instalado", "está instalados",
        "como ver", "como verificar", "como saber",
    ]
    
    for pattern in question_with_action:
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
    
    # ========================================
    # PRIORIDADE 4: Comandos específicos do Telegram
    # ========================================
    telegram_commands = {
        "status do sistema": "get_system_status",
        "status geral": "get_system_status",
        "quanta ram": "get_ram",
        "quantas ram": "get_ram",
        "uso da ram": "get_ram",
        "lista containers": "list_containers",
        "listar containers": "list_containers",
        "containers docker": "list_containers",
        "containers": "list_containers",
        "docker": "list_containers",
        "health check": "get_system_status",
        "healthcheck": "get_system_status",
        "health": "get_system_status",
    }
    
    for cmd_pattern, tool in telegram_commands.items():
        if cmd_pattern in msg_lower:
            return {
                "intent": "command",
                "confidence": 0.95,
                "entities": [tool],
                "action_required": True,
                "tool_suggestion": tool,
                "reasoning": f"Comando Telegram detectado: {cmd_pattern}"
            }
    
    # ========================================
    # PRIORIDADE 5: Self-Improve
    # ========================================
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
    
    # ========================================
    # DEFAULT: Chat (conversa natural)
    # ========================================
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
        # Fallback total: usar inferência local (não depende de intent_classifier.py)
        result = infer_intent_from_message(message)
        return (
            result["intent"],
            result["confidence"],
            result
        )


__all__ = [
    "IntentClassification",
    "classify_intent_llm",
    "classify_intent_with_llm",
]
