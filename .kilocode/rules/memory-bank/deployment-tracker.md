# Tracker de Implantação — AgentVPS

## 📊 Estado Atual

| Fase | Status | Jobs Completos | Progresso |
|------|--------|----------------|-----------|
| **FASE 1-13 (v1)** | ✅ Completo | 13/13 | 100% |
| **FASE 0 (Estabilização)** | ⏳ Em Andamento | 0/7 | 0% |
| **FASE 1 v2 (Fundação)** | ⏳ Pendente | 0/12 | 0% |
| **FASE 2 v2 (Skills)** | ⏳ Pendente | 0/10 | 0% |
| **FASE 3 v2 (Inteligência)** | ⏳ Pendente | 0/11 | 0% |
| **FASE 4 v2 (Autonomia)** | ⏳ Pendente | 0/11 | 0% |

---

## 🎯 FASE 0 — Estabilização v1

**Objetivo:** Corrigir bugs críticos, cleanup código, zero features novas  
**Início:** [DATA]  
**Prazo:** 1-2 semanas  
**Responsável:** Kilocode + suporte Opus 4.6

### Jobs

| # | Job | Status | Data Início | Data Fim | Notas |
|---|-----|--------|-------------|----------|-------|
| F0-01 | Cleanup de Código | ⏳ | - | - | Deletar duplicatas |
| F0-02 | Fix Graph Flow self_improve | ⏳ | - | - | Roteamento corrigido |
| F0-03 | Fix timezone + Validação | ⏳ | - | - | Import testado |
| F0-04 | Fix CI/CD | ⏳ | - | - | Pipeline verde |
| F0-05 | Testes Básicos end-to-end | ⏳ | - | - | 5 intents testados |
| F0-06 | Telegram Log Handler | ⏳ | - | - | Errors notificados |
| F0-07 | Documentação Mínima | ⏳ | - | - | README atualizado |

### ✅ Critérios de Saída FASE 0

- [ ] Todos os 5 intents retornam response via Telegram
- [ ] Zero NameError: timezone nos logs
- [ ] Apenas 1 cópia de cada arquivo (sem duplicatas)
- [ ] pytest verde com 5+ testes
- [ ] `__pycache__/` no .gitignore
- [ ] Erros CRITICAL notificados via Telegram

---

## 🚀 FASE 1 v2 — Refatoração da Fundação

**Objetivo:** Gateway + Sessões + Proteções fundamentais  
**Início:** Após FASE 0 completa  
**Duração:** 3-4 semanas (~102h)

| # | Job | Horas | Prioridade |
|---|-----|-------|------------|
| F1-01 | Gateway Module (FastAPI + Adapters) | 16h | P0 |
| F1-02 | Session Manager | 12h | P0 |
| F1-03 | Context Window Guard | 10h | P0 |
| F1-04 | JSONL Transcripts | 6h | P0 |
| F1-05 | Prompt Composer Dinâmico | 8h | P0 |
| F1-06 | LLM Provider Abstraction | 12h | P0 |
| F1-07 | Allowlist de Segurança | 4h | P0 |
| F1-08 | Structured Logging | 6h | P1 |
| F1-09 | Error Handling + Circuit Breaker | 8h | P1 |
| F1-10 | Health Check & Doctor | 6h | P1 |
| F1-11 | Docker Compose v2 | 4h | P1 |
| F1-12 | Testes Unitários Fundação | 10h | P1 |

---

## 🛠️ FASE 2 v2 — Skills & Segurança

**Objetivo:** Skills modulares + WhatsApp + segurança em camadas  
**Início:** Após FASE 1  
**Duração:** 3-4 semanas (~120h)

| # | Job | Horas | Prioridade |
|---|-----|-------|------------|
| F2-01 | Skill Registry | 20h | P0 |
| F2-02 | Skills Core (5 iniciais) | 16h | P0 |
| F2-03 | Action Classification & Approval | 14h | P0 |
| F2-04 | PII Redaction Layer | 8h | P0 |
| F2-05 | Prompt Injection Defense | 10h | P0 |
| F2-06 | Tool Contract Testing | 12h | P1 |
| F2-07 | Evolution API Adapter (WhatsApp) | 12h | P1 |
| F2-08 | Audit Logging | 8h | P1 |
| F2-09 | Tool Usage Policies | 8h | P1 |
| F2-10 | Testes Integração Skills | 12h | P1 |

---

## 🧠 FASE 3 v2 — Inteligência & Confiabilidade

**Objetivo:** Failover + RAG + Cache + Automações  
**Início:** Após FASE 2  
**Duração:** 4-5 semanas (~146h)

| # | Job | Horas | Prioridade |
|---|-----|-------|------------|
| F3-01 | Multi-Provider LLM Failover | 12h | P0 |
| F3-02 | Model Cascade Routing | 16h | P0 |
| F3-03 | Step-Level Reasoning Validation | 14h | P0 |
| F3-04 | Hierarchical Memory | 20h | P0 |
| F3-05 | RAG Ingestion Pipeline | 20h | P1 |
| F3-06 | Semantic Caching | 12h | P1 |
| F3-07 | Reflection & Self-Critique | 14h | P1 |
| F3-08 | LLM-Native Observability | 10h | P1 |
| F3-09 | Usage & Cost Tracking | 10h | P1 |
| F3-10 | n8n Integration | 10h | P1 |
| F3-11 | Cron & Scheduled Tasks | 8h | P2 |

---

## 🔄 FASE 4 v2 — Autonomia & Evolução

**Objetivo:** Multi-agent + Self-improvement + Guardrails  
**Início:** Após FASE 3  
**Duração:** 3-4 semanas (~140h)

| # | Job | Horas | Prioridade |
|---|-----|-------|------------|
| F4-01 | Multi-Agent Routing | 18h | P1 |
| F4-02 | Agent-to-Agent Communication | 14h | P1 |
| F4-03 | Goal Drift Monitor | 12h | P1 |
| F4-04 | Self-Improvement Pipeline | 20h | P1 |
| F4-05 | Indirect Prompt Injection Scanner | 14h | P1 |
| F4-06 | Behavioral Contract Testing | 10h | P2 |
| F4-07 | Shadow Testing para Prompts | 12h | P2 |
| F4-08 | Memory Compaction Scheduler | 8h | P2 |
| F4-09 | CLI Expandido | 10h | P2 |
| F4-10 | Environment Segregation | 10h | P2 |
| F4-11 | Documentação Completa | 12h | P2 |

---

## 📈 Resumo Total

| Fase | Jobs | Horas | Semanas |
|------|------|-------|---------|
| v1 (completo) | 13 | - | - |
| FASE 0 | 7 | ~26h | 1-2 |
| FASE 1 v2 | 12 | ~102h | 3-4 |
| FASE 2 v2 | 10 | ~120h | 3-4 |
| FASE 3 v2 | 11 | ~146h | 4-5 |
| FASE 4 v2 | 11 | ~140h | 3-4 |
| **TOTAL v2** | **44** | **~508h** | **13-17** |

---

## 📝 Últimas Atualizações

### [DATA] — Início FASE 0
- Plano de estabilização criado baseado em consultoria Opus 4.6
- Jobs definidos com prioridades e critérios de saída

### Histórico Completo
Ver `history.md` para decisões arquiteturais e mudanças.
