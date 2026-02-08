# Enhanced Intent Classifier - Classificador melhorado de intenções

"""
Módulo de classificação de intenções melhorado.

Este módulo implementa recomendações para melhorar a classificação de intents:
- Padrões mais abrangentes
- Suporte a mensagens em português e inglês
- Detecção de intents compostos
- Fallback para classificação por LLM
"""

from typing import Dict, List, Tuple, Optional, Any
from enum import Enum


class Intent(Enum):
    """Enumeração dos tipos de intenção suportados."""
    COMMAND = "command"
    TASK = "task"
    QUESTION = "question"
    CHAT = "chat"
    SELF_IMPROVE = "self_improve"
    UNKNOWN = "unknown"


# ============ Padrões de Classificação ============

# Comandos diretos do Telegram/sistema
TELEGRAM_COMMANDS = [
    "/start", "/status", "/ram", "/containers", "/health", "/help",
    "/memory", "/skills", "/version", "/about",
    # Sem barra (comandos alternativos)
    "start", "status", "ram", "containers", "health", "help",
    "memory", "skills", "version", "about",
    "parar", "iniciar", "reiniciar", "ajuda",
]

# Palavras-chave que indicam tarefas de auto-melhoria
SELF_IMPROVE_KEYWORDS = [
    # Criação
    "criar", "crie", "criando", "criação",
    "novo", "nova", "novos", "novas",
    # Implementação
    "implementar", "implementa", "implementando", "implementação",
    "desenvolver", "desenvolve", "desenvolvendo",
    "codar", "codando", "programar", "programando",
    # Agentes
    "agente", "subagente", "sub-agente", "assistant", "bot",
    # Ferramentas e integrações
    "mcp", "ferramenta", "tool", "skill",
    "integração", "integrar", "conectar", "conexão",
    "plugin", "extension", "extensão",
    # Busca e pesquisa
    "buscar", "busca", "procurar", "pesquisar", "search",
    "monitorar", "monitoramento", "watch",
    # GitHub específico
    "github", "repositório", "repo", "repos", "pr", "pull request",
    "commit", "branch", "merge", "issue",
]

# Perguntas sobre o sistema
SYSTEM_KEYWORDS = [
    # Hardware/Recursos
    "ram", "memória", "memory", "cpu", "disco", "disk", "espaço", "space",
    # Containers
    "docker", "container", "containers", "imagem", "image",
    # Serviços
    "serviço", "service", "serviços", "services",
    "postgresql", "postgres", "redis", "banco", "database",
    # Status
    "status", "saúde", "health", "como está", "está rodando",
    # Rede
    "rede", "network", "porta", "port", "ip",
]

# Preguntas gerais (indicadores de interrogacao)
QUESTION_INDICATORS = [
    "qual e", "quais sao", "o que e", "quem e", "onde esta",
    "quanto e", "por que", "porque", "como", "quando", "para que",
    "me explica", "me diz", "me conta", "voce sabe", "sabe dizer",
    "nao entendo", "nao compreendo",
]

# Acoes a executar
ACTION_KEYWORDS = [
    # Verbos de ação
    "rode", "roda", "rode", "executar", "executa", "executando",
    "rode", "run", "start", "iniciar", "inicia", "iniciando",
    "parar", "para", "parando", "stop", "stop",
    "reiniciar", "reinicia", "reiniciando", "restart",
    "instale", "instala", "instalar", "instala", "instalando",
    "configure", "configura", "configurar", "configurando",
    "liste", "lista", "listar", "listando",
    "mostre", "mostra", "mostrar", "mostrando",
    # Arquivos
    "arquivo", "file", "criar", "criando", "editar", "editando",
    "ler", "lendo", "leia", "deletar", "deletando",
]

# Palavras de conversa natural
CHAT_KEYWORDS = [
    "oi", "olá", "ola", "hello", "hi", "e aí", "eaí", "eai",
    "tudo bem", "como vai", "bom dia", "boa tarde", "boa noite",
    "obrigado", "obrigada", "thanks", "thank",
    "por favor", "please",
    "posso", "pode", "você consegue", "você pode",
]

# Keywords que indicam skills faltantes (para resposta smarter)
SKILL_INDICATORS = {
    "github": ["github", "repositório", "repo", "pr", "pull request", "commit", "branch"],
    "web_search": ["buscar", "pesquisar", "search", "google", "internet", "web"],
    "file_manager": ["arquivo", "file", "criar arquivo", "editar arquivo", "ler arquivo"],
    "email": ["email", "e-mail", "enviar email", "gmail", "smtp"],
    "slack": ["slack", "mensagem slack", "canal slack"],
    "database": ["banco de dados", "sql", "query", "postgres", "mysql"],
    "docker": ["docker", "container", "imagem", "kubernetes", "k8s"],
    "api": ["api", "endpoint", "rest", "http", "request"],
    "monitoring": ["monitorar", "monitoramento", "alerta", "notificação"],
}


