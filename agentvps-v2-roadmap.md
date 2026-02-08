# 🧠 AgentVPS v2 — Roadmap Unificado

## Origem deste plano

Este roadmap consolida **três fontes** em um plano coerente e executável:

| Fonte | O que traz | Stack |
|---|---|---|
| **AgentVPS v1** (atual) | Fundação funcional: Docker, PostgreSQL, Redis, Qdrant, LangGraph, Telegram Bot, Resource Manager | Python |
| **OpenClaw** (117k ★) | Padrões arquiteturais validados em produção: Gateway, Skills, Session model, Context Guard, Security | TypeScript/Node.js |
| **AgentStack** (planejado, 114 jobs) | Engenharia de produção: RAG pipeline, LLM abstraction, observability, failover, reasoning validation, cost management | TypeScript monorepo |

**Decisão fundamental:** O AgentVPS v2 permanece em **Python** com **LangGraph**. Não migramos de stack. Adaptamos os *padrões* do OpenClaw e do AgentStack para o nosso contexto.

---

## O que NÃO entra no v2

Antes de listar o que fazemos, é importante dizer o que **descartamos** e por quê:

| Descartado | Fonte | Motivo |
|---|---|---|
| Migração para TypeScript/monorepo | AgentStack T0-001 | Reescrita total sem benefício proporcional. Python + LangGraph é mais maduro para agentes. |
| Dual Orchestration (Langflow + LangGraph) | AgentStack T2-GAP-021 | Complexidade desnecessária. LangGraph cobre 100% dos nossos casos. |
| Multi-tenancy / ABAC / Tenant Promotion | AgentStack T0-025, T1-001, T1-GAP-023, T1-GAP-024 | Projeto single-user. Não é SaaS. |
| 12 canais simultâneos | OpenClaw | Telegram + Evolution API (WhatsApp) são suficientes. |
| Apps nativos (macOS/iOS/Android) | OpenClaw | Interface via Telegram resolve. |
| Voice Wake / Talk Mode | OpenClaw | Não se aplica ao caso de uso VPS. |
| Browser automation pesado | OpenClaw | APIs web são mais eficientes. |
| Enterprise SSO / Billing | AgentStack T3-002, T3-003 | Single-user, sem necessidade. |
| Plugin marketplace | AgentStack T3-004 | Prematuramente complexo. Skills modulares resolvem. |
| CORS/CSP Headers | AgentStack T1-009 | Sem interface web exposta. |
| API Key Management (multi-user) | AgentStack T1-008 | Single-user. |
| Self-Service Tenant Onboarding | AgentStack T1-014 | Single-user. |
| Admin Dashboard web | AgentStack T3-001 | Telegram + CLI são suficientes. |

---

## Arquitetura v2

