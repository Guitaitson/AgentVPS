# Fase 5-6: Modernização do Core

## Objetivo
Transformar o AgentVPS em um agente inteligente capaz de entender linguagem natural e executar ações via tools.

---

## Fase 5: LangGraph Moderno

### 5.1 Migrar State para `Annotated` (TypedDict moderno)

**Arquivo:** `core/vps_langgraph/state.py`

```python
from typing import Annotated, TypedDict
from langgraph.graph import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # Acumula mensagens automaticamente
    user_id: str
    intent: str
    intent_confidence: float
    plan: list
    execution_result: str
    response: str
```

**Benefícios:**
- Type safety completo
- Reducer automático para mensagens
- Melhor integração com LangGraph

### 5.2 Subgraphs para Organização

**Estrutura:**
```
main_graph/
├── classify_subgraph/     # Classificação de intent
├── security_subgraph/     # Validações de segurança  
├── execute_subgraph/      # Execução de ações
└── respond_subgraph/      # Geração de respostas
```

### 5.3 Checkpointing com PostgreSQL

**Configuração:**
```python
from langgraph.checkpoint.postgres import PostgresSaver

# Persistir estado no PostgreSQL
checkpointer = PostgresSaver(conn_string)
graph = builder.compile(checkpointer=checkpointer)
```

---

## Fase 6: Intent via LLM (Structured Output)

### 6.1 Substituir Regex por LLM

**Antes (Regex):**
```python
if "ram" in message.lower():
    return Intent.QUESTION
```

**Depois (LLM com Structured Output):**
```python
from langchain_core.pydantic_v1 import BaseModel, Field

class IntentClassification(BaseModel):
    intent: str = Field(..., enum=["command", "task", "question", "chat"])
    confidence: float = Field(..., ge=0, le=1)
    entities: list[str] = Field(default=[])
    action_required: bool = Field(default=False)

# LLM retorna JSON estruturado
result = llm.with_structured_output(IntentClassification).invoke(prompt)
```

### 6.2 Function Calling para Ações

**Definir Tools:**
```python
from langchain_core.tools import tool

@tool
def get_ram_usage() -> str:
    """Get current RAM usage in MB."""
    import subprocess
    result = subprocess.run(["free", "-m"], capture_output=True, text=True)
    return result.stdout

@tool
def list_docker_containers() -> str:
    """List all running Docker containers."""
    result = subprocess.run(
        ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"],
        capture_output=True, text=True
    )
    return result.stdout

# Bind tools ao LLM
llm_with_tools = llm.bind_tools([get_ram_usage, list_docker_containers])
```

**Fluxo:**
1. Usuário: "quanta RAM estamos usando?"
2. LLM identifica intent: `question` + entities: `["ram"]`
3. LLM chama tool: `get_ram_usage()`
4. Tool executa na VPS
5. LLM responde com resultado

---

## Fase 7: LLM Provider Unificado com Tool Use

### 7.1 Abstrair Provider

**Interface:**
```python
from abc import ABC, abstractmethod
from typing import Any

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str: ...
    
    @abstractmethod
    async def generate_with_tools(
        self, 
        prompt: str, 
        tools: list[dict],
        **kwargs
    ) -> dict[str, Any]: ...
    
    @abstractmethod
    def bind_tools(self, tools: list): ...
```

### 7.2 Implementações

- **OpenRouter** (atual)
- **Ollama** (local)
- **Anthropic** (Claude)

---

## Implementação Passo a Passo

### Semana 1: State Moderno + Subgraphs
- [ ] Migrar `state.py` para TypedDict com Annotated
- [ ] Criar subgraphs organizados
- [ ] Implementar checkpointing PostgreSQL

### Semana 2: Intent via LLM
- [ ] Criar schema Pydantic para classificação
- [ ] Implementar classificador com structured output
- [ ] Testar vs regex antigo

### Semana 3: Tools
- [ ] Definir tools básicos (RAM, containers, etc.)
- [ ] Implementar function calling
- [ ] Integrar ao grafo

### Semana 4: Provider Unificado
- [ ] Abstrair interface LLMProvider
- [ ] Migrar OpenRouter para nova interface
- [ ] Adicionar suporte a Ollama

---

## Critérios de Sucesso

1. ✅ Bot entende "quanta RAM?" e executa comando
2. ✅ Respostas mais naturais e contextuais
3. ✅ Sistema extensível via novas tools
4. ✅ Suporte a múltiplos providers LLM
5. ✅ Estado persistente entre sessões
