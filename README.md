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

### 2. Instalar Dependências

```bash
pip install -e ".[dev]"
```

### 3. Configurar Variáveis de Ambiente

```bash
cp configs/.env.example configs/.env
# Editar configs/.env com suas credenciais
```

### 4. Deploy na VPS

```bash
# SSH para a VPS
ssh -i ~/.ssh/vps_agent_ed25519 root@107.175.1.22

# Clone e setup
cd /opt/vps-agent
git pull origin main

# Iniciar serviços
docker compose -f configs/docker-compose.core.yml up -d

# Verificar status
./scripts/deploy.sh status
```

### 5. Usar o Bot

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
├── core/                   # Código fonte principal
│   ├── capabilities/       # Registro de capacidades
│   ├── gateway/           # Gateway FastAPI + auth
│   ├── health_check/      # Health checks
│   ├── llm/               # Provedores LLM
│   ├── resilience/        # Circuit breaker
│   ├── resource_manager/  # Gerenciador de recursos
│   ├── security/          # Allowlist e segurança
│   ├── structured_logging/# Logging estruturado
│   ├── vps_agent/         # Agente principal
│   ├── vps_langgraph/     # Grafo LangGraph
│   ├── mcp_server.py      # Servidor MCP
│   └── __version__.py     # Versão
├── telegram_bot/          # Bot Telegram
│   ├── bot.py
│   └── telegram_handler.py
├── configs/               # Configurações
│   ├── .env.example
│   ├── docker-compose.core.yml
│   ├── docker-compose.n8n.yml
│   ├── docker-compose.qdrant.yml
│   └── *.service          # Systemd services
├── scripts/               # Scripts de automação
│   ├── deploy.sh
│   ├── deploy-vps.sh
│   ├── setup-vps.sh
│   └── self_improve.sh
├── tests/                 # Testes
├── docs/                  # Documentação
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   ├── CONTRIBUTING.md
│   └── adr/               # Architecture Decision Records
├── plans/                 # Planos de implementação
├── brain/                 # Scripts de seleção de modelos
├── pyproject.toml         # Configuração do pacote Python
└── requirements.txt       # Dependências (legacy)
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

# Gateway
GATEWAY_API_KEY=sua_chave_segura
```

## Fases de Desenvolvimento

### ✅ Fase 0.5 — Estrutura e Foundation (Concluída)

- Eliminados todos `sys.path.insert` → pacote Python profissional
- Reorganização: `telegram-bot/` → `telegram_bot/`, `resource-manager/` → `core/resource_manager/`
- CI/CD modernizado com `pip install -e ".[dev]"`
- 1.200+ erros lint corrigidos
- Todos commits verdes ✅

### 🔄 Fase 1.0 — Documentação e Sync VPS (Em Progresso)

- [x] Corrigir imports quebrados no gateway
- [ ] Atualizar README.md
- [ ] Atualizar docs/ARCHITECTURE.md
- [ ] Sync VPS via SSH
- [ ] Criar CHANGELOG.md

### 📋 Fase 1.1 — Connection Pooling Async

- Criar `core/database/pool.py` com asyncpg
- Migrar AgentMemory para async
- Testes de integração

### 📋 Fase 1.2 — Allowlist no Grafo

- Adicionar nó `security_check` ao grafo
- Integrar allowlist antes de executar comandos
- Testes de bloqueio de comandos perigosos

### 📋 Fase 1.3 — Gateway Auth Real

- Implementar API Key via env var
- Corrigir imports restantes
- Testes de auth

## Regras de RAM

⚠️ **NUNCA ultrapassar 2.4 GB de RAM**

- Serviços sempre ligados: ~750 MB máximo
- Ferramentas sob demanda: máximo 2 simultâneas
- Resource Manager controla tudo automaticamente

## Documentação Completa

- [Arquitetura](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Contribuição](docs/CONTRIBUTING.md)
- [Plano de Implantação](plans/plano-implantacao-vps-agente-v2.md)

## Licença

MIT License - see [LICENSE](LICENSE) for details.