```
┌─────────────────────────────────────────────────────────┐
│                    VPS (Escalável)                       │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              GATEWAY (Python/FastAPI)              │  │
│  │  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │  │
│  │  │ Telegram  │  │Evolution │  │  Webhook/API  │   │  │
│  │  │ Adapter   │  │API Adapt.│  │   Adapter     │   │  │
│  │  └─────┬─────┘  └─────┬────┘  └──────┬────────┘   │  │
│  │        └───────────┬───┘──────────────┘            │  │
│  │                    ▼                               │  │
│  │         Message Envelope (normalizado)             │  │
│  │                    │                               │  │
│  │         ┌──────────▼──────────┐                    │  │
│  │         │   Session Router    │                    │  │
│  │         │  (isolamento por    │                    │  │
│  │         │   conversa/canal)   │                    │  │
│  │         └──────────┬──────────┘                    │  │
│  └────────────────────┼──────────────────────────────┘  │
│                       ▼                                  │
│  ┌────────────────────────────────────────────────────┐  │
│  │           CÉREBRO (LangGraph Agent)                │  │
│  │                                                    │  │
│  │  ┌─────────────┐  ┌──────────────────────────┐    │  │
│  │  │ Context     │  │ LLM Provider Abstraction  │    │  │
│  │  │ Window Guard│  │ (multi-provider + failover│    │  │
│  │  │ (token mgmt)│  │  + model cascade routing) │    │  │
│  │  └─────────────┘  └──────────────────────────┘    │  │
│  │                                                    │  │
│  │  ┌─────────────┐  ┌──────────────────────────┐    │  │
│  │  │ Prompt      │  │ Reasoning Validator       │    │  │
│  │  │ Composer    │  │ (step-level validation    │    │  │
│  │  │ (dinâmico)  │  │  + early termination)     │    │  │
│  │  └─────────────┘  └──────────────────────────┘    │  │
│  │                                                    │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │        SKILL REGISTRY                       │  │  │
│  │  │  web-search │ file-mgr │ n8n │ qdrant │ ...│  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │           MEMÓRIA (Hierárquica)                    │  │
│  │                                                    │  │
│  │  PostgreSQL ─── fatos, estado, sessões, audit log  │  │
│  │  Redis ──────── cache, pub/sub, semantic cache     │  │
│  │  JSONL ──────── transcripts (auditabilidade)       │  │
│  │  Markdown ───── MEMORY.md (destilado), prompts     │  │
│  │  Qdrant ─────── RAG semântico (on-demand)          │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │           SEGURANÇA & OBSERVABILIDADE              │  │
│  │                                                    │  │
│  │  Allowlist IDs │ Action Classification │ Approval  │  │
│  │  PII Redaction │ Prompt Injection Defense           │  │
│  │  Usage Tracking │ LangSmith │ Structured Logging   │  │
│  │  Circuit Breaker │ JSONL Audit Trail               │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │           AUTOMAÇÃO                                │  │
│  │  n8n (triggers) │ Cron │ Webhooks │ Evolution API  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Fases de Implementação

### FASE 1 — Refatoração da Fundação (3-4 semanas)
> Objetivo: Reestruturar o que existe para suportar a nova arquitetura sem quebrar o que já funciona.

| # | Job | Origem | Horas Est. | Prioridade |
|---|-----|--------|-----------|------------|
| F1-01 | **Gateway Module** — Criar `gateway/` com FastAPI. Extrair Telegram Bot para um adapter. Definir Message Envelope (channel, sender_id, content, metadata, timestamp). Toda comunicação passa pelo gateway. | OpenClaw #1 | 16h | P0 |
| F1-02 | **Session Manager** — Sessões isoladas por conversa/canal no PostgreSQL. Cada sessão tem seu próprio estado LangGraph, histórico, e metadata. Suporte a `/new`, `/reset`, `/compact`. | OpenClaw #7 + AgentStack T0-018 | 12h | P0 |
| F1-03 | **Context Window Guard** — Node no LangGraph que conta tokens antes de cada chamada LLM. Threshold a 70%: compactação automática (sumarização). Threshold a 90%: parada de segurança. Resumo salvo em MEMORY.md e PostgreSQL. | OpenClaw #4 + AgentStack T0-019 | 10h | P0 |
| F1-04 | **JSONL Transcripts** — Logger que grava toda interação (mensagens, tool calls, resultados, erros) em arquivos JSONL rotativos por sessão. Zero overhead de RAM, auditabilidade total. | OpenClaw #3 | 6h | P0 |
| F1-05 | **Prompt Composer Dinâmico** — Montar system prompt a partir de arquivos: `brain/SYSTEM.md` (personalidade), `brain/TOOLS.md` (gerado dos skills ativos), `brain/USER.md` (contexto do usuário), `brain/MEMORY.md` (destilado). | OpenClaw #8 + AgentStack T0-014 | 8h | P0 |
| F1-06 | **LLM Provider Abstraction** — Classe `LLMProvider` com interface unificada para Anthropic, OpenAI, OpenRouter. Config por modelo (temperatura, max_tokens, system prompt). Retry com backoff. | AgentStack T0-013 | 12h | P0 |
| F1-07 | **Allowlist de Segurança** — Lista de Telegram user IDs autorizados no `.env`. Mensagens de IDs não autorizados recebem resposta de pairing code (padrão OpenClaw). | OpenClaw #5 | 4h | P0 |
| F1-08 | **Structured Logging** — Logging com structlog (Python). Levels, contexto de sessão, trace IDs. Saída em JSON para ser processável. | AgentStack T0-008 | 6h | P1 |
| F1-09 | **Error Handling Padronizado** — Exceções tipadas (LLMError, ToolError, GatewayError). Circuit breaker para chamadas LLM (3 falhas → fallback/pausa). | AgentStack T0-009 + T0-024 | 8h | P1 |
| F1-10 | **Health Check & Doctor** — Endpoint `/health` + comando `agent-cli doctor` que verifica: serviços rodando, RAM disponível, conectividade APIs, estado do PostgreSQL/Redis, expiração de tokens. | OpenClaw #9 + AgentStack T0-011 | 6h | P1 |
| F1-11 | **Docker Compose v2** — Reescrever docker-compose para a nova estrutura. Profiles para dev/prod. Resource limits explícitos por container. | AgentStack T0-010 | 4h | P1 |
| F1-12 | **Testes Unitários Fundação** — Pytest setup + testes para Gateway, Session Manager, Context Guard, LLM Provider. Target: 60% cobertura dos módulos novos. | AgentStack T0-028 | 10h | P1 |

**Subtotal Fase 1: ~102h | Entrega: Gateway funcional + sessões + proteções fundamentais**

---

### FASE 2 — Skills & Segurança (3-4 semanas)
> Objetivo: Sistema de skills modular + camada de segurança robusta + primeiro canal adicional.

| # | Job | Origem | Horas Est. | Prioridade |
|---|-----|--------|-----------|------------|
| F2-01 | **Skill Registry** — `skills/` com estrutura padronizada. Cada skill: `SKILL.md` (descrição p/ LLM), `handler.py` (implementação), `config.yaml` (metadata: RAM, Docker?, dependências). Registro e descoberta automática. TOOLS.md gerado a partir dos skills ativos. | OpenClaw #2 + AgentStack T0-016, T0-027 | 20h | P0 |
| F2-02 | **Skills Core** — Implementar os 5 skills iniciais: `shell-exec` (rodar comandos), `file-manager` (CRUD arquivos), `web-search` (pesquisa web), `memory-query` (consultar PostgreSQL/Qdrant), `self-edit` (modificar código próprio). | AgentVPS Fase 7 | 16h | P0 |
| F2-03 | **Action Classification & Approval** — Classificar ações dos skills em 3 níveis: `safe` (ler, consultar), `moderate` (criar arquivo, instalar pacote), `dangerous` (deletar, executar script arbitrário, modificar serviços). Ações `dangerous` disparam approval workflow via Telegram (botão Aprovar/Rejeitar com timeout de 5 min). | OpenClaw #5 + AgentStack T1-GAP-021 | 14h | P0 |
| F2-04 | **PII Redaction Layer** — Regex-based scan de CPF, email, telefone, cartão de crédito nos logs e transcripts. Mask antes de persistir. Não bloquear a mensagem, só redact no armazenamento. | AgentStack T1-003 | 8h | P0 |
| F2-05 | **Prompt Injection Defense** — Delimitadores claros no system prompt entre instrução e input do usuário. Scanner básico de padrões de injection (ignore previous instructions, etc). Log de tentativas suspeitas. | AgentStack T1-005 | 10h | P0 |
| F2-06 | **Tool Contract Testing** — Cada skill define input/output schemas (Pydantic models). Testes automáticos que validam contratos. Versionamento de skills (semver no config.yaml). | AgentStack T1-GAP-018 | 12h | P1 |
| F2-07 | **Evolution API Adapter** — Novo adapter no Gateway para WhatsApp via Evolution API. Mesmo Message Envelope, roteamento transparente. Segundo canal funcional. | OpenClaw #1 + AgentVPS roadmap | 12h | P1 |
| F2-08 | **Audit Logging** — Eventos sensíveis (aprovações, execuções de skills dangerous, erros de LLM, tentativas de acesso não autorizado) salvos em tabela PostgreSQL append-only com timestamp, actor, action, result. | AgentStack T1-015 | 8h | P1 |
| F2-09 | **Tool Usage Policies** — Config YAML definindo allow/deny list de skills por contexto (modo casual = read-only, modo admin = full). Toggle via comando Telegram `/mode casual|admin`. | OpenClaw #5 + AgentStack T1-016 | 8h | P1 |
| F2-10 | **Testes Integração Skills** — Testes end-to-end: mensagem Telegram → Gateway → Agent → Skill → Response. Mock de LLM para testes determinísticos. Target: 70% cobertura. | AgentStack T0-029 | 12h | P1 |

**Subtotal Fase 2: ~120h | Entrega: Skills modulares + WhatsApp + segurança em camadas**

---

### FASE 3 — Inteligência & Confiabilidade (4-5 semanas)
> Objetivo: Agente mais inteligente, mais confiável, mais barato de operar.

| # | Job | Origem | Horas Est. | Prioridade |
|---|-----|--------|-----------|------------|
| F3-01 | **Multi-Provider LLM Failover** — Se Claude falhar (rate limit, erro 500), fallback automático para OpenAI ou OpenRouter. Ordem configurável. Log do failover. Retry inteligente (não repetir no mesmo provider). | AgentStack T2-GAP-015 | 12h | P0 |
| F3-02 | **Model Cascade Routing** — Classificar queries por complexidade: simples (Haiku/GPT-4o-mini), médio (Sonnet), complexo (Opus). Heurística baseada em: tokens do input, presença de código, tipo de skill requerido. Target: <$0.05/conversa média. | AgentStack T2-GAP-006 + T2-GAP-016 | 16h | P0 |
| F3-03 | **Step-Level Reasoning Validation** — Antes de executar uma ação, validar se o "raciocínio" do agente faz sentido. Checar: a tool chamada existe? Os argumentos são válidos? A ação é consistente com o pedido do usuário? Early termination se o agente "alucinando" tool calls inválidas. | AgentStack T1-GAP-017 | 14h | P0 |
| F3-04 | **Hierarchical Memory** — 3 camadas: (1) Episódica = JSONL transcripts recentes, (2) Semântica = Qdrant com embeddings dos fatos importantes, (3) Perfil = USER.md + PostgreSQL com preferências. Ao compactar contexto, os fatos importantes migram para semântica. | AgentStack T2-004 + OpenClaw #3 | 20h | P0 |
| F3-05 | **RAG Ingestion Pipeline** — Upload de documentos via Telegram (PDF, DOCX, TXT). Pipeline: parse → chunk (recursive text splitter) → embed → Qdrant. Metadata tracking (fonte, data, hash). Governance: log de proveniência. | AgentStack T1-GAP-025 + T1-GAP-026 | 20h | P1 |
| F3-06 | **Semantic Caching** — Cache em Redis de respostas baseado em similaridade semântica da query (embedding). TTL configurável. Invalidação por evento (skill result muda estado do mundo). Economia de 30-40% em chamadas LLM repetitivas. | AgentStack T2-010 + T2-GAP-009 | 12h | P1 |
| F3-07 | **Reflection & Self-Critique** — Após gerar resposta, rodar um segundo passo de "revisão": a resposta responde a pergunta? Tem erros factuais óbvios? O tom está correto? Se o score < threshold, regenerar. Custos controlados pelo cascade routing. | AgentStack T2-002 | 14h | P1 |
| F3-08 | **LLM-Native Observability** — Integrar LangSmith (grátis para dev) para trace completo de cada conversa: tokens, latência, tool calls, custo. Dashboard de uso acessível via Telegram (`/usage`). | AgentStack T1-GAP-020 | 10h | P1 |
| F3-09 | **Usage & Cost Tracking** — Calcular custo por sessão/dia/mês baseado em tokens consumidos × preço do modelo. Alertas via Telegram quando custo diário passa de threshold. Relatório semanal automático. | AgentStack T2-GAP-014 | 10h | P1 |
| F3-10 | **n8n Integration** — n8n como orquestrador de triggers externos. Webhooks, schedules, email triggers → disparam o agente via API do Gateway. O agente executa e responde pelo canal configurado. | OpenClaw #10 | 10h | P1 |
| F3-11 | **Cron & Scheduled Tasks** — Agente pode criar tarefas agendadas (verificar algo todo dia, enviar resumo semanal). Persistido no PostgreSQL, executado por worker em background. | OpenClaw #10 | 8h | P2 |

**Subtotal Fase 3: ~146h | Entrega: Agente inteligente com failover, cache, RAG, e automações**

---

### FASE 4 — Autonomia & Evolução (3-4 semanas)
> Objetivo: Agente auto-melhorável com guardrails, multi-agent preparado, e CLI maduro.

| # | Job | Origem | Horas Est. | Prioridade |
|---|-----|--------|-----------|------------|
| F4-01 | **Multi-Agent Routing** — Estrutura `agents/` com agentes especializados (main, researcher, devops). Cada agente tem workspace, memória, skills e personalidade separados. Gateway roteia baseado em canal/comando. | OpenClaw #6 | 18h | P1 |
| F4-02 | **Agent-to-Agent Communication** — Agentes podem enviar mensagens entre si via pub/sub Redis. Agente main pode delegar tarefas para agente researcher ou devops. Resultado volta para o agente delegante. | OpenClaw #6 + AgentStack T2-001 | 14h | P1 |
| F4-03 | **Goal Drift Monitor** — Em conversas longas ou tarefas multi-step, monitorar se o agente está derivando do objetivo original. Comparar embedding do objetivo inicial vs. ação atual. Alert se drift > threshold. | AgentStack T3-014 | 12h | P1 |
| F4-04 | **Self-Improvement Pipeline** — O agente pode: (1) identificar padrões de falha nos logs, (2) propor modificações no próprio código/skills, (3) testar em sandbox, (4) submeter para aprovação humana. Nunca deploy automático sem approval. | AgentVPS Fase 7 + AgentStack T2-GAP-019 | 20h | P1 |
| F4-05 | **Indirect Prompt Injection Scanner** — Além de regex, usar embedding-based similarity para detectar instruções maliciosas em documentos ingeridos (RAG), resultados de web search, ou conteúdo de arquivos. Log + block. | AgentStack T2-GAP-007 | 14h | P1 |
| F4-06 | **Behavioral Contract Testing** — Definir "persona contracts": tom, idioma, limites do que o agente deve/não deve fazer. Testes automáticos que verificam se respostas do agente respeitam os contratos. Rodados em CI. | AgentStack T2-GAP-017 | 10h | P2 |
| F4-07 | **Shadow Testing para Prompts** — Quando alterar system prompts ou skills, rodar o prompt antigo e novo em paralelo. Comparar respostas. Só promover o novo se não houver regressão significativa. | AgentStack T2-GAP-020 | 12h | P2 |
| F4-08 | **Memory Compaction Scheduler** — Job periódico que: (1) compacta transcripts antigos (>7 dias) em resumos, (2) migra fatos importantes para Qdrant, (3) limpa JSONL arquivado. Evita crescimento infinito. | AgentStack T2-017 | 8h | P2 |
| F4-09 | **CLI Expandido** — `agent-cli doctor`, `agent-cli usage`, `agent-cli skills list|enable|disable`, `agent-cli sessions list`, `agent-cli agents list`, `agent-cli logs tail`. | OpenClaw #9 + AgentStack T0-033 | 10h | P2 |
| F4-10 | **Environment Segregation** — Docker Compose profiles para `dev` e `prod`. Dev usa SQLite + Redis mock. Prod usa PostgreSQL + Redis real. Variáveis de ambiente separadas. CI rodando testes em dev profile. | AgentStack T1-GAP-019 | 10h | P2 |
| F4-11 | **Documentação Completa** — README atualizado, CONTRIBUTING.md, docs/ com: arquitetura, como criar skills, como configurar, troubleshooting. API docs do Gateway (OpenAPI/Swagger auto-gerado pelo FastAPI). | AgentStack T0-030, T0-031 | 12h | P2 |

**Subtotal Fase 4: ~140h | Entrega: Agente auto-melhorável com multi-agent e guardrails**

---

## Resumo de Esforço

| Fase | Jobs | Horas | Semanas | Entrega Principal |
|------|------|-------|---------|-------------------|
| **F1** — Fundação | 12 | ~102h | 3-4 | Gateway + Sessões + Proteções |
| **F2** — Skills & Segurança | 10 | ~120h | 3-4 | Skills modulares + WhatsApp + Security |
| **F3** — Inteligência | 11 | ~146h | 4-5 | Failover + RAG + Cache + Automações |
| **F4** — Autonomia | 11 | ~140h | 3-4 | Multi-agent + Self-improvement + Guardrails |
| **TOTAL** | **44 jobs** | **~508h** | **13-17 semanas** | |

Comparação: o AgentStack original tinha **114 jobs / ~1886h**. Este plano tem **44 jobs / ~508h** — 73% menos trabalho por eliminar: multi-tenancy, dual stack, enterprise features, e foco implacável no que importa para single-user.

---

## Mapeamento: De onde cada job veio

| Job | OpenClaw | AgentStack | AgentVPS Original |
|-----|----------|------------|-------------------|
| F1-01 Gateway | ✓ (#1) | — | — |
| F1-02 Session Manager | ✓ (#7) | T0-018 | — |
| F1-03 Context Window Guard | ✓ (#4) | T0-019 | — |
| F1-04 JSONL Transcripts | ✓ (#3) | — | — |
| F1-05 Prompt Composer | ✓ (#8) | T0-014 | — |
| F1-06 LLM Provider Abstraction | — | T0-013 | — |
| F1-07 Allowlist Segurança | ✓ (#5) | — | — |
| F1-08 Structured Logging | — | T0-008 | — |
| F1-09 Error Handling | — | T0-009, T0-024 | — |
| F1-10 Health Check / Doctor | ✓ (#9) | T0-011 | — |
| F1-11 Docker Compose v2 | — | T0-010 | ✓ (existente) |
| F1-12 Testes Unitários | — | T0-028 | — |
| F2-01 Skill Registry | ✓ (#2) | T0-016, T0-027 | — |
| F2-02 Skills Core | — | — | ✓ (Fase 7) |
| F2-03 Action Classification | ✓ (#5) | T1-GAP-021 | ✓ (roadmap) |
| F2-04 PII Redaction | — | T1-003 | — |
| F2-05 Prompt Injection Defense | — | T1-005 | — |
| F2-06 Tool Contract Testing | — | T1-GAP-018 | — |
| F2-07 Evolution API Adapter | ✓ (#1) | — | ✓ (roadmap) |
| F2-08 Audit Logging | — | T1-015 | — |
| F2-09 Tool Usage Policies | ✓ (#5) | T1-016 | — |
| F2-10 Testes Integração | — | T0-029 | — |
| F3-01 LLM Failover | — | T2-GAP-015 | — |
| F3-02 Model Cascade | — | T2-GAP-006, T2-GAP-016 | — |
| F3-03 Reasoning Validation | — | T1-GAP-017 | — |
| F3-04 Hierarchical Memory | ✓ (#3) | T2-004 | ✓ (Qdrant) |
| F3-05 RAG Pipeline | — | T1-GAP-025, T1-GAP-026 | — |
| F3-06 Semantic Caching | — | T2-010, T2-GAP-009 | — |
| F3-07 Reflection | — | T2-002 | — |
| F3-08 Observability | — | T1-GAP-020 | — |
| F3-09 Cost Tracking | — | T2-GAP-014 | — |
| F3-10 n8n Integration | ✓ (#10) | — | ✓ (existente) |
| F3-11 Cron Tasks | ✓ (#10) | — | — |
| F4-01 Multi-Agent Routing | ✓ (#6) | T2-001 | — |
| F4-02 Agent Communication | ✓ (#6) | T2-001 | — |
| F4-03 Goal Drift Monitor | — | T3-014 | — |
| F4-04 Self-Improvement | — | T2-GAP-019 | ✓ (Fase 7) |
| F4-05 Injection Scanner | — | T2-GAP-007 | — |
| F4-06 Behavioral Testing | — | T2-GAP-017 | — |
| F4-07 Shadow Testing | — | T2-GAP-020 | — |
| F4-08 Memory Compaction | ✓ (#4) | T2-017 | — |
| F4-09 CLI Expandido | ✓ (#9) | T0-033 | ✓ (existente) |
| F4-10 Env Segregation | — | T1-GAP-019 | — |
| F4-11 Documentação | — | T0-030, T0-031 | ✓ (Fase 6) |

**Resumo de contribuição por fonte:**
- OpenClaw: 20 jobs influenciados (padrões arquiteturais)
- AgentStack: 36 jobs influenciados (engenharia de produção)
- AgentVPS original: 8 jobs mantidos/evoluídos (fundação existente)

---

## Estrutura de Diretórios v2

```
agentvps-v2/
├── gateway/                    # NOVO — Gateway centralizado
│   ├── __init__.py
│   ├── server.py               # FastAPI app
│   ├── envelope.py             # Message Envelope model
│   ├── router.py               # Session routing
│   ├── adapters/
│   │   ├── telegram.py         # Telegram adapter
│   │   ├── evolution.py        # WhatsApp/Evolution API adapter
│   │   └── webhook.py          # Generic webhook adapter
│   └── security/
│       ├── allowlist.py        # User ID authorization
│       ├── pairing.py          # Pairing code flow
│       └── action_classifier.py # safe/moderate/dangerous
│
├── brain/                      # EVOLUÍDO — Cérebro do agente
│   ├── agent.py                # LangGraph entry point
│   ├── graph.py                # Workflow definition
│   ├── nodes/
│   │   ├── context_guard.py    # Context window management
│   │   ├── prompt_composer.py  # Dynamic prompt assembly
│   │   ├── reasoning_validator.py # Step-level validation
│   │   ├── reflection.py       # Self-critique node
│   │   └── goal_monitor.py     # Goal drift detection
│   ├── llm/
│   │   ├── provider.py         # LLM abstraction layer
│   │   ├── failover.py         # Multi-provider failover
│   │   ├── cascade.py          # Model cascade routing
│   │   └── cache.py            # Semantic caching
│   ├── prompts/                # NOVO — Prompt files
│   │   ├── SYSTEM.md
│   │   ├── TOOLS.md            # Auto-gerado dos skills
│   │   ├── USER.md
│   │   └── MEMORY.md           # Destilado
│   └── state.py                # AgentState TypedDict
│
├── skills/                     # NOVO — Skills modulares
│   ├── registry.py             # Skill discovery & loading
│   ├── base.py                 # BaseSkill class
│   ├── shell-exec/
│   │   ├── SKILL.md
│   │   ├── handler.py
│   │   └── config.yaml
│   ├── file-manager/
│   ├── web-search/
│   ├── memory-query/
│   ├── self-edit/
│   ├── rag-ingest/
│   └── n8n-trigger/
│
├── memory/                     # EVOLUÍDO — Memória hierárquica
│   ├── store.py                # Interface unificada
│   ├── postgres.py             # Fatos, estado, sessões
│   ├── redis_cache.py          # Cache + pub/sub
│   ├── qdrant_client.py        # RAG semântico
│   ├── transcripts/            # JSONL por sessão
│   │   └── session_xxx.jsonl
│   └── compaction.py           # Memory compaction scheduler
│
├── agents/                     # NOVO — Multi-agent (Fase 4)
│   ├── main/
│   │   ├── config.yaml
│   │   └── workspace/
│   ├── researcher/
│   └── devops/
│
├── observability/              # NOVO
│   ├── logging.py              # Structured logging (structlog)
│   ├── metrics.py              # Usage & cost tracking
│   ├── audit.py                # Audit trail
│   └── langsmith.py            # LangSmith integration
│
├── security/                   # NOVO
│   ├── pii_redaction.py        # Regex PII masking
│   ├── injection_defense.py    # Prompt injection scanner
│   └── tool_policies.py        # Allow/deny per context
│
├── configs/
│   ├── docker-compose.yml      # EVOLUÍDO — com profiles
│   ├── docker-compose.dev.yml
│   ├── .env.example
│   └── init-db.sql
│
├── scripts/
│   ├── agent-cli.sh            # EVOLUÍDO — mais comandos
│   └── setup.sh
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── contracts/              # NOVO — behavioral + tool contracts
│
├── docs/
│   ├── architecture.md
│   ├── skills-guide.md
│   ├── configuration.md
│   └── troubleshooting.md
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Stack Tecnológico v2

