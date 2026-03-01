# Avaliacao Tecnica v4 — AgentVPS — 15 Fevereiro 2026

## Contexto

Quarta avaliacao apos execucao parcial do Sprint 02. O Sprint 02 tinha 12 jobs em 5 fases. Esta avaliacao foi feita lendo todos os arquivos Python do repositorio, verificando cada commit da sprint, e comparando o estado real do codigo com o plano.

**Avaliacao anterior (v3):** Score 5.0/10 — "Motor instalado, mas com carburador em vez de injecao eletronica."

---

## 1. O Que Mudou Desde a v3

### Entregas Concretas do Sprint 02

| Item Planejado | Status | Evidencia |
|---|---|---|
| T1-01: Remover API key exposta | **FEITO** | `grep -r "BSA1" core/` retorna 0 |
| T1-02: Remover debug log /tmp | **FEITO** | `grep -r "security_debug" core/` retorna 0 |
| T2-01: Tool Schemas (parameters_schema) | **FEITO** | Todos os 10 config.yaml tem parameters_schema |
| T2-02: react_node.py implementado | **FEITO** | 163 linhas, node_react + node_format_response + route_after_react |
| T2-03: test_react_intelligence.py | **FEITO** | 20 formulacoes de teste criadas |
| T3-01: Purificar shell_exec | **FEITO** | 397 -> 173 linhas, docstring diz "funcao pura" |
| T4-01: Migration PostgreSQL | **FEITO** | migration-autonomous.sql com 3 tabelas |
| T4-02: Engine com 6 passos | **FEITO** | engine.py com Trigger, CapGate, AutonomousLoop, create_proposal, _check_cap_gates |
| T4-03: Cap Gates implementados | **FEITO** | check_rate_limit, check_ram_threshold, check_security_level |
| T5-01: Remover dead code | **NAO FEITO** | system_tools.py (426 linhas), intent_classifier.py (42), semantic_memory.py (9) ainda existem |
| T5-02: Curar documentacao | **NAO FEITO** | Docs inalteradas |
| **CRITICO: Integrar react_node no graph.py** | **NAO FEITO** | graph.py importa 10 nos antigos. react_node nao eh importado nem usado. |

### O Gap Critico: Motor Montado Mas Nao Ligado

O `react_node.py` foi escrito com qualidade — 163 linhas limpas com `node_react`, `node_format_response`, e `route_after_react`. Ele faz exatamente o que o Sprint 02 planejou: LLM recebe tool schemas, decide qual tool usar via function calling, executa, e LLM formata resposta.

**Porem, o `graph.py` nao foi alterado.** O grafo continua com 10 nos:

```python
# graph.py (estado ATUAL)
workflow.add_node("classify", node_classify_intent)      # ANTIGO
workflow.add_node("load_context", node_load_context)
workflow.add_node("plan", node_plan)                      # ANTIGO
workflow.add_node("security_check", node_security_check)
workflow.add_node("execute", node_execute)                # ANTIGO (com heuristicas)
workflow.add_node("respond", node_generate_response)
workflow.add_node("save_memory", node_save_memory)
workflow.add_node("check_capabilities", node_check_capabilities)
workflow.add_node("self_improve", node_self_improve)
workflow.add_node("implement_capability", node_implement_capability)
```

O react_node.py nao aparece em nenhum lugar do graph.py. Isso significa que **o agente em producao continua usando o fluxo antigo**: classify -> plan -> execute(heuristicas). A inteligencia do function calling existe no codigo mas nao esta ativa.

Isso eh o equivalente a construir um motor V8, instalar no carro, mas esquecer de conectar a ignicao.

### Metricas Comparativas

| Metrica | v3 | v4 | Mudanca |
|---|---|---|---|
| Total linhas core/ | ~16.930 | 13.724 | -3.206 (-19%) |
| Linhas testes/ | 2.594 | 2.776 | +182 (+7%) |
| shell_exec linhas | 397 | 173 | -224 (-56%) |
| if/elif em shell_exec | 35+ | 21 | -14 (restantes sao classificacao de seguranca = OK) |
| API keys no codigo | 1 | 0 | CORRIGIDO |
| Debug logs em /tmp | 3 | 0 | CORRIGIDO |
| Dead code (linhas) | ~800 | 477 | -323 (parcial) |
| Nos no grafo | 10 | 10 | SEM MUDANCA (react nao plugado) |
| Tabelas autonomous | 0 | 3 | +3 (migration criada) |
| Lint errors | 785 | 0 | CORRIGIDO |

