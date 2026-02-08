# 🔧 AgentVPS — FASE 0: Estabilização v1

## Por que esta fase existe

O roadmap v2 (Fases 1-4, 44 jobs, ~508h) assume uma **fundação estável**. Hoje a v1 tem bugs críticos que impedem o funcionamento básico. A Fase 0 corrige o que está quebrado sem construir nada novo — o princípio é **"consertar, não construir"**.

Tudo que será **reescrito** na v2 recebe apenas a **correção mínima** aqui. Tudo que **não existe na v2** (porque é infraestrutura básica que a v2 herda) recebe atenção adequada.

---

## Diagnóstico Técnico dos Problemas

### 🔴 CRÍTICO 1: `self_improve` não gera resposta

**Sintoma:** `result.get("response")` retorna `None` quando intent é `self_improve`.

**Causa raiz** (são duas):

**Causa A — Roteamento do grafo está errado:**
```python
# graph.py atual
workflow.add_conditional_edges("plan", lambda s: s.get("intent", "unknown"), {
    "self_improve": "respond",  # ← VAI DIRETO PARA respond, SEM passar por capabilities
})
```
O intent `self_improve` deveria passar por `check_capabilities` → `self_improve` → `respond`, mas está pulando direto para `respond`.

**Causa B — `node_generate_response` não trata `self_improve`:**
```python
# nodes.py atual
def node_generate_response(state: AgentState) -> AgentState:
    intent = state.get("intent")
    execution_result = state.get("execution_result")
    
    if execution_result:
        response = execution_result
    elif intent in ["chat", "question"]:  # ← self_improve NÃO ESTÁ AQUI
        response = generate_response_sync(...)
    else:
        response = "Comando executado com sucesso! ✅"  # ← cai aqui, mas...
    
    return {**state, "response": response}
```

Mesmo que o roteamento fosse corrigido, o nó `respond` não sabe o que fazer com `self_improve`. Se não há `execution_result` e o intent não é `chat` nem `question`, ele retorna a string genérica "Comando executado com sucesso!" — **mas isso deveria funcionar**, já que ele retorna com `response` na state. O problema real é provavelmente que o fluxo nem chega ao `respond` ou que o `response` key está sendo sobrescrita em algum ponto.

**Investigação necessária:** Verificar no código real se existe algum nó após `respond` que está limpando o state, ou se o `ainvoke` do LangGraph não está retornando a key `response`.

### 🔴 CRÍTICO 2: `timezone is not defined`

**Sintoma:** Erro de runtime quando `check_capabilities` é invocado.

**Causa raiz:** `registry.py` usava `timezone.utc` sem importar `timezone`:
```python
# ANTES (quebrado)
from datetime import datetime
self.created_at = datetime.now(timezone.utc)  # NameError: timezone not defined

# DEPOIS (corrigido?)
from datetime import datetime, timezone
self.created_at = datetime.now(timezone.utc)  # OK
```

**Status:** Segundo o documento, o import foi adicionado mas **não foi testado**. É necessário confirmar que o fix está no código real da VPS e rodar um teste.

### 🔴 CRÍTICO 3: Código duplicado em 3 locais

**Sintoma:** Confusão sobre qual arquivo é o "real":
```
/opt/vps-agent/core/
├── graph.py              ← VERSÃO ANTIGA (raiz)
├── nodes.py              ← VERSÃO ANTIGA (raiz)
├── state.py              ← VERSÃO ANTIGA (raiz)
├── memory.py             ← VERSÃO ANTIGA (raiz)
├── semantic_memory.py    ← VERSÃO ANTIGA (raiz)
├── vps_agent/
│   ├── agent.py          ← process_message_async (ATIVO)
│   ├── graph.py          ← VERSÃO ANTIGA?
│   ├── nodes.py          ← VERSÃO ANTIGA?
│   └── semantic_memory.py
├── vps_langgraph/
│   ├── graph.py          ← build_agent_graph (ATIVO)
│   ├── nodes.py          ← node_classify_intent, etc (ATIVO)
│   ├── state.py          ← AgentState (ATIVO)
│   └── memory.py         ← AgentMemory (ATIVO)
└── capabilities/
    └── registry.py       ← CapabilitiesRegistry (ATIVO)
```

