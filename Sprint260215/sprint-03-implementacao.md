# Sprint 03 — Plano de Implementacao Detalhado

> **Pre-requisito:** Ler `sprint-03-objetivo.md` e `sprint-03-roadmap.md`.

---

## T1-01: Plugar react_node no graph.py (~4h)

### A Mudanca Mais Importante do Projeto

O react_node.py ja existe (163 linhas), esta testado (20 formulacoes), e funciona. O unico problema eh que graph.py nao o utiliza.

### Passo a Passo

**1. Modificar imports em graph.py:**

```python
# REMOVER:
from .nodes import (
    node_classify_intent,     # SUBSTITUIDO por react
    node_plan,                # SUBSTITUIDO por react
    node_check_capabilities,  # DESABILITADO (nao funcional)
    node_self_improve,        # DESABILITADO (nao funcional)
    node_implement_capability, # DESABILITADO (nao funcional)
    ...
)

# ADICIONAR:
from .react_node import node_react, node_format_response, route_after_react
from .nodes import (
    node_load_context,
    node_security_check,
    node_execute,
    node_generate_response,
    node_save_memory,
)
```

**2. Reconstruir o grafo:**

```python
def build_agent_graph():
    workflow = StateGraph(AgentState)

    # 7 nos (vs 10 antigos)
    workflow.add_node("load_context", node_load_context)
    workflow.add_node("react", node_react)
    workflow.add_node("security_check", node_security_check)
    workflow.add_node("execute", node_execute)
    workflow.add_node("format_response", node_format_response)
    workflow.add_node("respond", node_generate_response)
    workflow.add_node("save_memory", node_save_memory)

    # Fluxo
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "react")

    # React decide: tool ou resposta direta
    workflow.add_conditional_edges("react", route_after_react, {
        "security_check": "security_check",
        "respond": "respond",
    })

    # Security -> execute ou respond (se bloqueado)
    def route_after_security(state):
        if state.get("blocked_by_security"):
            return "respond"
        return "execute"

    workflow.add_conditional_edges("security_check", route_after_security, {
        "execute": "execute",
        "respond": "respond",
    })

    workflow.add_edge("execute", "format_response")
    workflow.add_edge("format_response", "respond")
    workflow.add_edge("respond", "save_memory")
    workflow.set_finish_point("save_memory")

    checkpointer = get_checkpointer()
    return workflow.compile(checkpointer=checkpointer)
```

**3. Verificar node_execute compatibilidade:**

O `node_execute` atual no nodes.py espera `plan` com `[{"type": "skill", "action": ..., "args": ...}]`. O react_node.py gera exatamente esse formato. Compativel.

**4. Verificar que node_generate_response funciona com novo state:**

O react_node seta `state["response"]` quando o LLM responde diretamente. O `node_generate_response` deve verificar se `state["response"]` ja existe e nao sobrescrever.

### Checkpoint T1-01
```
[ ] graph.py importa react_node
[ ] graph.py tem 7 nos em vez de 10
[ ] "quanta RAM?" -> react chama get_ram -> format_response gera resposta
[ ] "ola, tudo bem?" -> react responde direto (sem tool)
[ ] "execute ls -la" -> react chama shell_exec -> security_check -> execute
[ ] CI verde
```

---

## T1-02: Adaptar node_execute para react output (~2h)

### Objetivo

Garantir que node_execute funcione tanto com output do react_node quanto com chamadas diretas (comandos Telegram como /ram).

### Modificacoes

```python
# node_execute deve:
# 1. Verificar state["plan"] (vem do react_node)
# 2. Extrair tool_name e args do plano
# 3. Executar via registry (ja faz isso)
# 4. NAO usar system_tools como fallback (remover import legado)
```

**Remover import legado:**
```python
# REMOVER de nodes.py:
from ..tools.system_tools import get_async_tool as legacy_get_async_tool
```

### Checkpoint T1-02
```
[ ] node_execute nao importa system_tools
[ ] node_execute funciona com output do react_node
[ ] Comandos /ram e /status continuam funcionando
```

---

## T2-01: Remover Dead Code (~1h)

### Arquivos Para Deletar

```bash
# 1. system_tools.py (426 linhas) - substituido pelo Skill Registry
rm core/tools/system_tools.py

# 2. intent_classifier.py (42 linhas) - stub DEPRECATED
rm core/vps_langgraph/intent_classifier.py

# 3. semantic_memory.py (9 linhas) - stub DEPRECATED
rm core/vps_agent/semantic_memory.py
```

### Verificar Dependencias Antes de Deletar

```bash
# Checar se algum arquivo importa esses modulos
grep -rn "system_tools\|intent_classifier\|semantic_memory" core/ --include="*.py"
```

Remover todos os imports encontrados. Se `nodes.py` importa `system_tools` como fallback, remover o fallback — o registry eh o unico caminho agora.

### Checkpoint T2-01
```
[ ] system_tools.py deletado
[ ] intent_classifier.py deletado
[ ] semantic_memory.py deletado
[ ] grep -r "system_tools\|intent_classifier\|semantic_memory" core/ retorna 0
[ ] CI verde (nenhum import quebrado)
[ ] -477 linhas de codigo
```

