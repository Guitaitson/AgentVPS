# Contexto do Projeto — VPS-Agente v2

## Visão
**VPS de 2.4 GB RAM que funciona como um AGENTE AUTÔNOMO com capacidade de self-improvement.**

A VPS é o agente. O CLI (Kilocode/Claude) é o CÉREBRO instalado na própria VPS. O agente pode:
- Desenvolver-se sozinho
- Aprender e melhorar automaticamente
- Implementar novas funções
- Criar novos agentes

## Stack Principal
- **Orquestração:** LangGraph (Python 3.12)
- **Memória Estruturada:** PostgreSQL 16 (fatos, configs, estado)
- **Cache/Filas:** Redis 7
- **Memória Semântica:** Qdrant (vector DB para aprendizado)
- **Interface:** Telegram Bot (@Molttaitbot)
- **Cérebro:** CLI (Kilocode/Claude CLI) na própria VPS
- **Containers:** Docker + Docker Compose
- **Ferramentas sob demanda:** n8n, Flowise

## Restrições Críticas
- RAM total: 2.4 GB — NUNCA ultrapassar
- Serviços "sempre ligados" devem caber em 750 MB
- Máximo 2 ferramentas sob demanda simultâneas
- CLI deve estar NA VPS para autonomia total
- Qdrant para memória semântica (conceitos, não só fatos)

## Arquitetura Autônoma
```
┌─────────────────────────────────────────┐
│           VPS 2.4 GB (AGENTE)          │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  CÉREBRO (~500 MB)                │  │
│  │  CLI (Kilocode/Claude)            │  │
│  │  LangGraph + Agent                │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  SEMPRE LIGADOS (~750 MB)         │  │
│  │  PostgreSQL + Redis + LangGraph    │  │
│  │  + Resource Manager                │  │
│  │  + Telegram Bot                    │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  SOB DEMANDA (~1650 MB livre)     │  │
│  │  Qdrant (memória semântica)       │  │
│  │  n8n, Flowise                     │  │
│  └───────────────────────────────────┘  │
│                                         │
│  Interface: Telegram                    │
└─────────────────────────────────────────┘
```

## Acesso VPS
- IP: 107.175.1.42
- Porta SSH: 22
- Usuário: root (CLI instalado localmente)

## Repositório GitHub
- URL: https://github.com/Guitaitson/AgentVPS
- Estrutura CI/CD: `.github/workflows/ci.yml`
- Status: Sempre manter atualizado após alterações

## Estrutura de Diretórios
```
/opt/vps-agent/
├── core/              # Serviços sempre ligados
├── tools/             # Ferramentas sob demanda
├── brain/             # CLI + Agente autônomo
├── scripts/           # Scripts de automação
├── configs/           # Docker Compose
├── data/              # Dados persistentes
├── logs/              # Logs
└── docs/              # Documentação GitHub
```