**Causa raiz:** Evolução orgânica do projeto sem cleanup. O código começou na raiz, depois foi organizado em `vps_agent/`, e depois refatorado para `vps_langgraph/`. Os arquivos antigos nunca foram removidos.

**Risco:** Um import pode estar puxando o módulo errado. O Python resolve imports pela ordem do `sys.path`, e se ambos os diretórios estão no path, o comportamento é indeterminado.

### 🟡 MÉDIO 4: CI/CD falhando

**Sintoma:** Module import errors no GitHub Actions, passa localmente.

**Causa provável:** Os imports no CI resolvem para o diretório errado (porque existem 3 cópias dos mesmos módulos). Localmente funciona porque o `sys.path` é diferente. Resolver o problema #3 (duplicação) provavelmente resolve este também.

### 🟡 MÉDIO 5: `__pycache__` causando problemas

**Causa:** Arquivos `.pyc` antigos no cache do Python referenciando módulos que foram movidos/renomeados. O Python tenta carregar o bytecode cacheado que aponta para paths que não existem mais.

**Fix simples:** `find /opt/vps-agent -type d -name __pycache__ -exec rm -rf {} +`

### 🟢 PEQUENO 6: Logs não chegam no Telegram

**Causa provável:** O bot loga para arquivo via `journalctl` mas não tem um handler que envia logs para o chat do Telegram. Isso é uma feature, não um bug — precisa implementar um `TelegramLogHandler`.

---

## Mapeamento de Sobreposições com v2

Este é o ponto crítico: **o que corrigimos agora vs. o que será substituído na v2**.

| Problema v1 | Correção Fase 0 | Substituído na v2 por... | Decisão |
|---|---|---|---|
| Graph flow self_improve | Fix mínimo no roteamento | F2-01 Skill Registry (substitui capabilities inteiro) | ✅ Fix mínimo agora |
| timezone error | Confirmar import correto | F2-01 Skill Registry (reescreve registry) | ✅ Fix agora (30min) |
| Código duplicado | Consolidar em vps_langgraph/, deletar cópias | F1-* (nova estrutura de diretórios) | ✅ Cleanup agora, reestruturar na F1 |
| CI/CD falhando | Fix imports + cleanup | F1-12 Testes + F4-10 Environment Segregation | ✅ Fix agora |
| `__pycache__` | Limpar + adicionar ao .gitignore | — (boas práticas permanentes) | ✅ Fix agora |
| Logs no Telegram | Log handler básico | F1-08 Structured Logging (structlog) | ✅ Handler simples agora |
| Qdrant integração | — | F3-04 Hierarchical Memory + F3-05 RAG Pipeline | ❌ **NÃO FAZER AGORA** |
| LLM routing | — | F3-01 Failover + F3-02 Model Cascade | ❌ **NÃO FAZER AGORA** |
| Multi-agent | — | F4-01 + F4-02 | ❌ **NÃO FAZER AGORA** |
| Self-improvement sandbox | — | F2-03 Action Classification + F4-04 Self-Improvement Pipeline | ❌ **NÃO FAZER AGORA** |
| Embedding model choice | — | F3-04 Hierarchical Memory | ❌ **NÃO FAZER AGORA** |
| Semantic caching | — | F3-06 Semantic Caching | ❌ **NÃO FAZER AGORA** |

**Regra de ouro:** Se a v2 tem um job dedicado para resolver algo de forma robusta, a Fase 0 só faz o **mínimo** para destravar o funcionamento.

---

## Jobs da Fase 0

### FASE 0 — Estabilização v1 (1-2 semanas)
> Objetivo: Agente funcional end-to-end via Telegram. Nenhuma feature nova — apenas bugs resolvidos e código limpo.

