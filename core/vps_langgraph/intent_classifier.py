# Enhanced Intent Classifier - Classificador melhorado de intencoes

"""
Modulo de classificacao de intencoes melhorado.

Este modulo implementa recomendacoes para melhorar a classificacao de intents:
- Padroes mais abrangentes
- Suporte a mensagens em portugues e ingles
- Deteccao de intents compostos
- Fallback para classificacao por LLM
"""

from typing import Dict, List, Tuple, Any
from enum import Enum


class Intent(Enum):
    """Enumeracao dos tipos de intencao suportados."""
    COMMAND = "command"
    TASK = "task"
    QUESTION = "question"
    CHAT = "chat"
    SELF_IMPROVE = "self_improve"
    UNKNOWN = "unknown"


# ============ Padroes de Classificacao ============

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
    # Criacao
    "criar", "crie", "criando", "criacao",
    "novo", "nova", "novos", "novas",
    # Implementacao
    "implementar", "implementa", "implementando", "implementacao",
    "desenvolver", "desenvolve", "desenvolvendo",
    "codar", "codando", "programar", "programando",
    # Agentes
    "agente", "subagente", "sub-agente", "assistant", "bot",
    # Ferramentas e integracoes
    "mcp", "ferramenta", "tool", "skill",
    "integracao", "integrar", "conectar", "conexao",
    "plugin", "extension", "extensao",
    # Busca e pesquisa
    "buscar", "busca", "procurar", "pesquisar", "search",
    "monitorar", "monitoramento", "watch",
    # GitHub especifico
    "github", "repositorio", "repo", "repos", "pr", "pull request",
    "commit", "branch", "merge", "issue",
]

# Perguntas sobre o sistema
SYSTEM_KEYWORDS = [
    # Hardware/Recursos
    "ram", "memoria", "memory", "cpu", "disco", "disk", "espaco", "space",
    # Containers
    "docker", "container", "containers", "imagem", "image",
    # Servicos
    "servico", "service", "servicos", "services",
    "postgresql", "postgres", "redis", "banco", "database",
    # Status
    "status", "saude", "health", "como esta", "esta rodando",
    # Rede
    "rede", "network", "porta", "port", "ip",
]

# Perguntas gerais (indicadores de interrogacao)
QUESTION_INDICATORS = [
    "qual e", "quais sao", "o que e", "quem e", "onde esta",
    "quanto e", "por que", "porque", "como", "quando", "para que",
    "me explica", "me diz", "me conta", "voce sabe", "sabe dizer",
    "nao entendo", "nao compreendo",
]

# Acoes a executar
ACTION_KEYWORDS = [
    # Verbos de acao
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
    "oi", "ola", "hello", "hi", "e ai", "eai",
    "tudo bem", "como vai", "bom dia", "boa tarde", "boa noite",
    "obrigado", "obrigada", "thanks", "thank",
    "por favor", "please",
    "posso", "pode", "voce consegue", "voce pode",
]

# Keywords que indicam skills faltantes (para resposta smarter)
SKILL_INDICATORS = {
    "github": ["github", "repositorio", "repo", "pr", "pull request", "commit", "branch"],
    "web_search": ["buscar", "pesquisar", "search", "google", "internet", "web"],
    "file_manager": ["arquivo", "file", "criar arquivo", "editar arquivo", "ler arquivo"],
    "email": ["email", "e-mail", "enviar email", "gmail", "smtp"],
    "slack": ["slack", "mensagem slack", "canal slack"],
    "database": ["banco de dados", "sql", "query", "postgres", "mysql"],
    "docker": ["docker", "container", "imagem", "kubernetes", "k8s"],
    "api": ["api", "endpoint", "rest", "http", "request"],
    "monitoring": ["monitorar", "monitoramento", "alerta", "notificacao"],
}


# ============ Funcoes de Classificacao ============

