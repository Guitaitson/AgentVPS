# Arquitetura — AgentVPS

> **⚠️ IMPORTANTE:** Leia [`CONTRIBUTING.md`](CONTRIBUTING.md) primeiro para entender como contribuir.

## 🎯 Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                    VPS 2.4 GB RAM (AGENTE)                      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    CÉREBRO (~500 MB)                    │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  CLI (Kilocode/Claude) + LangGraph + Agente       │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              SEMPRE LIGADOS (~750 MB TOTAL)             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │ PostgreSQL  │  │    Redis    │  │   LangGraph     │  │  │
│  │  │   (200 MB)  │  │   (60 MB)   │  │  Resource Mgr   │  │  │
│  │  └─────────────┘  └─────────────┘  │   Telegram Bot  │  │  │
│  │                                    └─────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              SOB DEMANDA (~1650 MB LIVRE)              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │   Qdrant   │  │     n8n     │  │    Flowise     │  │  │
│  │  │ (memória   │  │ (automações)│  │  (workflows)   │  │  │
│  │  │  semântica)│  │             │  │                 │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│  📱 Interface: Telegram Bot (@Molttaitbot)                       │
│  🧠 Memória: PostgreSQL + Redis + Qdrant                        │
│  🔧 Ferramentas: Docker containers sob demanda                  │
└─────────────────────────────────────────────────────────────────┘
```

## 🏗️ Arquitetura de Camadas

```mermaid
graph TB
    subgraph Interface
        T[📱 Telegram Bot] --> G[Gateway FastAPI]
        W[🌐 Webhooks] --> G
    end

    subgraph Core
        G --> R[Rate Limiter]
        R --> S[Session Manager]
        S --> I[Intent Classifier]
        I --> A[Agent LangGraph]
    end

    subgraph Memory
        A --> PG[(PostgreSQL)]
        A --> RQ[(Redis)]
        A --> QD[(Qdrant)]
    end

    subgraph Tools
        A --> RM[Resource Manager]
        RM --> DC[Docker Containers]
        RM --> MC[MCP Server]
    end

    subgraph LLM
        A --> LP[LLM Provider]
        LP --> OR[OpenRouter]
        LP --> AN[Anthropic]
    end

    subgraph Security
        G --> SL[Structured Logging]
        A --> SW[Security Allowlist]
    end
```

## 📦 Estrutura de Diretórios

```
AgentVPS/
├── core/                          # 🎯 Núcleo do sistema
│   ├── gateway/                   # 🌐 HTTP endpoints
│   │   ├── main.py                # FastAPI app
│   │   ├── adapters.py            # Telegram/Webhook adapters
│   │   ├── rate_limiter.py        # Rate limiting
│   │   └── session_manager.py      # Sessões Redis
│   │
│   ├── llm/                       # 🤖 Integração LLM
│   │   ├── provider.py            # Abstração de providers
│   │   ├── openrouter_client.py    # OpenRouter client
│   │   ├── agent_identity.py       # Prompt de identidade
│   │   └── prompt_composer.py      # Composição de prompts
│   │
│   ├── security/                   # 🔒 Segurança
│   │   └── allowlist.py           # Allowlist de ações
│   │
│   ├── resilience/                 # 🛡️ Resiliência
│   │   └── circuit_breaker.py      # Circuit breaker
│   │
│   ├── health_check/               # 🏥 Monitoramento
│   │   └── doctor.py               # Health checks
│   │
│   ├── structured_logging/         # 📊 Logging
│   │   └── structured.py           # JSON structured logs
│   │
│   ├── capabilities/               # ⚡ Capacidades
│   │   └── registry.py             # Registro de skills
│   │
│   ├── resource-manager/           # 📦 Recursos
│   │   └── manager.py              # Gerenciamento RAM
│   │
│   └── vps_langgraph/             # 🧠 Agente LangGraph
│       ├── graph.py               # Definition do grafo
│       ├── state.py               # Estado do agente
│       ├── nodes.py               # Nodes do workflow
│       ├── memory.py              # Memória PostgreSQL
│       ├── learnings.py           # Aprendizados
│       ├── intent_classifier.py  # Classificação intents
│       ├── error_handler.py      # Tratamento erros
│       └── smart_responses.py    # Respostas smart
│
├── telegram-bot/                  # 📱 Bot Telegram
│   ├── bot.py                    # Bot principal
│   └── telegram_handler.py        # Handler de logs
│
├── tests/                         # 🧪 Testes unitários
│   ├── test_gateway.py
│   ├── test_circuit_breaker.py
│   ├── test_health_check.py
│   ├── test_prompt_composer.py
│   ├── test_structured_logging.py
│   ├── test_allowlist.py
│   └── test_llm_provider.py
│
├── configs/                       # ⚙️ Configurações
│   ├── docker-compose.core.yml    # Serviços always-on
│   ├── init-db.sql                # DB initialization
│   └── .env.example               # Exemplo de variáveis
│
├── scripts/                       # 🔧 Scripts
│   └── deploy.sh                  # Deploy script
│
├── docs/                          # 📚 Documentação
│   ├── ARCHITECTURE.md           # Este arquivo
│   ├── MCP_SERVER.md             # MCP Server docs
│   └── adr/                      # Architecture Decision Records
│
├── .kilocode/                     # 🧠 Memory Bank (IA)
│   └── rules/
│       ├── memory-bank/
│       │   ├── brief.md          # Estado atual
│       │   ├── context.md         # Arquitetura
│       │   ├── deployment-tracker.md # Tracker progresso
│       │   ├── history.md         # Histórico decisões
│       │   └── project-context.md # Contexto projeto
│       └── vps-agent-rules.md    # Regras obrigatórias
│
├── requirements.txt               # Dependências Python
├── pyproject.toml                # Configuração projeto
└── README.md                     # Visão geral
```

## 🔄 Fluxo de Mensagem

```mermaid
sequenceDiagram
    participant U as Usuário
    participant T as Telegram Bot
    participant G as Gateway
    participant S as Session Manager
    participant I as Intent Classifier
    participant A as Agent LangGraph
    participant L as LLM Provider
    participant M as Memory

    U->>T: Envia mensagem
    T->>G: Webhook POST
    G->>S: create_session()
    S-->>G: Session ID

    G->>I: classify_intent(message)
    I-->>G: intent_type

    G->>A: process_message(state)
    A->>M: load_context()
    M-->>A: context

    A->>L: generate_response()
    L-->>A: response

    A->>M: save_memory()
    G->>T: Resposta