| # | Job | Horas Est. | Prioridade | Pré-requisito |
|---|-----|-----------|------------|---------------|
| F0-01 | **Cleanup de Código** — Eliminar duplicação. Consolidar em `vps_langgraph/` como módulo canônico. Deletar `core/graph.py`, `core/nodes.py`, `core/state.py`, `core/memory.py`, `core/semantic_memory.py`. Atualizar todos os imports em `vps_agent/agent.py` e `telegram-bot/bot.py`. Limpar **todos** os `__pycache__`. Adicionar `__pycache__/` e `*.pyc` ao `.gitignore`. | 4h | P0 | — |
| F0-02 | **Fix Graph Flow self_improve** — Corrigir roteamento no grafo LangGraph para que `self_improve` passe por `check_capabilities` antes de `respond`. Garantir que `node_generate_response` trate o intent `self_improve` chamando LLM com contexto de capabilities. Testar fluxo completo: mensagem → classify → capabilities → respond → resposta no Telegram. | 6h | P0 | F0-01 |
| F0-03 | **Fix timezone + Validação** — Confirmar import `timezone` em `capabilities/registry.py`. Rodar teste unitário que cria uma `Capability` e verifica `created_at`. Verificar se existem outros usos de `timezone` sem import no projeto. | 1h | P0 | F0-01 |
| F0-04 | **Fix CI/CD** — Corrigir imports no GitHub Actions. Garantir que `PYTHONPATH` inclui apenas `core/vps_langgraph/` (não os diretórios duplicados). Adicionar `.env.example` para variáveis de ambiente necessárias no CI. Verificar se `requirements.txt` está completo. Target: pipeline verde. | 4h | P0 | F0-01 |
| F0-05 | **Testes Básicos end-to-end** — Escrever 5 testes que cobrem os 5 intents: `command`, `task`, `question`, `chat`, `self_improve`. Cada teste: cria state → roda grafo → verifica que `response` não é None. Mock de LLM com respostas fixas. Usar `pytest` + `pytest-asyncio`. | 6h | P1 | F0-02, F0-03 |
| F0-06 | **Telegram Log Handler** — Handler de logging Python que envia mensagens de nível ERROR e CRITICAL para o chat do Telegram do admin. Não enviar DEBUG/INFO (spam). Rate limit de 1 msg/min para não ser bloqueado pela API do Telegram. | 3h | P1 | F0-01 |
| F0-07 | **Documentação Mínima** — Atualizar README com: estrutura real de arquivos (pós-cleanup), como rodar localmente, como rodar testes, como fazer deploy. Não documentar features futuras. | 2h | P2 | F0-01 |

**Subtotal Fase 0: 7 jobs | ~26h | 1-2 semanas**

---

## Correções de Código Concretas

### Correção F0-02: Fix do Graph Flow

O grafo precisa de duas mudanças:

**Mudança 1 — Roteamento correto para `self_improve`:**
```python
# core/vps_langgraph/graph.py — CORRIGIDO

def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Nós (mantém todos)
    workflow.add_node("classify", node_classify_intent)
    workflow.add_node("load_context", node_load_context)
    workflow.add_node("plan", node_plan)
    workflow.add_node("execute", node_execute)
    workflow.add_node("respond", node_generate_response)
    workflow.add_node("save_memory", node_save_memory)
    workflow.add_node("check_capabilities", node_check_capabilities)
    workflow.add_node("self_improve", node_self_improve)
    workflow.add_node("implement_capability", node_implement_capability)
    
    # Fluxo principal
    workflow.set_entry_point("classify")
    workflow.add_edge("classify", "load_context")
    workflow.add_edge("load_context", "plan")
    
    # CORREÇÃO: self_improve vai para check_capabilities, NÃO para respond
    workflow.add_conditional_edges("plan", lambda s: s.get("intent", "unknown"), {
        "command": "execute",
        "task": "execute",
        "question": "respond",
        "chat": "respond",
        "self_improve": "check_capabilities",  # ← CORRIGIDO
        "unknown": "respond",
    })
    
    # Fluxo de execução
    workflow.add_edge("execute", "respond")
    
    # Fluxo de self_improve: capabilities → self_improve → respond
    workflow.add_conditional_edges("check_capabilities", 
        lambda s: "self_improve" if s.get("needs_new_capability") else "respond",
        {
            "self_improve": "self_improve",
            "respond": "respond",
        }
    )
    workflow.add_edge("self_improve", "respond")
    
    # Todos os caminhos terminam em save_memory
    workflow.add_edge("respond", "save_memory")
    workflow.set_finish_point("save_memory")
    
    return workflow.compile()
```