# ============ Funções de Classificação ============

def classify_intent(message: str) -> Tuple[Intent, float, Dict[str, Any]]:
    """
    Classifica a intenção do usuário com base na mensagem.
    
    Args:
        message: Mensagem do usuário
        
    Returns:
        Tupla de (intent, confidence, details)
        - intent: Enum da intenção classificada
        - confidence: Confiança da classificação (0.0 a 1.0)
        - details: Dicionário com detalhes da classificação
    """
    message_lower = message.lower().strip()
    
    # 1. Verificar comandos diretos do Telegram
    for cmd in TELEGRAM_COMMANDS:
        if message_lower.startswith(cmd):
            return (
                Intent.COMMAND,
                0.95,
                {"command": cmd, "matched": "telegram_command"}
            )
    
    # 2. Verificar palavras-chave de self_improve (antes das outras)
    self_improve_score = _check_keywords(message_lower, SELF_IMPROVE_KEYWORDS)
    if self_improve_score >= 0.7:
        return (
            Intent.SELF_IMPROVE,
            self_improve_score,
            {"keywords": _get_matched_keywords(message_lower, SELF_IMPROVE_KEYWORDS)}
        )
    
    # 3. Verificar perguntas sobre o sistema\n    system_score = _check_keywords(message_lower, SYSTEM_KEYWORDS)\n    if system_score >= 0.6:\n        return (\n            Intent.QUESTION,\n            system_score,\n            {"keywords": _get_matched_keywords(message_lower, SYSTEM_KEYWORDS)}\n        )\n    \n    # 3.5. Verificar indicadores de perguntas gerais\n    question_score = _check_keywords(message_lower, QUESTION_INDICATORS)\n    if question_score >= 0.5:\n        return (\n            Intent.QUESTION,\n            question_score,\n            {"keywords": _get_matched_keywords(message_lower, QUESTION_INDICATORS)}\n        )\n    \n    # 4. Verificar acoes
    system_score = _check_keywords(message_lower, SYSTEM_KEYWORDS)
    if system_score >= 0.6:
        return (
            Intent.QUESTION,
            system_score,
            {"keywords": _get_matched_keywords(message_lower, SYSTEM_KEYWORDS)}
        )
    
    # 4. Verificar ações a executar
    action_score = _check_keywords(message_lower, ACTION_KEYWORDS)
    if action_score >= 0.6:
        return (
            Intent.TASK,
            action_score,
            {"keywords": _get_matched_keywords(message_lower, ACTION_KEYWORDS)}
        )
    
    # 5. Verificar conversa natural
    chat_score = _check_keywords(message_lower, CHAT_KEYWORDS)
    if chat_score >= 0.5 and len(message) < 50:
        return (
            Intent.CHAT,
            chat_score,
            {"keywords": _get_matched_keywords(message_lower, CHAT_KEYWORDS)}
        )
    
    # 6. Verificar se parece com pedido de skill faltante
    skill_indicators = _detect_skill_indicators(message_lower)
    if skill_indicators:
        return (
            Intent.SELF_IMPROVE,
            0.75,
            {"skill_indicators": skill_indicators}
        )
    
    # 7. Default: conversa (assumir que é conversa até prova em contrário)
    return (
        Intent.CHAT,
        0.60,
        {"reason": "default_fallback"}
    )


def _check_keywords(message: str, keywords: List[str]) -> float:
    """
    Calcula score baseado em palavras-chave encontradas.
    
    Args:
        message: Mensagem processada
        keywords: Lista de palavras-chave
        
    Returns:
        Score de 0.0 a 1.0
    """
    if not keywords:
        return 0.0
    
    matched = sum(1 for kw in keywords if kw in message)
    # Normalizar: mais matches = maior score, mas com decaimento
    ratio = matched / len(keywords)
    # Aplicar log para evitar scores muito altos com poucos matches
    import math
    score = min(1.0, math.log1p(matched) * 0.3 + ratio * 0.5)
    
    return score


def _get_matched_keywords(message: str, keywords: List[str]) -> List[str]:
    """
    Retorna lista de palavras-chave encontradas na mensagem.
    
    Args:
        message: Mensagem processada
        keywords: Lista de palavras-chave
        
    Returns:
        Lista de palavras-chave encontradas
    """
    return [kw for kw in keywords if kw in message]


def _detect_skill_indicators(message: str) -> Dict[str, bool]:
    """
    Detecta indicadores de skills que podem estar faltando.
    
    Args:
        message: Mensagem processada
        
    Returns:
        Dicionário com skills detectadas
    """
    detected = {}
    for skill, indicators in SKILL_INDICATORS.items():
        if any(ind in message for ind in indicators):
            detected[skill] = True
    return detected


