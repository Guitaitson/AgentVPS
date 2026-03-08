# Project Summary — AgentVPS

## Objetivo

AgentVPS é um agente operacional para VPS com interface principal via Telegram, orquestração em LangGraph e execução de skills com políticas de segurança.

## Estado Atual (Mar/2026)

- Orquestração principal com ReAct + function calling
- Memória persistente em PostgreSQL + cache Redis
- Registry de skills builtin (incluindo operações de sistema e integrações MCP)
- Integração FleetIntel em desenvolvimento ativo no ramo principal
- Servidor MCP disponível para expor ferramentas do agente

## Estrutura do Repositório

- `core/`: engine, grafo, skills, segurança, MCP e gateway
- `telegram_bot/`: interface Telegram e fluxo de aprovação
- `configs/`: compose, service units e templates de ambiente
- `docs/`: documentação técnica ativa
- `archive/`: histórico e planos antigos (não normativos)

## Segurança e Operação

- Não versionar segredos (`.env`, tokens, credenciais, hosts privados)
- Manter MCP bindado em `127.0.0.1` por padrão
- Usar `MCP_API_KEY` quando houver acesso além de localhost
- Exigir aprovação para operações classificadas como `dangerous`

## Referências

- [README](../README.md)
- [Arquitetura](ARCHITECTURE.md)
- [Deploy](DEPLOYMENT.md)
- [MCP Server](MCP_SERVER.md)