**Mudança 2 — `node_generate_response` trata `self_improve`:**
```python
# core/vps_langgraph/nodes.py — CORRIGIDO

def node_generate_response(state: AgentState) -> AgentState:
    """Gera resposta final ao usuário."""
    intent = state.get("intent")
    execution_result = state.get("execution_result")
    
    # Prioridade 1: se já tem resultado de execução, usar
    if execution_result:
        response = execution_result
    
    # Prioridade 2: self_improve — reportar o que aconteceu
    elif intent == "self_improve":
        capability_result = state.get("capability_result")
        if capability_result:
            response = f"🔧 Self-Improvement:\n{capability_result}"
        else:
            # Capabilities checadas mas nada novo necessário
            capabilities_info = state.get("capabilities_info", "")
            prompt = (
                f"O usuário pediu algo que envolve self-improvement. "
                f"Capacidades atuais: {capabilities_info}\n"
                f"Mensagem do usuário: {state.get('user_message')}\n"
                f"Explique o que o sistema pode fazer e o que será implementado."
            )
            response = generate_response_sync(prompt)
    
    # Prioridade 3: chat/question — chamar LLM
    elif intent in ["chat", "question"]:
        response = generate_response_sync(
            state.get("user_message"),
            context=state.get("context", ""),
        )
    
    # Fallback
    else:
        response = (
            f"Recebi sua mensagem (intent: {intent}). "
            "Não tenho certeza de como processar, mas registrei."
        )
    
    return {**state, "response": response}
```

### Correção F0-01: Estrutura pós-cleanup

Após eliminar duplicatas, a estrutura deve ficar:
```
/opt/vps-agent/
├── core/
│   ├── vps_langgraph/          # ← MÓDULO CANÔNICO
│   │   ├── __init__.py
│   │   ├── graph.py            # build_agent_graph()
│   │   ├── nodes.py            # todos os node_*
│   │   ├── state.py            # AgentState
│   │   └── memory.py           # AgentMemory
│   │
│   ├── vps_agent/
│   │   ├── __init__.py
│   │   └── agent.py            # process_message_async (imports de vps_langgraph)
│   │
│   ├── capabilities/
│   │   ├── __init__.py
│   │   └── registry.py         # CapabilitiesRegistry
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py
│   │   └── agent_identity.py
│   │
│   └── resource-manager/
│       └── manager.py
│
├── telegram-bot/
│   └── bot.py
│
├── configs/
├── scripts/
├── tests/
└── .gitignore                   # ← inclui __pycache__/, *.pyc
```

**Deletar:**
- `core/graph.py` (versão antiga na raiz)
- `core/nodes.py` (versão antiga na raiz)
- `core/state.py` (versão antiga na raiz)
- `core/memory.py` (versão antiga na raiz)
- `core/semantic_memory.py` (versão antiga na raiz)
- `core/vps_agent/graph.py` (versão antiga em vps_agent)
- `core/vps_agent/nodes.py` (versão antiga em vps_agent)
- `core/vps_agent/semantic_memory.py` (mover lógica útil para vps_langgraph primeiro se necessário)

---

## Respostas às 30 Perguntas

### 10.1 Correções Imediatas

**P1: Por que `result.get("response")` retorna `None` para intent `self_improve`?**

Três possíveis causas, em ordem de probabilidade:

1. **O nó `respond` nunca é alcançado.** Se o roteamento condicional após `plan` manda `self_improve` para `check_capabilities`, mas `check_capabilities` não tem edge de saída para `respond`, o grafo pode terminar prematuramente. Verificar no código real se **todos os caminhos** após `check_capabilities` eventualmente chegam em `respond`.

2. **O LangGraph não retorna a key.** O `ainvoke()` do LangGraph retorna apenas as keys que foram **modificadas** pelo último nó, não o state inteiro. Se `save_memory` (o último nó) não retorna `response` no seu dict, ela desaparece do resultado. Solução: o último nó deve retornar `{**state}` completo, ou usar `result_keys` explícito na compilação.

3. **`node_generate_response` não seta `response`.** Se o intent é `self_improve` e não cai em nenhum `if`, a variável `response` nunca é atribuída e o `return` falha silenciosamente.

**A correção está no código da seção anterior.** Implementar as duas mudanças (roteamento + tratamento de intent).

**P2: Qual é a correção mínima para `node_generate_response`?**

A **correção mínima absoluta** (1 linha):
```python
elif intent in ["chat", "question"]:
# ↓ MUDAR PARA:
elif intent in ["chat", "question", "self_improve"]:
```

Isso faz o `self_improve` ser tratado como `question` — chama o LLM com a mensagem do usuário. Não é ideal (não usa o resultado de capabilities), mas **funciona** e gera uma resposta.

A correção completa está na seção anterior e é recomendada.

