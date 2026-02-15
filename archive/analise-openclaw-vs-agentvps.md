# 🔍 Análise: O que o AgentVPS pode aprender com o OpenClaw

## Contexto

| | **AgentVPS** | **OpenClaw** |
|---|---|---|
| **Propósito** | Agente autônomo auto-melhorável em VPS com 2.4GB RAM | Assistente pessoal de IA multi-plataforma (local-first) |
| **Stack** | Python + LangGraph + PostgreSQL + Redis + Qdrant | TypeScript/Node.js + Gateway WebSocket |
| **Interface** | Telegram (único) | 12+ canais (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, etc.) |
| **Maturidade** | ~21 commits, Fase 6-7 | 8.300+ commits, 117k stars, comunidade ativa |
| **Arquitetura** | Monolítica com Docker Compose | Gateway-centric, modular por camadas |

---

## 1. GATEWAY CENTRALIZADO — Prioridade Alta

### O que o OpenClaw faz
O OpenClaw usa um **Gateway WebSocket** como plano de controle central. Tudo passa por ele: mensagens de canais, sessões, ferramentas, eventos. É um processo único que coordena tudo.

### O que falta no AgentVPS
Hoje o AgentVPS tem o Telegram Bot acoplado diretamente ao sistema. Não há uma camada intermediária que normalize mensagens e permita conectar novos canais facilmente.

### Recomendação concreta
Criar um módulo `gateway/` simples que:
- Receba mensagens de qualquer canal (Telegram hoje, WhatsApp/Evolution API depois)
- Normalize para um formato interno padrão (envelope unificado)
- Roteie para o LangGraph/agente
- Retorne a resposta pelo canal de origem

**Benefício imediato:** Quando você quiser integrar a Evolution API (que já está no seu roadmap como "sob demanda"), basta criar um adapter novo sem tocar no core do agente.

```
Telegram ──┐
            ├── Gateway (normaliza) ──→ LangGraph Agent
Evolution ──┘
```

---

## 2. SISTEMA DE SKILLS MODULAR — Prioridade Alta

### O que o OpenClaw faz
Em vez de tool calls avulsos, o OpenClaw usa **Skills**: pacotes modulares com um `SKILL.md` que define capacidades, dependências, e instruções. Skills são descobertos, carregados e injetados no system prompt dinamicamente. Cada skill pode ser habilitado/desabilitado por agente.

### O que falta no AgentVPS
Os nodes do LangGraph fazem tudo de forma acoplada. Não há uma forma padronizada de adicionar/remover capacidades sem editar código.

### Recomendação concreta
Criar uma pasta `skills/` onde cada skill é um diretório com:
- `SKILL.md` — descrição, dependências, instruções para o LLM
- `handler.py` — a implementação da tool
- `config.yaml` — metadados (requer Docker? quanta RAM?)

O Resource Manager (que você já tem) pode decidir quais skills carregar baseado na RAM disponível.

```
skills/
├── web-search/
│   ├── SKILL.md
│   ├── handler.py
│   └── config.yaml
├── file-manager/
│   ├── SKILL.md
│   ├── handler.py
│   └── config.yaml
└── n8n-trigger/
    ├── SKILL.md
    ├── handler.py
    └── config.yaml
```

---

## 3. MEMÓRIA SIMPLIFICADA (JSONL + Markdown) — Prioridade Alta

### O que o OpenClaw faz
O OpenClaw deliberadamente **evita arquiteturas de memória complexas**. Usa:
- **JSONL Transcripts** — log linha-a-linha de tudo que aconteceu (mensagens, tool calls, resultados). Auditável e simples.
- **MEMORY.md** — arquivo Markdown com o que deve ser lembrado (resumos, conhecimento destilado).
- A justificativa deles: busca vetorial sozinha frequentemente gera "ruído semântico" onde informação similar mas incorreta é recuperada.

### O que o AgentVPS faz diferente
Você tem 3 camadas: PostgreSQL (fatos estruturados), Redis (cache), Qdrant (memória semântica). Isso é muito mais complexo para gerenciar com 2.4GB de RAM.

