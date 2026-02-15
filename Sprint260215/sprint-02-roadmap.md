# 📋 Sprint 02 Roadmap — De Botões Para Inteligência

## Visão Geral

| Fase | Nome | Jobs | Horas | Semana | Entrega |
|------|------|------|-------|--------|---------|
| **T1** | Segurança Urgente | 2 | ~2h | Dia 1 | API key removida, debug log removido |
| **T2** | ReAct + Function Calling | 3 | ~24h | Semana 1 | Agente que PENSA |
| **T3** | Skill Purification | 2 | ~8h | Semana 2 | Skills como funções puras |
| **T4** | Autonomous Blueprint Real | 3 | ~16h | Semana 2-3 | Proposals + Cap Gates + Events |
| **T5** | Cleanup Final | 2 | ~4h | Paralelo | Código morto eliminado, docs curadas |
| **TOTAL** | | **12 jobs** | **~54h** | **3 semanas** | |

---

## T1 — Segurança Urgente (Dia 1, 2h)

> **Fazer ANTES de qualquer outra coisa.**

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T1-01 | **Revogar e remover API key** — Remover `BSA1oVa6QVwZf5E3lCRo1h19cmY9Ywo` de web_search/handler.py. Revogar no Brave Dashboard. Gerar nova key. Auditar TODO o código por outros segredos (`grep -r "key\|token\|password\|secret" --include="*.py"`). | 1h | Zero secrets no código |
| T1-02 | **Remover debug log** — Eliminar 3 ocorrências de `open("/tmp/security_debug.log")` em nodes.py. Substituir por structlog.debug() que já existe e é configurável. | 1h | Zero file writes no fluxo principal |

### Milestone T1: "Seguro"
```
✅ grep -r "BSA1" core/ retorna 0
✅ grep -r "/tmp/security_debug" core/ retorna 0
✅ git diff mostra remoções, não adições
```

---

## T2 — ReAct + Function Calling (Semana 1, 24h)

> **A transformação fundamental. O agente passa de string matching para raciocínio.**

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T2-01 | **Definir Tool Schemas** — Converter cada skill do registry em um tool schema compatível com function calling. Cada tool tem: name, description, parameters (JSON Schema). O registry expõe `list_tool_schemas()` que retorna a lista formatada para o LLM. | 6h | `registry.list_tool_schemas()` funcional |
| T2-02 | **Implementar ReAct Node** — Criar `node_react` que substitui `node_classify_intent` + `node_plan` + `node_execute`. O nó envia a mensagem ao LLM COM a lista de tools. O LLM responde com `tool_call` ou `text`. Se tool_call: executa via registry → retorna resultado ao LLM → LLM gera resposta final. Se text: responde diretamente. | 12h | Grafo simplificado funcional |
| T2-03 | **Testes do ReAct** — Testar 20 formulações diferentes da mesma pergunta. Verificar que todas produzem a mesma ação. Comparar latência e custo com sistema anterior. | 6h | 20/20 formulações funcionando |

### Milestone T2: "Agente Inteligente"
```
✅ "tem o docker?" → shell_exec(command="which docker") → resposta natural
✅ "docker tá instalado?" → shell_exec(command="which docker") → mesma resposta
✅ "o docker está na máquina?" → shell_exec(command="which docker") → mesma resposta
✅ "quanta memória RAM livre?" → get_ram() → resposta natural
✅ "como está a memória do servidor?" → get_ram() → resposta natural
✅ "busque sobre LangGraph" → web_search(query="LangGraph") → resultados formatados
✅ Nenhum bloco if/elif de interpretação nos skills
✅ Custo LLM por mensagem ≤ custo anterior
```

### Grafo Antes vs Depois

```
ANTES (10 nós):
classify → load_context → plan → security_check → execute → respond → save_memory
                                                                   ↗
                                   check_capabilities → self_improve ─┘

DEPOIS (6 nós):
load_context → react → security_check → execute_tool → respond → save_memory
              (LLM decide tool)   (se tool perigosa)  (skill puro)  (LLM formata)
```

O `react` node encapsula classify + plan + decisão de tool em uma única chamada LLM com function calling. O LLM retorna `{tool: "shell_exec", args: {command: "which docker"}}` ou responde diretamente.

---

## T3 — Skill Purification (Semana 2, 8h)