**P3: O import de `timezone` em `capabilities/registry.py` foi corrigido corretamente?**

O fix teórico está correto:
```python
from datetime import datetime, timezone  # ← timezone adicionado
```

Mas **precisa ser verificado no código real na VPS**. Rodar:
```bash
cd /opt/vps-agent
python3 -c "from core.capabilities.registry import Capability; print('OK')"
```

Se printar "OK", está corrigido. Se der `NameError`, o fix não foi salvo.

---

### 10.2 Arquitetura de Código

**P4: Qual estrutura de pastas é recomendada?**

`vps_langgraph/` como pasta canônica **para a Fase 0**. Na v2 (Fase 1), a estrutura será completamente reorganizada para:

```
agentvps-v2/
├── gateway/        # FastAPI + adapters
├── brain/          # LangGraph agent (substitui vps_langgraph/)
├── skills/         # Registry + handlers (substitui capabilities/)
├── memory/         # Hierárquica
├── agents/         # Multi-agent
├── observability/
├── security/
└── ...
```

Não vale a pena reorganizar para a estrutura v2 agora. Consolidar em `vps_langgraph/` é suficiente.

**P5: Como resolver a duplicação de arquivos?**

Ação descrita no job F0-01: deletar os arquivos antigos, manter apenas `vps_langgraph/`. Script:
```bash
# ANTES de deletar, verificar diffs para não perder código útil
diff core/graph.py core/vps_langgraph/graph.py
diff core/nodes.py core/vps_langgraph/nodes.py
diff core/vps_agent/graph.py core/vps_langgraph/graph.py

# Se não houver código útil nos antigos, deletar
rm core/graph.py core/nodes.py core/state.py core/memory.py core/semantic_memory.py
rm core/vps_agent/graph.py core/vps_agent/nodes.py core/vps_agent/semantic_memory.py

# Limpar caches
find /opt/vps-agent -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

**P6: Qual padrão de imports usar?**

**Imports absolutos** para a Fase 0 e v2:
```python
# ✅ CORRETO — absoluto, explícito
from vps_langgraph.graph import build_agent_graph
from vps_langgraph.nodes import node_classify_intent
from capabilities.registry import CapabilitiesRegistry

# ❌ EVITAR — relativo, ambíguo quando há duplicatas
from .nodes import node_classify_intent
```

Motivo: com duplicatas existentes, imports relativos são indeterminados. Absolutos deixam claro **qual** módulo está sendo importado. Na v2, absolutos continuam sendo o padrão (ex: `from brain.agent import ...`).

---

### 10.3 LangGraph Patterns

**P7: Como fazer o grafo retornar todas as chaves do estado?**

O `ainvoke()` do LangGraph retorna o **state final completo** por padrão. Se `response` não aparece, é porque **nenhum nó setou essa key**. A correção é garantir que `node_generate_response` sempre retorna `response` no dict.

Se mesmo assim não funcionar, forçar explicitamente:
```python
# No último nó (save_memory), retornar o state inteiro
def node_save_memory(state: AgentState) -> AgentState:
    # ... salvar memória ...
    return state  # retorna TODO o state, incluindo response
```

Alternativa: usar `output_keys` ao compilar o grafo:
```python
graph = workflow.compile()
# O LangGraph 0.2+ retorna o state completo por padrão
```

**P8: Quando usar nós síncronos vs assíncronos?**

Regra prática:
- **Síncrono**: classificação de intent (regex, rápido), validações, transformações de dados
- **Assíncrono**: chamadas a LLM (I/O-bound), consultas a banco, operações de rede

Na v1, `node_classify_intent` é síncrono e **está correto** — é apenas regex/keyword matching. `node_generate_response` deveria ser async porque chama LLM, mas como o LangGraph aceita funções sync dentro de `ainvoke()`, funciona mesmo sync (só é menos eficiente).

**Na v2 (Fase 1), todos os nós com I/O serão async.** Na Fase 0, não mudar.

**P9: Como implementar checkpoints no LangGraph?**

→ **NÃO FAZER NA FASE 0.** Será implementado na v2 como parte do Session Manager (F1-02).

Para referência futura:
```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string("postgresql://...")
graph = workflow.compile(checkpointer=checkpointer)