### Recomendação concreta
Considerar um modelo **híbrido simplificado**:
1. **Manter PostgreSQL** para fatos estruturados e estado (já funciona)
2. **Adicionar JSONL transcripts** — são arquivos de texto simples, zero overhead de RAM
3. **Usar MEMORY.md** como "memória destilada" do agente — resumo do que importa
4. **Qdrant como opcional** — só ligar quando realmente necessário para busca semântica pesada, não como memória primária

Isso libera RAM e reduz complexidade. O JSONL dá auditabilidade que o PostgreSQL sozinho não dá tão bem.

---

## 4. CONTEXT WINDOW GUARD — Prioridade Alta

### O que o OpenClaw faz
Tem um **Context Window Guard** que monitora o token count em tempo real. Antes da janela de contexto "explodir", dispara compactação automática (summarization) ou para o loop para evitar comportamento incoerente do modelo.

### O que falta no AgentVPS
Não há proteção contra overflow de contexto. Em conversas longas via Telegram, o agente pode perder coerência sem aviso.

### Recomendação concreta
Adicionar um node no LangGraph que:
1. Conta tokens antes de cada chamada ao LLM
2. Se passar de ~70% do limite, dispara compactação automática (resumir a conversa até aqui)
3. Armazena o resumo no MEMORY.md e reinicia o contexto com o resumo

Isso é especialmente crítico na sua VPS com RAM limitada — chamadas com contexto cheio são mais caras em API também.

---

## 5. SEGURANÇA E SANDBOXING — Prioridade Média

### O que o OpenClaw faz
- **DM Pairing**: desconhecidos recebem um código de pareamento antes de o bot processar a mensagem
- **Sandbox Docker** para sessões de grupo/canais
- **Tool policy** com allow/deny lists por agente
- **Elevated mode** com toggle on/off por sessão para comandos perigosos

### O que falta no AgentVPS
O plano de "aprovação para ações destrutivas" existe no roadmap mas não está implementado. Qualquer um com acesso ao Telegram bot pode potencialmente disparar comandos no sistema.

### Recomendação concreta
Implementar em etapas:
1. **Allowlist de Telegram user IDs** — só aceitar comandos dos seus IDs
2. **Classificação de ações** — safe (ler arquivos, consultar) vs dangerous (executar scripts, deletar, instalar)
3. **Approval workflow via Telegram** — antes de ações perigosas, enviar botão "Aprovar/Rejeitar"
4. Futuro: tool policy por contexto (conversa casual = read-only, modo admin = full access)

---

## 6. MULTI-AGENT ROUTING — Prioridade Média

### O que o OpenClaw faz
Permite múltiplos agentes isolados, cada um com seu workspace, sessões, memória e personalidade. Mensagens são roteadas para o agente certo baseado em regras (canal, grupo, peer).

### O que o AgentVPS poderia ter
Hoje é um agente único. Mas o seu roadmap menciona "criar novos agentes" como capacidade futura.

### Recomendação concreta
Estruturar desde já para multi-agent:
```
agents/
├── main/           # Agente principal (você via Telegram)
│   ├── workspace/
│   ├── memory/
│   └── config.yaml
├── researcher/     # Agente de pesquisa (futuro)
│   ├── workspace/
│   └── config.yaml
└── devops/         # Agente de infra (futuro)
    ├── workspace/
    └── config.yaml
```

Cada agente com skills limitados, memória separada, e o Gateway roteando.

---

## 7. SESSION MODEL — Prioridade Média

### O que o OpenClaw faz
Sessões são isoladas: DMs diretas vão para uma sessão "main", cada grupo tem sua própria sessão, com modos de ativação (sempre, só quando mencionado), e histórico persistente por sessão.

### O que melhorar no AgentVPS
Implementar sessões isoladas no LangGraph:
- Cada conversa do Telegram = uma sessão com seu próprio estado
- Estado persistido no PostgreSQL (já tem a infra)
- Compactação automática por sessão (Context Window Guard)

---

## 8. SISTEMA DE PROMPT DINÂMICO — Prioridade Média

### O que o OpenClaw faz
Usa arquivos injetáveis no prompt:
- `AGENTS.md` — instruções e personalidade
- `SOUL.md` — identidade e valores
- `TOOLS.md` — ferramentas disponíveis
- `USER.md` — contexto sobre o usuário
- Skills ativos são injetados dinamicamente

