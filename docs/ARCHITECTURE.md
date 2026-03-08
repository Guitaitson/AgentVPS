# Arquitetura do AgentVPS — Sprint 09

## Visão Geral

AgentVPS é um agente autônomo que roda em VPS com recursos limitados (~2 GB RAM). Usa LangGraph para orquestração, padrão ReAct com function calling real para decisões inteligentes, e se integra ao OpenClaw para delegação de sub-tarefas.

```
Usuário (Telegram)
       │
       ▼
  AgentVPS (Python / LangGraph)
       │
       ├── PostgreSQL  — memória estruturada, learnings, proposals
       ├── Redis       — cache e filas
       │
       └── OpenClaw (Node.js, docker exec) — sub-agente opcional
```

---

## Grafo LangGraph (7 nós)

```
START
  │
  ▼
load_context ──── Carrega histórico e fatos do usuário (PostgreSQL)
  │
  ▼
react ──────────── LLM com function calling decide:
  │                  tool_call → security_check
  │                  resposta direta → respond
  ├──────────────┐
  ▼              ▼
security_check  respond ──── Resposta direta ao usuário
  │
  ▼
execute ─────────── Executa skill via registry + hook system
  │
  ▼
format_response ─── LLM formata resultado em linguagem natural
  │
  ▼
respond
  │
  ▼
save_memory ──────── Persiste contexto no PostgreSQL
  │
  ▼
END
```

---

## Camadas

### 1. Interface Layer

| Componente | Localização | Descrição |
|---|---|---|
| Telegram Bot | `telegram_bot/bot.py` | Interface principal + `/approve`, `/reject`, `/proposals` |
| Gateway HTTP | `core/gateway/main.py` | API REST FastAPI |
| MCP Server | `core/mcp_server.py` | Model Context Protocol (SSE + WebSocket) |

### 2. Orquestração Layer (ReAct)

| Componente | Localização | Descrição |
|---|---|---|
| Graph | `core/vps_langgraph/graph.py` | Definição do grafo de 7 nós |
| React Node | `core/vps_langgraph/react_node.py` | LLM com function calling (ReAct) |
| Nodes | `core/vps_langgraph/nodes.py` | load_context, security_check, execute, respond, save_memory |
| State | `core/vps_langgraph/state.py` | `AgentState` TypedDict |

### 3. Skill Registry

| Componente | Localização | Descrição |
|---|---|---|
| Registry | `core/skills/registry.py` | Auto-discovery via `config.yaml + handler.py` |
| Base | `core/skills/base.py` | `SkillBase` — interface que todas as skills implementam |
| Tool Schemas | `registry.list_tool_schemas()` | JSON Schema para function calling |

**Skills disponíveis (13):**

| Skill | Nível | Descrição |
|-------|-------|-----------|
| `shell_exec` | dangerous | Executa comandos shell na VPS |
| `get_ram` | safe | Uso de memória RAM |
| `list_containers` | safe | Lista containers Docker |
| `get_system_status` | safe | Status geral do sistema |
| `check_postgres` | safe | Health do PostgreSQL |
| `check_redis` | safe | Health do Redis |
| `file_manager` | normal | Lê e escreve arquivos |
| `memory_query` | safe | Consulta memória persistida (PostgreSQL) |
| `web_search` | normal | Busca web (DuckDuckGo fallback) |
| `fleetintel` | normal | Consulta eventos e dados de frota via FleetIntel MCP |
| `self_edit` | dangerous | Auto-edição de código da VPS |
| `log_reader` | safe | Leitura de logs da VPS |
| `openclaw_exec` | dangerous | Controla OpenClaw via docker exec |

Skills `dangerous` passam por Tool Policy Engine e requerem aprovação humana (`on-dangerous`).

### 4. Hook System

| Componente | Localização | Descrição |
|---|---|---|
| HookRunner | `core/hooks/runner.py` | Executa hooks pre/post para cada skill |
| `logging_hook` | builtin | Structured logging com duração de execução |
| `feedback_pre_hook` | builtin | Consulta learnings antes de executar |
| `learning_hook` | builtin | Registra erros no PostgreSQL para aprendizado |

### 5. Autonomous Loop

| Componente | Localização | Descrição |
|---|---|---|
| Engine | `core/autonomous/engine.py` | Loop com 6 triggers com condições reais |
| Cap Gates | `core/autonomous/engine.py` | Rate limit, RAM threshold, security level |
| Proposals | PostgreSQL `agent_proposals` | Proposals persistidas com approval workflow |
| Missions | PostgreSQL `agent_missions` | Execuções rastreadas |