# Cada invocação com thread_id permite resumir
config = {"configurable": {"thread_id": "user-123-session-456"}}
result = await graph.ainvoke(initial_state, config)
```

---

### 10.4 Self-Improvement Design

**P10: Qual é o fluxo ideal para implementar uma nova capacidade?**

**Fase 0 (fix mínimo):**
```
classify → load_context → plan → check_capabilities → self_improve → respond → save_memory
```
O `check_capabilities` verifica se o que o usuário pediu já existe. Se não, `self_improve` registra a necessidade. `respond` informa ao usuário o que será feito.

**v2 (Fase 4, job F4-04 — Self-Improvement Pipeline):**
```
identify failure pattern → propose code change → test in sandbox → human approval → deploy
```
A diferença é que na v2 o agente **realmente implementa** código novo com guardrails. Na Fase 0, ele apenas **identifica e informa**.

**P11: O agente deve executar código gerado automaticamente?**

→ **NÃO NA FASE 0.** Executar código auto-gerado sem sandbox é o risco de segurança #1 do projeto.

Na v2:
- F2-03 implementa **Action Classification** (safe/moderate/dangerous)
- F2-09 implementa **Tool Usage Policies**
- F4-04 implementa o **Self-Improvement Pipeline** com sandbox Docker + human approval

**Sequência segura (v2):** gerar código → rodar em container efêmero com filesystem read-only → verificar saída → submeter para aprovação humana via Telegram → aplicar se aprovado.

**P12: Como implementar auto-commit no git?**

→ **NÃO NA FASE 0.** Será parte do F4-04 na v2.

Design planejado:
```bash
# O agente cria branch, commita, e pede aprovação
git checkout -b self-improve/add-capability-xyz
git add .
git commit -m "feat: add capability xyz [auto-generated]"
# Enviar para Telegram: "Nova capability proposta. Aprovar merge? [Sim/Não]"
# Se aprovado: git checkout main && git merge self-improve/add-capability-xyz
# Se rejeitado: git branch -D self-improve/add-capability-xyz
```

**P13: O que fazer em caso de erro na implementação?**

→ **Na Fase 0:** Apenas logar o erro e informar o usuário via Telegram.
→ **Na v2 (F4-04):** Rollback automático com `git revert`, notificação ao usuário, e log de falha para análise posterior.

---

### 10.5 Memória e Contexto

**P14: Quando usar PostgreSQL vs Qdrant?**

→ **Na Fase 0:** Apenas PostgreSQL. Qdrant NÃO será integrado agora.

→ **Na v2 (F3-04 Hierarchical Memory):**

| Camada | Storage | O que guarda | Quando consultar |
|---|---|---|---|
| Episódica | JSONL (arquivos) | Transcripts recentes (<7 dias) | Sempre (contexto imediato) |
| Semântica | Qdrant | Fatos importantes, embeddings | Quando precisa de contexto longo-prazo |
| Perfil | PostgreSQL + USER.md | Preferências, configs, fatos estruturados | Sempre (perfil do usuário) |

**P15: Como fazer hybrid search (PostgreSQL + Qdrant)?**

→ **Será implementado na v2, Fase 3 (F3-04 + F3-05).**

Design planejado:
```python
# 1. Buscar fatos estruturados no PostgreSQL
structured_facts = await pg.query("SELECT * FROM facts WHERE user_id = $1", user_id)

# 2. Buscar contexto semântico no Qdrant
query_embedding = embed(user_message)
semantic_results = await qdrant.search(collection="memories", query_vector=query_embedding, limit=5)

# 3. Combinar com ranking
combined = rank_by_relevance(structured_facts, semantic_results, user_message)
```

**P16: Qual modelo de embedding usar?**

→ **Decisão adiada para F3-04.**

Recomendação preliminar baseada na constraint de 2.4GB RAM:

| Modelo | Dimensão | RAM | Qualidade | Recomendação |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | ~80MB | Boa | ✅ **Usar este** (RAM limitada) |
| `all-mpnet-base-v2` | 768 | ~420MB | Melhor | ❌ Muito pesado para 2.4GB |
| Voyage AI / OpenAI embeddings (API) | 1024+ | 0MB local | Excelente | ✅ Alternativa: sem RAM local, custo por chamada |

A alternativa de usar **embeddings via API** (Voyage AI, OpenAI) em vez de rodar modelo local é a que mais faz sentido para 2.4GB RAM. Custo baixo (~$0.0001 por embedding) e zero RAM local.

---

### 10.6 LLM Routing

**P17: Como router inteligente entre MiniMax M2.1 e Sonnet 4.5?**

→ **Será implementado na v2, Fase 3 (F3-02 Model Cascade Routing).**

Design planejado:
```python
def classify_complexity(message: str, intent: str) -> str:
    """Classifica complexidade para routing de modelo."""
    # Simples: saudações, perguntas factuais curtas, chat casual
    if intent in ["chat", "question"] and len(message) < 100:
        return "simple"  # → MiniMax M2.1 / Haiku
    
    # Complexo: código, arquitetura, self-improvement, tarefas longas
    if intent in ["self_improve", "task"] or "```" in message:
        return "complex"  # → Sonnet 4.5 / Opus
    
    return "medium"  # → Sonnet 4.5
