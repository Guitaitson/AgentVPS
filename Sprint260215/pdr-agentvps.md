# 📋 PDR — Project Decision Record — AgentVPS

> Registro de decisões estratégicas do projeto. Cada decisão documenta contexto, alternativas, e razão.

---

## PDR-001: Continuar com AgentVPS (vs Migrar para OpenClaw)

**Data:** 08 Fev 2026 (primeira decisão), revalidada 15 Fev 2026
**Status:** APROVADA — MANTIDA
**Decidido por:** Guilherme (owner)

### Contexto

O OpenClaw (ex-Moltbot, ex-Clawdbot) explodiu para 180k+ GitHub stars em fevereiro 2026. Oferece 50+ integrações, 3.286 skills na ClawHub, self-improvement funcional, e comunidade ativa. É a comparação inevitável para qualquer projeto de agente autônomo.

### Alternativas Avaliadas

| Alternativa | Prós | Contras |
|---|---|---|
| **Migrar 100% para OpenClaw** | 180k community, 50+ integrações, self-improvement real | 3 CVEs em 3 semanas, 42k instâncias expostas, 11.7% skills maliciosos, Node.js (2-4GB min), Palo Alto classificou como "maior insider threat potencial 2026" |
| **Fork do OpenClaw + hardening** | Base funcional completa, comunidade contribui | Necessário auditar 100k+ linhas Node.js, manter fork sincronizado, stack diferente (JS vs Python) |
| **Continuar AgentVPS** | Segurança por design, Python/LangGraph (expertise), 2.4GB VPS compatível, 0 CVEs | Solo project, 10 skills vs 3.286, sem self-improvement real |
| **Híbrido: AgentVPS + OpenClaw patterns** | Melhor dos dois mundos | Mais complexo de implementar |

### Decisão

**Continuar com AgentVPS**, adotando patterns do OpenClaw sem herdar problemas.

### Razões

1. **Segurança não é negociável.** O AgentVPS gerencia uma VPS com dados corporativos de fleet leasing. Um CVE como o 2026-25253 no OpenClaw poderia expor dados de clientes. O AgentVPS tem 0 CVEs e security-by-design (3-level allowlist).

2. **Restrição de hardware real.** A VPS tem 2.4GB RAM. O OpenClaw requer 2-4GB mínimo antes de adicionar PostgreSQL e Redis. Ficaria no limite.

3. **O problema do AgentVPS não é features — é inteligência.** Adicionar mais skills não resolve. O que resolve é fazer o agente pensar via function calling em vez de string matching. Isso independe de features.

### Riscos Aceitos

- Desenvolvimento mais lento (solo vs 500+ contributors)
- Menos integrações disponíveis
- Sem comunidade para bug reports

### O Que Aprender do OpenClaw

| Pattern OpenClaw | Adaptação AgentVPS | Status |
|---|---|---|
| ClawHub skill discovery com SKILL.md | Skill Registry com config.yaml | ✅ Implementado Sprint 01 |
| Self-improvement (escrever próprios skills) | Futuro: LLM gera handler.py + config.yaml → testa → registra | Planejado |
| SOUL.md (system prompt persistente) | system_prompt.md editável pelo agente | Planejado |
| Persistent memory cross-session | PostgreSQL agent_memory + learnings | ⚠️ Parcial |
| 50+ integrações nativas | 10 skills é suficiente para uso atual | Consciente |

### Revisão

Esta decisão será reavaliada quando: (1) OpenClaw atingir 6 meses sem CVE crítico, (2) VPS for upgraded para 4GB+, ou (3) necessidade de integrações massivas surgir.

---

## PDR-002: Adotar ReAct com Function Calling (vs String Matching)

**Data:** 15 Fev 2026
**Status:** APROVADA
**Decidido por:** Guilherme + avaliação técnica v3

### Contexto

A avaliação v3 identificou que o shell_exec/handler.py tem 397 linhas com 35+ blocos if/elif para mapear linguagem natural → comandos. Isso é fundamentalmente o mesmo padrão de "botões pré-codificados" que o projeto propõe superar. O LLM é usado como tradutor (text → text), não como raciocinador (text → decisão → ação).

### Alternativas Avaliadas

| Alternativa | Prós | Contras |
|---|---|---|
| **Manter heurísticas + expandir patterns** | Funciona para casos conhecidos, determinístico | Cada nova formulação requer editar código. N^2 patterns para N perguntas. |
| **LLM classify → LLM plan → LLM interpret (3 chamadas)** | Mais inteligente que heurísticas | 3 chamadas LLM por mensagem. Custo e latência altos. |
| **ReAct com function calling (2 chamadas)** | LLM decide tool com 1 chamada. LLM formata com 1 chamada. Zero heurísticas. | Requer model com suporte a tool_use. Menos determinístico. |
| **ReAct single-shot (1 chamada)** | Mínimo custo | Limitado para ações complexas. Difícil formatar resposta. |

