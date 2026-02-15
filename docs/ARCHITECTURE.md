# Arquitetura do VPS-Agent v2

## Visão Geral

O VPS-Agent é um sistema de agente autônomo projetado para operar em uma VPS com recursos limitados (2.4 GB RAM). A arquitetura segue princípios de modularidade, resiliência e eficiência de recursos.

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                      VPS-Agent v2                           │
│                    (2.4 GB RAM Total)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              SEMPRE LIGADOS (~750 MB)              │   │
│  │                                                     │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐    │   │
│  │  │   Telegram  │◄──►│      Telegram Bot       │    │   │
│  │  │    Bot      │    │    (telegram_bot/)      │    │   │
│  │  └─────────────┘    └─────────────────────────┘    │   │
│  │                              │                      │   │
│  │                              ▼                      │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐    │   │
│  │  │   Gateway   │◄──►│   FastAPI Gateway       │    │   │
│  │  │    HTTP     │    │    (core/gateway/)      │    │   │
│  │  └─────────────┘    └─────────────────────────┘    │   │
│  │                              │                      │   │
│  │                              ▼                      │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐    │   │
│  │  │ LangGraph   │◄──►│   VPS Agent Graph       │    │   │
│  │  │  Workflow   │    │ (core/vps_langgraph/)   │    │   │
│  │  └─────────────┘    └─────────────────────────┘    │   │
│  │           │                    │                    │   │
│  │           ▼                    ▼                    │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐    │   │
│  │  │   Memory    │◄──►│  AgentMemory (PostgreSQL)│   │   │
│  │  │  (PSQL)     │    │  (core/vps_langgraph/)   │   │   │
│  │  └─────────────┘    └─────────────────────────┘    │   │
│  │                                                     │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐    │   │
│  │  │   Redis     │◄──►│   Cache & Sessions      │    │   │
│  │  │   (Cache)   │    │    (core/gateway/)      │    │   │
│  │  └─────────────┘    └─────────────────────────┘    │   │
│  │                                                     │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐    │   │
│  │  │  PostgreSQL │◄──►│   Structured Storage    │    │   │
│  │  │   (PSQL)    │    │    (PostgreSQL 16)      │    │   │
│  │  └─────────────┘    └─────────────────────────┘    │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           SOB DEMANDA (~1650 MB livre)             │   │
│  │                                                     │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐    │   │
│  │  │   Qdrant    │◄──►│  Semantic Memory        │    │   │
│  │  │  (Vector)   │    │  (Vector Search)        │    │   │
│  │  └─────────────┘    └─────────────────────────┘    │   │
│  │                                                     │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐    │   │
│  │  │     n8n     │◄──►│  Workflow Automation    │    │   │
│  │  │  (Low-code) │    │  (Node-based flows)     │    │   │
│  │  └─────────────┘    └─────────────────────────┘    │   ││  │                                                     │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐    │   │
│  │  │   Flowise   │◄──►│  LLM Workflows          │    │   │
│  │  │  (Chatflow) │    │  (Visual builder)       │    │   │
│  │  └─────────────┘    └─────────────────────────┘    │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Camadas da Arquitetura

### 1. Interface Layer

**Responsabilidade:** Comunicação com usuários externos

| Componente | Localização | Descrição |
|------------|-------------|-----------|
| Telegram Bot | `telegram_bot/bot.py` | Interface principal via Telegram |
| Gateway HTTP | `core/gateway/main.py` | API REST para integrações |
| Webhook Handler | `core/gateway/adapters.py` | Adaptadores para webhooks |

### 2. Orquestração Layer

**Responsabilidade:** Fluxo de decisão e processamento

| Componente | Localização | Descrição |
|------------|-------------|-----------|
| LangGraph | `core/vps_langgraph/graph.py` | Grafo de estado do agente |
| Nodes | `core/vps_langgraph/nodes.py` | Nós de processamento |
| State | `core/vps_langgraph/state.py` | Definição de estado |
| Intent Classifier | `core/vps_langgraph/intent_classifier.py` | Classificação de intenções |

### 3. Serviços Core

**Responsabilidade:** Lógica de negócio e capacidades

| Componente | Localização | Descrição |
|------------|-------------|-----------|
| VPS Agent | `core/vps_agent/agent.py` | Agente principal |
| Semantic Memory | `core/vps_agent/semantic_memory.py` | Memória vetorial |
| Capabilities | `core/capabilities/registry.py` | Registro de capacidades |
| Resource Manager | `core/resource_manager/manager.py` | Gerenciamento de recursos |

