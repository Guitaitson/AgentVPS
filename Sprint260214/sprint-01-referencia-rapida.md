# 📌 Referência Rápida — Mapa do Código Atual

> **Use este documento como "cola" durante a implementação. Mostra onde cada coisa está e como se conecta.**

---

## Fluxo de Uma Mensagem (Hoje)

```
Telegram → bot.py → process_message_async(user_id, msg)
                          ↓
              graph.py → build_agent_graph()
                          ↓
              classify (LLM) → intent: command|question|task|chat|self_improve
                          ↓
              load_context → PostgreSQL: agent_memory, conversation_log
                          ↓
              plan → cria lista de ações [{type, action}]
                          ↓
              route_after_plan:
                ├── command/task → security_check → execute → respond
                ├── self_improve → check_capabilities → self_improve → respond
                └── chat/question → respond (direto, usa LLM)
                          ↓
              save_memory → PostgreSQL
```

---

## Onde Cada Coisa Está

| Componente | Arquivo | Linhas | Status |
|---|---|---|---|
| Grafo LangGraph | `core/vps_langgraph/graph.py` | 164 | ✅ NÃO MEXER |
| Nós do grafo | `core/vps_langgraph/nodes.py` | 694 | ⚠️ Refatorar node_execute |
| State typedef | `core/vps_langgraph/state.py` | 116 | ⚠️ Remover AgentStateModern |
| Intent classifier (LLM) | `core/vps_langgraph/intent_classifier_llm.py` | 294 | ✅ Ativo |
| Intent classifier (regex) | `core/vps_langgraph/intent_classifier.py` | 571 | ❌ DELETAR (S3-01) |
| Smart responses | `core/vps_langgraph/smart_responses.py` | 303 | ⚠️ SKILL_GUIDE hardcoded |
| Learnings | `core/vps_langgraph/learnings.py` | 446 | ✅ Funcional |
| Error handler | `core/vps_langgraph/error_handler.py` | 415 | ✅ Funcional |
| Memory (PostgreSQL) | `core/vps_langgraph/memory.py` | 159 | ✅ Funcional |
| Tools (hardcoded) | `core/tools/system_tools.py` | 434 | ⚠️ DEPRECAR após S1 |
| Allowlist segurança | `core/security/allowlist.py` | 305 | ✅ Funcional |
| Gateway FastAPI | `core/gateway/main.py` | 312 | ✅ Funcional |
| LLM Provider | `core/llm/unified_provider.py` | 398 | ✅ Funcional |
| Telegram Bot | `telegram_bot/bot.py` | 255 | ⚠️ Convergir com gateway |
| Resource Manager | `core/resource_manager/manager.py` | 168 | ✅ Funcional |
| Health Doctor | `core/health_check/doctor.py` | 657 | ✅ Funcional |
| Self Improver | `core/self_improver.py` | 382 | ⚠️ Placeholder |
| Capabilities Registry | `core/capabilities/registry.py` | 281 | ⚠️ Substituído por Skill Registry |
| Semantic Memory (legado) | `core/vps_agent/semantic_memory.py` | 256 | ❌ DELETAR (S3-01) |
| DB Pool (asyncpg) | `core/database/pool.py` | 321 | ✅ Funcional |
| Config centralizado | `core/config.py` | 166 | ✅ Pydantic Settings |
| Circuit Breaker | `core/resilience/circuit_breaker.py` | 370 | ✅ Funcional |

---

## TOOLS_REGISTRY Atual (system_tools.py)

```python
TOOLS_REGISTRY = {
    "get_ram":            → get_ram_usage_async()
    "list_containers":    → list_docker_containers_async()
    "get_system_status":  → get_system_status_async()
    "check_postgres":     → check_postgres_async()
    "check_redis":        → check_redis_async()
}
```

Estas 5 funções serão migradas para skills em `core/skills/_builtin/`.

---

## Tabelas PostgreSQL Existentes (init-db.sql)

| Tabela | Uso | Usada por |
|---|---|---|
| `agent_memory` | Fatos por usuário (key/value JSONB) | `memory.py` |
| `system_state` | Estado de componentes | `doctor.py` |
| `conversation_log` | Histórico de conversas | `memory.py` |
| `scheduled_tasks` | Tarefas agendadas (cron) | Não integrado ainda |
| `agent_skills` | Skills aprendidos | Não integrado ainda |
| `agent_capabilities` | Capabilities catalog | `capabilities/registry.py` |
| `capability_implementations` | Histórico de implementações | `self_improver.py` |

**Tabelas que serão ADICIONADAS (S4-01):**
- `agent_proposals` — propostas do autonomous loop
- `agent_missions` — missões em execução
- `agent_policies` — políticas configuráveis

---

## Comandos Úteis

```bash
# Rodar testes
pytest tests/ -v

# Rodar linter
ruff check .
ruff format --check .

# Contar linhas
find core/ -name "*.py" -exec cat {} + | wc -l

# Ver logs do bot
journalctl -u telegram-bot -f

# Restart do bot
sudo systemctl restart telegram-bot

# Testar import do registry
python -c "from core.skills.registry import SkillRegistry; print('OK')"

# Ver containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Size}}"

# RAM
free -m

# Verificar PostgreSQL
psql -U postgres -d vps_agent -c "SELECT COUNT(*) FROM agent_memory"

# Aplicar migration
psql -U postgres -d vps_agent -f configs/migration-v2.sql
```

---

## Dependências Entre Arquivos (Para Não Quebrar)

```
bot.py ──imports──→ agent.py ──imports──→ graph.py ──imports──→ nodes.py
                                                                  ↓
                                                    system_tools.py (hoje)
                                                    skills/registry.py (depois)

allowlist.py ←──usado por──→ nodes.py (node_security_check)

memory.py ←──usado por──→ nodes.py (node_load_context, node_save_memory)

learnings.py ←──usado por──→ nodes.py (node_generate_response)

intent_classifier_llm.py ←──usado por──→ nodes.py (node_classify_intent)

unified_provider.py ←──usado por──→ openrouter_client.py ←──usado por──→ nodes.py
```

---

## Variáveis de Ambiente Necessárias

```bash
# Existentes (já configuradas)
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=vps_agent
POSTGRES_HOST=127.0.0.1
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
OPENROUTER_API_KEY=

# Novas (adicionar para S2)
BRAVE_SEARCH_API_KEY=    # Para web search (S2-03)
```