---

## T3-01: Hook System — Arquitetura (~4h)

### Conceito (Inspirado no OpenClaw)

O OpenClaw tem um `hook-runner-global.ts` que executa hooks antes/depois de cada tool execution. Adaptamos para Python:

### Implementacao: `core/hooks/runner.py`

```python
"""
Hook System — pre/post execution hooks para skills.

Inspirado no OpenClaw hook-runner-global.ts.
Permite logging, metricas, approval workflow, e feedback loop
sem modificar os skills individuais.
"""

import time
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()

@dataclass
class HookContext:
    """Contexto passado para cada hook."""
    skill_name: str
    args: Dict[str, Any]
    user_id: str
    timestamp: float = field(default_factory=time.time)
    result: Optional[str] = None       # Preenchido em post_execute
    error: Optional[str] = None        # Preenchido em post_execute se falhou
    duration_ms: Optional[float] = None # Preenchido em post_execute
    metadata: Dict[str, Any] = field(default_factory=dict)


class HookRunner:
    """Executa hooks pre/post execution."""

    def __init__(self):
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []

    def register_pre(self, hook: Callable):
        self._pre_hooks.append(hook)

    def register_post(self, hook: Callable):
        self._post_hooks.append(hook)

    async def run_pre(self, ctx: HookContext) -> bool:
        """Roda hooks pre-execucao. Retorna False para cancelar."""
        for hook in self._pre_hooks:
            try:
                result = await hook(ctx)
                if result is False:
                    return False  # Hook vetou a execucao
            except Exception as e:
                logger.error("pre_hook_error", hook=hook.__name__, error=str(e))
        return True

    async def run_post(self, ctx: HookContext):
        """Roda hooks pos-execucao."""
        for hook in self._post_hooks:
            try:
                await hook(ctx)
            except Exception as e:
                logger.error("post_hook_error", hook=hook.__name__, error=str(e))
```

### Hooks Builtin

```python
# Hook 1: Logging estruturado
async def logging_hook(ctx: HookContext):
    if ctx.result:  # post
        logger.info("skill_executed",
            skill=ctx.skill_name,
            duration_ms=ctx.duration_ms,
            success=ctx.error is None,
            user_id=ctx.user_id,
        )

# Hook 2: Metricas (Redis counters)
async def metrics_hook(ctx: HookContext):
    if ctx.result:  # post
        redis.incr(f"skill_usage:{ctx.skill_name}")
        redis.lpush(f"skill_latency:{ctx.skill_name}", ctx.duration_ms)

# Hook 3: Learning recorder
async def learning_hook(ctx: HookContext):
    if ctx.error:  # post com erro
        # Registrar no learnings para feedback loop
        await save_learning(
            category="execution_error",
            trigger=ctx.skill_name,
            observation=f"Erro ao executar {ctx.skill_name}: {ctx.error}",
        )
```

### Integracao com node_execute

```python
# Em node_execute, antes de executar:
hook_runner = get_hook_runner()
ctx = HookContext(skill_name=tool_name, args=tool_args, user_id=user_id)

should_proceed = await hook_runner.run_pre(ctx)
if not should_proceed:
    return {**state, "response": "Execucao cancelada por politica de seguranca."}

start = time.time()
result = await registry.execute_skill(tool_name, tool_args)
ctx.duration_ms = (time.time() - start) * 1000
ctx.result = result

await hook_runner.run_post(ctx)
```

### Checkpoint T3-01
```
[ ] core/hooks/runner.py criado
[ ] HookRunner com pre/post hooks
[ ] 3 hooks builtin (logging, metrics, learning)
[ ] node_execute integrado com hooks
[ ] Logs mostram skill_executed com duracao
[ ] Redis tem counters de skill_usage
```

---

## T3-02: Hook de Feedback Loop (~4h)

### Conceito

O hook de learning nao apenas registra erros — ele CONSULTA learnings anteriores antes de executar. Se uma acao similar falhou 3x na ultima hora, o hook pode:
1. Adicionar um warning ao contexto
2. Sugerir acao alternativa
3. Vetar execucao automatica

### Implementacao

```python
async def feedback_pre_hook(ctx: HookContext):
    """Consulta learnings antes de executar."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT observation, times_triggered
        FROM learnings
        WHERE trigger = %s
        AND category = 'execution_error'
        AND last_triggered > NOW() - INTERVAL '1 hour'
        ORDER BY times_triggered DESC
        LIMIT 3
    """, (ctx.skill_name,))
    recent_errors = cur.fetchall()
    conn.close()

    if recent_errors:
        total_failures = sum(r[1] for r in recent_errors)
        if total_failures >= 3:
            ctx.metadata["warning"] = f"Este skill falhou {total_failures}x na ultima hora"
            logger.warning("feedback_warning",
                skill=ctx.skill_name,
                failures=total_failures,
            )
    return True  # Continua execucao (warning, nao veto)
```

### Checkpoint T3-02
```
[ ] feedback_pre_hook consulta learnings
[ ] Warning adicionado ao contexto quando failures > 3
[ ] learning_hook (post) registra erros novos
[ ] Ciclo completo: erro -> learning -> consulta -> warning
```