```

## 🎯 Classificação de Intentos

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTENT CLASSIFIER                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  COMMAND ──────► /status, /help, /restart, /logs              │
│                  → Execução direta de comandos                  │
│                                                                  │
│  TASK ──────────► "liste containers", "mostre RAM"             │
│                  → Execução de tarefas complexas                │
│                                                                  │
│  QUESTION ─────► "qual a RAM?", "como você funciona?"          │
│                  → Resposta informativa                          │
│                                                                  │
│  CHAT ──────────► "oi", "tudo bem?", "obrigado"                 │
│                  → Conversa natural                             │
│                                                                  │
│  SELF_IMPROVE ──► "crie uma nova skill", "melhore você"        │
│                  → Auto-evolução do agente                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 💾 Camadas de Memória

```mermaid
graph LR
    subgraph "PostgreSQL (Fatos)"
        F1[Preferências usuário]
        F2[Configs sistema]
        F3[Estado atual]
    end

    subgraph "Redis (Cache/Filas)"
        C1[Sessões ativas]
        C2[Cache rápido]
        C3[Fila de msgs]
    end

    subgraph "Qdrant (Semântica)"
        S1[Embeddings conversas]
        S2[Conceitos aprendidos]
        S3[Contexto semântico]
    end

    User --> F1
    User --> C1
    User --> S1

    F1 --> S1
    C1 --> S1
```

## 🔧 Gerenciamento de Recursos

```mermaid
graph TB
    subgraph "Sempre Ligados (~750 MB)"
        PG[(PostgreSQL ~200MB)]
        RD[(Redis ~60MB)]
        LG[LangGraph + Bot ~400MB]
    end

    subgraph "Sob Demanda (~1650 MB livre)"
        QD[Qdrant]
        N8[n8n]
        FS[Flowise]
    end

    subgraph "Resource Manager"
        RM[Verifica RAM]
        RM -->|RAM > 300MB| START[Start tool]
        RM -->|RAM < 300MB| SKIP[Skip - sem recursos]
    end

    START --> QD
    START --> N8
    START --> FS
```

## 🔒 Segurança

### Allowlist de Ações

```python
# Tipos de permissão
ALLOW      # Permite direto
REQUIRE_APPROVAL  # Pede confirmação
DENY        # Bloqueia
```

### Categorias Protegidas

| Categoria | Ações Permitidas | Regras |
|-----------|------------------|--------|
| `read` | Ver status, logs, RAM | Sempre permitido |
| `command` | docker ps, git | Apenas allowlist |
| `write` | Criar arquivos | Requer aprovação |
| `delete` | Remover arquivos | Bloqueado |
| `network` | APIs externas | Rate limited |
| `database` | SQL queries | Apenas leitura |

## 🧪 Testes

### Pirâmide de Testes

```
        ┌─────────┐
       /   E2E    \    ← 5 testes (test_*.py)
      /   (10%)    \
     ├───────────────┤
    /   Integração    \  ← 30% dos testes
   /   (tests/test_*)  \
  ├─────────────────────┤
 /       Unitários       \ ← 60% dos testes
/       (tests/)          \
└─────────────────────────┘
```

### Cobertura Mínima

| Componente | Cobertura Mínima |
|------------|-----------------|
| Gateway | 80% |
| Circuit Breaker | 90% |
| Health Check | 90% |
| LLM Provider | 75% |
| Security | 85% |

## 📊 CI/CD Pipeline

```mermaid
graph LR
    A[Push] --> B[Lint]
    B --> C[Test]
    C --> D[Docker Build]
    D --> E[Security Scan]
    E --> F[Deploy]

    B -- Fail --> G[Notify]
    C -- Fail --> G
    E -- Fail --> G
```

## 📁 Referências

| Recurso | Link |
|---------|------|
| GitHub | https://github.com/Guitaitson/AgentVPS |
| CI/CD | https://github.com/Guitaitson/AgentVPS/actions |
| VPS | 107.175.1.42 |
| Telegram | @Molttaitbot |
| ADRs | [`docs/adr/`](docs/adr/) |
| Roadmap | [`.kilocode/rules/memory-bank/deployment-tracker.md`](.kilocode/rules/memory-bank/deployment-tracker.md) |

---

**⚠️ LEMBRE-SE:** Esta documentação deve ser atualizada sempre que a arquitetura mudar. Ver [`CONTRIBUTING.md`](CONTRIBUTING.md) para guidelines.
