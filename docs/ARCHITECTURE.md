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

**Skills disponiveis (19):**

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
| `fleetintel_analyst` | safe | Especialista FleetIntel para sinais, tendencias e market share |
| `brazilcnpj` | safe | Especialista BrazilCNPJ para CNPJ, socios, CNAE e grupo economico |
| `fleetintel_orchestrator` | safe | Coordena FleetIntel e BrazilCNPJ numa unica resposta |
| `self_edit` | dangerous | Auto-edição de código da VPS |
| `log_reader` | safe | Leitura de logs da VPS |
| `openclaw_exec` | dangerous | Controla OpenClaw via docker exec |
| `skills_catalog_sync` | moderate | Sync/pin/rollback/provenance do catalogo externo |
| `voice_context_sync` | moderate | Processa inbox de audio, mostra status e comita itens aprovados da captura de voz |
| `execute_scheduled` | dangerous | Executa acoes agendadas, incluindo context sync de voz |

Skills `dangerous` passam por Tool Policy Engine e requerem aprovação humana (`on-dangerous`).

Roteamento externo:
- `detect_external_skill()` decide entre `fleetintel_analyst`, `brazilcnpj` e `fleetintel_orchestrator`
- `RemoteMCPClient` encapsula autenticacao + initialize + tools/call para MCP remoto
- `configs/skills-catalog-sources.json` usa `fleetintel_skillpack_repo` como fonte primaria viva e mantem o snapshot versionado como fallback manual

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

### 5.1 Memory Core (Phase 1)

| Componente | Localização | Descrição |
|---|---|---|
| Memory Policy | `core/memory/policy.py` | Tipos de memória, TTL, retenção e redaction |
| Memory Audit | `core/memory/audit.py` | Trilha auditável de operações de memória |
| Memory Facade | `core/vps_langgraph/memory.py` | API compatível + memória tipada + fallback local |
| Migration | `configs/migration-memory-soul.sql` | `memory_audit_log` e tabelas de identidade versionada |

Tipos de memória suportados: `episodic`, `semantic`, `procedural`, `profile`, `goals`.

### 5.2 Soul Governance (Phase 1)

| Componente | Localização | Descrição |
|---|---|---|
| Soul Manager | `core/identity/soul.py` | Identidade versionada (`core_identity`, `personal_voice`, `behavior_contract`) |
| Prompt Integration | `core/llm/agent_identity.py` | Injeta artefatos da alma no prompt do agente |
| Tabelas | `agent_soul_artifacts`, `agent_soul_change_proposals` | Propostas auditáveis com aprovação/rejeição |

### 5.3 Catálogo e Atualização Contínua (Phase 1)

| Componente | Localização | Descrição |
|---|---|---|
| Sync Engine | `core/catalog/sync_engine.py` | Normaliza fontes externas e calcula diff (`check`/`apply`) |
| Updater Agent | `core/updater/agent.py` | Orquestra jobs de atualização, auto-apply com smoke e auto rollback para skills externas |
| Skill Operacional | `core/skills/_builtin/skills_catalog_sync/` | Trigger manual/on-demand para check/apply/pin/unpin/rollback/provenance |
| Trigger Autônomo | `core/autonomous/engine.py` (`catalog_sync_check`) | Check periódico estilo cron + auto-apply do catálogo vivo quando permitido |
| Tabelas | `skills_catalog`, `skills_catalog_history`, `skills_catalog_sync_runs` | Estado versionado, provenance e historico de sincronizacoes |

Modelo adotado (híbrido):
- `engine`: lógica de atualização e diff.
- `updater agent`: coordena checks e, para skills externas do FleetIntel, pode promover automaticamente após smoke.
- `skill`: execução explícita pelo operador/agente.
- `trigger`: automação periódica para detecção de updates; mappings/policies/runbooks continuam em proposal workflow.

### 5.4 Runtime Control (Phase 1)

| Componente | Localizacao | Descricao |
|---|---|---|
| Runtime Control | `core/orchestration/runtime_control.py` | Overrides de enable/disable por protocolo (MCP/A2A/ACP/DeepAgents/OpenClaw/Codex Operator) |
| Router Factory | `core/orchestration/router_factory.py` | Construcao do runtime router usando defaults + overrides persistidos |
| Comando Telegram | `telegram_bot/bot.py` (`/runtimes`) | `list`, `enable`, `disable` dos runtimes externos |

Runtime opcional `codex_operator`:
- adapter: `core/orchestration/runtime_adapters.py`
- bridge allowlisted: `core/codex_operator_bridge.py`
- uso inicial: operar `fleetintel_analyst`, `fleetintel_orchestrator` e `brazilcnpj` em consultas mais ambiguas ou multi-etapas
- isolamento: execucao do Codex em diretório temporário com `PYTHONPATH` apontando para o projeto; o runtime nao recebe workspace amplo do repositório
- soberania: memória, approvals, resposta final e policy continuam no AgentVPS

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

### 5.5 Voice Context Capture (Phase 2)

| Componente | Localizacao | Descricao |
|---|---|---|
| Voice Service | `core/voice_context/service.py` | Ingestao da inbox, deduplicacao, propostas de review e commit na memoria |
| Extractor | `core/voice_context/extraction.py` | Extracao estruturada (`summary`, `episodes`, `facts`, `preferences`, `commitments`) |
| Transcriber | `core/voice_context/transcription.py` | Transcricao local com `faster-whisper` + `ffmpeg`/`ffprobe` quando disponiveis |
| Skill Operacional | `core/skills/_builtin/voice_context_sync/` | `sync`, `status`, `commit_review_item`, `reject_review_item` |
| Telegram | `telegram_bot/bot.py` | `/contextsync [max_files]` e `/contextstatus` |
| Scheduler | `core/autonomous/engine.py` (`voice_context_batch`) | Lote diario automatico e limpeza de transcripts |
| Tabelas | `voice_ingestion_jobs`, `voice_audio_files`, `voice_context_items` | Estado operacional, arquivos, itens extraidos e ligacao logica com proposals |

Politica de commit adotada:
- `episodic` e `semantic` de baixo risco com confianca >= threshold entram direto.
- `profile`, `goals` ou dominios sensiveis (`saude_energia`, `financas`, `relacionamentos`, `valores_proposito`) viram proposal `voice_memory_commit`.
- Transcript bruto e artefato operacional curto; memoria duravel fica somente nos itens estruturados.
