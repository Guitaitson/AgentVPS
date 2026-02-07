# 🧠 VPS-Agente v2

Um agente autônomo auto-melhorável rodando em VPS com 2.4GB de RAM.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Stack](#stack)
- [Fases do Projeto](#fases-do-projeto)
- [Quick Start](#quick-start)
- [Estrutura de Diretórios](#estrutura-de-diretórios)
- [Contribuição](#contribuição)
- [Licença](#licença)

---

## 🎯 Visão Geral

**VPS-Agente v2** é um sistema de agente autônomo capaz de:
- Desenvolver-se sozinho
- Aprender e melhorar automaticamente
- Implementar novas funções
- Criar novos agentes

A VPS é o agente. O CLI (Kilocode/Claude) é o **CÉREBRO** instalado na própria VPS.

---

## 🏗️ Arquitetura

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
│  │  SOB DEMANDA (~1650 MB livre)     │  │
│  │  Qdrant (memória semântica)       │  │
│  │  n8n, Flowise                     │  │
│  └───────────────────────────────────┘  │
│                                         │
│  Interface: Telegram (@Molttaitbot)   │
└─────────────────────────────────────────┘
```

---

## 🛠️ Stack

| Componente | Propósito |
|------------|-----------|
| **LangGraph** | Orquestração do agente |
| **PostgreSQL 16** | Memória estruturada (fatos, configs, estado) |
| **Redis 7** | Cache e pub/sub |
| **Qdrant** | Memória semântica (vector DB) |
| **Docker** | Containers |
| **Claude CLI** | Cérebro (assinatura Anthropic) |
| **Kilocode CLI** | Cérebro (OpenRouter + créditos) |
| **Telegram Bot** | Interface de comunicação |

---

## 📊 Fases do Projeto

- ✅ **FASE 1:** Fundação (Docker, PostgreSQL, Redis, estrutura)
- ✅ **FASE 2:** Telegram Bot
- ✅ **FASE 3:** LangGraph + Memória (PostgreSQL)
- ✅ **FASE 4:** Qdrant (Memória Vetorial)
- ✅ **FASE 5:** CLI na VPS (Claude + Kilocode)
- 🔄 **FASE 6:** Arquitetura GitHub (docs, contributing)
- ⏳ **FASE 7:** Agente Autônomo (self-improving)

---

## 🚀 Quick Start

### Pré-requisitos

- VPS Ubuntu 24.04
- 2.4 GB RAM mínimo
- Docker + Docker Compose
- Git

### Instalação

```bash
# Clonar o repositório
git clone https://github.com/seu-usuario/vps-agente-v2.git
cd vps-agente-v2

# Configurar variáveis de ambiente
cp configs/.env.example configs/.env
nano configs/.env

# Iniciar serviços core
docker compose -f configs/docker-compose.core.yml up -d

# Configurar CLI (Claude ou Kilocode)
agent-cli configure claude
# ou
agent-cli configure kilocode

# Ativar CLI
agent-cli use claude
# ou
agent-cli use kilocode
```

### Uso do CLI Switcher

```bash
# Ver status
agent-cli status

# Executar tarefa
agent-cli run 'Analise o projeto e sugira melhorias'
```

---

## 📁 Estrutura de Diretórios

```
vps-agente-v2/
├── brain/              # CLI e cérebro do agente
│   └── agent-cli.sh    # Script de alternância Claude/Kilocode
├── configs/            # Configurações Docker e serviços
│   ├── docker-compose.core.yml
│   ├── docker-compose.qdrant.yml
│   ├── docker-compose.n8n.yml
│   ├── .env.example
│   ├── init-db.sql
│   └── telegram-bot.service
├── core/               # Serviços sempre ligados
│   ├── vps_agent/      # Módulo LangGraph
│   │   ├── state.py    # AgentState TypedDict
│   │   ├── memory.py   # PostgreSQL + Redis
│   │   ├── nodes.py    # LangGraph nodes
│   │   ├── graph.py    # Workflow
│   │   └── agent.py    # Entry point
│   └── resource-manager/
│       └── manager.py  # Gerenciador de RAM
├── data/               # Dados persistentes
├── docs/               # Documentação
├── logs/               # Logs
├── scripts/            # Scripts de automação
├── tools/              # Ferramentas sob demanda
│   ├── qdrant/         # Vector DB
│   └── n8n/            # Automation
├── telegram-bot/       # Bot Telegram
├── .kilocode/         # Memory Bank
│   └── rules/
│       ├── memory-bank/
│       │   ├── brief.md
│       │   ├── context.md
│       │   └── history.md
│       └── vps-agent-rules.md
├── README.md
└── LICENSE
```

---

## 🔧 Configuração

### Variáveis de Ambiente

```env
# PostgreSQL
POSTGRES_DB=vps_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=sua_senha

# Redis
REDIS_PASSWORD=sua_senha

# Telegram Bot
TELEGRAM_BOT_TOKEN=seu_token

# APIs (opcional)
ANTHROPIC_API_KEY=sua_chave
OPENROUTER_API_KEY=sua_chave
```

---

## 📖 Documentação

- [Plano de Implantação](plans/plano-implementacao-vps-agente.md)
- [Memory Bank](.kilocode/rules/memory-bank/)
- [Regras do Agente](.kilocode/rules/vps-agent-rules.md)

---

## 🤝 Contribuição

Consulte [CONTRIBUTING.md](docs/CONTRIBUTING.md) para diretrizes de contribuição.

---

## ⚠️ Restrições Críticas

- **RAM total: 2.4 GB** — NUNCA ultrapassar
- Serviços "sempre ligados" devem caber em **750 MB**
- Máximo **2 ferramentas sob demanda** simultâneas
- CLI deve estar NA VPS para autonomia total
- Qdrant para memória semântica (conceitos, não só fatos)

---

## 📝 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

## 🧠 Autor

Desenvolvido como projeto de agente autônomo auto-melhorável.

---

**Status:** Em Desenvolvimento | **Versão:** 2.0.0