| Componente | Tecnologia | Justificativa |
|---|---|---|
| **Linguagem** | Python 3.11+ | Ecossistema LangChain/LangGraph, maturidade em AI |
| **Orchestração** | LangGraph | Graphs estáveis, checkpointing, human-in-the-loop nativo |
| **Gateway** | FastAPI | Async, auto-docs OpenAPI, WebSocket suporte |
| **DB Relacional** | PostgreSQL 16 | Já em uso, maduro, JSONB para flexibilidade |
| **Cache** | Redis 7 | Já em uso, pub/sub, cache semântico |
| **Vector DB** | Qdrant | Já em uso, on-demand para RAG |
| **LLM Primary** | Claude (Anthropic) | Contexto longo, tool use robusto |
| **LLM Fallback** | OpenAI / OpenRouter | Failover automático |
| **Embeddings** | Voyage AI / OpenAI | Para RAG e semantic cache |
| **Observability** | LangSmith + structlog | Traces de LLM + logging estruturado |
| **Automação** | n8n | Triggers, webhooks, schedules |
| **Containers** | Docker Compose | Simples, profiles dev/prod |
| **Testes** | pytest + pytest-asyncio | Padrão Python |
| **CI** | GitHub Actions | Já configurado |

---

## Métricas de Sucesso por Fase

