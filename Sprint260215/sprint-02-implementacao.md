# 🔧 Sprint 02 — Plano de Implementação Detalhado

> **Pré-requisito:** Ler `sprint-02-objetivo.md` e `sprint-02-roadmap.md`.

---

## T1-01: Revogar e Remover API Key (~1h)

### Passo a Passo

```bash
# 1. Verificar exposição
grep -rn "BSA1\|API_KEY.*=.*[A-Za-z0-9]" core/ --include="*.py"

# 2. Corrigir web_search/handler.py
# ANTES:
# BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "BSA1oVa6QVwZf5E3lCRo1h19cmY9Ywo")
# DEPOIS:
# BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

# 3. Revogar key no Brave Dashboard: https://api.search.brave.com/app/keys
# 4. Gerar nova key, adicionar ao .env da VPS
# 5. Auditar completamente
grep -rn "key\|token\|password\|secret\|apikey" core/ --include="*.py" | grep -v "def \|#\|import\|API_KEY\|logger\|docstring"

# 6. Commit
git add -A && git commit -m "fix: remove exposed API key from source code [SECURITY]"
git push
```

### Checkpoint T1-01
```
□ grep -r "BSA1" core/ retorna 0
□ Nova key funciona no .env
□ Commit com tag [SECURITY]
```

---

## T1-02: Remover Debug Log (~1h)

### Onde Está

```python
# core/vps_langgraph/nodes.py — node_security_check (3 ocorrências)
with open("/tmp/security_debug.log", "a") as f:
    f.write(json.dumps(debug_info) + "\n")
```

### Substituição

Trocar cada ocorrência por:
```python
logger.debug("security_check_detail", **debug_info)
```

O structlog já está configurado e vai para o log normal do sistema (controlável via nível de log).

### Checkpoint T1-02
```
□ grep -r "security_debug" core/ retorna 0
□ grep -r "open.*tmp" core/vps_langgraph/nodes.py retorna 0
□ Logs de segurança aparecem via structlog quando level=DEBUG
```

---

## T2-01: Definir Tool Schemas (~6h)

### Conceito

Function calling funciona assim: enviamos ao LLM uma lista de "tools" com nome, descrição e parâmetros. O LLM decide se precisa chamar uma tool e com quais argumentos.

### Formato de Tool Schema (OpenRouter / Gemini)

```python
{
    "type": "function",
    "function": {
        "name": "shell_exec",
        "description": "Executa um comando shell na VPS. Use para verificar status do sistema, listar arquivos, verificar instalações, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "O comando shell a executar. Exemplos: 'which docker', 'free -h', 'ls -la /opt'"
                }
            },
            "required": ["command"]
        }
    }
}
```

### Implementação: Adicionar ao SkillConfig e Registry

**1. Adicionar `tool_schema` ao config.yaml de cada skill:**

```yaml
# core/skills/_builtin/shell_exec/config.yaml
name: shell_exec
description: "Executa um comando shell na VPS. Use para verificar status, listar arquivos, checar instalações, gerenciar containers, e executar qualquer comando do sistema operacional."
parameters_schema:
  command:
    type: string
    description: "O comando shell a executar (ex: 'which docker', 'free -h', 'df -h', 'docker ps')"
    required: true
```

```yaml
# core/skills/_builtin/web_search/config.yaml
name: web_search
description: "Pesquisa informações na internet. Use quando o usuário perguntar sobre qualquer assunto que não seja sobre o próprio servidor."
parameters_schema:
  query:
    type: string
    description: "O termo de busca (ex: 'como instalar Node.js 22 no Ubuntu')"
    required: true
```

```yaml
# core/skills/_builtin/file_manager/config.yaml
name: file_manager
description: "Lê, cria, edita ou lista arquivos e diretórios no servidor. Use para qualquer operação com arquivos."
parameters_schema:
  operation:
    type: string
    description: "A operação: 'read', 'write', 'append', ou 'list'"
    required: true
  path:
    type: string
    description: "O caminho do arquivo ou diretório (ex: '/opt/vps-agent/README.md')"
    required: true
  content:
    type: string
    description: "Conteúdo para escrita (apenas para write/append)"
    required: false
```

**2. Adicionar método ao SkillConfig e Registry:**

