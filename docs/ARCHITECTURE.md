# Arquitetura do VPS-Agent v3

## Visao Geral

O VPS-Agent eh um agente autonomo que roda em uma VPS com recursos limitados (2.4 GB RAM). Usa LangGraph para orquestracao, ReAct pattern com function calling para decisoes inteligentes, e um hook system para extensibilidade.

## Grafo LangGraph (7 nos)

```
                    START
                      |
                      v
                load_context        -- Carrega historico e fatos do usuario
                      |
                      v
                    react           -- LLM com function calling decide:
                   /     \             tool_call → security_check
                  /       \            text → respond (resposta direta)
                 v         v
          security_check  respond   -- Verifica allowlist
                |            |
                v            v
             execute     save_memory -- Executa skill via registry + hooks
                |
                v
          format_response           -- LLM formata resultado para usuario
                |
                v
              respond               -- Gera resposta final
                |
                v
           save_memory              -- Persiste contexto
                |
                v
               END
```

## Camadas

### 1. Interface Layer

| Componente | Localizacao | Descricao |
|---|---|---|
| Telegram Bot | `telegram_bot/bot.py` | Interface via Telegram + approval commands |
| Gateway HTTP | `core/gateway/main.py` | API REST |
| MCP Server | `core/mcp_sse.py` | Model Context Protocol (SSE + WebSocket) |

### 2. Orquestracao Layer (ReAct)

| Componente | Localizacao | Descricao |
|---|---|---|
| Graph | `core/vps_langgraph/graph.py` | Grafo de 7 nos |
| React Node | `core/vps_langgraph/react_node.py` | LLM com function calling |
| Nodes | `core/vps_langgraph/nodes.py` | load_context, security_check, execute, respond, save_memory |
| State | `core/vps_langgraph/state.py` | AgentState TypedDict |

### 3. Skill Registry

| Componente | Localizacao | Descricao |
|---|---|---|
| Registry | `core/skills/registry.py` | Auto-discovery de skills por config.yaml |
| Skills | `core/skills/*/handler.py` | Funcoes puras: recebem args, retornam output |
| Tool Schemas | `registry.list_tool_schemas()` | JSON Schema para function calling |

Skills disponiveis: shell_exec, get_ram, list_containers, get_system_status, check_postgres, check_redis, file_manager, memory_query, web_search, self_edit.

### 4. Hook System

| Componente | Localizacao | Descricao |
|---|---|---|
| HookRunner | `core/hooks/runner.py` | Pre/post hooks para skill execution |
| logging_hook | builtin | Logging estruturado com duracao |
| feedback_pre_hook | builtin | Consulta learnings antes de executar |
| learning_hook | builtin | Registra erros no PostgreSQL |

### 5. Autonomous Loop

| Componente | Localizacao | Descricao |
|---|---|---|
| Engine | `core/autonomous/engine.py` | Loop com 6 triggers |
| Cap Gates | `core/autonomous/engine.py` | Rate limit, RAM threshold, security level |
| Proposals | PostgreSQL `agent_proposals` | Proposals persistidas com approval workflow |
| Missions | PostgreSQL `agent_missions` | Execucoes rastreadas |

Blueprint: DETECT → PROPOSE → FILTER (Cap Gates) → EXECUTE → COMPLETE → RE-TRIGGER

### 6. LLM Layer

| Componente | Localizacao | Descricao |
|---|---|---|
| Provider | `core/llm/provider.py` | Interface unificada LLM |
| OpenRouter | `core/llm/openrouter_client.py` | Cliente OpenRouter (Gemini 2.5 Flash Lite) |

### 7. Seguranca

| Componente | Localizacao | Descricao |
|---|---|---|
| Allowlist | `core/security/allowlist.py` | Whitelist de comandos permitidos |
| Cap Gates | `core/autonomous/engine.py` | Rate limit + RAM + security level |
| Telegram Approval | `telegram_bot/bot.py` | /approve, /reject para proposals DANGEROUS |

## Fluxo de Dados

```
Usuario (Telegram)
    |
    v
bot.py → process_message_async()
    |
    v
agent.py → graph.ainvoke(initial_state)
    |
    v
load_context → react (LLM + tools) → security_check → execute (+ hooks) → format_response → respond → save_memory
    |                                                                                                      |
    v                                                                                                      v
PostgreSQL (memoria, learnings, proposals)                                                           Redis (cache)
```

## Metricas (Sprint 03)

- Nos no grafo: 7 (era 10)
- Chamadas LLM por mensagem: 2 (decidir + responder)
- Blocos if/elif no shell_exec: 21 (era 35, restantes sao security classification)
- API keys no codigo: 0
- Dead code removido: ~600 linhas
- Hook system: 3 hooks builtin
- Triggers com condicoes reais: 6/6
