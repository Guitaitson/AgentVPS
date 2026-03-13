# Guia de Contribuição — AgentVPS

> **⚠️ IMPORTANTE:** Antes de contribuir, leia todos os documentos em [`docs/`](docs/) e [`docs/adr/`](docs/adr/).

## 📚 Documentação Obrigatória

Antes de iniciar qualquer contribuição, **você DEVE** ler:

| Documento | Por Que Ler | Tempo |
|----------|------------|-------|
| [`README.md`](README.md) | Visão geral do projeto | 5 min |
| [`docs/GIT_GOVERNANCE.md`](docs/GIT_GOVERNANCE.md) | Branch, PR, release e deploy | 10 min |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Arquitetura e fluxos | 15 min |
| [`docs/adr/README.md`](docs/adr/README.md) | Decisões arquiteturais | 10 min |
| [`.kilocode/rules/memory-bank/brief.md`](.kilocode/rules/memory-bank/brief.md) | Estado atual e próximos passos | 5 min |
| [`.kilocode/rules/vps-agent-rules.md`](.kilocode/rules/vps-agent-rules.md) | Regras obrigatórias do projeto | 5 min |

## 🚀 Quick Start

### 1. Setup do Ambiente

```bash
# Clonar o repositório
git clone https://github.com/Guitaitson/AgentVPS.git
cd AgentVPS

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Instalar dependências de desenvolvimento
pip install pytest pytest-asyncio ruff

# Verificar instalação
pytest --version
ruff --version
```

### 2. Verificar Status dos Serviços

```bash
# Docker deve estar rodando
docker ps

# PostgreSQL deve estar acessível
psql -h localhost -U postgres -c "SELECT 1"

# Redis deve estar acessível
redis-cli ping
```

### 3. Rodar Testes

```bash
# Rodar todos os testes
pytest -v

# Rodar testes específicos
pytest tests/test_gateway.py -v
pytest tests/test_circuit_breaker.py -v

# Rodar com coverage
pytest --cov=core --cov-report=term-missing
```

### 4. Verificar Lint

```bash
# Rodar linter
ruff check .

# Verificar formatação (opcional)
ruff check . --fix  # Auto-corrigir erros
```

## 📋 Checklist de Contribuição

Para **cada contribuição**, verifique:

- [ ] **Branch** criada a partir de `main` atual
- [ ] **PR** aberta para `main` antes de pensar em deploy
- [ ] **Release** só sera publicada depois do merge em `main`
- [ ] **Documentei** a mudança em `docs/adr/` (se for decisão arquitetural)
- [ ] **Atualizei** `deployment-tracker.md` com o progresso
- [ ] **Atualizei** `brief.md` se mudou o estado atual
- [ ] **Rodei** `pytest -v` e todos os testes passaram
- [ ] **Rodei** `ruff check .` e não há erros
- [ ] **Rodei** `python scripts/audit_git_governance.py`
- [ ] **Commit** tem descrição clara seguindo [Conventional Commits](#-convenções-de-commit)

## Governança Git e GitHub

Fluxo oficial:

1. sincronizar com `origin/main`
2. criar branch curta de trabalho
3. implementar e validar localmente
4. abrir PR para `main`
5. mergear apenas com CI verde
6. publicar GitHub Release com tag semântica
7. deixar o workflow de release fazer o deploy na VPS

Regras:

- `main` e a unica branch de producao
- nunca deployar branch temporaria como estado final da VPS
- nunca publicar release de commit que ainda nao entrou em `main`
- limpar branches locais `gone` ou `ahead` depois do merge

## 🏗️ Estrutura do Projeto

```
AgentVPS/
├── core/                    # Código principal
│   ├── gateway/             # FastAPI + adapters (Telegram, webhooks)
│   ├── llm/                # Providers LLM (OpenRouter, Anthropic)
│   ├── security/           # Allowlist, autenticação
│   ├── resilience/         # Circuit breaker, retry
│   ├── health_check/       # Doctor, health checks
│   ├── structured_logging/ # JSON logs
│   ├── capabilities/        # Registro de capacidades
│   ├── resource-manager/   # Gerenciamento de recursos
│   └── vps_langgraph/      # Agente LangGraph
├── telegram-bot/            # Bot Telegram
├── tests/                  # Testes unitários
├── configs/                # Docker Compose, environment
├── scripts/                # Scripts de automação
├── docs/                   # Documentação
│   └── adr/               # Architecture Decision Records
└── .kilocode/
    └── rules/             # Memory Bank (Contexto para IA)
```

## 🔧 Adicionando Nova Feature

### Passo 1: Criar ADR (Se mudar arquitetura)

```bash
# Criar novo ADR
cp docs/adr/000-template.md docs/adr/XXX-descricao.md
```

### Passo 2: Implementar

1. Criar código em `core/` seguindo padrões existentes
2. Adicionar testes em `tests/`
3. Documentar em `docs/` se necessário

### Passo 3: Atualizar Contexto

```markdown
# Em .kilocode/rules/memory-bank/brief.md
## Estado Atual
- [x] Nova feature implementada

# Em .kilocode/rules/memory-bank/deployment-tracker.md
Adicionar linha na tabela de progresso
```

## 🧪 Testes

### Tipos de Testes

| Tipo | Local | Objetivo |
|------|-------|----------|
| Unit | `tests/test_*.py` | Testar funções individuais |
| Integration | `tests/test_*` | Testar integrações |
| E2E | `test_*.py` | Testar fluxo completo |

### Rodar Testes Específicos

```bash
# Testes de Circuit Breaker
pytest tests/test_circuit_breaker.py -v

# Testes de Gateway
pytest tests/test_gateway.py -v

# Testes de Health Check
pytest tests/test_health_check.py -v

# Testes de Prompt Composer
pytest tests/test_prompt_composer.py -v

# Todos os testes
pytest -v --tb=short
```

## 📝 Convenções de Commit

Formato: `<tipo>(<escopo>): <descrição>`

### Tipos

| Tipo | Descrição |
|------|-----------|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `docs` | Mudança em documentação |
| `style` | Formatação de código |
| `refactor` | Refatoração |
| `test` | Adição/modificação de testes |
| `chore` | Tarefas de manutenção |
| `ci` | Mudanças no CI/CD |
| `adr` | Nova decisão arquitetural |

### Exemplos

```
feat(gateway): Adiciona rate limiting por usuário
fix(circuit-breaker): Corrige timeout não funcionando
docs(adr): Adiciona ADR-005 sobre cache strategy
ci: Remove black do workflow
refactor(llm): Simplifica provider abstraction
test(health): Adiciona teste para PostgreSQL
```

## 🔒 Regras de Ouro

**NUNCA violar:**

1. **NÃO executar comandos destrutivos** sem confirmação
   - `rm -rf`, `DROP TABLE`, `docker system prune` → SEMPRE pedir confirmação

2. **SEMPRE verificar RAM** antes de subir container
   ```bash
   free -m | grep Mem
   # Se < 300 MB disponível, NÃO subir nada
   ```

3. **NÃO hardcodar credenciais**
   - Tudo via `.env` ou Docker secrets

4. **SEMPRE testar** após cada alteração
   - `pytest -v` e `ruff check .`

5. **SEMPRE auditar o estado Git/GitHub** antes de push importante e antes de release
   - `python scripts/audit_git_governance.py`

6. **Uma tarefa por vez**
   - Completar subtarefa atual antes de começar outra

7. **NÃO inventar soluções complexas**
   - Se a instrução diz "copiar e colar", copiar e colar

8. **Moltbot NÃO faz parte deste projeto**
   - Remover qualquer referência

## 📖 Recursos para IA/Agentes

Se você é um **agente IA** (Claude, Cline, Kilocode, etc.):

1. **Leia o Memory Bank primeiro**
   ```bash
   cat .kilocode/rules/memory-bank/brief.md
   cat .kilocode/rules/memory-bank/deployment-tracker.md
   cat .kilocode/rules/memory-bank/project-context.md
   ```

2. **Verifique estado atual**
   - Qual fase está completa?
   - Qual job está em andamento?
   - Quais são os critérios de saída?

3. **Siga as regras**
   - `.kilocode/rules/vps-agent-rules.md` tem regras obrigatórias

4. **Documente progresso**
   - Atualize `brief.md` após cada subtarefa
   - Atualize `deployment-tracker.md` quando completar jobs

## 🆘 Problemas Comuns

### Testes falhando

```bash
# Verificar dependências
pip install -r requirements.txt

# Limpar cache
rm -rf __pycache__ .pytest_cache

# Rodar com mais detalhes
pytest -v --tb=long
```

### Lint errors

```bash
# Verificar instalação do ruff
pip install ruff

# Auto-corrigir
ruff check . --fix

# Verificar manualmente
ruff check . --show-source
```

### Docker não rodando

```bash
# Verificar status
docker ps

# Verificar logs
docker logs <container_name>

# Reiniciar serviços
docker compose -f configs/docker-compose.core.yml up -d
```

## 📞 Suporte

- **Issues:** https://github.com/Guitaitson/AgentVPS/issues
- **CI/CD:** https://github.com/Guitaitson/AgentVPS/actions
- **VPS:** configure no seu ambiente privado (`SEU_HOST_VPS`)

---

**⚡ LEMBRE-SE:** Documentação desatualizada é pior que ausência de documentação. **SEMPRE** atualize os documentos quando:
- Completar uma tarefa
- Tomar uma decisão arquitetural
- Encontrar um problema e a solução
- Mudar o estado do projeto
