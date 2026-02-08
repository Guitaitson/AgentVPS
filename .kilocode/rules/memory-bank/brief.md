# Estado Atual — VPS-Agente v2

## Fase Atual: FASE 0 (Estabilização v1) — COMPLETA
## Última ação: Commit tracker com FASE 0 validada
## Próxima ação: Iniciar F1-01 — Gateway Module (FastAPI)

## Checklist de Fases

### v1 (Completo)
- [x] Fase 1: Fundação (Docker, PostgreSQL, Redis, estrutura)
- [x] Fase 2: CLI + Telegram Bot
- [x] Fase 3: LangGraph + Memória
- [x] Fase 4: Ferramentas Sob Demanda (Resource Manager)
- [x] Fase 5: Monitoramento + Hardening
- [x] Fase 6: CLI (Claude + Kilocode)
- [x] Fase 7: Arquitetura GitHub
- [x] Fase 8: Interpretador de Intenções (LangGraph)
- [x] Fase 9: MiniMax M2.1 via Kilocode
- [x] Fase 10: Roteamento Telegram → CLI
- [x] Fase 11: Memória Semântica Qdrant
- [x] Fase 12: FastAPI-MCP Integration
- [x] Fase 13: Self-Improvement Agent

### v2 (Pendente)
- [ ] FASE 0: Estabilização v1 (COMPLETA - 7/7 jobs)
- [ ] FASE 1: Fundação (Gateway + Sessões)
- [ ] FASE 2: Skills & Segurança
- [ ] FASE 3: Inteligência & Confiabilidade
- [ ] FASE 4: Autonomia & Evolução

## Problemas Conhecidos (FASE 0)
1. ✅ **self_improve não gera resposta** — Corrigido (graph flow)
2. ✅ **timezone is not defined** — Corrigido (import added)
3. ✅ **Código duplicado em 3 locais** — Corrigido (duplicatas deletadas)
4. ⚠️ CI/CD pipeline — Adaptado para requirements.txt

## Decisões Tomadas
- Arquitetura v2: VPS é o agente, CLI é o cérebro
- Resource Manager controla RAM
- PostgreSQL + Redis sempre ligados (~750 MB)
- Ferramentas sob demanda (máx 2 simultâneas)
- MiniMax M2.1 via OpenRouter (gratuito) como modelo default
- LangGraph classifica intents: command, task, question, chat, self_improve
- Qdrant para memória semântica (embeddings de conversas)
- FASE 0 obrigatória antes de v2 (recomendação Opus 4.6)

## Resultados FASE 0 (Completo)
- ✅ Cleanup de código (deletadas duplicatas)
- ✅ Graph flow self_improve corrigido
- ✅ Timezone import validado
- ✅ CI/CD funcionando com requirements.txt
- ✅ 5 testes end-to-end passando
- ✅ Telegram Log Handler implementado
- ✅ README atualizado
- ✅ Deploy script criado (scripts/deploy.sh)

## Recursos
- Tracker: `.kilocode/rules/memory-bank/deployment-tracker.md`
- Roadmap v2: `agentvps-v2-roadmap.md`
- Plano completo: `plans/plano-implantacao-vps-agente-v2.md`

## Próximos Passos
1. F1-01: Gateway Module (FastAPI + Adapters) - 16h P0
2. F1-02: Session Manager - 12h P0
3. F1-03: Context Window Guard - 10h P0
