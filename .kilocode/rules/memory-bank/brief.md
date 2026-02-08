# Estado Atual — VPS-Agente v2

## Fase Atual: FASE 0 (Estabilização v1)
## Última ação: Criado plano de implantação e deployment tracker
## Próxima ação: Iniciar F0-01 — Cleanup de Código

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
- [ ] FASE 0: Estabilização v1 (em andamento)
- [ ] FASE 1: Fundação (Gateway + Sessões)
- [ ] FASE 2: Skills & Segurança
- [ ] FASE 3: Inteligência & Confiabilidade
- [ ] FASE 4: Autonomia & Evolução

## Problemas Conhecidos (FASE 0)
1. **self_improve não gera resposta** — Graph flow incorreto
2. **timezone is not defined** — Import faltando
3. **Código duplicado em 3 locais** — Imports confusos

## Decisões Tomadas
- Arquitetura v2: VPS é o agente, CLI é o cérebro
- Resource Manager controla RAM
- PostgreSQL + Redis sempre ligados (~750 MB)
- Ferramentas sob demanda (máx 2 simultâneas)
- MiniMax M2.1 via OpenRouter (gratuito) como modelo default
- LangGraph classifica intents: command, task, question, chat, self_improve
- Qdrant para memória semântica (embeddings de conversas)
- FASE 0 obrigatória antes de v2 (recomendação Opus 4.6)

## Resultados FASE 0 (Planejado)
- Cleanup de código (deletar duplicatas)
- Graph flow self_improve corrigido
- Timezone import validado
- CI/CD funcionando
- 5 testes end-to-end passando
- Telegram Log Handler implementado
- README atualizado

## Recursos
- Plano completo: `plans/fase-0-estabilizacao.md`
- Roadmap v2: `agentvps-v2-roadmap.md`
- Tracker: `.kilocode/rules/memory-bank/deployment-tracker.md`
