# Plano de Estabilização v1.5 — AgentVPS

> **Baseado na consultoria Opus 4.6**  
> **Data:** 08/02/2026  
> **Objetivo:** Estabilizar v1 e preparar v2

---

## 🎯 Princípios Fundamentais

### Contexto Persistente

Este documento é a **fonte única da verdade** para o estado do projeto. Todas as decisões, arquitetura e roadmap estão documentados aqui.

**Arquivos de Contexto (leia primeiro):**
- `.kilocode/rules/memory-bank/project-context.md` — Contexto centralizado
- `.kilocode/rules/memory-bank/brief.md` — Estado atual
- `.kilocode/rules/memory-bank/deployment-tracker.md` — Progresso

### Documentação Robusta

Todo código, feature ou decisão deve ter:
1. **Docstrings** em todas as funções públicas
2. **Comentários** explicando o "porquê", não o "quê"
3. **CHANGELOG.md** atualizado após cada mudança significativa
4. **README.md** refletindo o estado atual

---

## 📊 Estado Atual

### O Que Funciona (v1)

| Componente | Status | Observação |
|------------|--------|------------|
| Classificação de intents | ✅ | command, task, question, chat, self_improve |
| Memória Redis | ✅ | Cache e filas operacionais |
| PostgreSQL | ✅ | Fatos e configurações |
| Docker containers | ✅ | Status e gerenciamento |
| RAM/System | ✅ | Monitoramento funcionando |
| Telegram Bot | ✅ | Interface operacional |
| LangGraph | ✅ | Orquestração de workflows |

### O Que Não Funciona (v1)

| Problema | Causa | Solução |
|----------|-------|---------|
| self_improve retorna None | Fluxo do grafo quebrado | Corrigido na FASE 0 |
| Sem GitHub API | Skill não implementada | FASE 2 |
| Sem busca web | Skill não implementada | FASE 2 |
| Sem CLI execution | Skill não implementada | FASE 2 |
| Memória frágil | Qdrant não iniciado | FASE 3 |

---

## 🏗️ Arquitetura Proposta

### Fluxo Atual (v1 — Funcional)

```
Telegram → Bot → classify → load_context → plan → [intent?]
                                             ├── chat → LLM → respond → save_memory
                                             ├── question → LLM → respond → save_memory
                                             ├── command → execute → respond → save_memory
                                             ├── task → execute → respond → save_memory
                                             └── self_improve → check_capabilities → respond
```

### Hierarquia de Ferramentas

| Nível | Classificação | Exemplos | Controle |
|-------|---------------|----------|----------|
| **0 — SAFE** | Leitura, consulta | Ler arquivo, query DB, checar status | Automático |
| **1 — MODERATE** | Escrita limitada | Criar arquivo, chamar API, pip install | Auto + log |
| **2 — DANGEROUS** | Escrita destrutiva | Deletar, instalar MCP, git push | Aprovação Telegram |
| **3 — FORBIDDEN** | Destruição irreversível | rm -rf/, desabilitar firewall | Bloqueado sempre |

### Arquitetura de Memória (3 Camadas)

```
CAMADA 1 — Episódica (JSONL)
├── Transcripts das últimas conversas (7 dias)
├── Formato: JSONL append-only, um arquivo por dia
└── Custo RAM: ~0 (leitura sob demanda)

CAMADA 2 — Semântica (Qdrant)
├── Fatos importantes extraídos das conversas
├── Embeddings via API (0 RAM extra local)
└── Custo RAM: ~400MB quando ativo (sob demanda)

CAMADA 3 — Perfil (PostgreSQL)
├── Preferências, configs, credenciais (encrypted)
├── Capabilities registradas
└── Custo RAM: ~200MB (já rodando)
```

---

## 📋 Plano de Implementação

### Fase 0.5 — Quick Wins (IMEDIATO)

**Objetivo:** Melhorias cosméticas que não precisam de nova arquitetura

| # | Task | Descrição | Prioridade |
|---|------|-----------|------------|
| 0.5.1 | Resposta smarter | Quando skill não existe, informar plano de implementação | P0 |
| 0.5.2 | Learnings table | Tabela PostgreSQL para registrar falhas e lições | P1 |
| 0.5.3 | Better prompts | Melhorar prompts de classificação de intents | P1 |
| 0.5.4 | Error handling | Tratar erros de forma mais informativa | P1 |

**Entregável 0.5:** Bot responde "sei que você quer X, posso implementar assim..." em vez de "não tenho ferramenta"

---

### Fase 1 — Fundação v2 (PRÓXIMA)

**Objetivo:** Infraestrutura para skills reais

| # | Job | Descrição | Dependência |
|---|-----|-----------|-------------|
| F1-01 | Gateway Module | FastAPI + Adapters (Telegram, WhatsApp) | — |
| F1-02 | Session Manager | Gerenciamento de sessões de usuário | F1-01 |
| F1-03 | Context Window Guard | Limitar contexto para evitar overflow | F1-01 |
| F1-04 | JSONL Transcripts | Camada episódica de memória | — |
| F1-05 | Prompt Composer | Prompts dinâmicos baseados no contexto | F1-03 |
| F1-06 | LLM Provider Abstraction | Multi-model support | — |
| F1-07 | Allowlist de Segurança | Whitelist de comandos permitidos | — |
| F1-08 | Structured Logging | Logs consistentes e estruturados | — |

