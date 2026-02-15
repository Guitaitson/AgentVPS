# Sprint 03: De Motor Montado Para Motor Ligado

## Uma Frase

**Ativar a inteligencia que ja foi construida e dar o primeiro passo rumo a autonomia real.**

---

## O Problema (Diagnosticado na Avaliacao v4)

O Sprint 02 construiu os componentes corretos mas nao os conectou:

```
ESTADO ATUAL:                          O QUE DEVERIA SER:

react_node.py [EXISTE]                 react_node.py [ATIVO no grafo]
   |                                      |
   X (nao conectado)                      |
   |                                      v
graph.py [USA GRAFO ANTIGO]            graph.py [USA REACT]
   |                                      |
   v                                      v
classify -> plan -> execute             react -> security -> execute -> format
(heuristicas, 10 nos)                  (function calling, 6 nos)
```

O agente tem um cerebro (react_node) construido mas desligado. Em producao, usa o cerebro antigo (classify + plan + heuristicas).

---

## O Objetivo Desta Sprint

Ao final desta sprint:

1. **react_node ATIVO** — graph.py usa react em vez de classify+plan. LLM decide tools via function calling. Qualquer formulacao funciona.
2. **Zero dead code** — system_tools.py, intent_classifier.py, semantic_memory.py deletados. Um unico registry.
3. **Hook system** — pre/post execution hooks para logging, metricas, e feedback. Inspirado OpenClaw.
4. **Triggers com condicoes reais** — Substituir `lambda: True` por condicoes que verificam estado do sistema.
5. **Feedback loop basico** — Execucoes geram learnings. Learnings sao consultados antes de novas decisoes.

```
SPRINT 02 (construcao):                SPRINT 03 (integracao + ativacao):

Construiu react_node.py                Pluga react_node no graph.py
Construiu cap gates                    Conecta cap gates ao Telegram
Construiu migration SQL                Ativa triggers com condicoes reais
Purificou shell_exec                   Remove dead code restante
Criou testes                           Adiciona hook system
                                       Cria feedback loop
```

---

## Metricas de Sucesso

| Metrica | Antes (v4) | Depois | Como Medir |
|---|---|---|---|
| Nos no grafo | 10 (antigo) | 6-7 (react) | Contar nodes em graph.py |
| react_node importado em graph.py | Nao | Sim | `grep "react_node" graph.py` |
| Dead code (linhas) | 477 | 0 | Arquivos deletados |
| Formulacoes entendidas | ~60% (matching) | ~98% (LLM) | Teste 20 formulacoes end-to-end |
| Triggers com lambda: True | 4/6 | 0/6 | Inspecao do engine.py |
| Hook system | Nao existe | pre/post execute | Verificar logs de hooks |
| Learnings consultados | Nao | Sim | `grep "learnings" react_node.py` |
| Score Inteligencia | 3/10 | 7/10 | Avaliacao v5 |
| Score Overall | 5.9/10 | 7.5/10 | Avaliacao v5 |

---

## O Que Esta Sprint NAO Eh

- **Nao eh construir novos componentes.** Os componentes existem. Eh CONECTA-LOS.
- **Nao eh adicionar skills.** 10 skills eh suficiente.
- **Nao eh implementar RAG/embeddings.** SQLite-vec fica para Sprint 04.
- **Nao eh goal-oriented autonomy.** Goals ficam para Sprint 04-05.
- **Nao eh multi-channel.** Telegram continua.

---

## Principio Guia

**"Integrar > Construir"**

O Sprint 02 provou que sabemos construir componentes de qualidade. O Sprint 03 prova que sabemos conecta-los em um sistema funcional. A diferenca entre um kit de pecas e um motor funcionando eh integracao.

---

## Restricoes

1. **RAM: 2.4 GB** — Sem novos servicos permanentes
2. **Custo LLM: ~mesmo** — 2 chamadas por mensagem (react + format)
3. **Backward compatible** — Commands /ram, /status continuam funcionando
4. **Model: Gemini 2.5 Flash Lite** — Suporta function calling
5. **Testes** — CI verde em cada commit
6. **Zero downtime** — Deploy sem interromper servico

---

## Dependencias

```
T1 (Plugar React) ──────────── PRIMEIRO (desbloqueia tudo)
    |
T2 (Dead Code) ─────────────── Paralelo com T1
    |
T3 (Hook System) ───────────── Depende de T1 (hooks rodam no novo grafo)
    |
T4 (Triggers Reais) ────────── Depende de T1 (usam function calling)
    |
T5 (Feedback Loop) ─────────── Depende de T3 (hooks alimentam learnings)
```