### Decisão

**ReAct com function calling (2 chamadas):** LLM decide qual tool usar → executa → LLM formata resposta.

### Razões

1. Gemini 2.5 Flash (já configurado via OpenRouter) suporta function calling nativamente.
2. Custo é similar ou menor: troca 2-3 chamadas burras por 2 chamadas inteligentes.
3. Elimina 100% das heurísticas hardcoded → qualquer formulação funciona.
4. Adicionar novo skill = adicionar tool schema ao config.yaml → zero código de roteamento.

### Riscos

- Function calling pode ter alucinações (chamar tool errada). Mitigação: security_check antes de executar.
- Latência pode aumentar se o LLM demorar para decidir. Mitigação: timeout de 10s + fallback para resposta direta.
- Modelo gratuito pode não suportar tools. Mitigação: testar antes; fallback para classify+plan se necessário.

---

## PDR-003: Autonomous Loop com PostgreSQL (vs Redis/In-Memory)

**Data:** 15 Fev 2026
**Status:** APROVADA
**Decidido por:** Guilherme + avaliação técnica v3

### Contexto

O engine.py da Sprint 01 implementou triggers como cron jobs in-memory com proposals efêmeras no Redis. Isso não é o Autonomous Blueprint de 6 passos. Falta persistência, cap gates, eventos, e re-triggering.

### Decisão

**PostgreSQL para proposals/missions/policies.** Redis continua para cache efêmero e contadores.

### Razões

1. PostgreSQL já roda na VPS e é o banco principal.
2. Proposals precisam sobreviver a restarts (persistência).
3. Policies devem ser editáveis sem redeploy (tabela, não código).
4. Histórico de missões é valioso para auto-improvement futuro.
5. Redis não suporta queries complexas (ex: "proposals rejeitadas por RAM na última semana").

---

## PDR-004: Separação de Responsabilidades nos Skills

**Data:** 15 Fev 2026
**Status:** APROVADA

### Contexto

O shell_exec handler faz 3 trabalhos: interpretar intenção (20+ heurísticas), executar comando (subprocess), e formatar resposta (15 formatadores). Isso viola Single Responsibility.

### Decisão

Skills são **funções puras**: recebem parâmetros estruturados (do function calling), executam ação, retornam output raw. Interpretação é responsabilidade do LLM (via react node). Formatação é responsabilidade do LLM (via format_response node).

### Antes vs Depois

```
ANTES:
  shell_exec.execute(raw_input="tem o docker?")
    → _interpret_and_generate_command("tem o docker?")  # 100+ linhas
    → subprocess.run("which docker")
    → _format_response("tem o" in input → "✅ Sim, está instalado")  # 100+ linhas
  Total: 397 linhas

DEPOIS:
  shell_exec.execute(command="which docker")  # Parâmetro vem do LLM
    → classify_command("which docker") → SAFE
    → subprocess.run("which docker")
    → return "/usr/bin/docker"  # Output raw
  Total: ~70 linhas
  (LLM formata: "Sim, Docker está instalado em /usr/bin/docker")
```

---

## PDR-005: Stack Tecnológica (Confirmação)

**Data:** 15 Fev 2026
**Status:** CONFIRMADA

| Componente | Tecnologia | Alternativa Avaliada | Razão |
|---|---|---|---|
| Linguagem | Python 3.12 | Node.js (OpenClaw) | Expertise, LangGraph, menor RAM |
| Orchestração | LangGraph | LangChain, CrewAI | Controle explícito do grafo |
| Database | PostgreSQL 16 | SQLite, Supabase | Já rodando, asyncpg, JSONB |
| Cache | Redis 7 | Memcached | Já rodando, pub/sub futuro |
| LLM | Gemini 2.5 Flash Lite (OpenRouter) | GPT-4o, Claude | Gratuito, function calling |
| Interface | Telegram | WhatsApp, Discord | Simples, funcional, API estável |
| CI/CD | GitHub Actions | GitLab CI | Já configurado |
| Linter | Ruff | Black + flake8 | Mais rápido, all-in-one |

---

## Índice de Decisões

| # | Decisão | Data | Status |
|---|---|---|---|
| PDR-001 | Continuar AgentVPS (vs OpenClaw) | 08/02/26 | ✅ Mantida |
| PDR-002 | ReAct com Function Calling | 15/02/26 | ✅ Aprovada |
| PDR-003 | PostgreSQL para Autonomous Loop | 15/02/26 | ✅ Aprovada |
| PDR-004 | Skills como funções puras | 15/02/26 | ✅ Aprovada |
| PDR-005 | Stack tecnológica | 15/02/26 | ✅ Confirmada |
