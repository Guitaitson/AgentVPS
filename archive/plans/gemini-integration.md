# Plano de Integração: Google Gemini 2.5 Flash Lite via OpenRouter

## Objetivo
Tornar as conversas com o Telegram Bot mais naturais e fluidas, usando LLM para gerar respostas contextuais.

## Arquitetura Atual
- **Respostas atuais:** Templates string fixos em `node_generate_response()`
- **Intent "chat":** `"Entendi sua mensagem: '{user_message}'. Como posso ajudar?"`

## Arquitetura Proposta

```
┌─────────────────────────────────────────────────────────────────┐
│                    Telegram Bot (@Molttaitbot)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Agent                              │
│  classify → load_context → plan → execute → respond → save     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              node_generate_response (MODIFICADO)                │
│                                                              │
│  intent=chat? ──► OpenRouter API (Gemini 2.5 Flash Lite)     │
│                        │                                       │
│                        ▼                                       │
│              Resposta natural e contextualizada                 │
└─────────────────────────────────────────────────────────────────┘
```

## Componentes a Implementar

### 1. Novo Módulo: `core/llm/openrouter_client.py`

```python
# Funções principais:
- generate_response(system_prompt: str, user_message: str) -> str
- count_tokens(text: str) -> int
- estimate_cost(input_tokens: int, output_tokens: int) -> float
```

### 2. Modificar: `core/vps_langgraph/nodes.py`

Atualizar `node_generate_response()` para:
- Detectar intent "chat" ou perguntas
- Chamar LLM com contexto da conversa
- Fallback para resposta genérica em caso de erro

### 3. Atualizar: `core/.env`

```env
# OpenRouter (LLM)
OPENROUTER_API_KEY=sk-or-v1-nova-chave-aqui
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
OPENROUTER_MAX_TOKENS=500
OPENROUTER_TEMPERATURE=0.7
```

### 4. Prompt do Sistema

```python
SYSTEM_PROMPT = """Você é o VPS-Agent, um assistente virtual que ajuda
o usuário a gerenciar sua VPS (Virtual Private Server).

Suas características:
- Respostas curtas e úteis
- Sempre oferece ajuda com comandos
- Mantém contexto da conversa
- Pode executar tarefas via Docker e CLI

Histórico recente da conversa:
{conversation_history}

Contexto do usuário:
{user_context}

Responda de forma natural e helpful."""
```

## Passos de Implementação

### Passo 1: Criar diretório e módulo LLM
- [ ] Criar `core/llm/__init__.py`
- [ ] Criar `core/llm/openrouter_client.py` com funções básicas

### Passo 2: Implementar cliente OpenRouter
- [ ] Função `generate_response()` com chiamda HTTP
- [ ] Tratamento de erros e retry
- [ ] Logging de requisições

### Passo 3: Integrar com node_generate_response
- [ ] Modificar função para detectar quando usar LLM
- [ ] Construir prompt com contexto
- [ ] Implementar fallback para erro

### Passo 4: Configurar variáveis de ambiente
- [ ] Atualizar `.env.example`
- [ ] Atualizar `.env` na VPS com nova API key
- [ ] Testar conexão

### Passo 5: Testes
- [ ] Testar respostas para intents "chat"
- [ ] Testar fallback em caso de erro LLM
- [ ] Verificar custos (dashboard OpenRouter)

## Considerações de Custo

| Modelo | Custo por 1M tokens | Uso estimado |
|--------|---------------------|--------------|
| Gemini 2.5 Flash Lite | ~$0.10 (entrada) / $0.40 (saída) | ~$0.001 por mensagem |

- **Média de mensagens/dia:** ~50
- **Custo mensal estimado:** ~$1.50

## Variáveis de Ambiente Novas

```env
# OpenRouter (LLM)
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
OPENROUTER_MAX_TOKENS=256
OPENROUTER_TEMPERATURE=0.7
OPENROUTER_TIMEOUT=10
```

## Resultados Esperados

### Antes
```
"oi" → "Entendi sua mensagem: 'oi'. Como posso ajudar?"
```

### Depois
```
"oi" → "Olá! Tudo bem? Sou o VPS-Agent, seu assistente de VPS. 
Posso ajudar a verificar containers, memory usage, executar comandos, 
ou qualquer outra tarefa. O que precisa?"
```

## Timeline Sugerido

1. **Criação do módulo LLM:** 30 minutos
2. **Integração com nodes:** 1 hora
3. **Configuração e testes:** 1 hora
4. **Total:** ~2-3 horas

## Riscos e Mitigações

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| API Key inválida | Média | Fallback para respostas genéricas |
| Timeout LLM | Baixa | Timeout de 10s, retry 1x |
| Custo alto | Baixa | Limitar tokens (256), monitorar uso |
| Respostas ruins | Média | Ajustar prompt e temperature |