```python
# Em base.py, adicionar ao SkillConfig:
parameters_schema: Dict[str, Any] = field(default_factory=dict)

# Em registry.py, adicionar método:
def list_tool_schemas(self) -> list[dict]:
    """Retorna lista de tool schemas para function calling."""
    tools = []
    for skill in self._skills.values():
        properties = {}
        required = []
        for param_name, param_info in skill.config.parameters_schema.items():
            properties[param_name] = {
                "type": param_info.get("type", "string"),
                "description": param_info.get("description", ""),
            }
            if param_info.get("required", False):
                required.append(param_name)
        
        tools.append({
            "type": "function",
            "function": {
                "name": skill.name,
                "description": skill.config.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        })
    return tools
```

**3. Incluir skills builtin que NÃO precisam de parâmetros:**

```yaml
# ram/config.yaml
name: get_ram
description: "Mostra uso atual de memória RAM do servidor. Use quando perguntem sobre memória, RAM, ou recursos."
parameters_schema: {}
```

O LLM chamará `get_ram()` sem argumentos — correto.

### Checkpoint T2-01
```
□ registry.list_tool_schemas() retorna 10 schemas válidos
□ Cada schema tem name, description, e parameters corretos
□ Schemas sem parâmetros (ram, containers, etc.) funcionam
```

---

## T2-02: Implementar ReAct Node (~12h)

### Conceito Central

O nó `react` é o coração do novo sistema. Ele:
1. Recebe a mensagem do usuário + histórico
2. Chama o LLM com a lista de tools (function calling)
3. Se o LLM retorna `tool_call`: executa a tool, envia resultado de volta ao LLM
4. Se o LLM retorna texto: usa como resposta direta

### Novo Nó: `core/vps_langgraph/react_node.py`

```python
"""
ReAct Node — O cérebro do agente.

Usa function calling para que o LLM decida qual tool usar.
Substitui: node_classify_intent + node_plan + interpretação do shell_exec.
"""

import json
from typing import Any, Dict, Optional, Tuple

import structlog

from ..skills.registry import get_skill_registry
from .state import AgentState

logger = structlog.get_logger()

SYSTEM_PROMPT = """Você é o VPS-Agent, um assistente autônomo rodando em um servidor VPS Ubuntu.

Você tem acesso a ferramentas (tools) para executar ações no servidor. Use-as quando necessário.

Regras:
1. Para perguntas sobre o servidor (RAM, disco, processos, Docker, arquivos), USE uma tool.
2. Para perguntas gerais de conhecimento, responda diretamente SEM usar tools.
3. Para buscas na internet, use a tool web_search.
4. Para ler/criar/editar arquivos, use a tool file_manager.
5. Sempre responda em português brasileiro de forma concisa e natural.
6. Quando usar uma tool, interprete o resultado e responda de forma conversacional.

Exemplos de quando usar tools:
- "quanta RAM?" → use get_ram
- "tem docker?" → use shell_exec com command="which docker"
- "liste os containers" → use list_containers
- "leia o arquivo X" → use file_manager com operation="read"
- "busque sobre Y" → use web_search com query="Y"

Exemplos de quando NÃO usar tools:
- "o que é Python?" → responda diretamente
- "olá, tudo bem?" → responda diretamente
- "me ajude com um código" → responda diretamente
"""


async def node_react(state: AgentState) -> AgentState:
    """
    Nó ReAct: LLM decide se usa tool ou responde diretamente.
    """
    from ..llm.unified_provider import get_llm_provider

    user_message = state["user_message"]
    conversation_history = state.get("conversation_history", [])
    
    registry = get_skill_registry()
    tools = registry.list_tool_schemas()

    logger.info("react_start", message=user_message[:80], tools_count=len(tools))

    provider = get_llm_provider()

    # Primeira chamada: LLM decide se usa tool ou responde
    response = await provider.generate_with_tools(
        user_message=user_message,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        conversation_history=conversation_history,
    )

    if not response.success:
        logger.error("react_llm_failed", error=response.error)
        return {
            **state,
            "intent": "chat",
            "response": "Desculpe, tive um problema ao processar sua mensagem. Tente novamente.",
        }

    # Se LLM retornou tool_call
    if response.tool_calls:
        tool_call = response.tool_calls[0]  # Processar primeira tool
        tool_name = tool_call["name"]
        tool_args = tool_call.get("arguments", {})

        logger.info("react_tool_call", tool=tool_name, args=tool_args)

        return {
            **state,
            "intent": "task",
            "action_required": True,
            "tool_suggestion": tool_name,
            "plan": [{"type": "skill", "action": tool_name, "args": tool_args}],
            "current_step": 0,
            "tools_needed": [tool_name],
        }

    # Se LLM respondeu diretamente
    logger.info("react_direct_response")
    return {
        **state,
        "intent": "chat",
        "action_required": False,
        "response": response.content,
        "plan": None,
    }


async def node_format_response(state: AgentState) -> AgentState:
    """
    Após execução da tool, envia resultado ao LLM para formatação.
    """
    from ..llm.unified_provider import get_llm_provider

    execution_result = state.get("execution_result", "")
    user_message = state.get("user_message", "")
    tool_name = state.get("tool_suggestion", "")

    if not execution_result:
        return state

    provider = get_llm_provider()
    
    format_prompt = f"""O usuário perguntou: "{user_message}"

Você usou a ferramenta '{tool_name}' e obteve este resultado:

{execution_result}

Responda a pergunta do usuário de forma natural e conversacional em português, 
interpretando o resultado acima. Seja conciso."""

    response = await provider.generate(
        user_message=format_prompt,
        system_prompt="Responda de forma concisa e natural em português brasileiro.",
    )

    if response.success and response.content:
        return {**state, "response": response.content}

    # Fallback: usar resultado raw
    return {**state, "response": execution_result}
```

