# Changelog

Baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).
Adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [Unreleased] — Sprint 09: Integração OpenClaw + Hardening

### Adicionado
- **Skill `openclaw_exec` v2.0.0**: controla OpenClaw via `docker exec repo-openclaw-gateway-1 node /app/dist/entry.js`
  - Ações: `health`, `status`, `agent`, `agents`, `channels`, `approvals`
  - Substituiu abordagem CLI quebrada (binário não existe no host)
- **Anti-prompt-injection**: output do OpenClaw envolvido com marcadores `[DADO EXTERNO OPENCLAW]`
- **Skill `log_reader`**: leitura de logs da VPS
- **Skill `notify_handler`**: notificações via Telegram
- **Auto-planejamento**: trigger autônomo para manutenção proativa
- **Self-edit real**: skill `self_edit` com validação de patch antes de aplicar

### Alterado
- Modelo LLM: `minimax/minimax-m2.5` (padrão para AgentVPS e OpenClaw)
- `OPENROUTER_MAX_TOKENS`: 256 → 2048
- `OPENROUTER_TIMEOUT`: 10 → 30 segundos
- `.env.example`: sanitizado (sem tokens reais, valores de produção corrigidos)

### Corrigido
- `openclaw_exec`: handler reescrito — subprocess CLI (FileNotFoundError) → docker exec correto
- Config do modelo no `.env`: removido `google/gemini-2.5-flash-lite` que alucinou código Python

### Segurança
- Token Telegram removido de `archive/plans/` e `.env.example`
- Separação de API keys por serviço (AgentVPS e OpenClaw com chaves independentes)

---

## [3.0.0] — Sprint 08: Consciência e Aprendizado Real

### Adicionado
- Aprendizado real: erros registrados no PostgreSQL via `learning_hook`, consultados antes de repetir
- Proatividade avançada: Engine detecta padrões de uso e propõe melhorias
- Consciência de estado: agente ciente do próprio histórico de execuções

---

## [2.9.0] — Sprint 07: Formatação e Busca Web

### Adicionado
- Formatação inteligente: resposta adaptada ao tipo de conteúdo (código, lista, texto)
- Web search fallback: DuckDuckGo quando OpenRouter não tem info recente
- Contexto temporal: agente ciente da data/hora atual

---

## [2.8.0] — Sprint 06: Estabilidade e Correções

### Corrigido
- State reset entre conversas (vazamento de contexto entre usuários)
- Resultado vazio não mais exibido ao usuário
- Proatividade não mais disparada em conversas normais

### Alterado
- Modelo: MiniMax M2.5 via OpenRouter

---

## [2.7.0] — Sprint 05: Inteligência Desbloqueada

### Adicionado
- ReAct loop multi-step: agente executa múltiplas tools por mensagem quando necessário
- Self-awareness: agente conhece suas próprias skills e limitações

### Corrigido
- Security check bloqueando tools legítimas (tipo `"tool"` agora permitido)
- Response preservada em casos de execução sem resultado

---

## [2.6.0] — Sprint 04: Memória e Observabilidade

### Adicionado
- Persistência de memória no PostgreSQL (fatos do usuário, histórico de conversas)
- Self-awareness: agente carrega contexto de sessões anteriores
- Observabilidade: métricas de execução em cada nó do grafo

### Alterado
- `AgentMemory` migrado para PostgreSQL com fallback graceful

---

## [2.5.0] — Sprint 03: Arquitetura ReAct

### Adicionado
- **Grafo LangGraph de 7 nós**: `load_context → react → security_check → execute → format_response → respond → save_memory`
- **Hook system** (`core/hooks/runner.py`): pre/post hooks para skills
  - `logging_hook`: timing e structured logging
  - `feedback_pre_hook`: consulta learnings antes de executar
  - `learning_hook`: registra erros no PostgreSQL
- **6 triggers autônomos** com condições reais (era 5 lambdas retornando True)
- Comandos Telegram: `/proposals`, `/approve <id>`, `/reject <id>`

### Removido
- `core/tools/system_tools.py` (426 linhas de dead code)
- `core/vps_langgraph/intent_classifier.py` (42 linhas — substituído por LLM)
- `core/vps_agent/semantic_memory.py` (9 linhas — arquivo vazio)
- Nós deletados do grafo: `node_classify_intent`, `node_plan`, `node_check_capabilities`, `node_self_improve`, `node_implement_capability`

### Alterado
- `react_node.py` substitui todo o fluxo heurístico por LLM com function calling

---

## [2.0.0] — Sprints 01-02: Foundation

### Sprint 02 — ReAct Design

- Arquitetura ReAct + function calling projetada e documentada
- Skill Registry com auto-discovery via `config.yaml + handler.py`
- Avaliações v3 e v4 com design decisions

### Sprint 01 — Estabilização

- Logging estruturado (structlog) em todos os nós do grafo
- Checkpointing PostgreSQL no LangGraph com fallback MemorySaver
- Async tools via `asyncio.to_thread()` (Python 3.9+)
- Singleton do grafo via `get_agent_graph()` para performance
- Thread ID por usuário para persistência de conversa

---

## [1.9.0] — Fase 0.5: Foundation e Estrutura

- Eliminação de todos `sys.path.insert` → pacote Python profissional
- Reorganização: `telegram-bot/` → `telegram_bot/`, etc.
- CI/CD com `pip install -e ".[dev]"`
- 1.202 erros lint corrigidos (ruff)
- Todos commits verdes no CI ✅

---

## [1.0.0] — Fase 0: Estabilização v1

- Cleanup de código e remoção de duplicatas
- Telegram Log Handler
- Testes end-to-end (5/5 passaram)