> **Skills viram funções puras: recebem parâmetros estruturados, retornam output raw.**

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T3-01 | **Purificar shell_exec** — Remover `_interpret_and_generate_command` (100+ linhas de heurísticas). Remover 15 blocos if/elif de formatação. Handler fica: `classify_command(cmd) → check security → subprocess → return raw output`. De 397 para ~70 linhas. | 4h | shell_exec < 80 linhas |
| T3-02 | **Purificar demais skills** — Remover parsing de `raw_input` dos handlers (file_manager, web_search, memory_query). Cada handler recebe args estruturados do function calling, não texto livre. | 4h | Cada handler < 100 linhas |

### Milestone T3: "Skills Puros"
```
✅ shell_exec/handler.py < 80 linhas
✅ Nenhum skill importa unified_provider (não faz chamada LLM própria)
✅ Nenhum skill tem bloco "if X in raw_input.lower()"
✅ Cada skill recebe args tipados (command: str, path: str, query: str)
```

---

## T4 — Autonomous Blueprint Real (Semana 2-3, 16h)

> **O agente propõe ações, verifica limites, executa, e re-trigera.**

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T4-01 | **Schema PostgreSQL** — Criar migration com tabelas `agent_proposals`, `agent_missions`, `agent_policies`. Inserir policies iniciais. Migration idempotente. | 4h | `configs/migration-v2.sql` aplicada |
| T4-02 | **Refatorar engine.py** — Substituir triggers simples por ciclo real: `detect → propose (INSERT INTO agent_proposals) → cap_gate_check (SELECT FROM agent_policies) → execute (via Skill Registry) → complete (UPDATE + emit event)`. Proposals persistem no PostgreSQL, não Redis efêmero. | 8h | engine.py com 6 passos reais |
| T4-03 | **Cap Gates + Notificação** — Implementar 3 gates: (1) RAM disponível > 200MB, (2) proposals/hora < 10, (3) security level do skill ≠ DANGEROUS sem approval. Proposals DANGEROUS geram mensagem Telegram com botões Sim/Não. | 4h | Cap gates funcionais + approval Telegram |

### Milestone T4: "Autonomous Agent"
```
✅ RAM > 80% → INSERT INTO agent_proposals → cap gate → notifica Telegram
✅ Telegram: "🔔 RAM alta (82%). Limpar containers inativos? [Sim/Não]"
✅ Usuário clica Sim → INSERT INTO agent_missions → executa → UPDATE completed
✅ SELECT count(*) FROM agent_proposals retorna > 0
✅ Policy max_proposals_per_hour impede flood
```

---

## T5 — Cleanup Final (Paralelo, 4h)

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T5-01 | **Código morto** — Deletar `intent_classifier.py` (stub), `semantic_memory.py` (stub), `system_tools.py` (substituído pelo registry). Remover caractere Unicode corrompido do self_edit. Remover `AgentStateModern` não usado. | 2h | -500 linhas |
| T5-02 | **Docs curadas** — Mover planos obsoletos para `archive/`. Manter apenas: README.md, ARCHITECTURE.md, Sprint ativo, CHANGELOG.md. | 2h | docs/ limpo |

---

## Cronograma

```
Dia 1              Semana 1              Semana 2-3
│                  │                     │
├─ T1-01 API Key   ├─ T2-01 Tool Schemas  ├─ T3-01 Purify shell
├─ T1-02 Debug Log  ├─ T2-02 ReAct Node    ├─ T3-02 Purify others
│                  ├─ T2-03 Testes ReAct   ├─ T4-01 Schema
│                  │                     ├─ T4-02 Engine refactor
│                  │                     ├─ T4-03 Cap Gates
│                  │                     │
│                  │                     ├─ T5-01 Dead code
│                  │                     └─ T5-02 Docs
│                  │                     │
✓ Seguro           ✓ Agente Inteligente   ✓ Autônomo + Limpo
```

---

## Impacto nos Scores

| Dimensão | Antes (v3) | Alvo | Como |
|---|---|---|---|
| Inteligência | 2/10 | 7/10 | Function calling elimina heurísticas |
| Segurança | 5/10 | 8/10 | API key removida + cap gates |
| Funcionalidade | 5/10 | 6/10 | Mesmos skills, mas funcionam com qualquer formulação |
| Qualidade | 4/10 | 7/10 | shell_exec de 397 para 70 linhas, dead code removido |
| Autonomia | 3/10 | 6/10 | Blueprint real com proposals + cap gates + events |
| **OVERALL** | **5.0/10** | **6.8/10** | +1.8 pontos |