def classify_with_context(
    message: str,
    conversation_history: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Classifica intenção considerando contexto da conversa.
    
    Args:
        message: Mensagem atual
        conversation_history: Histórico de mensagens anteriores
        
    Returns:
        Dicionário completo com classificação
    """
    # Classificação básica
    intent, confidence, details = classify_intent(message)
    
    # Ajustar baseado em contexto
    if conversation_history:
        # Verificar se há uma tendência
        intents_in_history = [
            msg.get("intent") for msg in conversation_history[-5:]
            if msg.get("intent")
        ]
        
        if intents_in_history:
            # Se últimas mensagens foram self_improve, manter tendência
            if intents_in_history[-1] == Intent.SELF_IMPROVE.value:
                if any(kw in message.lower() for kw in ["e", "também", "also", "mais"]):
                    # Parece continuação de self_improve
                    details["context_adjusted"] = True
                    details["original_intent"] = intent.value
                    intent = Intent.SELF_IMPROVE
                    confidence = max(confidence, 0.8)
    
    return {
        "intent": intent.value,
        "confidence": confidence,
        "details": details,
        "timestamp": "auto",
    }


def get_intent_description(intent: Intent) -> str:
    """
    Retorna descrição legível do intent.
    
    Args:
        intent: Enum do intent
        
    Returns:
        Descrição formatada
    """
    descriptions = {
        Intent.COMMAND: "Comando direto do Telegram",
        Intent.TASK: "Tarefa a ser executada",
        Intent.QUESTION: "Pergunta sobre o sistema",
        Intent.CHAT: "Conversa geral",
        Intent.SELF_IMPROVE: "Pedido de nova capacidade",
        Intent.UNKNOWN: "Intenção não reconhecida",
    }
    return descriptions.get(intent, "Desconhecido")


def suggest_alternatives(message: str) -> List[str]:
    """
    Sugere alternativas quando a classificação é incerta.
    
    Args:
        message: Mensagem original
        
    Returns:
        Lista de sugestões
    """
    suggestions = []
    message_lower = message.lower()
    
    # Sugerir comandos disponíveis
    if any(kw in message_lower for kw in ["ram", "memória", "memory"]):
        suggestions.append("Tente: /ram para ver status de memória")
    
    if any(kw in message_lower for kw in ["container", "docker"]):
        suggestions.append("Tente: /containers para listar containers")
    
    if any(kw in message_lower for kw in ["status", "como está"]):
        suggestions.append("Tente: /status para ver status geral")
    
    if any(kw in message_lower for kw in ["criar", "novo", "agente"]):
        suggestions.append("Posso criar novos agentes! Me diga o que você precisa.")
    
    return suggestions


# ============ Prompt para Classificação por LLM ============

INTENT_CLASSIFICATION_PROMPT = """
Você é um classificador de intenções para um agente VPS.

## Intenções Suportadas:
1. **command** - Comandos diretos do sistema (/status, /ram, /help)
2. **task** - Tarefas a executar (iniciar algo, parar algo, configurar)
3. **question** - Perguntas sobre o sistema (quanta RAM? como está?)
4. **chat** - Conversa natural (oi, tudo bem, obrigado)
5. **self_improve** - Pedidos para criar/implementar algo novo (criar agente, integrar GitHub)

## Exemplos:
- "oi" → chat
- "/status" → command
- "quanta RAM está livre?" → question
- "liste meus containers" → task
- "crie um novo agente" → self_improve
- "liste meus projetos no github" → self_improve (requer nova skill)

## Contexto:
Histórico recente: {history}

## Mensagem do usuário:
{message}

## Responda em JSON:
{{
    "intent": "...",
    "confidence": 0.0-1.0,
    "reasoning": "..."
}}
"""


def build_classification_prompt(message: str, history: str = "") -> str:
    """
    Constrói prompt para classificação por LLM.
    
    Args:
        message: Mensagem a classificar
        history: Histórico formatado
        
    Returns:
        Prompt completo
    """
    return INTENT_CLASSIFICATION_PROMPT.format(
        message=message,
        history=history or "Nenhum histórico"
    )


# ============ Testes ============

if __name__ == "__main__":
    # Testes básicos
    test_cases = [
        ("oi", Intent.CHAT),
        ("/status", Intent.COMMAND),
        ("quanta RAM?", Intent.QUESTION),
        ("liste containers", Intent.TASK),
        ("crie um agente", Intent.SELF_IMPROVE),
        ("liste meus projetos no github", Intent.SELF_IMPROVE),
    ]
    
    print("=== Testes de Classificação ===")
    for message, expected in test_cases:
        intent, confidence, details = classify_intent(message)
        status = "✅" if intent == expected else "❌"
        print(f"{status} '{message}' → {intent.value} ({confidence:.2f})")

