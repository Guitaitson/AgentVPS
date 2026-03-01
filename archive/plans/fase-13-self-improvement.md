# FASE 13: Self-Improvement Agent

## Objetivo
Implementar capacidade de self-improvement no agente VPS, permitindo que ele:
1. Reconheça capacidades faltantes
2. Planeje e implemente novas funcionalidades automaticamente
3. Aprenda e evolua de forma autônoma

## Arquitetura Proposta

```
┌─────────────────────────────────────────────────────────────────┐
│                    VPS-Agent (Autônomo)                │
│                                                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Telegram Bot (Interface Humana)                │   │
│  │  - Recebe mensagens do usuário                │   │
│  │  - Envia respostas                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                        ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  LangGraph (Orquestrador)                     │   │
│  │  - Classifica intenções                          │   │
│  │  - Carrega contexto + memória                   │   │
│  │  - Planeja ações                              │   │
│  │  - Executa comandos diretos                   │   │
│  │  - Chama CLI para tarefas complexas            │   │
│  │  - Detecta capacidades faltantes               │   │
│  │  - Implementa auto-improvement                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                        ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  CLI/Kilocode (Cérebro)                       │   │
│  │  - Processa tarefas complexas                   │   │
│  │  - Gera código                                 │   │
│  │  - Implementa novas funcionalidades               │   │
│  └──────────────────────────────────────────────────────┘   │
│                        ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  MCP Server (Ferramentas)                      │   │
│  │  - RAM, Containers, Tools, Services            │   │
│  └──────────────────────────────────────────────────────┘   │
│                        ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Capabilities Registry (Novo)                    │   │
│  │  - Registra capacidades disponíveis              │   │
│  │  - Detecta capacidades faltantes               │   │
│  │  - Gerencia auto-implementação                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Fluxo de Self-Improvement

```
Usuário: "Lista meus projetos do GitHub"
    ↓
Telegram Bot → LangGraph
    ↓
node_classify_intent: "task" (não é comando direto)
    ↓
node_load_context: Carrega memória + contexto
    ↓
node_plan: Analisa o pedido
    ↓
node_check_capabilities: "GitHub API não disponível"
    ↓
node_self_improve: "Preciso implementar GitHub API"
    ↓
node_call_cli: "Implemente GitHub API client"
    ↓
CLI/Kilocode: Gera código para GitHub API
    ↓
node_implement_capability: Adiciona GitHub API ao projeto
    ↓
node_save_memory: Salva nova capacidade
    ↓
