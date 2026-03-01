# Arquitetura: Agente Autônomo VPS-Agent

## Visão
**Uma VPS de 2.4GB RAM que funciona como um AGENTE AUTÔNOMO completo.**

O agente deve ser capaz de:
1. **Entender** qualquer pedido (NLU)
2. **Decidir** qual ferramenta/conhecimento usar
3. **Executar** ações (CLI, APIs, Docker)
4. **Aprender** com interações
5. **Evoluir** implementando novas capacidades sozinho

---

## Arquitetura Atual (Parcial)
```
Telegram → LangGraph → LLM → Resposta Genérica
              ↓
         Capabilities (verifica)
              ↓
         Self-Improve (detecta)
```

## Arquitetura Alvo (Completa)
```
┌─────────────────────────────────────────────────────────────────┐
│                      Agente Autônomo VPS-Agent                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. ENTRADA (Telegram / MCP / API)                              │
│     - Mensagens em linguagem natural                             │
│     - Solicitações de ferramentas                                │
│     - Comandos                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. CLASSIFICAÇÃO DE INTENÇÃO (LangGraph)                       │
│                                                                     │
│     user_message → classify_intent → intent_type                    │
│                                                                     │
│     intent_types:                                                  │
│     - command: "/status", "/ram", "/help"                         │
│     - task: "crie um agente", "liste containers"                  │
│     - question: "quanta RAM tenho?", "o que você sabe?"           │
│     - chat: "oi", "tudo bem?", conversa casual                    │
│     - learn: "aprenda isso", "guarde essa informação"              │
│     - self_improve: "implemente nova capacidade"                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. SELEÇÃO DE FERRAMENTA                                        │
│                                                                     │
│     Se command → executa comando local                            │
│     Se task     → verifica ferramentas disponíveis                │
│     Se question → busca memória / internet                       │
│     Se chat     → LLM (conversação natural)                      │
│     Se learn    → salva na memória                               │
│     Se self_imp → Self-Improvement Agent                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. EXECUÇÃO                                                     │
│                                                                     │
│     Ferramentas Disponíveis:                                      │
│     ┌─────────────────────────────────────────────────────────┐   │
│     │ MEMÓRIA                                                  │   │
│     │ • PostgreSQL: Fatos estruturados                         │   │
│     │ • Redis: Cache e sessão                                 │   │
│     │ • Qdrant: Memória semântica (embeddings)               │   │
│     └─────────────────────────────────────────────────────────┘   │
│     ┌─────────────────────────────────────────────────────────┐   │
│     │ FERRAMENTAS DO SISTEMA                                  │   │
│     │ • Docker: Containers                                   │   │
│     │ • CLI: Kilocode/Claude                                 │   │
│     │ • Git: Versionamento                                    │   │
│     └─────────────────────────────────────────────────────────┘   │
│     ┌─────────────────────────────────────────────────────────┐   │
│     │ ACESSO EXTERNO                                         │   │
│     │ • MCP Servers: Ferramentas expostas                     │   │
│     │ • APIs: GitHub, Search, Browser                        │   │
│     │ • n8n/Flowise: Workflows de automação                 │   │
│     └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. APRENDIZADO & EVOLUÇÃO                                       │
│                                                                     │
│     Após cada interação:                                           │
│     • Salvar contexto na memória                                  │
│     • Atualizar capacidades se necessário                          │
│     • Gerar código para novas funcionalidades                     │
│     • Commitar changes no GitHub                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Capacidades Atuais vs. Necessárias

### Atuais (Já Implementadas)
| Capacidade | Status | Implementação |
|------------|--------|---------------|
| VPS RAM | ✅ | `core/mcp_server.py:/ram` |
| Containers Docker | ✅ | `core/mcp_server.py:/containers` |
| Serviços Core | ✅ | `core/mcp_server.py:/services` |
| Memória PostgreSQL | ✅ | `core/vps_langgraph/memory.py` |
| Memória Redis | ✅ | `core/vps_langgraph/memory.py` |
| LangGraph Agent | ✅ | `core/vps_langgraph/graph.py` |
| Telegram Bot | ✅ | `telegram-bot/bot.py` |
| MCP Server | ✅ | `core/mcp_server.py` |

### Necessárias (A Implementar)
| Capacidade | Prioridade | Como Implementar |
|-----------|------------|-------------------|
| 🔴 **GitHub API** | Alta | MCP ou ferramenta direta |
| 🔴 **Web Search** | Alta | Brave MCP ou API |
| 🔴 **Git Operations** | Média | CLI git integrado |
| 🟡 **Browser/Web Fetch** | Média | Playwright ou httpx |
| 🟡 **File Operations** | Média | Python pathlib |
| 🟢 **Self-Improvement** | Crítica | Já existe, precisa integrar |
| 🟢 **Memory Learning** | Crítica | Qdrant + PostgreSQL |

---

## Plano de Implementação

### Fase 1: Corrigir Identidade do Agente (Imediato)
- [ ] System prompt atualizado com todas as capacidades
- [ ] LLM sabe que é VPS-Agent, não "modelo genérico"
- [ ] Respostas contextualizadas

### Fase 2: Conectar Ferramentas Reais
- [ ] Criar `core/tools/` com ferramentas modulares
- [ ] GitHub API (repositórios, issues, PRs)
- [ ] Web Search (Brave Search API)
- [ ] Git Operations (clone, commit, push)

### Fase 3: Integrar Self-Improvement
- [ ] Fluxo: usuário pede → detecta capacidade faltante → implementa
- [ ] Auto-geração de código
- [ ] Commit automático no GitHub

### Fase 4: Memória Semântica (Qdrant)
- [ ] Embeddings de conversas
- [ ] Busca vetorial de conhecimento
- [ ] O agente "lembra" de conversas anteriores

---

## Exemplo de Conversa Futura

```
Usuário: "oi, tudo bem?"

Agente: "Olá! Tudo bem sim! 😊 
Sou o VPS-Agent, seu assistente autonomous.
Posso ajudar com:
• Gerenciar sua VPS (RAM, containers, serviços)
• Acessar seu GitHub
• Pesquisar na web
• Criar novos agentes e ferramentas
• E muito mais!

O que precisa hoje?"

---

Usuário: "quais projetos tenho no github?"

Agente: "Vou verificar seus repositórios..."
[Chama GitHub API]
"Você tem 12 repositórios:

🌟 Principais:
• AgenteVPS (público) - Seu agente autonomous
• Moltbot (público) - Bot Telegram

📁 Outros:
• projeto-teste-1
• ...
"
```

---

## Métricas de Sucesso

| Métrica | Meta |
|---------|------|
| Respostas naturais | 100% das conversas |
| Ferramentas utilizadas | 90% dos pedidos |
| Self-Improvement | Mínimo 1 capacidade/semana |
| Memória persistente | 100% das interações |
| Uptime do agente | 99% |

---

## Próximos Passos Imediatos

1. **Corrigir System Prompt** - LLM sabe que é VPS-Agent
2. **Criar Ferramenta GitHub** - API para listar repos
3. **Testar Fluxo Completo** - Pedido → Classificação → Execução → Resposta
