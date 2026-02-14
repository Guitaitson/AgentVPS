# 📋 Sprint Roadmap — De Infraestrutura Para Capacidade

## Visão Geral

| Fase | Nome | Jobs | Horas | Semana | Entrega |
|------|------|------|-------|--------|---------|
| **S1** | Skill Registry | 3 | ~18h | Semana 1 | Skills dinâmicos, node_execute limpo |
| **S2** | 5 Skills Core | 5 | ~20h | Semana 2 | Agente útil (shell, files, web, memory, self-edit) |
| **S3** | Cleanup | 2 | ~6h | Semana 2 (paralelo) | -800 linhas de código morto |
| **S4** | Autonomous Loop | 3 | ~16h | Semana 3 | Agente proativo |
| **TOTAL** | | **13 jobs** | **~60h** | **3 semanas** | |

---

## S1 — Skill Registry (Semana 1)

> **Objetivo:** Criar sistema de skills dinâmico que substitui o TOOLS_REGISTRY hardcoded.
> **Critério de saída:** Adicionar um skill novo criando apenas 1 arquivo Python.

| # | Job | Horas | Prioridade | Entrega |
|---|-----|-------|------------|---------|
| S1-01 | **Base do Skill Registry** — Classe `SkillRegistry` com discover, register, get, list. Cada skill é um diretório em `skills/` com `handler.py` + `config.yaml`. Auto-discovery no startup. | 8h | P0 | `core/skills/registry.py` funcional |
| S1-02 | **Migrar tools existentes** — Converter as 5 tools de `system_tools.py` para o formato de skill. Refatorar `node_execute` para delegar ao registry em vez de if/elif hardcoded. | 6h | P0 | `node_execute` com <50 linhas |
| S1-03 | **Testes do Registry** — Testes de discover, register, execute. Mock skill para testes. Verificar que skills antigos continuam funcionando. | 4h | P0 | `tests/test_skill_registry.py` |

### Milestone S1: "Registry Green"
```
✅ `python -c "from core.skills.registry import SkillRegistry; r = SkillRegistry(); print(r.list_skills())"` retorna 5 skills
✅ Enviar "/ram" no Telegram → resposta via registry (não via hardcoded)
✅ `pytest tests/test_skill_registry.py` passa
```

---

## S2 — 5 Skills Core (Semana 2)

> **Objetivo:** O agente faz coisas úteis. Cada skill é um diretório isolado em `skills/`.
> **Critério de saída:** Cada skill funciona via Telegram e tem pelo menos 1 teste.

| # | Job | Horas | Prioridade | Entrega |
|---|-----|-------|------------|---------|
| S2-01 | **shell-exec** — Executa comandos shell arbitrários. Classificação de segurança: SAFE (ls, cat, df, uptime), MODERATE (apt list, pip list), DANGEROUS (rm, kill, systemctl). Dangerous requer approval via Telegram (botão Sim/Não com timeout 5min). Output truncado a 2000 chars. | 6h | P0 | `skills/shell-exec/` |
| S2-02 | **file-manager** — CRUD de arquivos. Ler (cat), criar, editar (append/replace), listar diretórios. Paths permitidos configuráveis (default: `/opt/vps-agent/`, `/tmp/`, `/home/`). Paths proibidos: `/etc/shadow`, `/root/.ssh/`, etc. | 4h | P0 | `skills/file-manager/` |
| S2-03 | **web-search** — Busca na internet via Brave Search API (free tier: 2000 queries/mês). Retorna top 5 resultados com título, URL, snippet. Sem scraping (não consome RAM extra). | 4h | P1 | `skills/web-search/` |
| S2-04 | **memory-query** — Consulta PostgreSQL: learnings, conversation_log, agent_memory, agent_capabilities. Queries predefinidas seguras (sem SQL injection). Exemplos: "o que você aprendeu?", "qual meu histórico?". | 3h | P1 | `skills/memory-query/` |
| S2-05 | **self-edit** — Lê e modifica arquivos do próprio projeto AgentVPS. Sempre cria backup antes de editar. Sempre commita com mensagem "[self-edit] description". Requer approval para qualquer modificação. | 3h | P2 | `skills/self-edit/` |

### Milestone S2: "5 Skills Live"
```
✅ Telegram: "execute ls -la /opt/vps-agent" → lista de arquivos
✅ Telegram: "leia o arquivo /opt/vps-agent/README.md" → conteúdo do README
✅ Telegram: "busque na internet como instalar Node.js 22 Ubuntu" → resultados
✅ Telegram: "o que você aprendeu até agora?" → lista de learnings
✅ Telegram: "rm -rf /tmp/teste" → botão de approval no Telegram → executa só se aprovado
✅ Cada skill tem pelo menos 1 teste em tests/
```

---

## S3 — Cleanup (Semana 2, paralelo com S2)

> **Objetivo:** Eliminar código morto e duplicações identificadas na avaliação.
> **Critério de saída:** -800 linhas, 0 módulos duplicados.