| Fase | Métrica | Target |
|------|---------|--------|
| F1 | Mensagem Telegram → resposta via Gateway | < 3s latência |
| F1 | Context overflow prevention | 0 crashes por overflow |
| F1 | Testes passando | 60% cobertura novos módulos |
| F2 | Skill adicionado sem editar core | < 30min para criar novo skill |
| F2 | WhatsApp funcional | Mensagem → resposta end-to-end |
| F2 | Ação dangerous sem approval | 0 (bloqueado) |
| F3 | Custo por conversa média | < $0.05 |
| F3 | LLM downtime percebido | 0 (failover transparente) |
| F3 | RAG query com doc ingerido | Resposta relevante em < 5s |
| F4 | Self-improvement sem approval humano | 0 (sempre com approval) |
| F4 | Multi-agent delegation funcional | Main → Researcher → resultado |

---

## Jobs do AgentStack NÃO incluídos (e onde podem entrar futuramente)

Para referência, estes jobs do AgentStack foram avaliados mas não incluídos neste plano. Se o projeto crescer, podem ser reconsiderados:

| Job AgentStack | Razão da exclusão | Pode entrar se... |
|---|---|---|
| T0-001 Monorepo Turborepo | Stack Python | Projeto migrar para TypeScript |
| T0-005 API Gateway (Express) | Substituído por FastAPI | — |
| T0-006 JWT Auth | Single-user | Múltiplos usuários |
| T0-007 User & Tenant Models | Single-user | Multi-tenant |
| T0-012 Rate Limiting | Single-user | Expor API publicamente |
| T0-025 Multi-Tenant Partitioning | Single-user | SaaS |
| T0-026 API Key Auth | Single-user | API pública |
| T0-036-037 Langflow | Dual orchestration | Complexidade justificada |
| T1-001 Namespace Isolation | Multi-tenant | SaaS |
| T1-010 Encrypted Storage | Overkill para single-user | Dados sensíveis de terceiros |
| T1-017 Smart Context Pruning | Coberto por Context Guard | Contextos extremos (>200k) |
| T2-003 Dynamic Tool Discovery | Coberto por Skill Registry | Federation de skills |
| T2-007 Conditional Tool Exec | Coberto por skills | Workflows complexos |
| T2-008 Agent Composability | Coberto por multi-agent | Pipelines complexos |
| T2-009 Streaming Events | Telegram não suporta streaming sofisticado | Interface web |
| T2-011 Horizontal Scaling | Single VPS | Cluster |
| T2-012 DB Replicas | Overkill | Alto volume |
| T2-015 Rate Limit Tiers | Single-user | Multi-tier |
| T2-GAP-010 Dependency Graph Exec | Overkill | Workflows pesados |
| T2-GAP-011 Dynamic Topology Pruning | Overkill | Muitos agentes |
| T2-GAP-012 Speculative Prefetch | Overkill | Latência crítica |
| T2-GAP-013 Agent State Sync | Coberto por Redis pub/sub | Distributed system |
| T2-GAP-018 MCP Security Adapter | Não usa MCP | Integrar MCP |
| T2-GAP-021 Dual Orchestration | Só LangGraph | — |
| T3-001 Admin Dashboard | CLI + Telegram | Interface web necessária |
| T3-002 Billing | Single-user | Monetização |
| T3-003 Enterprise SSO | Single-user | Enterprise |
| T3-004 Plugin Marketplace | Premature | Comunidade |
| T3-005 Audit Explorer | CLI suficiente | Volume grande de audits |
| T3-006 External KB | Coberto por RAG Pipeline | Integrações específicas |
| T3-007 Multi-Language UI | Sem UI web | Interface web |
| T3-008 Voice I/O | Não aplicável VPS | Caso de uso voice |
| T3-009 Integration SDK | Sem terceiros | API pública |
| T3-010 Crypto-Shredding | Single-user | LGPD para terceiros |
| T3-011 IP Egress Filter | Low priority | Conteúdo sensível |
| T3-012 Agent Identity JWTs | Overkill | Zero-trust entre agents |
| T3-013 Red Team Agent | Coberto parcialmente por injection scanner | Security focus |
| T3-015 A/B Testing | Coberto por shadow testing | Múltiplas variantes |
| T3-016 Hybrid RAG Graph | Overkill para agora | Multi-hop queries |

---

## Próximos Passos Imediatos

1. **Criar branch `v2-refactor`** no repositório AgentVPS
2. **Iniciar F1-01 (Gateway)** — é a fundação de tudo mais
3. **Paralelizar F1-04 (JSONL) e F1-07 (Allowlist)** — são independentes e rápidos
4. **Configurar pytest** antes de escrever código novo

O plano inteiro é iterativo — cada fase entrega valor funcional. Você pode pausar após qualquer fase e ter um sistema utilizável.
