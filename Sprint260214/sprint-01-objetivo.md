# 🎯 Sprint: De Infraestrutura Para Capacidade

## Uma Frase

**Transformar o AgentVPS de um agente que fala sobre o que pode fazer em um agente que faz.**

---

## O Problema

O AgentVPS tem 11.871 linhas de código de infraestrutura (grafo LangGraph, security allowlist, circuit breaker, structured logging, health check doctor, prompt composer, LLM provider abstraction) mas apenas **5 tools hardcoded** que fazem coisas reais: checar RAM, listar containers, status do sistema, ping PostgreSQL, ping Redis.

Quando um usuário pede "liste meus projetos no GitHub" ou "busque informações sobre X na internet", o agente responde com um plano do que *seria necessário* para fazer isso — mas não faz.

A avaliação técnica de fevereiro 2026 deu nota **3/10 em funcionalidade** e **8/10 em arquitetura**. O diagnóstico é claro: chassi de Ferrari, motor de Fusca.

---

## O Objetivo Desta Sprint

Ao final desta sprint, o AgentVPS deve ser capaz de:

1. **Executar comandos shell** arbitrários na VPS (com classificação de segurança e approval para comandos perigosos)
2. **Ler, criar e editar arquivos** no filesystem (com paths permitidos)
3. **Buscar informações na internet** via API de busca
4. **Consultar sua própria memória** (PostgreSQL + learnings)
5. **Adicionar novas skills** sem editar código hardcoded — via registry dinâmico
6. **Propor ações proativamente** — não apenas reagir a mensagens

Isso significa que perguntas como "quanta RAM livre?" continuam funcionando, mas agora também funcionam:
- "Quais arquivos existem em /opt/vps-agent/configs?"
- "Busque na internet como instalar Node.js 22 no Ubuntu"
- "Crie um arquivo /tmp/teste.txt com o conteúdo 'hello world'"
- "Execute 'docker ps -a' e me diga o resultado"

---

## O Que Esta Sprint NÃO É

- **Não é reescrita.** Usamos a infraestrutura existente (grafo, gateway, security, logging).
- **Não é Qdrant/RAG.** Memória semântica fica para depois.
- **Não é multi-agent.** Um agente, fazendo coisas reais.
- **Não é WhatsApp/Evolution API.** Telegram continua sendo o canal.
- **Não é migração para OpenClaw.** Continuamos com AgentVPS.

---

## Métricas de Sucesso

| Métrica | Antes | Depois | Como Medir |
|---|---|---|---|
| Tools funcionais | 5 (hardcoded) | 10+ (via registry) | `agent-cli skills list` |
| Comandos shell executáveis | 0 | Qualquer (com approval) | Enviar "execute ls -la" no Telegram |
| Busca web funcional | 0 | 1 (Brave Search) | Enviar "busque X" no Telegram |
| Operações de arquivo | 0 | CRUD completo | Enviar "leia /etc/hostname" no Telegram |
| Código para adicionar skill | ~4 arquivos, ~100 linhas | 1 arquivo, ~30 linhas | Criar skill de teste |
| Ações proativas/dia | 0 | 1+ (heartbeat detecta problemas) | Verificar tabela agent_proposals |
| Tempo para adicionar skill | ~2h (editar 4 arquivos) | ~15min (criar handler) | Cronometrar |

---

## Restrições Inegociáveis

1. **RAM total: 2.4 GB** — Nenhuma skill pode consumir mais de 100MB
2. **Segurança: approval para dangerous** — Comandos destrutivos SEMPRE pedem confirmação via Telegram
3. **Sem execução cega** — O agente NUNCA roda código que ele mesmo gerou sem sandbox/approval
4. **Backward compatible** — Tudo que funciona hoje continua funcionando
5. **Testes para cada skill** — Nenhuma skill entra sem pelo menos 1 teste

---

## Contexto Técnico (Para Não Perder)

### Arquivos-chave que serão modificados:
- `core/tools/system_tools.py` → Será refatorado para usar Skill Registry
- `core/vps_langgraph/nodes.py` → `node_execute` será simplificado para delegar ao registry
- `core/vps_langgraph/smart_responses.py` → Será alimentado pelo registry em vez de SKILL_GUIDE hardcoded
- `configs/init-db.sql` → Novas tabelas para autonomous loop

### Arquivos-chave que NÃO serão modificados:
- `core/vps_langgraph/graph.py` → O grafo está correto, não mexer
- `core/security/allowlist.py` → Expandir, não reescrever
- `core/vps_langgraph/state.py` → Adicionar campos, não remover
- `core/config.py` → Adicionar settings, não alterar existentes

### Stack confirmada:
- Python 3.12, LangGraph 0.2+, FastAPI, PostgreSQL 16, Redis 7
- LLM: Google Gemini 2.5 Flash Lite via OpenRouter (default, grátis)
- Interface: Telegram (@Molttaitbot)
- CI/CD: GitHub Actions (pytest + ruff)

---

## Dependências Entre as Fases

```
S1 (Skill Registry) ──────────────────┐
    │                                  │
    ├── S2 (5 Skills Core) ────────────┤
    │       │                          │
    │       ├── S2.1 shell-exec        │
    │       ├── S2.2 file-manager      │
    │       ├── S2.3 web-search        │
    │       ├── S2.4 memory-query      │
    │       └── S2.5 self-edit         │
    │                                  │
S3 (Cleanup código morto) ─────────────┤
    │                                  │
S4 (Autonomous Loop) ─────────────────┘
    │
    ├── Tabelas PostgreSQL
    ├── Heartbeat worker
    └── Cap Gates (usa allowlist existente)
```

S1 é pré-requisito de tudo. S2 e S3 podem ser paralelos. S4 depende de S2 (precisa de skills para executar missões).