Telegram Bot: "Implementei GitHub API! Agora posso listar seus projetos."
```

## Componentes a Implementar

### 1. vps_agent/agent.py (Interface Telegram → LangGraph)
```python
# Função principal que conecta o bot ao LangGraph
async def process_message_async(user_id: str, message: str) -> str:
    """Processa mensagem do usuário através do LangGraph."""
    graph = build_agent_graph()
    state = {
        "user_id": user_id,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    result = await graph.ainvoke(state)
    return result.get("response", "Desculpe, não entendi.")
```

### 2. Capabilities Registry (Novo Módulo)
```python
# core/capabilities/registry.py

class Capability:
    """Representa uma capacidade do agente."""
    name: str
    description: str
    implemented: bool
    dependencies: list[str]
    implementation_path: str

class CapabilitiesRegistry:
    """Gerencia capacidades disponíveis e detecta faltantes."""
    
    def register(self, capability: Capability)
    def check_capability(self, name: str) -> bool
    def detect_missing(self, task: str) -> list[Capability]
    def get_implementation_plan(self, capability: Capability) -> str
```

### 3. Novos Nodes do LangGraph

#### node_check_capabilities
```python
async def node_check_capabilities(state: AgentState) -> dict:
    """Verifica se o agente tem as capacidades necessárias."""
    task = state.get("message", "")
    missing = capabilities_registry.detect_missing(task)
    
    if missing:
        return {
            "missing_capabilities": missing,
            "needs_improvement": True
        }
    return {
        "missing_capabilities": [],
        "needs_improvement": False
    }
```

#### node_self_improve
```python
async def node_self_improve(state: AgentState) -> dict:
    """Planeja e executa auto-improvement."""
    missing = state.get("missing_capabilities", [])
    
    if not missing:
        return {"should_improve": False}
    
    # Criar plano de implementação
    plan = []
    for cap in missing:
        plan.append({
            "capability": cap.name,
            "description": cap.description,
            "steps": capabilities_registry.get_implementation_plan(cap)
        })
    
    return {
        "improvement_plan": plan,
        "should_improve": True
    }
```

#### node_implement_capability
```python
async def node_implement_capability(state: AgentState) -> dict:
    """Implementa uma nova capacidade usando o CLI."""
    plan = state.get("improvement_plan", [])
    
    if not plan:
        return {"implementation_result": "Nada para implementar"}
    
    # Chamar CLI para implementar
    cli_result = await call_cli_for_implementation(plan[0])
    
    return {
        "implementation_result": cli_result,
        "new_capability": plan[0]["capability"]
    }
```

### 4. Atualização do LangGraph Graph

```python
# Novo fluxo com self-improvement
graph.add_node("check_capabilities", node_check_capabilities)
graph.add_node("self_improve", node_self_improve)
graph.add_node("implement_capability", node_implement_capability)

# Fluxo atualizado
graph.set_entry_point("classify")
graph.add_edge("classify", "load_context")
graph.add_edge("load_context", "plan")
graph.add_edge("plan", "check_capabilities")

# Condicional: precisa melhorar?
graph.add_conditional_edges(
    "check_capabilities",
    lambda state: "self_improve" if state.get("needs_improvement") else "execute",
    {
        "self_improve": "self_improve",
        "execute": "execute"
    }
)

graph.add_edge("self_improve", "implement_capability")
graph.add_edge("implement_capability", "respond")
```

## Capacidades Iniciais

### Capacidades Core (Sempre Disponíveis)
1. **VPS Management**
   - RAM status
   - Container management
   - Service control
   - System info

2. **Memory**
   - Structured memory (PostgreSQL)
   - Semantic memory (Qdrant)
   - Context retrieval

3. **Communication**
   - Telegram Bot
   - Message processing

### Capacidades a Implementar (Exemplos)
1. **GitHub Integration**
   - Listar repositórios
   - Criar issues
   - Gerenciar PRs
   - Dependência: GitHub PAT

2. **File Operations**
   - Ler arquivos
   - Criar arquivos
   - Editar arquivos
   - Dependência: Filesystem MCP

3. **Web Scraping**
   - Buscar informações online
   - Extrair dados de sites
   - Dependência: HTTP client

## Teste de Self-Improvement

### Cenário 1: Listar Projetos GitHub
```
Usuário: "Quais projetos eu tenho no GitHub?"

1. node_classify_intent: "task"
2. node_load_context: Carrega memória
3. node_plan: "Preciso listar repositórios do usuário"
4. node_check_capabilities: "GitHub API não disponível"
5. node_self_improve: "Implementar GitHub API client"
6. node_call_cli: "Gera código para GitHub API"
7. node_implement_capability: "Adiciona github_client.py"
8. node_save_memory: "Salva nova capacidade"
9. node_respond: "Implementei GitHub API! Agora posso listar seus projetos."
```

### Cenário 2: Criar Novo Projeto
```
Usuário: "Cria um projeto Python básico"

1. node_classify_intent: "task"
2. node_load_context: Carrega memória
3. node_plan: "Criar estrutura de projeto Python"
4. node_check_capabilities: "File operations disponíveis"
5. node_execute: "Cria diretório e arquivos"
6. node_save_memory: "Salva novo projeto"
7. node_respond: "Projeto criado em /opt/vps-agent/projects/novo-projeto"
```

## Checklist de Implementação

### Passo 1: Infraestrutura Base
- [ ] Criar `core/capabilities/registry.py`
- [ ] Criar `core/capabilities/__init__.py`
- [ ] Definir classes `Capability` e `CapabilitiesRegistry`
- [ ] Criar tabela PostgreSQL para capacidades

### Passo 2: LangGraph Nodes
- [ ] Implementar `node_check_capabilities`
- [ ] Implementar `node_self_improve`
- [ ] Implementar `node_implement_capability`
- [ ] Atualizar `core/langgraph/graph.py` com novos nós
- [ ] Atualizar `core/langgraph/nodes.py` com novos nós

### Passo 3: Interface Telegram
- [ ] Criar `core/vps_agent/agent.py`
- [ ] Implementar `process_message_async`
- [ ] Atualizar `telegram-bot/bot.py` para usar nova interface

### Passo 4: Integração CLI
- [ ] Criar função `call_cli_for_implementation`
- [ ] Definir prompt para auto-implementação
- [ ] Testar geração de código pelo CLI

### Passo 5: Testes
- [ ] Testar cenário GitHub
- [ ] Testar cenário file operations
- [ ] Testar detecção de capacidades
- [ ] Testar auto-implementação
- [ ] Verificar memória semântica

## Dependências

### Novas Dependências Python
```txt
# core/requirements.txt
pydantic>=2.7.0
```

### Dependências de Serviço
- PostgreSQL (já existe)
- Qdrant (já existe)
- CLI/Kilocode (já existe)

## Riscos e Mitigações

### Risco 1: Loop Infinito de Self-Improvement
**Problema:** Agente tenta implementar algo, falha, tenta de novo.
**Mitigação:** Limite de tentativas (max 3) e timeout (5 min).

### Risco 2: Implementações Incorretas
**Problema:** CLI gera código que não funciona.
**Mitigação:** Testes automáticos após implementação e rollback em caso de falha.

### Risco 3: Excesso de RAM
**Problema:** Múltiplas implementações simultâneas.
**Mitigação:** Resource Manager controla RAM e limita implementações.

## Próximos Passos Após FASE 13

1. **FASE 14:** Teste Completo do Agente Autônomo
2. **FASE 15:** Monitoramento e Logging Avançado
3. **FASE 16:** Interface Web (Dashboard)