**Blueprint:** DETECT → PROPOSE → FILTER (Cap Gates) → APPROVE (Telegram) → EXECUTE → COMPLETE

### 6. LLM Layer

| Componente | Localização | Descrição |
|---|---|---|
| Provider | `core/llm/provider.py` | Interface unificada |
| OpenRouter | `core/llm/openrouter_client.py` | Cliente OpenRouter |
| Modelo padrão | `OPENROUTER_MODEL` env | `minimax/minimax-m2.5` |

### 7. Segurança

| Componente | Localização | Descrição |
|---|---|---|
| Allowlist | `core/security/allowlist.py` | Whitelist de comandos permitidos |
| Cap Gates | `core/autonomous/engine.py` | Rate limit + RAM + security level |
| Telegram Approval | `telegram_bot/bot.py` | `/approve`, `/reject` para proposals DANGEROUS |
| Anti-injection | `core/skills/_builtin/openclaw_exec/handler.py` | Output externo marcado como não-confiável |

---

## Integração OpenClaw

OpenClaw é um app Node.js rodando no container `repo-openclaw-gateway-1`, **separado** do AgentVPS.

```
AgentVPS (vps-core-network: 172.28.0.0/16)
    │
    │  [skill openclaw_exec]
    │  docker exec repo-openclaw-gateway-1 node /app/dist/entry.js <cmd>
    ▼
OpenClaw (repo_default: 172.18.0.0/16)
    │
    └── Gateway WebSocket: ws://127.0.0.1:18789
```

**Modelo de segurança — unidirecional por design:**
- AgentVPS → OpenClaw: sim (via skill `openclaw_exec`)
- OpenClaw → AgentVPS: **NÃO** (redes separadas, sem credenciais cruzadas)

**Comandos disponíveis:**

| Ação | Comando interno |
|------|----------------|
| `health` | `gateway health` |
| `status` | `gateway status --json` |
| `agent` | `agent --message "..." --json` |
| `agents` | `agents list` |
| `channels` | `channels status` |
| `approvals` | `approvals list` |

---

## Fluxo de Dados

```
Usuário (Telegram)
    │
    ▼
bot.py → process_message_async()
    │
    ▼
agent.py → graph.ainvoke(initial_state)
    │
    ▼
load_context → react (LLM + tools) → security_check → execute (+ hooks) → format_response → respond → save_memory
    │                                                        │                                              │
    ▼                                                        ▼                                              ▼
PostgreSQL                                         Skill (ex: openclaw_exec)                          Redis (cache)
(memória, learnings, proposals)                    [DADO EXTERNO — tag anti-injection]
```

---

## Banco de Dados (PostgreSQL)

Tabelas principais:

| Tabela | Descrição |
|--------|-----------|
| `agent_memory` | Fatos e contexto por usuário |
| `agent_conversations` | Histórico de conversas |
| `agent_learnings` | Erros e aprendizados |
| `agent_proposals` | Proposals autônomas + status |
| `agent_missions` | Execuções rastreadas |

Schema: `configs/init-db.sql` + `configs/migration-autonomous.sql`

---

## Métricas (Sprint 09)

| Métrica | Valor |
|---------|-------|
| Nós no grafo | 7 (era 10) |
| Chamadas LLM por mensagem | 1-2 (decidir + opcionalmente formatar) |
| Skills disponíveis | 13 |
| Dead code removido (Sprint 03) | ~600 linhas |
| Hook system builtin | 3 hooks |
| Triggers autônomos com condições reais | 6/6 |
| API keys hardcoded no código | 0 |
| Redes Docker isoladas | 2 (vps-core-network / repo_default) |

---

## Deploy na VPS (Produção)

| Item | Valor |
|------|-------|
| Diretório app | `/opt/vps-agent/` |
| Python venv | `/opt/vps-agent/core/venv/` |
| Env file | `/opt/vps-agent/.env` |
| Serviço 1 | `telegram-bot.service` (systemd) |
| Serviço 2 | `mcp-server.service` (systemd) |
| PostgreSQL | container `vps-postgres` (172.28.x.x) |
| Redis | container `vps-redis` (172.28.x.x) |
| Logs | `/opt/vps-agent/logs/telegram-bot.log` |