```

**P18: Como implementar fallback automático?**

→ **v2, Fase 3 (F3-01 Multi-Provider LLM Failover).**

**P19: Como fazer cache de respostas?**

→ **v2, Fase 3 (F3-06 Semantic Caching).**

---

### 10.7 Resource Management

**P20: Quando subir o Qdrant?**

→ **Sob demanda.** Com 2.4GB total, Qdrant (~400MB) não pode ficar sempre ligado.

Na v2 (F3-04), o Resource Manager decidirá quando subir/descer o Qdrant baseado na necessidade. Se uma query precisa de busca semântica → subir Qdrant → consultar → manter por 5 minutos → desligar se inativo.

**P21: Como gerenciar RAM com 2.4 GB total?**

Budget de RAM:
```
SEMPRE LIGADOS (~750 MB):
  PostgreSQL 16    = ~200 MB
  Redis 7          = ~50 MB
  Python (agent)   = ~300 MB (vps_langgraph + bot + fastapi-mcp)
  Sistema (OS)     = ~200 MB

SOB DEMANDA (~1650 MB restantes):
  Qdrant           = ~400 MB (subir/descer conforme necessidade)
  n8n              = ~300 MB
  Sentence-transf. = ~80-420 MB (depende do modelo; ou usar API)
  Margem segurança = ~150 MB mínimo

REGRA: nunca rodar mais de 2 serviços sob-demanda simultaneamente
```

Isso será formalizado na v2 como parte do Resource Manager evoluído. Na Fase 0, a estrutura atual já funciona — só não rodar Qdrant + n8n ao mesmo tempo.

---

### 10.8 Testing e CI/CD

**P22: Como testar o LangGraph localmente?**

```python
# tests/test_graph.py
import pytest
from unittest.mock import patch, AsyncMock
from vps_langgraph.graph import build_agent_graph

@pytest.mark.asyncio
async def test_chat_intent_returns_response():
    """Testa que intent 'chat' produz response."""
    # Mock do LLM para não depender de API
    with patch("vps_langgraph.nodes.generate_response_sync", return_value="Olá!"):
        graph = build_agent_graph()
        result = await graph.ainvoke({
            "user_id": "test-user",
            "user_message": "Olá, tudo bem?",
            "timestamp": "2026-02-08T00:00:00Z",
        })
        assert result.get("response") is not None
        assert result["intent"] == "chat"

@pytest.mark.asyncio
async def test_self_improve_intent_returns_response():
    """Testa que intent 'self_improve' produz response."""
    with patch("vps_langgraph.nodes.generate_response_sync", return_value="Vou implementar"):
        graph = build_agent_graph()
        result = await graph.ainvoke({
            "user_id": "test-user",
            "user_message": "Crie um novo agente de monitoramento",
            "timestamp": "2026-02-08T00:00:00Z",
        })
        assert result.get("response") is not None
        assert result["intent"] == "self_improve"