**Entregável F1:** Infraestrutura pronta para receber skills

---

### Fase 2 — Skills Core (APÓS F1)

**Objetivo:** Adicionar capacidades reais ao agente

| # | Skill | Tipo | RAM Extra | Descrição |
|---|-------|------|-----------|-----------|
| S2-01 | shell-exec | Native | 0 | Executar comandos shell |
| S2-02 | file-manager | Native | 0 | Ler/editar/criar arquivos |
| S2-03 | web-search | Native | 0 | Busca via Brave Search API |
| S2-04 | github-api | Native | 0 | GitHub REST API |
| S2-05 | memory-query | Native | 0 | Query PostgreSQL e learnings |

**Ordem de implementação:** S2-01 → S2-02 → S2-03 → S2-04 → S2-05

**Entregável F2:** Bot consegue listar projetos do GitHub e buscar na web

---

### Fase 3 — Inteligência (APÓS F2)

**Objetivo:** Fazer o agente aprender e melhorar

| # | Job | Descrição |
|---|-----|-----------|
| F3-01 | Hierarchical Memory | Qdrant + compaction de memórias |
| F3-02 | RAG Ingestion | Indexar documentos e conversas |
| F3-03 | Semantic Caching | Cache de perguntas similares |
| F3-04 | Self-Critique | Agente avalia próprias respostas |
| F3-05 | Multi-Provider Failover | Fallback entre LLMs |

**Entregável F3:** Agente aprende com conversas e melhora respostas

---

### Fase 4 — Autonomia (APÓS F3)

**Objetivo:** Self-improvement real

| # | Job | Descrição |
|---|-----|-----------|
| F4-01 | Self-Improvement Pipeline | Detectar → Planejar → Implementar → Validar |
| F4-02 | Multi-Agent Delegation | Delegar tarefas para sub-agentes |
| F4-03 | Behavioral Contracts | Testes de comportamento do agente |
| F4-04 | Shadow Testing | Testar novos prompts antes de deploy |

**Entregável F4:** Agente propõe e implementa próprias melhorias

---

## 💰 Budget de RAM

```
CENÁRIO A — Modo Normal (sem Qdrant, sem n8n)
  OS + sistema:              ~200 MB
  PostgreSQL:                ~200 MB
  Redis:                     ~50 MB
  Python (agente):           ~300 MB
  ─────────────────────────────────
  Total:                     ~750 MB
  Livre:                    ~1650 MB

CENÁRIO B — Com Qdrant (busca semântica)
  Cenário A:                 ~750 MB
  Qdrant:                    ~400 MB
  ─────────────────────────────────
  Total:                    ~1150 MB
  Livre:                    ~1250 MB

CENÁRIO C — Qdrant + n8n (automação)
  Cenário B:                ~1150 MB
  n8n:                      ~300 MB
  ─────────────────────────────────
  Total:                    ~1450 MB
  Livre:                     ~950 MB

REGRA: Mínimo 500 MB livre. Se livre < 500MB, recusar novas ferramentas.
```

---

## 📈 Métricas de Sucesso

### Fase 0.5

- [ ] 5/5 intents retornam resposta (não None)
- [ ] 0 crashes em 24h de operação
- [ ] CI/CD verde
- [ ] Resposta "smarter" quando skill não existe

### Fase 1

- [ ] Gateway FastAPI funcionando
- [ ] Session Manager rastreando sessões
- [ ] JSONL transcripts sendo salvos
- [ ] Context Window Guard limitando tokens

### Fase 2

- [ ] 5 skills core operacionais
- [ ] shell-exec funcionando
- [ ] web-search retornando resultados
- [ ] github-api listando repositórios

### Fase 3

- [ ] Qdrant indexando memórias
- [ ] RAG retornando contexto relevante
- [ ] Cache hit rate > 30%

### Fase 4

- [ ] Self-improvement pipeline funcional
- [ ] 0 melhorias sem aprovação humana
- [ ] Multi-agent delegation funcionando

---

## 🔗 Referências

| Documento | Local |
|-----------|-------|
| Contexto Centralizado | `.kilocode/rules/memory-bank/project-context.md` |
| Estado Atual | `.kilocode/rules/memory-bank/brief.md` |
| Tracker de Deployment | `.kilocode/rules/memory-bank/deployment-tracker.md` |
| Consulta Opus | `plans/consulta-opus-estabilizacao.md` |
| Resposta Opus | `plans/Resposta Claude002_260208.md` |
| Roadmap Original | `agentvps-v2-roadmap.md` |

---

## 🚀 Próximos Passos Imediatos

1. **IMEDIATO:** Implementar 0.5.1 — Resposta smarter quando skill não existe
2. **APÓS CI/CD PASSAR:** Validar FASE 0 completa
3. **PRÓXIMA SEMANA:** Iniciar F1-01 — Gateway Module

---

> **Nota:** Este documento deve ser atualizado conforme o projeto evolui.  
> **Responsável:** Kilocode + Suporte Opus 4.6