### 4. Infraestrutura Layer

**Responsabilidade:** Persistência, segurança e resiliência

| Componente | Localização | Descrição |
|------------|-------------|-----------|
| Agent Memory | `core/vps_langgraph/memory.py` | Persistência PostgreSQL |
| Allowlist | `core/security/allowlist.py` | Segurança de comandos |
| Circuit Breaker | `core/resilience/circuit_breaker.py` | Resiliência |
| Rate Limiter | `core/gateway/rate_limiter.py` | Limitação de taxa |
| Session Manager | `core/gateway/session_manager.py` | Gestão de sessões |

### 5. LLM Layer

**Responsabilidade:** Abstração de modelos de linguagem

| Componente | Localização | Descrição |
|------------|-------------|-----------|
| LLM Provider | `core/llm/provider.py` | Interface unificada LLM |
| OpenRouter Client | `core/llm/openrouter_client.py` | Cliente OpenRouter |
| Prompt Composer | `core/llm/prompt_composer.py` | Composição de prompts |
| Agent Identity | `core/llm/agent_identity.py` | Personalidade do agente |

## Fluxo de Processamento

### Fluxo Principal (Mensagem)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Usuário   │────►│  Telegram   │────►│  Telegram   │
│  (Mensagem) │     │    Bot      │     │   Handler   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                                                ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Resposta  │◄────│   Agent     │◄────│   Gateway   │
│  (Formatada)│     │   Graph     │     │  (process)  │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ Intent  │  │  Plan   │  │ Execute │
        │Classify │  │         │  │         │
        └─────────┘  └─────────┘  └─────────┘
```

### Grafo LangGraph (Detalhado)

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
              ┌────│  classify   │────┐
              │    │   intent    │    │
              │    └─────────────┘    │
              │           │           │
              │           ▼           │
              │    ┌─────────────┐    │
              │    │load_context │    │
              │    └──────┬──────┘    │
              │           │           │
              │           ▼           │
              │    ┌─────────────┐    │
              └────│    plan     │────┘
                   └──────┬──────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        ┌─────────┐ ┌─────────┐ ┌─────────┐
        │ command │ │  task   │ │  chat   │
        │  ─────► │ │  ─────► │ │  ─────► │
        │ execute │ │ execute │ │ respond │
        └────┬────┘ └────┬────┘ └────┬────┘
             │           │           │
             └───────────┼───────────┘
                         ▼
                  ┌─────────────┐
                  │save_memory  │
                  └──────┬──────┘
                         │
                         ▼
                       [END]
```

## Gerenciamento de Estado

### State Definition (AgentState)

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str
    intent_confidence: float
    context: dict
    plan: list
    execution_result: dict
    response: str
    session_id: str
    user_id: str
    metadata: dict
```

### Persistência

| Tipo | Tecnologia | Caso de Uso |
|------|------------|-------------|
| Estruturada | PostgreSQL | Conversas, metadados, estado |
| Cache | Redis | Sessões, rate limits, tokens |
| Vetorial | Qdrant | Memória semântica, embeddings |
| Arquivos | Local | Logs, backups, configurações |

## Segurança

### Allowlist de Comandos

O sistema implementa uma camada de segurança via allowlist:

```python
# Regras padrão
- ALLOW: docker ps, stats, logs, inspect
- ALLOW: free -m, df -h, uptime, whoami
- REQUIRE_APPROVAL: docker start/stop/restart
- DENY: rm -rf, dd, mkfs, fork bombs
```

### Autenticação

| Camada | Mecanismo | Status |
|--------|-----------|--------|
| Telegram | Bot Token + User ID whitelist | ✅ Implementado |
| Gateway | API Key (env var) | 🔄 Em progresso |
| Internal | Service-to-service trust | ✅ Implementado |

## Resiliência

### Circuit Breaker

```python
 Estados:
 CLOSED  ──► OPEN (após N falhas)
    ▲           │
    │           ▼
    └────── HALF_OPEN (retry)
```

### Rate Limiting

- Per-user: 60 req/min
- Per-endpoint: Configurável
- Global: Proteção contra DDoS

## Recursos e Limites

### Memória (2.4 GB Total)

| Categoria | Serviços | Limite |
|-----------|----------|--------|
| Sempre ON | PSQL, Redis, Core | ~750 MB |
| Sob demanda | Qdrant, n8n | ~1.5 GB |
| Máximo | - | 2.4 GB (hard limit) |

### Concorrência

- Max workers: 4 (CPU-bound)
- Async tasks: ilimitado (IO-bound)
- Docker containers simultâneos: 2

## Configuração do Pacote

O projeto usa `pyproject.toml` como pacote Python profissional:

```toml
[project]
name = "vps-agent"
version = "2.0.0"
requires-python = ">=3.11"