---

## 2. Problemas Criticos

### CRITICO 1: react_node.py Desconectado do Grafo

**Severidade:** BLOQUEANTE para a proposta de valor do projeto.

O AgentVPS se propoe a ser um "sistema inteligente, autonomo e auto-melhorante." Sem o react_node ativo, ele continua sendo um sistema de "botoes pre-codificados" — exatamente o que o usuario identifica como o problema fundamental.

**Localizacao:** `core/vps_langgraph/graph.py` — nao importa `react_node.py`
**Impacto:** 100% das mensagens passam pelo fluxo antigo (classify -> plan -> execute com heuristicas)
**Fix:** Rewirar graph.py para usar react_node em vez de classify+plan. ~30 linhas de mudanca.

### CRITICO 2: Dead Code Persiste

`system_tools.py` (426 linhas) ainda existe com `TOOLS_REGISTRY` intacto. `node_execute` em `nodes.py` ainda importa o registry legado como fallback. Dois registries coexistem desnecessariamente.

### IMPORTANTE: Engine Autonomo Parcialmente Integrado

O engine.py foi reescrito com o blueprint correto (Trigger -> Proposal -> CapGate -> Mission -> Complete). As tabelas PostgreSQL foram definidas na migration. Porem:
- A migration precisa ser aplicada no banco (nao eh automatica)
- Os triggers ainda usam `condition: lambda: True` para 4 de 6 triggers
- O `_execute_mission` so suporta `shell_exec` (hardcoded no elif)
- Nao ha notificacao Telegram para proposals DANGEROUS

---

## 3. O Que Funciona Bem

### Skill Registry — Excelente
O registry.py (203 linhas) eh o melhor codigo do projeto. Auto-discovery, carregamento dinamico, singleton, `list_tool_schemas()` funcional. Adicionar um skill novo requer apenas criar diretorio + handler.py + config.yaml.

### shell_exec Purificado — Bom
De 397 para 173 linhas. Docstring declara "funcao pura". Os if/elif restantes (21) sao para classificacao de seguranca (FORBIDDEN/DANGEROUS/MODERATE/SAFE), que eh uma responsabilidade legitima do skill. Nao ha mais heuristicas de interpretacao NLP.

### Seguranca — Melhorada Significativamente
- API key removida do codigo
- Debug log removido
- Cap Gates implementados (rate limit, RAM, security level)
- Classificacao de comandos shell robusta

### react_node.py — Bem Escrito (mesmo desconectado)
163 linhas limpas. System prompt claro. Logica de routing correta: tool_call -> security_check -> execute | direct_response -> respond. Quando for plugado, deve funcionar.

### Lint Clean
De 785 erros para 0. Ruff configurado e passando.

---

## 4. OpenClaw vs AgentVPS — O Que Aprender

### OpenClaw: Arquitetura em Fevereiro 2026

O OpenClaw (180k+ stars, Node.js/TypeScript) implementa patterns que o AgentVPS deveria adotar seletivamente:

| Pattern OpenClaw | O Que Faz | Relevancia para AgentVPS |
|---|---|---|
| **Plugin SDK + Manifest Registry** | Cada plugin tem manifest com schema validation, capability detection (tools, hooks, channels, services). Loader valida JSON schema antes de ativar. | ALTA — Adicionar schema validation nos configs do registry |
| **Tool Policy System** | 4 niveis de permissao: minimal, coding, messaging, full. Grupos (group:fs, group:runtime). Owner-only tools. | ALTA — Substituir o sistema plano de SecurityLevel por politicas por contexto |
| **Hook System** | Pre/post execution hooks globais. Permite logging, metricas, approval workflow sem modificar skills. | ALTA — Essencial para feedback loop e observabilidade |
| **Session Routing** | Cada canal/peer pode ser roteado para agentes diferentes com state isolado. | MEDIA — Util quando adicionar mais canais |
| **SQLite-vec para Embeddings** | Embeddings locais sem servidor separado. Batch processing multi-provider. Hybrid search. | ALTA — Substitui Qdrant (500MB RAM) por SQLite (~5MB) |
| **Skill Refresh** | Hot reload de skills sem restart do agente. | MEDIA — Util para desenvolvimento |
| **Memory Slot System** | Apenas 1 plugin de memoria ativo por vez, resolve conflitos automaticamente. | BAIXA — Relevante quando tiver plugins de terceiros |

