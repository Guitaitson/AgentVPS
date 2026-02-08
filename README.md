# VPS-Agent v2

🤖 **Agente Autônomo para VPS de 2.4 GB RAM**

[![CI/CD](https://github.com/Guitaitson/AgentVPS/actions/workflows/ci.yml/badge.svg)](https://github.com/Guitaitson/AgentVPS/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Visão Geral

VPS-Agent é um agente autônomo que roda em uma VPS de 2.4 GB RAM, utilizando LangGraph para orquestração, PostgreSQL e Redis para memória estruturada, e Qdrant para memória semântica.

## Arquitetura

```
┌─────────────────────────────────────────────┐
│                 VPS 2.4 GB                  │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │     SEMPRE LIGADOS (~750 MB)       │    │
│  │  PostgreSQL + Redis + LangGraph    │    │
│  │  + Resource Manager + Telegram Bot │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │     SOB DEMANDA (~1650 MB livre)   │    │
│  │  Qdrant + n8n + Flowise            │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  Interface: Telegram Bot (@Molttaitbot)     │
└─────────────────────────────────────────────┘
```

## Stack Principal

- **Orquestração:** LangGraph (Python 3.11+)
- **Memória Estruturada:** PostgreSQL 16
- **Cache/Filas:** Redis 7
- **Memória Semântica:** Qdrant (sob demanda)
- **Interface:** Telegram Bot (python-telegram-bot)
- **Containers:** Docker + Docker Compose
- **LLM:** MiniMax M2.1 via OpenRouter

## Intents Suportados

| Intent | Descrição | Exemplo |
|--------|-----------|---------|
| `command` | Comandos do sistema | "mostre o status" |
| `task` | Tarefas complexas | "crie um backup" |
| `question` | Perguntas | "quanta RAM está livre?" |
| `chat` | Conversa geral | "olá, tudo bem?" |
| `self_improve` | Auto-evolução | "analise suas capacidades" |

## Quick Start

### 1. Clonar e Configurar

```bash
git clone https://github.com/Guitaitson/AgentVPS.git
cd AgentVPS
```

### 2. Configurar Variáveis de Ambiente

```bash
cp configs/.env.example configs/.env
# Editar configs/.env com suas credenciais
```

### 3. Deploy na VPS

```bash
# SSH para a VPS
ssh root@107.175.1.42

# Clone e setup
cd /opt/vps-agent
git pull origin main

# Iniciar serviços
docker compose -f configs/docker-compose.core.yml up -d

# Verificar status
./scripts/deploy.sh status
```

### 4. Usar o Bot

Iniciar conversa com [@Molttaitbot](https://t.me/Molttaitbot) no Telegram:

```
/start - Iniciar
/status - Estado da VPS
/ram - Uso de memória
/health - Health check
```

## Comandos de Deployment

```bash
# Deploy completo
./scripts/deploy.sh deploy

# Ver status
./scripts/deploy.sh status

# Ver logs
./scripts/deploy.sh logs [servico]

# Backup
./scripts/deploy.sh backup
```

## Estrutura de Diretórios

```
AgentVPS/
├── core/                   # Serviços sempre ligados
│   ├── langgraph/         # Agente LangGraph
│   ├── telegram-bot/       # Interface Telegram
│   └── vps_agent/         # Agente principal
├── tools/                  # Ferramentas sob demanda
│   ├── n8n/
│   ├── flowise/
│   └── qdrant/
├── configs/                # Configurações Docker
├── scripts/               # Scripts de automação
├── data/                  # Dados persistentes
├── logs/                  # Logs da aplicação
└── requirements.txt       # Dependências Python
```

## Variáveis de Ambiente Necessárias

```env
# Telegram
TELEGRAM_BOT_TOKEN=seu_token
TELEGRAM_ALLOWED_USERS=id1,id2
TELEGRAM_ADMIN_CHAT_ID=chat_id

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=senha
POSTGRES_DB=vps_agent

# Redis
REDIS_PASSWORD=senha

# LLM (OpenRouter)
OPENROUTER_API_KEY=sua_chave

# Qdrant
QDRANT_API_KEY=sua_chave
```

## FASE 0 — Estabilização v1 (Concluída)

- ✅ Cleanup de código (deletadas duplicatas)
- ✅ Fix Graph Flow self_improve
- ✅ Fix timezone import
- ✅ CI/CD adaptado para requirements.txt
- ✅ Telegram Log Handler implementado
- ✅ Testes end-to-end (5/5 passaram)

## Roadmap v2

| Fase | Jobs | Descrição |
|------|------|-----------|
| F1 | 12 | Gateway + Sessions + Protections |
| F2 | 10 | Skills + Security + WhatsApp |
| F3 | 11 | Intelligence + Reliability |
| F4 | 11 | Autonomy + Evolution |

## Regras de RAM

⚠️ **NUNCA ultrapassar 2.4 GB de RAM**

- Serviços sempre ligados: ~750 MB máximo
- Ferramentas sob demanda: máximo 2 simultâneas
- Resource Manager controla tudo automaticamente

## Documentação Completa

- [Plano de Implantação](plans/plano-implantacao-vps-agente-v2.md)
- [Roadmap v2](agentvps-v2-roadmap.md)
- [Tracker de Deployment](.kilocode/rules/memory-bank/deployment-tracker.md)

## Licença

MIT License - see [LICENSE](LICENSE) for details.