### Modificar unified_provider.py

Adicionar método `generate_with_tools`:

```python
async def generate_with_tools(
    self,
    user_message: str,
    system_prompt: str,
    tools: list[dict],
    conversation_history: list = None,
) -> LLMResponse:
    """Gera resposta com suporte a function calling."""
    messages = []
    if conversation_history:
        messages.extend(conversation_history[-5:])
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": self.model,
        "messages": messages,
        "tools": tools,
        "max_tokens": 1024,
    }
    if system_prompt:
        payload["messages"].insert(0, {"role": "system", "content": system_prompt})

    # Chamar OpenRouter API
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        data = resp.json()

    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})

    # Verificar se há tool_calls
    if message.get("tool_calls"):
        tool_calls = []
        for tc in message["tool_calls"]:
            func = tc.get("function", {})
            tool_calls.append({
                "name": func.get("name", ""),
                "arguments": json.loads(func.get("arguments", "{}")),
            })
        return LLMResponse(success=True, content="", tool_calls=tool_calls)

    return LLMResponse(success=True, content=message.get("content", ""))
```

### Modificar graph.py

```python
# Substituir nós antigos pelo novo fluxo:
workflow.add_node("load_context", node_load_context)
workflow.add_node("react", node_react)              # NOVO
workflow.add_node("security_check", node_security_check)
workflow.add_node("execute", node_execute)           # Simplificado
workflow.add_node("format_response", node_format_response)  # NOVO
workflow.add_node("respond", node_generate_response)  # Simplificado
workflow.add_node("save_memory", node_save_memory)

workflow.set_entry_point("load_context")
workflow.add_edge("load_context", "react")

# React decide: tool ou resposta direta
def route_after_react(state):
    if state.get("action_required"):
        return "security_check"
    return "respond"  # LLM já respondeu

workflow.add_conditional_edges("react", route_after_react, {
    "security_check": "security_check",
    "respond": "respond",
})

# Security → execute ou respond (se bloqueado)
workflow.add_conditional_edges("security_check", route_after_security, {
    "execute": "execute",
    "respond": "respond",
})

workflow.add_edge("execute", "format_response")  # LLM formata resultado
workflow.add_edge("format_response", "respond")
workflow.add_edge("respond", "save_memory")
workflow.set_finish_point("save_memory")
```

### Checkpoint T2-02
```
□ node_react funciona com function calling
□ "quanta ram?" → LLM chama get_ram → resultado formatado
□ "o que é Python?" → LLM responde diretamente (sem tool)
□ "execute ls -la" → LLM chama shell_exec(command="ls -la")
□ Grafo tem 7 nós em vez de 10
```

---

## T2-03: Testes do ReAct (~6h)

### 20 Formulações de Teste