### Patterns a NAO Adotar

| Pattern OpenClaw | Por Que Nao |
|---|---|
| ClawHub (marketplace de skills) | 11.7% maliciosos. Supply chain attack vetor. |
| Permissao irrestrita de shell | 3 CVEs em 3 semanas resultaram disso |
| Multi-provider com failover automatico | Complexidade desnecessaria com 1 provider |

### Recomendacao: Adotar 3 Patterns Prioritarios

1. **Hook System** — pre_execute / post_execute hooks para logging, metricas, e approval. Sem isso, nao ha feedback loop e o agente nao pode aprender com suas acoes.

2. **Tool Policy Layers** — Evoluir SecurityLevel plano (SAFE/MODERATE/DANGEROUS/FORBIDDEN) para politicas contextuais: quem esta pedindo, em que canal, com que historico. OpenClaw faz isso com profiles (minimal/coding/full).

3. **SQLite-vec** — Embeddings locais para memoria semantica. Qdrant consome 500MB+ de RAM. SQLite-vec consome ~5MB e roda in-process. Para 2.4GB de RAM total, essa diferenca eh critica.

---

## 5. Alinhamento com "The Autonomous Agent Blueprint"

### O Blueprint Define 6 Capacidades

| Capacidade | Blueprint | AgentVPS Status | Gap |
|---|---|---|---|
| **1. Percepcao** | Agente percebe ambiente via sensores | Triggers detectam RAM, erros, containers | Triggers sao cron, nao percepcao real |
| **2. Raciocinio** | LLM decide o que fazer baseado em contexto | react_node.py usa function calling | NAO ATIVO — grafo antigo em uso |
| **3. Acao** | Executa acoes no mundo real | 10 skills funcionais | OK mas dependem do grafo antigo |
| **4. Memoria** | Persiste aprendizado e contexto | PostgreSQL + Redis | Funcional mas sem semantica |
| **5. Autonomia** | Age sem instrucao humana | Engine + CapGates + Proposals | Parcial — triggers sao cronicos, nao deliberativos |
| **6. Auto-melhoria** | Melhora a si proprio | self_edit skill + learnings table | Placeholder — nao funcional |

### Nivel de Maturidade: 2 de 5

```
Nivel 1: Chatbot         — Recebe texto, retorna texto (concluido)
Nivel 2: Tool User       — Executa tools via heuristicas (ESTADO ATUAL)
Nivel 3: Reasoner        — LLM decide tools via function calling (CONSTRUIDO, NAO ATIVO)
Nivel 4: Autonomous      — Age proativamente baseado em contexto (PARCIALMENTE CONSTRUIDO)
Nivel 5: Self-Improving  — Aprende e melhora autonomamente (NAO INICIADO)
```

O AgentVPS esta no Nivel 2 em producao, com infraestrutura para Nivel 3 construida mas nao conectada.

---

## 6. O Problema Fundamental: Usabilidade Inteligente

O usuario colocou com precisao: "minha sensacao eh que atualmente estou desenvolvendo comando por comando igual a forma tradicional de codigos, estou criando botoes pre-codificados."

### Diagnostico

O projeto tem engenharia de alta qualidade (registry, cap gates, migration SQL, lint clean, testes) mas nao tem usabilidade inteligente ativa. As pecas estao montadas mas nao conectadas:

```
PECAS CONSTRUIDAS:                    CONEXOES FALTANDO:

[react_node.py]  ─── X ───>  [graph.py]    (nao importa react_node)
[cap_gates]      ─── X ───>  [telegram]    (nao notifica proposals)
[engine.py]      ─── X ───>  [react_node]  (nao usa function calling)
[learnings]      ─── X ───>  [triggers]    (nao influencia decisoes)
[tool_schemas]   ─── X ───>  [LLM call]    (nao enviados via graph antigo)
```

O sprint construiu 80% dos componentes corretos, mas nao fez o "ultimo km" de integracao que transforma componentes em sistema funcional.

### Causa Raiz

Cada componente foi construido e testado isoladamente (unit tests passam), mas a integracao end-to-end nao foi feita. O graph.py — que eh o "backbone" que conecta tudo — nao foi modificado.

---

## 7. Scores v4

| Dimensao | v3 | v4 | Tendencia | Justificativa |
|---|---|---|---|---|
| Arquitetura | 7/10 | 7/10 | -> | react_node bem desenhado mas desconectado. Registry excelente. Dead code persiste. |
| Seguranca | 5/10 | 7/10 | UP | API key removida, debug log removido, cap gates implementados. |
| Funcionalidade | 5/10 | 5/10 | -> | Mesmos 10 skills. react_node nao ativo = mesma experiencia usuario. |
| Testes | 6/10 | 7/10 | UP | +test_react_intelligence.py com 20 formulacoes. Lint 785->0. |
| Qualidade de Codigo | 4/10 | 6/10 | UP | shell_exec 397->173. Lint clean. Mas dead code (477 linhas) persiste. |
| Documentacao | 5/10 | 5/10 | -> | Inalterada. Planos obsoletos ainda existem. |
| DevOps | 8/10 | 8/10 | -> | CI/CD, Docker, pyproject.toml, ruff. |
| Autonomia | 3/10 | 5/10 | UP | Engine com 6 passos + Cap Gates + Migration SQL. Parcialmente integrado. |
| Inteligencia | 2/10 | 3/10 | UP | react_node escrito mas nao plugado = potencial nao realizado. |
| **OVERALL** | **5.0/10** | **5.9/10** | **UP +0.9** | Progresso real em seguranca e infraestrutura. Gap critico: integracao. |

### Diagnostico v4

**"Motor montado mas nao ligado."**

A Sprint 02 construiu os componentes certos: react_node com function calling, shell_exec purificado, cap gates, migration de tabelas autonomas. Mas o componente mais critico — rewirar o graph.py para usar o react_node — nao foi feito.

O score subiu 0.9 pontos (5.0 -> 5.9) pelo progresso real em seguranca (+2), qualidade (+2), testes (+1), e autonomia (+2). Mas a nota de Inteligencia subiu apenas 1 ponto (2 -> 3) porque a inteligencia esta construida mas inativa.

Quando o react_node for plugado no grafo, o score de Inteligencia deve saltar para 6-7/10 e o overall para ~7.0. Isso pode ser feito com ~30 linhas de mudanca no graph.py.

### Comparacao com Targets da Sprint 02

| Dimensao | Target Sprint 02 | Atingido v4 | Gap |
|---|---|---|---|
| Inteligencia | 7/10 | 3/10 | -4 (react nao plugado) |
| Seguranca | 8/10 | 7/10 | -1 (falta notificacao Telegram) |
| Funcionalidade | 6/10 | 5/10 | -1 (mesma UX) |
| Qualidade | 7/10 | 6/10 | -1 (dead code) |
| Autonomia | 6/10 | 5/10 | -1 (engine parcial) |
| **OVERALL** | **6.8/10** | **5.9/10** | **-0.9** |

---

## 8. Top 5 Acoes de Maior Impacto

### Acao 1: PLUGAR react_node.py no graph.py (TRANSFORMACIONAL)

**O que:** Modificar graph.py para importar e usar react_node em vez de classify+plan. Mudar de 10 nos para 6-7 nos.

