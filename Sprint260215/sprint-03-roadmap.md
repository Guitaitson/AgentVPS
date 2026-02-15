# Sprint 03 Roadmap — De Motor Montado Para Motor Ligado

## Visao Geral

| Fase | Nome | Jobs | Horas | Semana | Entrega |
|------|------|------|-------|--------|---------|
| **T1** | Plugar React + Adaptar Execute | 2 | ~6h | Dia 1 | Grafo inteligente ATIVO |
| **T2** | Dead Code Cleanup | 1 | ~1h | Dia 1 | -477 linhas, 1 unico registry |
| **T3** | Hook System + Feedback Loop | 2 | ~8h | Semana 1 | Observabilidade + aprendizado |
| **T4** | Triggers Reais + Approvals | 2 | ~8h | Semana 2 | Autonomia deliberativa |
| **T5** | Curar Documentacao | 1 | ~2h | Paralelo | Docs limpos e atualizados |
| **TOTAL** | | **8 jobs** | **~25h** | **2 semanas** | |

> Sprint 03 tem METADE das horas da Sprint 02 (25h vs 54h) porque o trabalho eh integracao, nao construcao.

---

## T1 — Plugar React + Adaptar Execute (Dia 1, 6h)

> **Fazer ANTES de qualquer outra coisa. Desbloqueia tudo.**

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T1-01 | **Plugar react_node no graph.py** — Substituir imports de classify_intent + plan por react_node. Reconstruir grafo com 7 nos. Testar end-to-end com 20 formulacoes. | 4h | Grafo com react ativo |
| T1-02 | **Adaptar node_execute** — Remover import de system_tools. Garantir compatibilidade com output do react_node. Manter /ram e /status funcionando. | 2h | node_execute limpo |

### Milestone T1: "Motor Ligado"
```
ANTES: User -> classify -> plan -> execute(heuristicas) -> respond
DEPOIS: User -> load_context -> react(function calling) -> security -> execute -> format -> respond

Verificacao:
[ ] "quanta RAM?" -> react chama get_ram -> resposta natural
[ ] "tem o docker?" -> react chama shell_exec(which docker) -> resposta natural
[ ] "docker ta instalado?" -> MESMA resposta (function calling entende)
[ ] "o docker esta na maquina?" -> MESMA resposta
[ ] "ola!" -> resposta direta (sem tool)
[ ] /ram -> continua funcionando
[ ] /status -> continua funcionando
```

---

## T2 — Dead Code Cleanup (Dia 1, 1h)

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T2-01 | **Deletar dead code** — Remover system_tools.py (426 linhas), intent_classifier.py (42 linhas), semantic_memory.py (9 linhas). Limpar imports. | 1h | -477 linhas, 0 imports quebrados |

### Milestone T2: "Codigo Limpo"
```
[ ] ls core/tools/system_tools.py -> No such file
[ ] ls core/vps_langgraph/intent_classifier.py -> No such file
[ ] ls core/vps_agent/semantic_memory.py -> No such file
[ ] grep -r "system_tools\|intent_classifier\|semantic_memory" core/ -> 0
[ ] CI verde
```

---

## T3 — Hook System + Feedback Loop (Semana 1, 8h)

> **Cria observabilidade e aprendizado. Inspirado no OpenClaw hook-runner-global.**

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T3-01 | **Hook System** — Criar core/hooks/runner.py com HookRunner, HookContext, pre/post hooks. 3 hooks builtin: logging, metrics, learning. Integrar no node_execute. | 4h | Hooks executando a cada skill |
| T3-02 | **Feedback Loop** — Hook pre-execute consulta learnings. Se skill falhou 3x na ultima hora, adiciona warning. Hook post-execute registra erros novos. | 4h | Ciclo learning -> consulta -> warning |

### Milestone T3: "Agente Observavel"
```
[ ] core/hooks/runner.py existe
[ ] Cada execucao de skill gera log "skill_executed" com duracao
[ ] Redis tem counters por skill
[ ] Erros sao registrados na tabela learnings
[ ] Learnings sao consultados antes de nova execucao
[ ] Warning aparece quando skill falhou 3x recentemente
```

---

## T4 — Triggers Reais + Approvals (Semana 2, 8h)

> **De cron jobs para percepcao real do estado do sistema.**

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T4-01 | **Triggers com condicoes reais** — Substituir 4 `lambda: True` por funcoes que verificam estado (ultimo check, count de rows, skill usage, errors). | 4h | 0 triggers com lambda: True |
| T4-02 | **Approvals Telegram** — Proposals DANGEROUS geram mensagem Telegram. Novos comandos: /approve, /reject, /proposals. | 4h | Approval workflow funcional |