def classify_intent(message: str) -> Tuple[Intent, float, Dict[str, Any]]:
    """
    Classifica a intencao do usuario com base na mensagem.
    
    Args:
        message: Mensagem do usuario
        
    Returns:
        Tupla de (intent, confidence, details)
        - intent: Enum da intencao classificada
        - confidence: Confianca da classificacao (0.0 a 1.0)
        - details: Dicionario com detalhes da classificacao
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
    
    # 3. Verificar perguntas sobre o sistema
    system_score = _check_keywords(message_lower, SYSTEM_KEYWORDS)
    if system_score >= 0.6:
        return (
            Intent.QUESTION,
            system_score,
            {"keywords": _get_matched_keywords(message_lower, SYSTEM_KEYWORDS)}
        )
    
    # 3.5. Verificar indicadores de perguntas gerais
    question_score = _check_keywords(message_lower, QUESTION_INDICATORS)
    if question_score >= 0.5:
        return (
            Intent.QUESTION,
            question_score,
            {"keywords": _get_matched_keywords(message_lower, QUESTION_INDICATORS)}
        )
    
    # 4. Verificar acoes a executar
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
    
    # 7. Default: conversa (assumir que e conversa ate prova em contrario)
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
        Dicionario com skills detectadas
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
    Classifica intencao considerando contexto da conversa.
    
    Args:
        message: Mensagem atual
        conversation_history: Historico de mensagens anteriores
        
    Returns:
        Dicionario completo com classificacao
    """
    # Classificacao basica
    intent, confidence, details = classify_intent(message)
    
    # Ajustar baseado em contexto
    if conversation_history:
        # Verificar se ha uma tendencia
        intents_in_history = [
            msg.get("intent") for msg in conversation_history[-5:]
            if msg.get("intent")
        ]
        
        if intents_in_history:
            # Se ultimas mensagens foram self_improve, manter tendencia
            if intents_in_history[-1] == Intent.SELF_IMPROVE.value:
                if any(kw in message.lower() for kw in ["e", "tambem", "also", "mais"]):
                    # Parece continuacao de self_improve
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
    Retorna descricao legivel do intent.
    
    Args:
        intent: Enum do intent
        
    Returns:
        Descricao formatada
    """
    descriptions = {
        Intent.COMMAND: "Comando direto do Telegram",
        Intent.TASK: "Tarefa a ser executada",
        Intent.QUESTION: "Pergunta sobre o sistema",
        Intent.CHAT: "Conversa geral",
        Intent.SELF_IMPROVE: "Pedido de nova capacidade",
        Intent.UNKNOWN: "Intencao nao reconhecida",
    }
    return descriptions.get(intent, "Desconhecido")


def suggest_alternatives(message: str) -> List[str]:
    """
    Sugere alternativas quando a classificacao e incerta.
    
    Args:
        message: Mensagem original
        
    Returns:
        Lista de sugestoes
    """
    suggestions = []
    message_lower = message.lower()
    
    # Sugerir comandos disponiveis
    if any(kw in message_lower for kw in ["ram", "memoria", "memory"]):
        suggestions.append("Tente: /ram para ver status de memoria")
    
    if any(kw in message_lower for kw in ["container", "docker"]):
        suggestions.append("Tente: /containers para listar containers")
    
    if any(kw in message_lower for kw in ["status", "como esta"]):
        suggestions.append("Tente: /status para ver status geral")
    
    if any(kw in message_lower for kw in ["criar", "novo", "agente"]):
        suggestions.append("Posso criar novos agentes! Me diga o que voce precisa.")
    
    return suggestions


# ============ Prompt para Classificacao por LLM ============

INTENT_CLASSIFICATION_PROMPT = """
Voce e um classificador de intencoes para um agente VPS.

## Intencoes Suportadas:
1. **command** - Comandos diretos do sistema (/status, /ram, /help)
2. **task** - Tarefas a executar (iniciar algo, parar algo, configurar)
3. **question** - Perguntas sobre o sistema (quanta RAM? como esta?)
4. **chat** - Conversa natural (oi, tudo bem, obrigado)
5. **self_improve** - Pedidos para criar/implementar algo novo (criar agente, integrar GitHub)

## Exemplos:
- "oi" -> chat
- "/status" -> command
- "quanta RAM?" -> question
- "liste containers" -> task
- "crie um agente" -> self_improve
- "liste meus projetos no github" -> self_improve (requer nova skill)

## Contexto:
Historico recente: {history}

## Mensagem do usuario:
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
    Constroi prompt para classificacao por LLM.
    
    Args:
        message: Mensagem a classificar
        history: Historico formatado
        
    Returns:
        Prompt completo
    """
    return INTENT_CLASSIFICATION_PROMPT.format(
        message=message,
        history=history or "Nenhum historico"
    )


# ============ Testes ============

if __name__ == "__main__":
    # Testes basicos
    test_cases = [
        ("oi", Intent.CHAT),
        ("/status", Intent.COMMAND),
        ("quanta RAM?", Intent.QUESTION),
        ("liste containers", Intent.TASK),
        ("crie um agente", Intent.SELF_IMPROVE),
        ("liste meus projetos no github", Intent.SELF_IMPROVE),
    ]
    
    print("=== Testes de Classificacao ===")
    for message, expected in test_cases:
        intent, confidence, details = classify_intent(message)
        status = "OK" if intent == expected else "FALHA"
        print(f"{status} '{message}' -> {intent.value} ({confidence:.2f})")