```python
# tests/test_react_intelligence.py

EQUIVALENCE_TESTS = [
    # Grupo 1: RAM (5 formulações → mesma tool)
    ("quanta ram?", "get_ram"),
    ("como está a memória?", "get_ram"),
    ("uso de memória", "get_ram"),
    ("memoria do servidor", "get_ram"),
    ("RAM disponível", "get_ram"),
    
    # Grupo 2: Instalação (5 formulações → shell_exec com which)
    ("tem o docker instalado?", "shell_exec"),
    ("docker tá na máquina?", "shell_exec"),
    ("o docker está disponível?", "shell_exec"),
    ("verifica se tem docker", "shell_exec"),
    ("docker existe no servidor?", "shell_exec"),
    
    # Grupo 3: Busca web (5 formulações → web_search)
    ("busque sobre LangGraph", "web_search"),
    ("pesquise como instalar Node", "web_search"),
    ("procure informações sobre FastAPI", "web_search"),
    ("o que é Kubernetes?", "web_search"),  # Pode ser direto ou busca
    ("como configurar nginx?", "web_search"),
    
    # Grupo 4: Chat direto (5 formulações → sem tool)
    ("olá!", None),
    ("tudo bem?", None),
    ("obrigado pela ajuda", None),
    ("me conta uma piada", None),
    ("qual sua opinião sobre IA?", None),
]
```

### Checkpoint T2-03
```
□ 18+ de 20 formulações produzem a tool esperada
□ Latência média < 3 segundos por mensagem
□ Custo LLM ≤ custo do sistema anterior
```

---

## T4: Autonomous Blueprint Real

### T4-01: Schema PostgreSQL

Usar o schema definido no `sprint-01-implementacao.md` (seção S4-01). As tabelas `agent_proposals`, `agent_missions`, `agent_policies` não foram criadas na sprint anterior — criar agora.

### T4-02: Refatorar engine.py

Substituir `Trigger` com `condition: lambda: True` por ciclo real:

```python
async def _heartbeat(self):
    """Um ciclo do heartbeat — segue os 6 passos do Blueprint."""
    
    # 1. DETECT — verificar condições
    conditions = await self._check_conditions()
    
    for condition in conditions:
        # 2. PROPOSE — criar proposal no PostgreSQL
        proposal_id = await self._create_proposal(condition)
        
        # 3. FILTER — cap gates
        gate_result = await self._check_cap_gates(proposal_id)
        
        if gate_result["blocked"]:
            await self._update_proposal(proposal_id, "rejected", gate_result["reason"])
            continue
        
        if gate_result["requires_approval"]:
            await self._request_approval(proposal_id, condition)
            continue  # Será executado quando aprovado via Telegram
        
        # 4. EXECUTE — criar missão e executar
        mission_id = await self._create_mission(proposal_id)
        result = await self._execute_mission(mission_id)
        
        # 5. COMPLETE — emitir evento
        event = await self._complete_mission(mission_id, result)
        
        # 6. RE-TRIGGER — evento pode gerar novas proposals
        if event.get("trigger_new_proposals"):
            for new_condition in event["trigger_new_proposals"]:
                await self._create_proposal(new_condition)
```

### Checkpoint T4
```
□ SELECT count(*) FROM agent_proposals retorna > 0 após 30 min
□ SELECT count(*) FROM agent_missions retorna > 0 para proposals executadas
□ Policy max_proposals_per_hour é respeitada
□ Proposals DANGEROUS geram notificação Telegram
```

---

## Checklist Final

```
DIA 1
□ T1-01: API key removida e revogada
□ T1-02: Debug log removido

SEMANA 1
□ T2-01: Tool schemas definidos para 10 skills
□ T2-02: node_react funcional com function calling
□ T2-03: 18+ de 20 formulações funcionam

SEMANA 2-3
□ T3-01: shell_exec < 80 linhas
□ T3-02: Todos skills recebem args estruturados
□ T4-01: Tabelas PostgreSQL criadas
□ T4-02: Engine com 6 passos reais
□ T4-03: Cap gates + approval Telegram
□ T5-01: Dead code removido (-500 linhas)
□ T5-02: Docs obsoletas arquivadas

VALIDAÇÃO FINAL
□ Inteligência: 20 formulações diferentes → mesma ação
□ Segurança: 0 secrets no código, 0 debug logs
□ Autonomia: Proposals no PostgreSQL, cap gates funcionais
□ Qualidade: shell_exec < 80 linhas, total core/ < 12.500 linhas
□ CI/CD verde
```