[project.scripts]
vps-agent = "telegram_bot.bot:main"
vps-mcp = "core.mcp_server:main"
vps-gateway = "core.gateway.main:run_server"
```

Instalação:
```bash
pip install -e ".[dev]"
```

## Decisões de Arquitetura (ADRs)

Consulte o diretório `docs/adr/` para decisões documentadas:

- [ADR-001: Estratégia de Memória](adr/001-memory-strategy.md)
- [ADR-002: Abstração LLM](adr/002-llm-abstraction.md)

## Evolução Planejada

| Fase | Foco | Componentes |
|------|------|-------------|
| 1.1 | Async | Connection pooling, asyncpg |
| 1.2 | Segurança | Allowlist no grafo |
| 1.3 | Auth | Gateway API key real |
| 2.0 | Modernização | LangGraph moderno, tool use |

## Autonomous Engine (Sprint 02)

O **Autonomous Engine** implementa o ciclo de 6 passos para automação autônoma:

### 6-Step Blueprint

```mermaid
DETECT → PROPOSE → FILTER → EXECUTE → COMPLETE → RE-TRIGGER
```

| Passo | Descrição | Componente |
|-------|-----------|-------------|
| DETECT | Monitora condições do sistema | Triggers (RAM, erro, schedule) |
| PROPOSE | Cria proposal no PostgreSQL | `create_proposal()` |
| FILTER | Verifica recursos/segurança | Cap Gates |
| EXECUTE | Executa via Skill Registry | `_execute_mission()` |
| COMPLETE | Emite resultado | `agent_missions` table |
| RE-TRIGGER | Gera novas proposals | Event loop |

### Cap Gates

Verificações de segurança antes de executar:

```python
class CapGate:
    check_rate_limit()    # max 10 proposals/hora
    check_ram_threshold()  # min 200MB RAM livre
    check_security_level() # ações perigosas requerem aprovação
```

### Tabelas PostgreSQL

- `agent_proposals`: Ações sugeridas pelo agente
- `agent_missions`: Execução de proposals
- `agent_policies`: Regras de governança

### Triggers Autônomos

| Trigger | Condição | Ação |
|---------|----------|------|
| `ram_high` | RAM > 80% | Limpar containers inativos |
| `error_repeated` | >3 erros/hora | Investigar erros |
| `schedule_due` | Tarefa pendente | Executar tarefa |
| `health_check` | A cada 60s | Verificar containers |

## ReAct Node (Sprint 02)

O **ReAct Node** permite que o agente use tools via LLM:

```python
# Fluxo ReAct
1. LLM analiza mensagem → tool_call
2. Skill Registry executa tool
3. LLM gera resposta final
```

### Tool Schemas

Todas as skills expõem schemas OpenAI-compatible:

```python
# Exemplo: shell_exec
{
    "type": "function",
    "function": {
        "name": "shell_exec",
        "description": "Executa comando shell",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"}
            }
        }
    }
}
```

## Skills System (Sprint 02)

Sistema de plugins para capacidades do agente:

### Built-in Skills

| Skill | Descrição | Handler |
|-------|-----------|---------|
| `shell_exec` | Executa comandos shell | `core/skills/_builtin/shell_exec/` |
| `get_ram` | Consulta memória RAM | `core/skills/_builtin/ram/` |
| `list_containers` | Lista Docker containers | `core/skills/_builtin/containers/` |
| `get_system_status` | Status geral | `core/skills/_builtin/system_status/` |
| `check_postgres` | Health PostgreSQL | `core/skills/_builtin/check_postgres/` |
| `check_redis` | Health Redis | `core/skills/_builtin/check_redis/` |
| `file_manager` | Operações arquivo | `core/skills/_builtin/file_manager/` |
| `memory_query` | Consulta memória | `core/skills/_builtin/memory_query/` |
| `web_search` | Pesquisa web | `core/skills/_builtin/web_search/` |
| `self_edit` | Auto-edição | `core/skills/_builtin/self_edit/` |

### Skill Registry

Padrão registry para descoberta dinâmica:

```python
registry = get_skill_registry()
schemas = registry.list_tool_schemas()
result = await registry.execute_skill("shell_exec", {"command": "ls"})
```

## Referências

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
