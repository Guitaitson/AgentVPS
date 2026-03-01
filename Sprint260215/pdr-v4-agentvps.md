# PDR v4 — Project Decision Record — AgentVPS

> Registro de decisoes estrategicas do projeto. Inclui PDR-001 a PDR-005 (Sprint 02) + novas decisoes PDR-006 a PDR-009 (Sprint 03).

---

## Indice de Decisoes

| # | Decisao | Data | Status |
|---|---|---|---|
| PDR-001 | Continuar AgentVPS (vs OpenClaw) | 08/02/26 | MANTIDA |
| PDR-002 | ReAct com Function Calling | 15/02/26 | APROVADA — implementada mas NAO integrada |
| PDR-003 | PostgreSQL para Autonomous Loop | 15/02/26 | APROVADA — migration criada |
| PDR-004 | Skills como funcoes puras | 15/02/26 | APROVADA — shell_exec purificado |
| PDR-005 | Stack tecnologica | 15/02/26 | CONFIRMADA |
| PDR-006 | Integrar react_node no graph.py | 15/02/26 | **NOVA — URGENTE** |
| PDR-007 | Adotar patterns seletivos do OpenClaw | 15/02/26 | **NOVA** |
| PDR-008 | Autonomia deliberativa vs cronica | 15/02/26 | **NOVA** |
| PDR-009 | SQLite-vec vs Qdrant para memoria semantica | 15/02/26 | **NOVA** |

---

## PDR-001 a PDR-005

Mantidos conforme `pdr-agentvps.md` (v3). Nenhuma revisao necessaria.

---

## PDR-006: Integrar react_node no graph.py

**Data:** 15 Fev 2026
**Status:** APROVADA — URGENTE
**Prioridade:** P0 (bloqueante)

### Contexto

O Sprint 02 construiu o `react_node.py` (163 linhas) com function calling, `node_format_response`, e `route_after_react`. Testes foram escritos (20 formulacoes). O shell_exec foi purificado para receber argumentos estruturados.

Porem, `graph.py` nao foi modificado. O grafo continua com 10 nos usando o fluxo antigo (`classify_intent` -> `plan` -> `execute` com heuristicas). O react_node nao eh importado nem referenciado.

### Alternativas

| Alternativa | Pros | Contras |
|---|---|---|
| **Substituir grafo inteiro por react** | Simples, elimina toda a complexidade antiga | Perde check_capabilities e self_improve |
| **Adicionar react como branch condicional** | Coexistencia — pode fazer A/B test | Complexidade dobra, 2 caminhos de execucao |
| **Substituir classify+plan por react, manter self_improve** | Melhor dos mundos: inteligencia ativa + self_improve futuro | Precisa adaptar self_improve para novo state |

### Decisao

**Substituir classify+plan por react, manter self_improve como branch futuro (desabilitado por enquanto).**

Novo grafo:
```
load_context -> react -> [security_check -> execute -> format_response] -> respond -> save_memory
                    \-> respond (se chat direto)
```

Self_improve e check_capabilities ficam como nos dormentes que podem ser reativados quando a auto-melhoria for implementada.

### Razoes

1. O react_node ja esta escrito e testado. Nao integra-lo eh desperdicio.
2. classify + plan sao redundantes quando o LLM faz function calling.
3. ~30 linhas de mudanca em graph.py para ganho transformacional.
4. Self_improve nao funciona hoje — nao ha perda em desabilita-lo temporariamente.

---

## PDR-007: Adotar Patterns Seletivos do OpenClaw

**Data:** 15 Fev 2026
**Status:** APROVADA

### Contexto

O OpenClaw (180k+ stars, Node.js) implementa patterns maduros que o AgentVPS pode adotar. A analise do repositorio identificou 6 patterns relevantes. Nem todos fazem sentido para um projeto solo com 2.4GB RAM.

### Patterns Selecionados