```

**P23: Por que o CI/CD falha no GitHub Actions?**

Causas prováveis (em ordem):
1. **Duplicação de módulos** → Python importa o módulo errado. Resolver com F0-01.
2. **`PYTHONPATH` não configurado** → CI não sabe onde encontrar os módulos. Adicionar ao workflow:
   ```yaml
   env:
     PYTHONPATH: /opt/vps-agent/core
   ```
3. **Variáveis de ambiente ausentes** → `.env` não existe no CI. Criar `.env.example` e carregar no workflow.
4. **Dependências incompletas** → `requirements.txt` faltando pacotes. Rodar `pip freeze` na VPS e comparar.

**P24: Como garantir coverage de testes?**

→ **Fase 0:** Target 40% (apenas os 5 testes de intents, F0-05).
→ **v2 F1-12:** Target 60%.
→ **v2 F2-10:** Target 70%.

Priorizar cobertura em: `graph.py`, `nodes.py`, `agent.py` — o core do fluxo.

---

### 10.9 Segurança

**P25: Como sandbox de self-improvement?**

→ **NÃO na Fase 0.** Será v2 Fase 2 (F2-03 Action Classification) + Fase 4 (F4-04).

Design v2:
```bash
# Container efêmero para testar código gerado
docker run --rm \
  --read-only \
  --tmpfs /tmp:rw,size=100m \
  --network=none \
  --memory=256m \
  --cpus=0.5 \
  --timeout=60 \
  python:3.12-slim \
  python /tmp/generated_code.py
```

**P26: Como proteger credenciais?**

Isso vale **agora** (Fase 0) e continua na v2:
```bash
# .env com permissões restritas
chmod 600 /opt/vps-agent/.env

# No systemd (já funciona)
EnvironmentFile=/opt/vps-agent/.env

# NO .gitignore (verificar!)
echo ".env" >> .gitignore

# NUNCA commitar .env — usar .env.example sem valores reais
```

---

### 10.9 Future Features

**P27-30:** Multi-agent, web interface, WhatsApp, auto-scaling — **todas cobertas pela v2:**

| Pergunta | Resposta v2 |
|---|---|
| P27: Multi-agente | F4-01 + F4-02 (Multi-Agent Routing + Communication) |
| P28: Web interface | ❌ Descartado (Telegram + CLI suficientes) |
| P29: WhatsApp | F2-07 (Evolution API Adapter) |
| P30: Auto-scaling | ❌ Descartado (single-VPS, não é SaaS) |

---

## Roadmap Completo Atualizado

| Fase | Jobs | Horas | Semanas | Entrega Principal |
|------|------|-------|---------|-------------------|
| **F0** — Estabilização v1 | 7 | ~26h | 1-2 | Agente funcional end-to-end |
| **F1** — Refatoração da Fundação | 12 | ~102h | 3-4 | Gateway + Sessões + Proteções |
| **F2** — Skills & Segurança | 10 | ~120h | 3-4 | Skills modulares + WhatsApp + Security |
| **F3** — Inteligência | 11 | ~146h | 4-5 | Failover + RAG + Cache + Automações |
| **F4** — Autonomia | 11 | ~140h | 3-4 | Multi-agent + Self-improvement + Guardrails |
| **TOTAL** | **51 jobs** | **~534h** | **14-19 semanas** | |

A Fase 0 adiciona apenas ~26h e 1-2 semanas, mas é **pré-requisito** para todas as outras. Sem ela, não temos uma base funcional para construir a v2.

---

## Critérios de Saída da Fase 0

A Fase 0 está **completa** quando:

- [ ] Mensagem enviada no Telegram com intent `self_improve` retorna resposta (não `None`)
- [ ] Mensagem com intent `chat` retorna resposta
- [ ] Mensagem com intent `command` retorna resposta
- [ ] Mensagem com intent `question` retorna resposta
- [ ] Mensagem com intent `task` retorna resposta
- [ ] Nenhum `NameError: timezone` nos logs
- [ ] Apenas **1 cópia** de cada arquivo (graph.py, nodes.py, state.py, memory.py)
- [ ] `pytest` passa com 5+ testes no CI (GitHub Actions verde)
- [ ] `__pycache__` no `.gitignore`
- [ ] Erros CRITICAL/ERROR aparecem no Telegram

**Só avançar para F1 quando todos os checkboxes estiverem marcados.**

---

## Próximos Passos Imediatos

1. **Acessar a VPS** e verificar o estado real do código (os snippets do doc podem estar desatualizados)
2. **Executar F0-01** — cleanup é pré-requisito de tudo
3. **Executar F0-02 + F0-03** — corrigir os bugs críticos
4. **Rodar teste manual via Telegram** — enviar mensagens com cada intent e verificar respostas
5. **Executar F0-04** — CI verde
6. **F0-05 a F0-07** em paralelo

Tempo estimado para ter o agente funcional: **1 semana focada** ou **2 semanas em ritmo normal**.
