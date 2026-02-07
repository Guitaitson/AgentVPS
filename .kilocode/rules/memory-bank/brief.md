# Estado Atual — VPS-Agente v2

## Fase Atual: FASE 11
## Última ação: FASE 10 completa — CLI Routing implementado
## Próxima ação: FASE 11.1 — Memória Semântica Qdrant

## Checklist de Fases
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
- [ ] Fase 11: Memória Semântica Qdrant

## Problemas Conhecidos
- Nenhum

## Decisões Tomadas
- Arquitetura v2: VPS é o agente, CLI é o cérebro
- Resource Manager controla RAM
- PostgreSQL + Redis sempre ligados (~750 MB)
- Ferramentas sob demanda (máx 2 simultâneas)
- Moltbot NÃO faz parte deste projeto
- MiniMax M2.1 via OpenRouter (gratuito) como modelo default
- LangGraph classifica intents: command, task, question, chat

## Resultados FASE 1
- Ubuntu 24.04 configurado
- Docker 29.2.1 instalado
- UFW ativo com regras para SSH, 443, 8443
- Fail2ban bloqueando IPs maliciosos
- PostgreSQL 16 rodando (~24 MB)
- Redis 7 rodando (~3 MB)
- RAM disponível: ~2000 MB

## Resultados FASE 2
- Python 3.12 + venv configurado
- Telegram Bot @Molttaitbot rodando via systemd
- Comandos implementados: /start, /status, /ram, /containers, /health, /help

## Resultados FASE 8-10
- Interpretador de Intenções LangGraph implementado
- node_classify_intent: command, task, question, chat
- node_call_cli: Chama MiniMax M2.1 via OpenRouter
- node_generate_response: Gera respostas finais
- node_save_memory: Salva histórico PostgreSQL
- Fluxo: classify → load_context → plan → execute|call_cli → respond → save_memory