| # | Pattern | Origem OpenClaw | Adaptacao AgentVPS | Prioridade |
|---|---|---|---|---|
| 1 | **Hook System** | `hook-runner-global.ts`, `hooks.ts` | `core/hooks/runner.py` — pre_execute/post_execute para cada skill | P1 |
| 2 | **Tool Policy Layers** | `tool-policy.ts` — profiles minimal/coding/full | Evoluir SecurityLevel para ToolPolicy com contexto (quem, canal, historico) | P2 |
| 3 | **SQLite-vec** | `sqlite.ts`, `sqlite-vec.ts` — embeddings locais | Substituir Qdrant (500MB RAM) por sqlite-vec (~5MB) | P2 |
| 4 | **Manifest Validation** | `schema-validator.ts`, `config-schema.ts` | Adicionar JSON schema validation nos config.yaml do registry | P3 |
| 5 | **Skill Refresh** | `refresh.ts` — hot reload | Adicionar `registry.reload()` sem restart | P3 |
| 6 | **Session Routing** | `resolve-route.ts`, `session-key.ts` | Futuro: multi-canal com state isolado | P4 |

### Patterns Rejeitados

| Pattern | Razao |
|---|---|
| ClawHub marketplace | 11.7% skills maliciosos — supply chain risk |
| Multi-provider failover | Complexidade desnecessaria |
| Browser control | Fora do escopo VPS management |
| Voice wake/PTT | Desktop feature, irrelevante para VPS |

### Decisao

Adotar patterns 1-3 no Sprint 03. Patterns 4-5 no Sprint 04. Pattern 6 quando necessario.

---

## PDR-008: Autonomia Deliberativa vs Cronica

**Data:** 15 Fev 2026
**Status:** APROVADA

### Contexto

O engine.py atual implementa triggers cronicos: funcoes que rodam em intervalos fixos (60s, 300s, 3600s). 4 de 6 triggers tem `condition: lambda: True` (sempre disparam). Isso eh um scheduler, nao um agente autonomo.

### Alternativas

| Alternativa | Pros | Contras |
|---|---|---|
| **Manter cron triggers** | Simples, previsivel | Nao eh autonomia. Nao toma decisoes. |
| **Goal-oriented deliberation** | Agente real: observa, compara com goals, propoe acoes | Mais complexo. Precisa de goal definition. |
| **Event-driven reactive** | Responde a eventos (webhook, erro, threshold) | Reativo, nao proativo. Nao planeja. |
| **Hibrido: cron + goals + events** | Cobertura completa | Mais complexo de implementar |

### Decisao

**Hibrido em 3 fases:**

1. **Fase 1 (Sprint 03):** Manter cron para health/cleanup + adicionar event-driven (threshold triggers com condicoes reais).
2. **Fase 2 (Sprint 04):** Adicionar goals definidos pelo usuario ("mantenha containers criticos running").
3. **Fase 3 (Sprint 05):** LLM gera proposals baseado em observacao do estado vs goals.

### Razoes

1. Goals sem function calling ativo nao fazem sentido — first things first (PDR-006).
2. Event-driven eh o proximo passo logico: triggers com condicoes reais em vez de lambda: True.
3. Full deliberation requer LLM no loop autonomo — custo de tokens precisa ser avaliado.

---

## PDR-009: SQLite-vec vs Qdrant para Memoria Semantica

**Data:** 15 Fev 2026
**Status:** APROVADA

### Contexto

O plano original usa Qdrant para busca semantica. Qdrant consome 500MB+ de RAM (on-demand). A VPS tem 2.4GB total. O OpenClaw usa SQLite-vec com embeddings multi-provider (OpenAI, Gemini, Voyage) batched.

### Comparacao

| Aspecto | Qdrant | SQLite-vec |
|---|---|---|
| RAM | 500MB+ | ~5MB |
| Servidor separado | Sim (Docker) | Nao (in-process) |
| Performance | Alta (milhoes de vetores) | Boa (milhares de vetores) |
| Setup | Docker + config | pip install sqlite-vec |
| Scale necessario | Milhares no maximo | Milhares (suficiente) |
| Backup | Export/restore separado | Arquivo .db (cp) |

### Decisao

**SQLite-vec** para embeddings locais. Qdrant fica como opcao futura se escalar alem de 100k vetores.

### Razoes

1. 500MB para Qdrant eh 21% do RAM total da VPS. Inaceitavel como sempre-on.
2. O AgentVPS vai armazenar milhares de embeddings, nao milhoes. SQLite-vec suficiente.
3. Backup trivial (arquivo .db). Qdrant requer export/restore.
4. OpenClaw validou o pattern em producao com 180k+ usuarios.
