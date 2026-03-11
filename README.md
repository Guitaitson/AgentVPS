# AgentVPS

[![CI/CD](https://github.com/Guitaitson/AgentVPS/actions/workflows/ci.yml/badge.svg)](https://github.com/Guitaitson/AgentVPS/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Agente autônomo que roda em uma VPS de baixo custo (~2 GB RAM), controlado via Telegram. Usa LangGraph com padrão ReAct, function calling real, e se integra ao OpenClaw para orquestração de sub-agentes.

---

## Visão Geral

```
Você (Telegram)
     │
     ▼
AgentVPS — LangGraph 7 nós — PostgreSQL + Redis
     │
     ▼ (skill openclaw_exec)
OpenClaw — sub-agente Node.js
```

**AgentVPS** é o orquestrador. Recebe mensagens, decide com LLM (ReAct + function calling), executa skills, e opcionalmente delega tarefas ao **OpenClaw** via docker exec.

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Orquestração | LangGraph (Python 3.11+) |
| LLM | MiniMax M2.5 via OpenRouter |
| Interface | Telegram Bot (python-telegram-bot) |
| Memória Estruturada | PostgreSQL 16 + Redis 7 |
| Containers | Docker + Docker Compose v2 |
| Sub-agente | OpenClaw (Node.js, `repo-openclaw-gateway-1`) |

---

## Arquitetura do Grafo (7 nós)

```
START → load_context → react → security_check → execute → format_response → respond → save_memory → END
                          └──────────────────────────────────────────────────────────┘ (resposta direta)
```

- **react**: LLM decide entre tool_call (→ security_check) ou resposta direta (→ respond)
- **security_check**: verifica allowlist antes de executar qualquer skill
- **execute**: roda a skill via registry + hook system (logging, feedback, learning)
- **format_response**: LLM formata o resultado em linguagem natural

---

## Skills Disponiveis (19)

| Skill | Descrição | Nível |
|-------|-----------|-------|
| `shell_exec` | Executa comandos shell na VPS | dangerous |
| `get_ram` | Uso de memória RAM | safe |
| `list_containers` | Lista containers Docker | safe |
| `get_system_status` | Status geral da VPS | safe |
| `check_postgres` | Health do PostgreSQL | safe |
| `check_redis` | Health do Redis | safe |
| `file_manager` | Lê/escreve arquivos | normal |
| `memory_query` | Consulta memória persistida | safe |
| `web_search` | Busca na web (fallback DuckDuckGo) | normal |
| `fleetintel` | Consulta eventos e dados de frota via FleetIntel MCP | normal |
| `fleetintel_analyst` | Analise comercial via FleetIntel MCP (signals, trends, market share) | safe |
| `brazilcnpj` | Enriquecimento cadastral e societario via BrazilCNPJ MCP | safe |
| `fleetintel_orchestrator` | Cruza FleetIntel + BrazilCNPJ numa resposta unica | safe |
| `self_edit` | Auto-edição de código | dangerous |
| `log_reader` | Lê logs da VPS | safe |
| `openclaw_exec` | Controla OpenClaw via docker exec | dangerous |
| `skills_catalog_sync` | Sync/pin/rollback/provenance do catalogo externo | normal |
| `voice_context_sync` | Processa inbox de audio, mostra status e comita contexto de voz | normal |
| `execute_scheduled` | Executa acoes agendadas (notify/catalog apply/context sync) | dangerous |

Skills com `dangerous` requerem aprovação humana (configurável via `on-dangerous`).

Os especialistas `fleetintel_analyst`, `brazilcnpj` e `fleetintel_orchestrator` usam MCP remoto autenticado e sao escolhidos automaticamente quando a pergunta pede inteligencia de frota, enriquecimento CNPJ ou cruzamento dos dois dominios.

---

## Segurança

- **Allowlist**: apenas comandos aprovados são executados (`core/security/allowlist.py`)
- **Tool Policy**: skills `dangerous` exigem `/approve` do usuário via Telegram
- **Anti-injection**: output do OpenClaw é marcado como `[DADO EXTERNO]` antes de passar ao LLM
- **Usuários autorizados**: `TELEGRAM_ALLOWED_USERS` define quem pode interagir
- **API keys**: nunca em código — apenas em `.env` (excluído do git)

---

## Quick Start

### Pré-requisitos

- VPS com Debian/Ubuntu, ~2 GB RAM, Docker instalado
- Conta OpenRouter: [openrouter.ai](https://openrouter.ai)
- Bot Telegram: criar em [@BotFather](https://t.me/BotFather)

### 1. Clonar

```bash
git clone https://github.com/Guitaitson/AgentVPS.git
cd AgentVPS
```

### 2. Configurar Variáveis

```bash
cp configs/.env.example /opt/vps-agent/.env
nano /opt/vps-agent/.env  # preencher credenciais reais
```

### 3. Subir Containers

```bash
docker compose -f configs/docker-compose.core.yml up -d
```

### 4. Instalar Python e Dependências

```bash
python3 -m venv /opt/vps-agent/core/venv
/opt/vps-agent/core/venv/bin/pip install -e ".[dev]"
# se for habilitar transcricao local de audio na VPS:
/opt/vps-agent/core/venv/bin/pip install -e ".[voice]"
```

### 5. Aplicar Schema do Banco

```bash
docker exec -i vps-postgres psql -U vps_agent -d vps_agent < configs/init-db.sql
docker exec -i vps-postgres psql -U vps_agent -d vps_agent < configs/migration-autonomous.sql
docker exec -i vps-postgres psql -U vps_agent -d vps_agent < configs/migration-voice-context.sql
```

### 6. Instalar e Iniciar Serviços Systemd

```bash
sudo cp configs/telegram-bot.service /etc/systemd/system/
sudo cp configs/mcp-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-bot mcp-server
```

### 7. Verificar

```bash
sudo systemctl status telegram-bot mcp-server
sudo tail -f /opt/vps-agent/logs/telegram-bot.log
```

## Fluxo de Entrega

O fluxo recomendado para manter GitHub, PRs e VPS sincronizados e auditaveis e:

1. criar branch de trabalho a partir de `main`
2. abrir PR para `main`
3. mergear apenas depois do CI verde
4. publicar uma release no GitHub
5. deixar o workflow `.github/workflows/release-deploy.yml` fazer o deploy na VPS

Enquanto o deploy automatico por release nao for o caminho exclusivo, qualquer deploy manual deve terminar com a VPS alinhada em `main`, nao em branch temporaria.

O deploy automatico por release nao reinicia o AgentVPS no meio de trabalho critico. O script `scripts/deploy_release.sh` adia a tentativa quando detecta:
- transcricao/ingestao de voz em andamento
- missions em execucao
- proposals em estado `executing`
- tarefas agendadas rodando
- blockers manuais em `runtime/deploy-blockers`

Para o acervo externo, a estrategia e diferente: skills/tools/agentes entram por catalog sync com proposal/approval, sem substituir automaticamente o core do AgentVPS.

---

## Estrutura de Diretórios

```
AgentVPS/
├── core/
│   ├── autonomous/         # Loop autônomo (6 triggers, cap gates, proposals)
│   ├── capabilities/       # Registro de capacidades
│   ├── database/           # Conexão PostgreSQL
│   ├── gateway/            # API REST FastAPI
│   ├── health_check/       # Health monitoring
│   ├── hooks/              # Hook system (logging, feedback, learning)
│   ├── llm/                # Provider OpenRouter unificado
│   ├── security/           # Allowlist de comandos
│   ├── skills/             # Skill registry + 15 skills builtin
│   │   └── _builtin/       # handler.py + config.yaml por skill
│   ├── structured_logging/ # JSON logging com structlog
│   ├── vps_agent/          # Orquestração principal
│   ├── vps_langgraph/      # Grafo LangGraph 7 nós
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   ├── react_node.py   # ReAct com function calling
│   │   └── state.py
│   └── mcp_server.py       # Model Context Protocol server
├── telegram_bot/
│   └── bot.py              # Bot + /approve, /reject, /proposals
├── configs/
│   ├── .env.example        # Template de variáveis (sem credenciais reais)
│   ├── docker-compose.core.yml
│   ├── init-db.sql
│   ├── migration-autonomous.sql
│   ├── telegram-bot.service
│   └── mcp-server.service
├── tests/                  # Testes unitários e integração
├── docs/                   # Documentação técnica
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── adr/                # Architecture Decision Records
├── Sprint260214/            # Docs Sprint 01
├── Sprint260215/            # Docs Sprints 02-09
└── archive/                # Documentos obsoletos arquivados
```

---

## Variáveis de Ambiente

Ver `configs/.env.example` para a lista completa. Mínimo necessário:

```env
TELEGRAM_BOT_TOKEN=...        # Token do BotFather
TELEGRAM_ALLOWED_USERS=...    # IDs separados por vírgula
POSTGRES_PASSWORD=...         # Senha PostgreSQL
OPENROUTER_API_KEY=...        # Chave OpenRouter
OPENROUTER_MODEL=minimax/minimax-m2.5
FLEETINTEL_MCP_TOKEN=...      # Token do FleetIntel MCP
BRAZILCNPJ_MCP_TOKEN=...      # Token do BrazilCNPJ MCP
```

---

## Captura de Contexto por Voz

- Inbox operacional na VPS: `/opt/vps-agent/data/voice/inbox`
- Processamento: transcricao local opcional com `faster-whisper` via extra `.[voice]`
- Memoria derivada: `episodic`, `semantic`, `profile`, `goals` com auto-commit de baixo risco e proposals para itens sensiveis
- Companion Windows: `desktop_companion/windows/voice_device_watcher.ps1` para detectar o gravador e enviar os arquivos via `scp`

## Comandos Telegram

| Comando | Descrição |
|---------|-----------|
| `/start` | Iniciar conversa |
| `/status` | Status da VPS |
| `/proposals` | Ver proposals pendentes |
| `/approve <id>` | Aprovar proposal |
| `/reject <id>` | Rejeitar proposal |
| `/catalogsync <cmd>` | check/apply/pin/unpin/rollback/provenance do catalogo |
| `/runtimes [list|enable|disable]` | Gerenciar runtime adapters externos |
| `/contextsync` | Processar audios pendentes na inbox de voz |
| `/contextstatus` | Ver status do pipeline de voz, inbox e revisoes |
| `/updatestatus` | Status do updater e ultimo catalog sync |

---

## Histórico de Sprints

| Sprint | Foco | Status |
|--------|------|--------|
| 01 — Foundation | Logging, checkpointing, async tools, singleton | ✅ |
| 02 — ReAct Design | Arquitetura ReAct + function calling projetada | ✅ |
| 03 — ReAct Impl | Grafo 7 nós, hook system, remoção dead code | ✅ |
| 04 — Memory | Persistência PostgreSQL, auto-consciência | ✅ |
| 05 — Intelligence | Destravar inteligência do agente | ✅ |
| 06 — Stability | State reset, resultado vazio, proatividade | ✅ |
| 07 — Formatting | Formatação inteligente, web search fallback | ✅ |
| 08 — Consciousness | Aprendizado real, proatividade avançada | ✅ |
| 09 — OpenClaw | Integração OpenClaw, self-edit, anti-injection | ✅ |

---

## Documentação

- [Índice da documentação](docs/README.md)
- [Status atual consolidado](docs/PROJECT_STATUS.md)
- [Arquitetura detalhada](docs/ARCHITECTURE.md)
- [Guia de Deploy](docs/DEPLOYMENT.md)
- [ADRs — Decisões de Arquitetura](docs/adr/README.md)
- [Contribuição](CONTRIBUTING.md)

## Licença

MIT — see [LICENSE](LICENSE).

