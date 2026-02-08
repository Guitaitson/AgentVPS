# Architecture Decision Records (ADRs)

> **⚠️ IMPORTANTE:** Leia [`CONTRIBUTING.md`](CONTRIBUTING.md) antes de criar novos ADRs.

## 📚 Índice de ADRs

| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [000](000-template.md) | Template ADR | Template | - |
| [001](001-memory-strategy.md) | Estratégia de Memória Multi-Camada | Aceito | 2026-02-06 |
| [002](002-llm-abstraction.md) | Abstração de Providers LLM | Aceito | 2026-02-06 |
| [003](003-circuit-breaker.md) | Circuit Breaker Pattern | Aceito | 2026-02-07 |
| [004](004-langgraph-orchestration.md) | Orquestração com LangGraph | Aceito | 2026-02-07 |
| [005](005-rate-limiting.md) | Rate Limiting no Gateway | Aceito | 2026-02-08 |

## 📖 O Que é um ADR?

ADR (Architecture Decision Record) é um documento que registra uma **decisão arquitetural significativa** tomada durante o desenvolvimento do projeto.

Cada ADR inclui:
- **Contexto** — Por que a decisão foi necessária
- **Decisão** — O que foi decidido
- **Consequências** — Prós e contras da decisão
- **Status** — Proposto, Aceito ou Depreciado

## 📝 Como Criar um Novo ADR

### Passo 1: Copiar o Template

```bash
cp docs/adr/000-template.md docs/adr/XXX-descricao.md
```

### Passo 2: Preencher o ADR

Preencha todas as seções:
- **Número** — Próximo número sequencial
- **Título** — Descrição clara da decisão
- **Status** — Proposto inicialmente
- **Contexto** — Situação que motivou a decisão
- **Decisão** — O que foi decidido (com detalhes técnicos)
- **Consequências** — Prós, contras, trade-offs
- **Status** — Atualize para "Aceito" após review

### Passo 3: Criar Pull Request

1. Criar branch: `feat/adr-XXX-descricao`
2. Adicionar ADR
3. Atualizar `deployment-tracker.md` com referência
4. Criar PR para review

## 🔄 Atualizando ADRs

Quando uma decisão arquitetural mudar:

1. **Criar novo ADR** referenciando o anterior
2. Marcar ADR anterior como **Depreciado**
3. Explicar por que a decisão mudou
4. Documentar migração se necessário

Exemplo:

```markdown
## Status

⚠️ **DEPRECADO** — Ver [ADR-006](006-nova-decisao.md)

Substituído por ADR-006 devido a...
```

## 🏷️ Convenções

### Prefixos

| Prefixo | Significado |
|---------|-------------|
| `[PENDING]` | Aguardando decisão |
| `[PROPOSED]` | Proposto, em discussão |
| `[ACCEPTED]` | Aceito e em vigor |
| `[DEPRECATED]` | Substituído por outro |
| `[SUPERSEDED]` | Atualizado por outro |

### Nomenclatura

```bash
# ✅ Bom
docs/adr/001-memory-strategy.md
docs/adr/002-llm-abstraction.md
docs/adr/003-circuit-breaker.md

# ❌ Ruim
docs/adr/ADR-001.md
docs/adr/memory.md
docs/adr/001.md
```

## 📊 Estatísticas

| Métrica | Valor |
|---------|-------|
| Total de ADRs | 5 |
| Aceitos | 5 |
| Depreciados | 0 |
| Propostos | 0 |

## 🔗 Referências

- [ADR GitHub Repo](https://github.com/joelparkerhenderson/architecture-decision-record)
- [MADR Template](https://github.com/adr/madr)
- [Sustainable Architectural Decisions](https://www.infoq.com/articles/sustainable-architectural-decisions/)

---

**⚡ LEMBRE-SE:** Cada mudança arquitetural significativa DEVE ter um ADR. Documentação desatualizada causa confusão e retrabalho.
