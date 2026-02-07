# Histórico de Decisões

## 2026-02-06 — Arquitetura v2 definida
- VPS é o agente, não apenas infra
- CLI-agnóstico: inteligência vive no LangGraph + memória
- Resource Manager para gerenciar 2.4 GB de RAM
- PostgreSQL + Redis sempre ligados (~750 MB)
- Ferramentas sob demanda (máx 2 simultâneas)
- Moltbot NÃO faz parte deste projeto

## Modelos de execução
- Preferência: MiniMax M2.1, GLM-4.7 (custo baixo)
- Quando necessário: Sonnet 4.5 ou superior
- Decisões arquiteturais: revisar com modelo robusto

## 2026-02-07 — FASE 12: FastAPI-MCP Integration
- Integração com FastAPI-MCP para expor ferramentas do agente via MCP Protocol
- Ferramentas expostas: RAM, containers, services, memory
- Permite integração com Claude Desktop e outros clientes MCP
- Documentação completa em docs/MCP_SERVER.md