**Codigo necessario (~30 linhas de mudanca em graph.py):**
```python
# REMOVER imports antigos: node_classify_intent, node_plan
# ADICIONAR:
from .react_node import node_react, node_format_response, route_after_react

# NOVO GRAFO:
workflow.add_node("load_context", node_load_context)
workflow.add_node("react", node_react)
workflow.add_node("security_check", node_security_check)
workflow.add_node("execute", node_execute)
workflow.add_node("format_response", node_format_response)
workflow.add_node("respond", node_generate_response)
workflow.add_node("save_memory", node_save_memory)

workflow.set_entry_point("load_context")
workflow.add_edge("load_context", "react")
workflow.add_conditional_edges("react", route_after_react, {
    "security_check": "security_check",
    "respond": "respond",
})
```

**Impacto:** Inteligencia salta de 3/10 para 6-7/10. OVERALL de 5.9 para ~7.0. Todas as 20 formulacoes de teste passam a funcionar. Zero heuristicas de NLP no fluxo.

**Esforco:** 2-4 horas.

### Acao 2: Remover Dead Code

**O que:** Deletar system_tools.py (426 linhas), intent_classifier.py (42 linhas), semantic_memory.py (9 linhas). Remover import legado de nodes.py.

**Impacto:** -477 linhas. Qualidade sobe de 6/10 para 7/10. Ninguem mais confunde qual registry usar.

**Esforco:** 1 hora.

### Acao 3: Implementar Hook System (inspirado OpenClaw)

**O que:** Criar pre_execute e post_execute hooks que rodam antes/depois de cada skill. Permite: logging estruturado de todas as execucoes, metricas de latencia por skill, registro de learnings automatico, e workflow de approval para acoes DANGEROUS.

**Impacto:** Cria o feedback loop necessario para auto-melhoria. Sem hooks, o agente executa mas nao aprende. Com hooks, cada execucao gera dados para melhoria.

**Esforco:** 8-12 horas.

### Acao 4: Goal-Oriented Autonomy (substituir cron por deliberacao)

**O que:** Em vez de triggers com `condition: lambda: True` que rodam como cron jobs, implementar goal-oriented behavior: o agente observa o estado do sistema, identifica gaps entre estado atual e estado desejado, e cria proposals para fechar os gaps.

**Exemplo:**
```
CRON (atual):     "A cada 60s, verificar containers"
DELIBERATIVO:     "Goal: todos containers criticos running.
                   Observacao: postgres parado.
                   Proposal: restart postgres.
                   CapGate: RAM ok, rate ok, security=DANGEROUS -> pedir approval."
```

**Impacto:** Autonomia sobe de 5/10 para 7/10. Diferencia de um scheduler.

**Esforco:** 16-20 horas.

### Acao 5: Feedback Loop (execucao -> learning -> melhoria)

**O que:** Conectar a tabela `learnings` ao ciclo de decisao. Quando o agente executa uma acao e falha, registra o aprendizado. Quando uma situacao similar aparece, consulta learnings antes de agir.

**Impacto:** Cria as bases para auto-melhoria real (Nivel 5 do Blueprint).

**Esforco:** 8-12 horas.

---

## 9. Prompt Para Validacao Cross-Model (Atualizado v4)

