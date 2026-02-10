# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado
- Gateway FastAPI com endpoints REST
- Sistema de allowlist de segurança
- Circuit breaker para resiliência
- Health check modular
- Rate limiter no gateway
- Session manager para estado de conversas

### Mudado
- Estrutura de pacotes reorganizada (Fase 0.5)
- CI/CD modernizado para usar `pip install -e ".[dev]"`
- Imports padronizados sem `sys.path.insert`

## [2.0.0] - 2025-02-09

### Fase 0.5 — Foundation e Estrutura ✅

#### Resumo
Reestruturação completa da base de código para seguir padrões profissionais Python, eliminando anti-padrões e estabelecendo foundation sólida para evolução.

#### Mudanças

**Estrutura de Pacotes**
- `telegram-bot/` → `telegram_bot/` (PEP 8)
- `resource-manager/` → `core/resource_manager/`
- Adicionado `pyproject.toml` como pacote Python profissional
- Scripts de entry point configurados:
  - `vps-agent` → `telegram_bot.bot:main`
  - `vps-mcp` → `core.mcp_server:main`
  - `vps-gateway` → `core.gateway.main:run_server`

**Qualidade de Código**
- 1.202 erros de lint (W293) corrigidos
- 158 erros em docstrings corrigidos
- 43 arquivos formatados com ruff
- Configuração ruff em `pyproject.toml`:
  - Target: Python 3.12
  - Line length: 100
  - Select: F, E, W, I, N

**CI/CD**
- Workflow atualizado para `pip install -e ".[dev]"`
- Testes em Python 3.11 e 3.12
- Lint e format check com ruff
- Docker build e security scan com Trivy
- Release automático em pushes para main

**Scripts de Deploy**
- `scripts/deploy.sh` — deploy local e status
- `scripts/deploy-vps.sh` — deploy na VPS
- `scripts/setup-vps.sh` — setup inicial da VPS
- Todos atualizados para novo structure

#### Commits
- `dcee9a0` — Correções finais de imports e estrutura
- `3a2ac13` — CI/CD e scripts atualizados
- `6a1fe74` — Reorganização inicial de pacotes

---

## [1.9.0] - 2025-02-08

### Fase 0 — Estabilização v1 ✅

- Cleanup de código (duplicatas removidas)
- Fix Graph Flow self_improve
- Fix timezone import
- Telegram Log Handler implementado
- Testes end-to-end (5/5 passaram)

---

## Roadmap Preview

### Fase 1.0 — Documentação e Sync VPS 🔄
- [ ] Atualizar docs/ARCHITECTURE.md
- [ ] Sync VPS via SSH
- [ ] CHANGELOG.md criado ✅

### Fase 1.1 — Connection Pooling Async
- asyncpg com pool de conexões
- AgentMemory async

### Fase 1.2 — Allowlist no Grafo
- Nó de segurança no LangGraph
- Bloqueio de comandos perigosos

### Fase 1.3 — Gateway Auth Real
- API Key via environment variable
- Remover modo "development:unauthenticated"

---

## Como Contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes sobre como contribuir para o projeto.

## Referências

- [Plano de Implementação](plans/plano-implementacao-vps-agente-v2.md)
- [Deployment Tracker](plans/deployment-tracker.md)
- [ADR Index](docs/adr/README.md)