---

## T4-01: Triggers com Condicoes Reais (~4h)

### Problema

4 de 6 triggers tem `condition: lambda: True`. Isso significa que SEMPRE disparam, independente do estado do sistema. Sao cron jobs, nao percepcao.

### Solucao

Substituir `lambda: True` por funcoes que verificam estado real:

```python
# Trigger 1: Health Check — a cada 60s APENAS se ultimo check > 60s
def health_check_condition() -> bool:
    last_check = redis.get("health:last_check")
    if last_check:
        elapsed = time.time() - float(last_check)
        return elapsed > 60
    return True  # Nunca checou

# Trigger 2: Memory Cleanup — APENAS se conversation_log > 1000 rows
def memory_cleanup_condition() -> bool:
    count = redis.get("conversation_log:count")
    if count:
        return int(count) > 1000
    return False  # Nao sabe o count, nao limpa

# Trigger 3: Skill Stats — APENAS se algum skill foi usado desde ultimo flush
def skill_stats_condition() -> bool:
    for skill_name in SKILL_NAMES:
        count = redis.get(f"skill_usage:{skill_name}")
        if count and int(count) > 0:
            return True
    return False

# Trigger 5: Error Repeated — APENAS se houve erro recente
def error_repeated_condition() -> bool:
    recent_errors = redis.get("errors:last_hour")
    return recent_errors and int(recent_errors) > 0
```

### Checkpoint T4-01
```
[ ] 0 triggers com lambda: True
[ ] Cada trigger verifica estado real antes de disparar
[ ] Health check roda apenas quando necessario
[ ] Memory cleanup roda apenas quando conversation_log > 1000
[ ] Skill stats roda apenas quando houve uso
```

---

## T4-02: Conectar Engine ao Telegram para Approvals (~4h)

### Problema

Cap Gates marcam proposals DANGEROUS como `requires_approval = TRUE`, mas nao notificam o usuario. A proposal fica parada no banco sem ninguem saber.

### Solucao

Quando uma proposal eh marcada como requerendo approval, enviar mensagem Telegram:

```python
async def _request_approval(self, proposal_id: int, proposal: dict):
    """Envia pedido de approval via Telegram."""
    action = proposal.get("suggested_action", {})
    description = action.get("description", "Acao autonoma")

    message = (
        f"Proposta autonoma #{proposal_id}:\n"
        f"{description}\n\n"
        f"Acao: {action.get('action', 'desconhecida')}\n"
        f"Aprovar? Responda: /approve {proposal_id} ou /reject {proposal_id}"
    )

    # Enviar via Telegram bot
    from telegram_bot.bot import send_notification
    await send_notification(message)
```

### Novos comandos Telegram

```
/approve <id>  — Aprova proposal, muda status para 'approved'
/reject <id>   — Rejeita proposal, muda status para 'rejected'
/proposals     — Lista proposals pendentes
```

### Checkpoint T4-02
```
[ ] Proposal DANGEROUS gera mensagem Telegram
[ ] /approve <id> aprova e executa
[ ] /reject <id> rejeita com nota
[ ] /proposals lista pendentes
```

---

## T5-01: Curar Documentacao (~2h)

### Acoes

1. Mover planos obsoletos para `archive/`:
   - `plano-implantacao-vps-agente-v2.md`
   - `agentvps-v2-roadmap.md`
   - `agentvps-fase0-estabilizacao.md`
   - Outros planos em `plans/` que nao sao Sprint 03

2. Atualizar ARCHITECTURE.md com:
   - Novo grafo de 7 nos (react-based)
   - Hook system
   - Remocao de dead code

3. Atualizar README.md com estado real

### Checkpoint T5-01
```
[ ] Planos obsoletos em archive/
[ ] ARCHITECTURE.md reflete grafo atual
[ ] README.md atualizado
[ ] Ratio docs:codigo < 0.3
```

---

## Checklist Final

```
DIA 1 (URGENTE)
[ ] T1-01: react_node plugado no graph.py
[ ] T1-02: node_execute adaptado, sem import system_tools
[ ] T2-01: Dead code deletado (-477 linhas)

SEMANA 1
[ ] T3-01: Hook system implementado
[ ] T3-02: Feedback loop basico (learning -> consulta -> warning)

SEMANA 2
[ ] T4-01: Triggers com condicoes reais (0 lambda: True)
[ ] T4-02: Approvals Telegram para proposals DANGEROUS
[ ] T5-01: Documentacao curada

VALIDACAO FINAL
[ ] 20 formulacoes funcionam end-to-end via react_node
[ ] graph.py tem 7 nos (nao 10)
[ ] 0 imports de system_tools, intent_classifier, semantic_memory
[ ] Hooks geram logs estruturados por skill
[ ] Learnings sao consultados antes de execucao
[ ] Triggers verificam estado real
[ ] Proposals DANGEROUS geram notificacao Telegram
[ ] CI/CD verde
[ ] Score Inteligencia >= 7/10
[ ] Score Overall >= 7.5/10
```