```
Voce eh um avaliador tecnico senior de software. Preciso de uma avaliacao extremamente detalhada, criteriosa e realista de um projeto no GitHub.

INSTRUCOES:
1. Clone e leia TODOS os arquivos Python do repositorio. NAO confie no README.
2. Para CADA arquivo, verifique se o codigo realmente funciona ou eh placeholder/stub.
3. Conte linhas reais de codigo funcional vs comentarios/docstrings/imports.
4. Identifique padroes (ou anti-padroes) recorrentes.

REPOSITORIO: https://github.com/Guitaitson/AgentVPS

CONTEXTO ATUAL (verificado em 15/02/2026):
- 78 arquivos Python no core/, ~13.724 linhas
- 2.776 linhas de testes
- shell_exec foi purificado de 397 para 173 linhas
- react_node.py (163 linhas) existe mas NAO esta integrado no graph.py
- graph.py ainda usa 10 nos antigos (classify, plan, execute com heuristicas)
- API key e debug log foram removidos
- Cap Gates implementados mas nao totalmente integrados
- Dead code: system_tools.py (426 linhas), intent_classifier.py (42), semantic_memory.py (9) ainda existem
- Lint clean (0 erros ruff)
- Migration SQL para tabelas autonomas existe

AVALIE ESTAS DIMENSOES (0-10 cada):

1. **INTELIGENCIA vs BOTOES** — O agente PENSA ou faz string matching?
   - O react_node.py usa function calling — mas esta integrado no graph.py?
   - O graph.py usa classify_intent + plan (antigo) ou react (novo)?
   - Se eu perguntar a mesma coisa de 5 formas diferentes, quantas funcionam?
   - Verifique: core/vps_langgraph/graph.py importa react_node?

2. **ARQUITETURA** — As pecas se encaixam ou sao componentes isolados?
   - react_node.py, engine.py, registry.py, graph.py — estao conectados?
   - Existe um fluxo end-to-end funcional ou cada parte roda isolada?
   - Quantos registries de tools coexistem? (skill registry vs system_tools)

3. **QUALIDADE DE CODIGO** — Evolucao real?
   - shell_exec: era 397, agora 173 — os if/elif restantes sao justificados?
   - Dead code: system_tools.py (426 linhas) ainda existe e eh usado?
   - Lint: 0 erros? Consistencia de estilo?

4. **SEGURANCA** — Melhorou?
   - API keys no codigo? Debug logs em /tmp?
   - Cap Gates funcionam? Proposals DANGEROUS pedem approval?
   - Classificacao de comandos shell eh robusta?

5. **AUTONOMOUS LOOP** — Implementado ou placeholder?
   - engine.py implementa o blueprint de 6 passos de verdade?
   - Triggers usam condicoes reais ou lambda: True?
   - Proposals sao persistidas no PostgreSQL?
   - Cap Gates bloqueiam proposals quando deveriam?
   - Existe notificacao para o usuario quando proposal eh DANGEROUS?

6. **FUNCIONALIDADE** — O que realmente funciona end-to-end?
   - Envie mentalmente "quanta RAM tenho?" — o que acontece no grafo?
   - Envie "tem o Docker?" — passa pelo react_node ou pelo classify antigo?
   - Qual eh a experiencia real do usuario via Telegram?

7. **AUTO-MELHORIA** — O agente aprende com suas acoes?
   - Existe feedback loop (execucao -> learning -> melhoria)?
   - A tabela learnings eh consultada antes de novas decisoes?
   - O agente pode criar novos skills autonomamente?

8. **COMPARACAO COM OPENCLAW** — Dado que OpenClaw (180k stars) tem:
   - Hook system (pre/post execution)
   - Tool Policy layers (minimal/coding/messaging/full)
   - Plugin SDK com manifest validation
   - SQLite-vec para embeddings sem servidor dedicado
   - Session routing e multi-agent
   Quais desses patterns o AgentVPS deveria adotar?

9. **TOP 5 ACOES** — Liste as 5 coisas que teriam maior impacto, com esforco estimado.

FORMATO DE SAIDA:
- Para cada dimensao: nota 0-10, 3-5 paragrafos de analise com file paths especificos
- Nota overall com media ponderada (Inteligencia e Autonomia pesam 2x)
- Diagnostico em uma frase
- Comparacao explicita: "Na v3 era X, agora eh Y, deveria ser Z"
- Avalie o gap entre "componentes construidos" e "sistema integrado"
```

---

## 10. Conclusao

O Sprint 02 foi um sprint de construcao, nao de integracao. Construiu os componentes certos (react_node, cap gates, migration SQL, shell_exec purificado) mas nao fez a integracao que transforma componentes em sistema funcional.

A acao de maior impacto eh tambem a mais simples: plugar o react_node.py no graph.py. Isso requer ~30 linhas de mudanca e transforma a nota de Inteligencia de 3/10 para 6-7/10.

O projeto tem maturidade de engenharia alta (lint clean, testes, registry pattern, cap gates) mas maturidade de inteligencia baixa (o agente nao pensa, reage a patterns). A proxima sprint deve focar em integracao e ativacao, nao em construcao de novos componentes.

**Score v4: 5.9/10** (subiu de 5.0 na v3)
**Score potencial apos integracao: ~7.0/10** (apenas plugando react_node)
**Score alvo Sprint 03: 7.5/10** (react + cleanup + hooks + autonomia deliberativa)