### Recomendação para o AgentVPS
Criar arquivos equivalentes no `brain/`:
```
brain/
├── SYSTEM.md       # Personalidade e regras gerais
├── TOOLS.md        # Ferramentas disponíveis (gerado dinamicamente dos skills ativos)
├── USER.md         # Contexto sobre você
└── MEMORY.md       # Conhecimento destilado
```

O LangGraph já pode montar o system prompt concatenando esses arquivos. Quando um skill é ativado/desativado, o TOOLS.md é regenerado.

---

## 9. CLI E OBSERVABILIDADE — Prioridade Baixa

### O que o OpenClaw faz
- CLI rico: `openclaw doctor` (diagnóstico), `openclaw status`, `openclaw onboard`
- Logging estruturado
- Usage tracking (tokens, custo)

### Recomendação para o AgentVPS
O `agent-cli.sh` já existe. Expandir com:
- `agent-cli doctor` — verifica se todos os serviços estão rodando, RAM disponível, conectividade
- `agent-cli usage` — mostra tokens consumidos, custo estimado
- Log tudo em JSONL (reutiliza o mesmo formato da memória)

---

## 10. AUTOMAÇÃO (Cron + Webhooks) — Prioridade Baixa

### O que o OpenClaw faz
Suporte nativo a cron jobs e webhooks. O agente pode ser disparado por timer ou por evento externo, não só por mensagem.

### Recomendação para o AgentVPS
Você já tem n8n como ferramenta sob demanda. A integração seria:
1. n8n como orchestrador de triggers (webhooks, schedules, email)
2. n8n dispara o agente via API/Redis pub-sub
3. O agente executa e responde pelo Telegram

Isso já está no espírito da sua arquitetura — só precisa da cola entre n8n e o LangGraph.

---

## Roadmap Sugerido de Implementação

### Fase 1 — Fundação (próximas semanas)
- [ ] Gateway simples com adapter de Telegram
- [ ] JSONL transcripts para auditabilidade
- [ ] Context Window Guard no LangGraph
- [ ] Allowlist de Telegram IDs

### Fase 2 — Modularidade (1-2 meses)
- [ ] Sistema de Skills (`skills/` + SKILL.md)
- [ ] Prompt dinâmico (SYSTEM.md + TOOLS.md + USER.md + MEMORY.md)
- [ ] Approval workflow para ações destrutivas
- [ ] Session model isolado

### Fase 3 — Escalabilidade (2-3 meses)
- [ ] Adapter de Evolution API no Gateway
- [ ] Multi-agent routing básico
- [ ] CLI doctor + usage tracking
- [ ] Integração n8n → agente via triggers

---

## O que NÃO copiar do OpenClaw

Nem tudo do OpenClaw se aplica ao seu caso:

1. **Node.js/TypeScript** — Seu projeto é Python e faz sentido continuar assim com LangGraph. Não migre de stack.
2. **Apps nativos (macOS/iOS/Android)** — Complexidade desnecessária. Telegram é sua interface principal e isso está certo.
3. **12 canais simultâneos** — Comece com Telegram + Evolution API (WhatsApp). Não tente suportar tudo de uma vez.
4. **Browser automation** — O OpenClaw tem controle de Chrome/Chromium embutido. Com 2.4GB de RAM, isso é inviável na sua VPS. Use APIs quando precisar de dados web.
5. **Voice Wake / Talk Mode** — Feature premium do OpenClaw que não se aplica ao seu caso de uso.

---

## Conclusão

O OpenClaw é um projeto muito mais maduro e ambicioso, mas várias das suas decisões arquiteturais são **diretamente aplicáveis** ao AgentVPS, mesmo com as restrições de RAM. As lições mais valiosas são:

1. **Gateway-centric design** — desacopla canais do core
2. **Skills modulares** — extensibilidade sem editar código
3. **Memória simples (JSONL + .md)** — mais leve que vector DB para 90% dos casos
4. **Context Window Guard** — proteção contra overflow
5. **Segurança por camadas** — allowlists, approval workflows, tool policies

A boa notícia é que a fundação do AgentVPS (Docker, PostgreSQL, Redis, LangGraph, Telegram) já suporta todas essas melhorias. É uma questão de reestruturar, não de recomeçar.
