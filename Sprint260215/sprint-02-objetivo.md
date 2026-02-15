# 🎯 Sprint 02: De Botões Pré-Codificados Para Inteligência Real

## Uma Frase

**Fazer o agente PENSAR em vez de fazer string matching.**

---

## O Problema (Diagnosticado na Avaliação v3)

O AgentVPS hoje funciona assim:

```
Usuário: "tem o Node.js instalado?"

1. LLM classifica intent → "task" (gasta tokens)
2. node_plan roteia para shell_exec
3. shell_exec._interpret_and_generate_command():
   - Testa "tem o" in text → match → "which nodejs"
   - 20+ blocos if/elif hardcoded
4. Executa "which nodejs"
5. shell_exec.execute():
   - Testa "tem o" in text → match → formata "✅ Sim, está instalado"
   - 15+ blocos if/elif hardcoded
```

**Total: 2 chamadas LLM + 35 blocos if/elif para uma pergunta simples.**

Agora mude a formulação para "o Node está na máquina?" — nenhum pattern reconhece "na máquina". Cai no fallback LLM (3ª chamada). Funciona com latência triplicada.

**Isso NÃO é inteligência. É simulação de inteligência com string matching.**

---

## O Objetivo Desta Sprint

Ao final desta sprint:

1. O agente entende QUALQUER formulação de QUALQUER pergunta — sem heurísticas hardcoded
2. O LLM decide qual tool usar e com quais parâmetros (function calling / tool use)
3. Skills são funções puras que recebem parâmetros estruturados e retornam output raw
4. O LLM interpreta o output e gera resposta conversacional
5. O Autonomous Loop cria proposals reais em PostgreSQL com cap gates
6. Zero API keys no código

```
ANTES (botões):                    DEPOIS (inteligência):
                                   
User → LLM classify (tokens)      User → LLM com tools disponíveis
     → node_plan (if/elif)              → LLM decide: "chamar shell_exec(cmd='which node')"
     → shell_exec 397 linhas            → shell_exec executa (30 linhas)
       → 20 patterns interpret           → retorna output raw
       → maybe LLM again (tokens)       → LLM gera resposta natural
       → 15 patterns format             
     → respond                     1 chamada LLM para decidir
                                   1 chamada LLM para responder
2-3 chamadas LLM + 35 if/elif     0 if/elif, funciona com qualquer formulação
```

---

## Métricas de Sucesso

| Métrica | Antes | Depois | Como Medir |
|---|---|---|---|
| Blocos if/elif no shell_exec | 35+ | 0 | `grep -c "if\|elif" shell_exec/handler.py` |
| Linhas do shell_exec handler | 397 | <80 | `wc -l handler.py` |
| Chamadas LLM por mensagem | 2-3 | 2 (decidir + responder) | Log de chamadas |
| Formulações entendidas | ~60% (as que matcham) | ~98% (LLM entende) | Teste com 20 formulações |
| API keys no código | 1 (Brave) | 0 | `grep -r "BSA1\|API_KEY.*=" --include="*.py"` |
| Tabelas autonomous no PostgreSQL | 0 | 3 (proposals, missions, policies) | `psql \dt` |
| Proposals criados por trigger | 0 (salva no Redis efêmero) | Persistidas no PostgreSQL | `SELECT count(*) FROM agent_proposals` |

---

## O Que Esta Sprint NÃO É

- **Não é adicionar mais skills.** 10 skills é suficiente. O problema não é quantidade, é inteligência.
- **Não é reescrever o grafo.** Simplificamos nós, não reescrevemos de zero.
- **Não é implementar RAG/Qdrant.** Memória semântica fica para depois.
- **Não é multi-channel.** Telegram continua.

---

## Restrições

1. **RAM: 2.4 GB** — Function calling não consome RAM extra significativa
2. **Custo LLM: ~mesmo** — Trocamos 2-3 chamadas burras por 2 chamadas inteligentes
3. **Backward compatible** — Commands `/ram`, `/status` etc continuam funcionando
4. **Model: Gemini 2.5 Flash Lite** — Suporta function calling via OpenRouter
5. **Testes** — Cada mudança mantém CI verde

---

## Dependências

```
T1 (Segurança Urgente) ──────── Independente, fazer PRIMEIRO
    │
T2 (ReAct + Function Calling) ── Principal entrega
    │
T3 (Skill Purification) ──────── Consequência de T2
    │   (skills viram funções puras)
    │
T4 (Autonomous Blueprint Real) ─ Depende de skills puros
    │
T5 (Cleanup Final) ───────────── Paralelo com qualquer fase
```
