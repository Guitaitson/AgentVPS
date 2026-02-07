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
