# VPS-Agente v2 — Resumo Completo do Projeto

## 🎯 Visão do Projeto

**VPS-Agente v2** é um agente autônomo auto-melhorável rodando em uma VPS com 2.4GB de RAM. A VPS é o agente, e o CLI (Kilocode/Claude) é o **CÉREBRO** instalado na própria VPS.

### O Agente Pode:
- Desenvolver-se sozinho
- Aprender e melhorar automaticamente
- Implementar novas funções
- Criar novos agentes

---

## 🔑 Credenciais de Acesso VPS

| Campo | Valor |
|-------|-------|
| **IP** | 107.175.1.42 |
| **Porta SSH** | 22 |
| **Usuário** | root |
| **Senha** | 1kAA7xQjKr23v96dHV |

### Acesso via SSH
```bash
ssh root@107.175.1.42
# Senha: 1kAA7xQjKr23v96dHV
```

---

## 📊 Fases do Projeto (Status)

| Fase | Descrição | Status |
|------|-----------|--------|
| FASE 1 | Fundação (Docker, PostgreSQL, Redis, estrutura) | ✅ Completa |
| FASE 2 | Telegram Bot (@Molttaitbot) | ✅ Completa |
| FASE 3 | LangGraph + Memória (PostgreSQL) | ✅ Completa |
| FASE 4 | Ferramentas Sob Demanda (Resource Manager) | ✅ Completa |
| FASE 5 | Monitoramento + Hardening | ✅ Completa |
| FASE 6 | CLI (Claude + Kilocode) | ✅ Completa |
| FASE 7 | Arquitetura GitHub | ✅ Completa |
| FASE 8 | Interpretador de Intenções (LangGraph) | ✅ Completa |
| FASE 9 | MiniMax M2.1 via Kilocode | ✅ Completa |
| FASE 10 | Roteamento Telegram → CLI | ✅ Completa |
| FASE 11 | Memória Semântica Qdrant | ✅ Completa |
| FASE 12 | FastAPI-MCP Integration | ✅ Completa |
| FASE 13 | **Deploy MCP Server na VPS** | 🔄 Em andamento |

---

## 🏗️ Arquitetura do Sistema

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
│  │  PostgreSQL + Redis + LangGraph   │  │
│  │  + Resource Manager               │  │
│  │  + Telegram Bot                   │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  SOB DEMANDA (~1650 MB livre)    │  │
│  │  Qdrant (memória semântica)      │  │
│  │  MCP Server (Ferramentas expostas)│ │
│  └───────────────────────────────────┘  │
│                                         │
│  Interface: Telegram (@Molttaitbot)     │
└─────────────────────────────────────────┘
```

---

## 🛠️ Stack Tecnológica

| Componente | Propósito | Status |
|------------|-----------|--------|
| **Ubuntu 24.04** | Sistema operacional | ✅ Instalado |
| **Docker 29.2.1** | Containers | ✅ Instalado |
| **PostgreSQL 16** | Memória estruturada (~24 MB) | ✅ Rodando |
| **Redis 7** | Cache e pub/sub (~3 MB) | ✅ Rodando |
| **Qdrant** | Memória semântica (vector DB) | ✅ Instalado |
| **LangGraph** | Orquestração do agente | ✅ Implementado |
| **Claude CLI** | Cérebro (assinatura Anthropic) | ✅ Autenticado |
| **Kilocode CLI** | Cérebro (OpenRouter + MiniMax M2.1 free) | ✅ Configurado |
| **Telegram Bot** | Interface de comunicação | ✅ Rodando |
| **FastAPI-MCP** | Servidor MCP para ferramentas | ✅ Criado |

---

## 📁 Estrutura de Diretórios

```
/opt/vps-agent/
├── brain/              # CLI e cérebro do agente
│   ├── agent-cli.sh    # Script de alternância Claude/Kilocode
│   └── model-selector.sh
├── configs/            # Configurações Docker e serviços
│   ├── docker-compose.core.yml    # PostgreSQL + Redis
│   ├── docker-compose.qdrant.yml  # Qdrant
│   ├── docker-compose.n8n.yml     # n8n (opcional)
│   ├── .env.example
│   ├── .env               # Configurado na VPS
│   ├── init-db.sql
│   ├── telegram-bot.service
│   └── mcp-server.service
├── core/               # serviços sempre ligados
│   ├── vps_agent/      # Módulo LangGraph
│   │   ├── state.py    # AgentState TypedDict
│   │   ├── memory.py   # PostgreSQL + Redis
│   │   ├── nodes.py    # LangGraph nodes (classify_intent)
│   │   ├── graph.py    # Workflow
│   │   ├── agent.py    # Entry point
│   │   └── semantic_memory.py  # Qdrant integration
│   ├── resource-manager/
│   │   └── manager.py  # Gerenciador de RAM
│   ├── mcp_server.py   # Servidor FastAPI-MCP
│   ├── requirements-mcp.txt
│   └── __version__.py
├── data/               # Dados persistentes
├── docs/               # Documentação
│   ├── PROJECT_SUMMARY.md  # Este arquivo
│   ├── ARCHITECTURE.md
│   ├── CLAUDE_AUTH_GUIDE.md
│   ├── SSH_TUNNEL_GUIDE.md
│   ├── MCP_SERVER.md
│   └── CONTRIBUTING.md
├── logs/               # Logs
├── scripts/            # Scripts de automação
│   ├── deploy-mcp.sh
│   ├── install-mcp.sh
│   └── self_improve.sh
├── tools/              # Ferramentas sob demanda
│   └── qdrant/
├── telegram-bot/       # Bot Telegram
│   └── bot.py
├── .github/           # CI/CD
│   └── workflows/
├── .kilocode/         # Memory Bank
│   └── rules/
│       ├── memory-bank/
│       │   ├── brief.md
│       │   ├── context.md
│       │   └── history.md
│       └── vps-agent-rules.md
├── plans/
│   └── plano-implementacao-vps-agente.md
└── README.md
```

---

## 📋 Resumo por Fase

### FASE 1: Fundação
- Ubuntu 24.04 configurado
- Docker 29.2.1 instalado
- UFW ativo com regras para SSH, 443, 8443
- Fail2ban bloqueando IPs maliciosos
- PostgreSQL 16 rodando (~24 MB)
- Redis 7 rodando (~3 MB)
- RAM disponível: ~2000 MB

### FASE 2: Telegram Bot
- Python 3.12 + venv configurado
- Telegram Bot @Molttaitbot rodando via systemd
- Comandos implementados: /start, /status, /ram, /containers, /health, /help

### FASE 3-4: LangGraph + Memória + Resource Manager
- Resource Manager implementado em core/resource-manager/manager.py
- Funções: get_ram_status(), list_containers(), stop_container(), start_container()
- Gerenciamento de RAM: nunca ultrapassar 2.4 GB

### FASE 5-6: CLI (Claude + Kilocode)
- Claude CLI autenticado via OAuth
- Kilocode CLI configurado com OpenRouter
- MiniMax M2.1 como modelo default (gratuito)
- Sistema de alternância: agent-cli.sh

### FASE 7-8: Interpretador de Intenções (LangGraph)
- node_classify_intent: classifica intents como command, task, question, chat
- Roteamento inteligente baseado na intenção
- Fluxo: classify → load_context → plan → execute|call_cli → respond → save_memory

### FASE 9-10: Roteamento Telegram → CLI
- Bot conecta com LangGraph
- Intent classification funcionando
- Respostas conversacionais implementadas

### FASE 11: Memória Semântica Qdrant
- save_conversation(): armazena conversas como vetores
- search_similar(): busca conversas similares
- Integração com PostgreSQL para fatos estruturados

### FASE 12: FastAPI-MCP Integration
- Servidor MCP criado em core/mcp_server.py
- Ferramentas expostas via MCP Protocol:
  - get_ram_status
  - list_containers
  - get_container_status
  - stop_container / start_container / restart_container
  - list_services
  - get_system_info
  - search_memory
  - get_facts
- Documentação em docs/MCP_SERVER.md
- Serviço systemd: configs/mcp-server.service

---

## 🔧 Configuração de Variáveis de Ambiente

```env
# VPS
VPS_HOST=107.175.1.42
SSH_PORT=22

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vps_agent
POSTGRES_USER=vps_agent
POSTGRES_PASSWORD=postgres

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Telegram Bot
TELEGRAM_BOT_TOKEN=seu_token_aqui

