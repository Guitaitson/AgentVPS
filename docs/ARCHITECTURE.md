# Arquitetura VPS-Agente v2 — Interpretador de Intenções

## Visão Geral

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram User                           │
│                     (@Molttaitbot)                         │
└────────────────────────┬──────────────────────────────────┘
                         │ /start, /help, /status
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Telegram Bot Handler                          │
│              (Mensagens simples + Comandos)                │
└────────────────────────┬──────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              AGENTE INTERPRETADOR                          │
│              (LangGraph + classify_intent)                 │
│                                                            │
│    ┌─────────────────────────────────────────────────┐     │
│    │  classify_intent:                               │     │
│    │  • task_request → CLI                          │     │
│    │  • conversation → Memory only                  │     │
│    │  • question → CLI (with memory)                │     │
│    │  • system_command → Direct response            │     │
│    └─────────────────────────────────────────────────┘     │
└────────────────────────┬──────────────────────────────────┘
                         │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
         ┌──────┐   ┌──────┐   ┌──────────┐
         │ CLI  │   │Memory │   │ Response │
         │      │   │Only   │   │          │
         └──┬───┘   └────┬───┘   └──────────┘
            │            │
            ▼            ▼
    ┌──────────────┐  ┌────────────────┐
    │ Kilocode CLI │  │ PostgreSQL     │
    │ MiniMax M2.1 │  │ Qdrant         │
    │ (free)       │  │ (semantic)     │
    └──────────────┘  └────────────────┘
```

---

## Fluxo de Processamento

### 1. Mensagem Recebida
```
User → /start
     → "Oi, tudo bem?"
     → "Analise os logs e me diga o status"
```

### 2. Classificação de Intenção (LangGraph Node)

```python
def classify_intent(state: AgentState) -> AgentState:
    """
    Classifica a intenção do usuário e decide o fluxo.
    """
    message = state["user_message"].lower()
    
    # Comandos do sistema
    if message.startswith("/"):
        intent = "system_command"
    # Requisições de tarefa
    elif any(word in message for word in [
        "analise", "verifique", "execute", "rode",
        "crie", "implemente", "desenvolva"
    ]):
        intent = "task_request"
    # Perguntas sobre contexto
    elif "?" in message:
        intent = "question"
    # Conversa normal
    else:
        intent = "conversation"
    
    return {
        **state,
        "intent": intent,
        "timestamp": datetime.now().isoformat()
    }
```

### 3. Decisão de Roteamento

| Intenção | Ação | Destino |
|----------|------|---------|
| `system_command` | Responde diretamente | /status, /ram, /help |
| `task_request` | Envia para CLI | Kilocode + MiniMax M2.1 |
| `question` | CLI + Memória | Kilocode + contexto |
| `conversation` | Apenas memoriza | PostgreSQL + Qdrant |

---

## Configuração do MiniMax M2.1 (Free)

### Kilocode com OpenRouter

```python
# No agent-cli.sh ou configuração
export OPENROUTER_API_KEY="sk-or-v1-sua-chave"
export OPENROUTER_MODEL="minimax/minimax-m2.1"

# No kilocode.config.json
{
  "provider": "openrouter",
  "model": "minimax/minimax-m2.1",
  "api_key": "${OPENROUTER_API_KEY}",
  "temperature": 0.7,
  "system_prompt": "Você é um assistente útil e conciso."
}
```

---

## Integração com Telegram

### Handler de Mensagens

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processa mensagens através do agente interpretador.
    """
    user_id = str(update.effective_user.id)
    message = update.message.text
    
    # Classificar intenção
    intent = classify_intent({"user_message": message})
    
    if intent == "system_command":
        await handle_system_command(update, message)
    elif intent == "task_request":
        await handle_task_request(update, message)  # CLI
    elif intent == "question":
        await handle_question(update, message)  # CLI + Memory
    else:
        await handle_conversation(update, message)  # Memory only
```

---

## Memory Bank

### PostgreSQL (Memória Estruturada)

```sql
-- Tabela de intenções classificadas
CREATE TABLE conversation_intents (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(32),
    original_message TEXT,
    classified_intent VARCHAR(32),
    routed_to VARCHAR(32),
    response TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabela de memórias
CREATE TABLE agent_memory (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(32),
    content TEXT,
    embedding vector(1536),  -- OpenAI/Claude embeddings
    category VARCHAR(32),
    importance FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Qdrant (Memória Semântica)

```python
# Salvar embedding no Qdrant
async def save_semantic_memory(user_id: str, content: str, embedding: list):
    qdrant_client.upsert(
        collection_name="agent_memory",
        points=[{
            "id": str(uuid.uuid4()),
            "vector": embedding,
            "payload": {
                "user_id": user_id,
                "content": content,
                "type": "conversation"
            }
        }]
    )
```

---

## Exemplo de Conversa

### Usuário
> "Oi, tudo bem?"

### Fluxo
```
1. /start → sistema
2. "Oi..." → conversa
3. Salva em PostgreSQL + Qdrant
4. Responde: "Olá! Estou funcionando bem. Como posso ajudar?"
```

### Usuário
> "Analise o uso de RAM e me diga se há problemas"

### Fluxo
```
1. "Analise..." → task_request
2. Envia para Kilocode CLI
3. CLI executa: free -m && docker stats
4. Retorna análise
5. Responde: "RAM em 25% de uso, tudo ok."
```

---

## Não Precisa de Flowise!

**Flowise** seria uma camada extra desnecessária. O LangGraph já oferece:

- ✅ Classificação de intenção (nodes.py)
- ✅ Roteamento inteligente
- ✅ Memória PostgreSQL
- ✅ Memória semântica Qdrant
- ✅ Integração CLI

Flowise seria útil apenas para:
- Visualização de flows (UI)
- Drag-and-drop workflows
- Integrações pré-construídas

Para **agente autônomo**, LangGraph é a escolha correta.

---

## Próximos Passos

1. ✅ Classificar intenções no LangGraph
2. ⏳ Conectar Kilocode com MiniMax M2.1
3. ⏳ Implementar roteamento Telegram → CLI
4. ⏳ Adicionar memória semântica Qdrant
5. ⏳ Testar fluxo completo
