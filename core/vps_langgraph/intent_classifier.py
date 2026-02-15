# DEPRECATED: Este módulo foi substituído por intent_classifier_llm.py
# A funcionalidade de classificação de intents foi movida para:
# - core/vps_langgraph/intent_classifier_llm.py (classificador LLM + fallback local)
#
# O fallback local (infer_intent_from_message) está agora incluído no próprio
# intent_classifier_llm.py, então este arquivo não é mais necessário.
#
# Este arquivo permanece apenas por compatibilidade histórica.
# Pode ser deletado com segurança total.

# LINHAS ORIGINAIS REMOVIDAS: 571

# ============================================
# FUNÇÕES DE COMPATIBILIDADE PARA TESTES
# ============================================

def classify_intent(message: str) -> dict:
    """
    Função de compatibilidade para testes.
    classification simples baseada em padrões (sem LLM).
    """
    message = message.strip().lower()
    
    # Comando startswith /
    if message.startswith("/") or message.startswith("!"):
        return {"intent": "command", "confidence": 0.95}
    
    # Palavras-chave de tarefa
    task_keywords = ["liste", "crie", "execute", "rode", "rode", "verifique", "mostre"]
    for kw in task_keywords:
        if kw in message:
            return {"intent": "task", "confidence": 0.8}
    
    # Palavras-chave de pergunta
    question_keywords = [" quanto", " qual", " como", " o que", "?", "porque", "por que"]
    for kw in question_keywords:
        if kw in message:
            return {"intent": "question", "confidence": 0.8}
    
    # Default: chat
    return {"intent": "chat", "confidence": 0.7}