# APIs
ANTHROPIC_API_KEY=sk-ant-api03-sua-chave
OPENROUTER_API_KEY=sk-or-v1-sua-chave

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

---

## 📌 Comandos Úteis

### Verificar Status dos Serviços
```bash
# Status do Telegram Bot
systemctl status telegram-bot

# Status do MCP Server
systemctl status mcp-server

# Status do PostgreSQL
systemctl status postgresql

# Status do Redis
systemctl status redis
```

### Verificar RAM
```bash
free -m
docker stats
```

### Verificar Containers
```bash
docker ps -a
```

### Verificar Logs
```bash
# Telegram Bot
journalctl -u telegram-bot -f

# MCP Server
journalctl -u mcp-server -f
```

### Reiniciar Serviços
```bash
systemctl restart telegram-bot
systemctl restart mcp-server
```

---

## 🚨 Restrições Críticas

1. **RAM total: 2.4 GB** — NUNCA ultrapassar
2. Serviços "sempre ligados" devem caber em **750 MB**
3. Máximo **2 ferramentas sob demanda** simultâneas
4. CLI deve estar NA VPS para autonomia total
5. Qdrant para memória semântica (conceitos, não só fatos)

---

## 📝 Próximos Passos

### Imediato (FASE 13)
1. Executar script de deploy do MCP Server
2. Testar health endpoint: `curl http://localhost:8000/health`
3. Configurar Claude Desktop com MCP via SSH tunnel

### Curto Prazo
1. Testar todas as ferramentas MCP
2. Integrar com Claude Desktop
3. Criar workflow completo Telegram → MCP

### Médio Prazo
1. Implementar self-improvement automático
2. Adicionar mais ferramentas sob demanda
3. Expandir memória semântica

---

## 🔗 Links Importantes

- **Repositório GitHub**: https://github.com/Guitaitson/AgentVPS
- **Telegram Bot**: @Molttaitbot
- **Documentação MCP**: docs/MROCP_SERVER.md
- **Guia Claude CLI**: docs/CLAUDE_AUTH_GUIDE.md
- **Guia SSH Tunnel**: docs/SSH_TUNNEL_GUIDE.md

---

**Status do Projeto**: Em Desenvolvimento Ativo  
**Versão**: 2.0.0  
**Última Atualização**: 2026-02-07