### Milestone T4: "Agente Deliberativo"
```
[ ] health_check roda apenas quando ultimo check > 60s
[ ] memory_cleanup roda apenas quando conversation_log > 1000
[ ] skill_stats roda apenas quando houve uso
[ ] Proposal DANGEROUS -> mensagem Telegram
[ ] /approve 1 -> aprova e executa
[ ] /reject 1 -> rejeita com nota
[ ] /proposals -> lista pendentes
```

---

## T5 — Curar Documentacao (Paralelo, 2h)

| # | Job | Horas | Entrega |
|---|-----|-------|---------|
| T5-01 | **Docs curadas** — Mover planos obsoletos para archive/. Atualizar ARCHITECTURE.md e README.md com estado real. | 2h | Docs limpas |

---

## Cronograma

```
Dia 1                  Semana 1              Semana 2
|                      |                     |
+- T1-01 Plugar React  +- T3-01 Hook System  +- T4-01 Triggers Reais
+- T1-02 Adaptar Exec  +- T3-02 Feedback     +- T4-02 Approvals Telegram
+- T2-01 Dead Code     |                     |
|                      |                     +- T5-01 Docs
|                      |                     |
v Motor Ligado         v Agente Observavel   v Agente Deliberativo
```

---

## Impacto nos Scores

| Dimensao | v4 (atual) | Apos T1-T2 | Apos T3-T5 | Como |
|---|---|---|---|---|
| Inteligencia | 3/10 | **7/10** | 7/10 | React plugado = function calling ativo |
| Seguranca | 7/10 | 7/10 | **8/10** | Approval workflow para proposals DANGEROUS |
| Funcionalidade | 5/10 | **6/10** | **7/10** | Qualquer formulacao funciona + hooks |
| Qualidade | 6/10 | **7/10** | **8/10** | -477 dead code + hooks limpos |
| Autonomia | 5/10 | 5/10 | **7/10** | Triggers reais + approvals + feedback |
| Testes | 7/10 | 7/10 | 7/10 | Manter CI verde |
| Documentacao | 5/10 | 5/10 | **7/10** | Docs curadas |
| DevOps | 8/10 | 8/10 | 8/10 | Inalterado |
| Arquitetura | 7/10 | **8/10** | **8/10** | 1 registry, hooks, grafo limpo |
| **OVERALL** | **5.9/10** | **6.8/10** | **7.5/10** | **+1.6 pontos** |

### Projecao de Maturidade

```
                Nivel 1     Nivel 2      Nivel 3      Nivel 4      Nivel 5
                Chatbot     Tool User    Reasoner     Autonomous   Self-Improve
                                |
v4 (atual):     =============[X]         (grafo antigo, heuristicas)
                                         |
Apos T1-T2:     ====================[X]  (react ativo, function calling)
                                                      |
Apos T3-T5:     =============================[X]      (hooks, feedback, triggers reais)
                                                                    |
Sprint 04-05:   ======================================[X]           (goals, SQLite-vec, self-edit)
```

---

## Riscos

| Risco | Probabilidade | Impacto | Mitigacao |
|---|---|---|---|
| Function calling do Gemini Flash nao funciona bem | Media | Alto | Testar antes com 5 queries. Fallback: Claude via OpenRouter |
| node_execute incompativel com react output | Baixa | Medio | react_node gera mesmo formato que plan antigo |
| Hooks adicionam latencia perceptivel | Baixa | Baixo | Hooks sao async, nao bloqueiam |
| Triggers reais perdem health checks | Media | Medio | Log quando trigger NAO dispara para debug |

---

## Metricas de Sucesso da Sprint 03

```
QUANTITATIVAS:
[ ] Score Overall >= 7.5/10
[ ] Score Inteligencia >= 7/10
[ ] Nos no grafo: 7 (nao 10)
[ ] Dead code: 0 linhas (nao 477)
[ ] Triggers com lambda: True: 0 (nao 4)
[ ] 20/20 formulacoes funcionam end-to-end

QUALITATIVAS:
[ ] Usuario pode perguntar qualquer coisa de qualquer forma e funciona
[ ] Sistema aprende com erros (feedback loop)
[ ] Proposals autonomas geram notificacao
[ ] Codigo limpo, 1 unico registry, 0 imports legados
```
