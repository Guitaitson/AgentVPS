# Estado Atual — VPS-Agente v2

## Fase Atual: FASE 12 Completa
## Última ação: FASE 12 completa — MCP Server deployado com sucesso
## Próxima ação: Configurar SSH tunnel para acesso remoto ao MCP

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
- [x] Fase 11: Memória Semântica Qdrant
- [x] Fase 12: FastAPI-MCP Integration

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
- Qdrant para memória semântica (embeddings de conversas)

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

## Resultados FASE 8-11
- Interpretador de Intenções LangGraph implementado
- node_classify_intent: command, task, question, chat
- node_call_cli: Chama MiniMax M2.1 via OpenRouter
- node_load_context: Carrega contexto + memória semântica Qdrant
- node_save_memory: Salva em PostgreSQL + Qdrant
- Fluxo: classify → load_context → plan → execute|call_cli → respond → save_memory

## Resultados FASE 12
- Servidor FastAPI-MCP criado em core/mcp_server.py
- MCP Server rodando em http://localhost:8000 (systemd)
- Ferramentas expostas: /ram, /containers, /tools, /services, /system
- Endpoints REST: health, ram, containers, tools, services, system
- Documentação: docs/MCP_SERVER.md
- Integração com Claude Desktop via SSH tunnel
