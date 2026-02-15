# Plano: Agente Autônomo com Integração GitHub

## Problema Atual

O LLM (Gemini) responde como um modelo genérico, sem saber das capacidades reais do agente.

```
Usuário: "você tem acesso ao kilocode CLI?"
LLM: "Não tenho acesso direto ao kilocode CLI, pois sou um modelo de linguagem..."
```

**Problema:** O LLM não sabe que é o VPS-Agent com acesso a ferramentas reais!

## Arquitetura Atual vs. Necessária

### Atual
```
Telegram → LangGraph → LLM (sem contexto) → Resposta genérica
```

### Necessária
```
Telegram → LangGraph → [Capabilities + Memória + LLM] → Ferramenta Real → Resposta
```

## Solução em 3 Fases

### FASE 1: Contexto do Agente no LLM
**Objetivo:** O LLM saberá suas capacidades reais

Modificar `openrouter_client.py` para passar:
- Lista de capacidades implementadas
- Ferramentas disponíveis (MCP)
- Memória do usuário

### FASE 2: Fluxo de Ferramentas
**Objetivo:** Quando usuário pedir algo, usar ferramenta real

```python
# Fluxo desejado
if intent == "github_projects":
    if has_github_capability():
        result = call_github_api(user.token)
    else:
        result = self_improve_agent.implement_github()
```

### FASE 3: Auto-Implementation
**Objetivo:** O agente implementa capacidades faltantes sozinho

## Componentes a Desenvolver

### 1. `core/capabilities/capabilities_context.py`
```python
def get_capabilities_context() -> str:
    """Retorna string com todas as capacidades para o LLM."""
    caps = capabilities_registry.get_implemented_capabilities()
    return "\n".join([
        f"- {cap.name}: {cap.description}"
        for cap in caps
    ])
```

### 2. `core/tools/github_tool.py`
```python
class GitHubTool:
    """Ferramenta para interagir com GitHub API."""
    async def list_repos(self, token: str) -> List[dict]:
        # Chamar GitHub API
        pass
```

### 3. Modificar `node_generate_response()`
Passar contexto das capacidades para o LLM:

```python
capabilities_context = get_capabilities_context()
llm_prompt = f"""Você é o VPS-Agent com estas capacidades:
{capabilities_context}

O usuário disse: "{user_message}"
"""
```

## Plano de Implementação

### Passo 1: Atualizar System Prompt
- [ ] Adicionar lista de capacidades ao system prompt
- [ ] Adicionar ferramentas MCP disponíveis
- [ ] Adicionar instruções de quando usar ferramentas vs. responder

### Passo 2: Criar Ferramenta GitHub
- [ ] Criar `core/tools/github_tool.py`
- [ ] Adicionar integração com GitHub API
- [ ] Suportar Personal Access Token (PAT)
- [ ] Listar repositórios do usuário

### Passo 3: Modificar node_plan
- [ ] Detectar intents que requerem GitHub
- [ ] Verificar se capacidade existe
- [ ] Chamar Self-Improvement se não existir

### Passo 4: Auto-Implementation
- [ ] O agente gera código para nova capacidade
- [ ] Salva em arquivo
- [ ] Registra no CapabilitiesRegistry
- [ ] Testa e marca como implementada

## Exemplo de Conversa Futura

```
Usuário: "quais projetos tenho no github?"

Agente:
1. Verifica capacidades → Não tem GitHub
2. Chama Self-Improvement → Implementa GitHub Tool
3. Pede PAT ao usuário (se não tiver)
4. Lista projetos
```

## Resultado Esperado

```
Usuário: "quais projetos tenho no github?"
Agente: "Vou verificar seus repositórios no GitHub..."
[Busca API]
"Você tem 12 repositórios:
- AgenteVPS (público)
- Moltbot (público)
- ..."
```

## Próximos Passos Imediatos

1. **Corrigir system prompt** → LLM sabe que é VPS-Agent
2. **Criar GitHub Tool** → Integração real com API
3. **Testar fluxo** → Usuário pede → Agente executa