| # | Job | Horas | Prioridade | Entrega |
|---|-----|-------|------------|---------|
| S3-01 | **Eliminar duplicações** — Deletar `intent_classifier.py` (571 linhas, regex-based — `intent_classifier_llm.py` é o ativo). Remover bloco duplicado em `node_execute` (~120 linhas). Remover `core/vps_agent/semantic_memory.py` (256 linhas legado, `learnings.py` é o substituto). Consolidar ou remover `AgentStateModern` de `state.py` se não é usado. | 4h | P1 | -800+ linhas |
| S3-02 | **Convergir Bot → Gateway** — Fazer o Telegram bot receber via webhook no Gateway (FastAPI) em vez de polling independente. Isso elimina 2 entry points e permite WhatsApp futuro. | 2h | P2 | 1 entry point |

### Milestone S3: "Clean Codebase"
```
✅ `find core/ -name "*.py" -exec cat {} + | wc -l` < 11.000 (atual: 11.871)
✅ `grep -r "intent_classifier.py" core/` retorna 0 resultados (exceto em __pycache__)
✅ Telegram continua funcionando normalmente
✅ CI/CD verde
```

---

## S4 — Autonomous Loop (Semana 3)

> **Objetivo:** O agente propõe ações sozinho, não apenas reage a mensagens.
> **Critério de saída:** Heartbeat roda a cada 30 min, detecta pelo menos 1 tipo de problema, e propõe ação.

| # | Job | Horas | Prioridade | Entrega |
|---|-----|-------|------------|---------|
| S4-01 | **Schema + tabelas** — Criar tabelas `agent_proposals`, `agent_missions`, `agent_policies` no PostgreSQL. Migração SQL idempotente. Policies iniciais: max_daily_cost, require_approval_for_dangerous, heartbeat_interval. | 4h | P0 | `configs/migration-v2.sql` |
| S4-02 | **Autonomous Loop engine** — Módulo `core/autonomous/loop.py` com: `heartbeat()` (verifica triggers), `create_proposal()` (cria proposta), `cap_gate_check()` (verifica recursos + segurança), `execute_mission()` (delega ao Skill Registry), `emit_event()` (persiste resultado). Worker background via `asyncio.create_task` no startup do bot. | 8h | P0 | `core/autonomous/loop.py` |
| S4-03 | **3 Triggers iniciais** — (1) RAM > 80% → propor limpeza de containers inativos. (2) Erro repetido nos logs (>3x em 1h) → propor investigação. (3) Tarefa agendada vencida → propor execução. Cada trigger gera proposal no PostgreSQL e notifica via Telegram. | 4h | P1 | 3 triggers funcionais |

### Milestone S4: "Proactive Agent"
```
✅ Heartbeat roda a cada 30 minutos sem erro
✅ Quando RAM > 80%, aparece no Telegram: "🔔 RAM alta (82%). Posso limpar containers inativos? [Sim/Não]"
✅ Tabela agent_proposals tem registros
✅ `agent-cli proposals list` mostra propostas pendentes
✅ Política de custo impede mais de X propostas/dia
```

---

## Cronograma Visual

```
Semana 1          Semana 2              Semana 3
│                 │                     │
├─ S1-01 Registry ├─ S2-01 shell-exec   ├─ S4-01 Schema
├─ S1-02 Migrate  ├─ S2-02 file-mgr     ├─ S4-02 Loop Engine
├─ S1-03 Tests    ├─ S2-03 web-search   ├─ S4-03 Triggers
│                 ├─ S2-04 memory-query │
│                 ├─ S2-05 self-edit    │
│                 │                     │
│                 ├─ S3-01 Cleanup      │
│                 └─ S3-02 Converge Bot │
│                 │                     │
✓ Registry Green  ✓ 5 Skills Live      ✓ Proactive Agent
                  ✓ Clean Codebase
```

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| shell-exec usado para destruir sistema | Média | Crítico | Allowlist de segurança + approval para DANGEROUS |
| Brave Search API tier grátis insuficiente | Baixa | Baixo | Fallback para DuckDuckGo Instant Answer API |
| Autonomous Loop consome RAM em idle | Média | Médio | Heartbeat leve (1 query SQL + /proc/meminfo, sem LLM) |
| Migrar tools existentes quebra algo | Média | Alto | Manter TOOLS_REGISTRY como fallback durante migração |
| Testes não passam no CI após mudanças | Alta | Médio | Rodar testes localmente antes de cada push |

---

## Relação com Roadmap v2 (Fases 1-4)

Esta sprint implementa parcialmente estes jobs do roadmap v2:

| Job v2 | Sprint | Status |
|---|---|---|
| F2-01 Skill Registry | S1 | ✅ Implementação completa |
| F2-02 Skills Core (5) | S2 | ✅ Implementação completa |
| F2-03 Action Classification | S2-01 (parcial) | ⚠️ Classificação básica no shell-exec |
| F3-12 Autonomous Loop (novo) | S4 | ✅ Implementação v1 |
| Cleanup (técnico) | S3 | ✅ Eliminação de dívida |

**Após esta sprint, o roadmap v2 avança diretamente para:**
- F2-03 completo (approval workflow com botões Telegram para todos os skills)
- F2-07 (Evolution API / WhatsApp — Gateway já preparado por S3-02)
- F3-01/F3-02 (LLM failover + cascade routing)
