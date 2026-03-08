# Solicitação de Ajuda - VPS-Agent v2

## ⚠️ Contexto Importante

Este documento foi criado para ser analisado por um modelo de IA mais potente (como Claude Sonnet 4.5, GPT-4.5, ou similar) que tenha:
- Capacidade de análise de código mais robusta
- Contexto de janela maior
- Capacidade de reasoning mais avançada

**Modelo atual em uso:** MiniMax M2.1 (via OpenRouter - gratuito)
**Objetivo:** Obter orientação para resolver problemas arquiteturais e de implementação

---

## 📋 Índice

1. [Visão Geral do Projeto](#visão-geral-do-projeto)
2. [Arquitetura Atual](#arquitetura-atual)
3. [Stack Tecnológico](#stack-tecnológico)
4. [Problemas Conhecidos](#problemas-conhecidos)
5. [Problemas Antecipados (Roadmap)](#problemas-antecipados-roadmap)
6. [Decisões Arquiteturais Pendentes](#decisões-arquiteturais-pendentes)
7. [Riscos e Mitigações](#riscos-e-mitigações)
8. [Estrutura de Arquivos](#estrutura-de-arquivos)
9. [Código Relevante](#código-relevante)
10. [Perguntas Específicas](#perguntas-específicas)

---

## 1. Visão Geral do Projeto

### O que é o VPS-Agent?

Um **agente autônomo self-improving** rodando em uma VPS com apenas **2.4 GB de RAM**. O agente é capaz de:
- Gerenciar a própria infraestrutura (Docker, containers, serviços)
- Receber comandos via Telegram
- Classificar intenções do usuário
- Aprender e melhorar autonomamente
- Implementar novas capacidades sob demanda

### Diferencial Principal

A VPS é o **agente**, não apenas infraestrutura. O CLI (Kilocode/Claude) é o **cérebro** instalado na própria VPS.

```
┌─────────────────────────────────────────┐
│           VPS 2.4 GB (AGENTE)          │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  CÉREBRO (~500 MB)                │  │
│  │  CLI (Kilocode/Claude)            │  │
│  │  LangGraph + Agent                │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  SEMPRE LIGADOS (~750 MB)         │  │
│  │  PostgreSQL + Redis + LangGraph    │  │
│  │  + Resource Manager                │  │
│  │  + Telegram Bot                    │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  SOB DEMANDA (~1650 MB livre)     │  │
│  │  Qdrant (memória semântica)       │  │
│  │  n8n, Flowise                     │  │
│  └───────────────────────────────────┘  │
│                                         │
│  Interface: Telegram                    │
└─────────────────────────────────────────┘
```

---

## 2. Arquitetura Atual

### Fluxo de Processamento de Mensagens

```
Telegram → Bot → process_message_async → LangGraph → Resposta
```

### Grafo LangGraph (nodes.py)

```
classify → load_context → plan → respond → save_memory
                              ↓
                    ┌────────┴────────┐
                    ↓                 ↓
              execute/respond    check_capabilities
                    ↓                 ↓
              save_memory         self_improve
                    ↓                 ↓
                    └────→ respond ←──┘
                              ↓
                         capabilities
```

### Intents Classificados

| Intent | Descrição | Fluxo |
|--------|-----------|-------|
| `command` | Comandos diretos do Telegram | → execute → respond |
| `task` | Tarefas a executar | → execute → respond |
| `question` | Perguntas sobre o sistema | → respond |
| `chat` | Conversa geral | → respond |
| `self_improve` | Criar algo novo/integração | → respond + capabilities |

### Self-Improvement Agent

O agente pode:
1. Detectar quando precisa de uma nova capacidade
2. Analisar o que é necessário
3. Implementar a nova funcionalidade
4. Salvar a nova capacidade no registry

---

## 3. Stack Tecnológico

### Backend
- **Python 3.12** com venv
- **LangGraph** para orquestração de agentes
- **PostgreSQL 16** para memória estruturada
- **Redis 7** para cache e filas
- **Qdrant** para memória semântica (pendente)

### Interface
- **Telegram Bot** (@Molttaitbot)
- **FastAPI-MCP** para integrações MCP

### Integrações
- **OpenRouter** para LLM (MiniMax M2.1 como default)
- **Docker** para containers sob demanda
- **Systemd** para serviços

### CI/CD
- **GitHub Actions** com pytest
- **SSH** para deploy na VPS

---

## 4. Problemas Conhecidos

### 🔴 Críticos

1. **Erro `timezone is not defined`**
   - Ocorre ao processar mensagens que disparam `check_capabilities`
   - Já corrigido em `capabilities/registry.py` (adicionado import)
   - Precisa testar se está funcionando

2. **Self-Improvement Agent não gera resposta**
   - Intent é classificado como `self_improve`
   - O fluxo passa por `check_capabilities` mas não por `respond`
   - O `node_generate_response` não trata `self_improve`
   - Resultado: `response` key não aparece no resultado final

3. **Código duplicado em múltiplas pastas**
   - `/opt/vps-agent/core/vps_langgraph/`
   - `/opt/vps-agent/core/vps_agent/`
   - `/opt/vps-agent/core/` (arquivos na raiz)
   - Confusão sobre qual usar

### 🟡 Médios

4. **Qdrant não integrado**
   - Memória semântica pendente
   - Dependencies: `qdrant-client`, `sentence-transformers`
   - Requer ~500MB RAM

5. **CI/CD falhando no GitHub Actions**
   - Module import errors
   - pytest passando localmente mas falhando no CI

6. **Limpeza de arquivos pycache**
   - Múltiplos `.pyc` causando problemas de importação

### 🟢 Pequenos

7. **Logs não reaching Telegram**
   - Bot logs vão para arquivo, não para Telegram
   - Necesário verificar configuração de logging

---

## 5. Problemas Antecipados (Roadmap)

### 5.1 Curto Prazo (Próximas 2 semanas)

#### Self-Improvement Agent
- [ ] **Fluxo de resposta não funciona**
  - Intent `self_improve` não gera resposta
  - `node_generate_response` não trata este intent
- [ ] **Testes do fluxo completo**
  - Classificação → Contexto → Plano → Resposta
  - Verificar se capabilities são carregadas
- [ ] **Cleanup de código duplicado**
  - Decidir qual estrutura usar (`vps_langgraph/` vs `vps_agent/`)
  - Remover arquivos obsoletos

#### Qdrant (Memória Semântica)
- [ ] **Integração pendente**
  - Dependencies: `qdrant-client`, `sentence-transformers`
  - RAM necessária: ~400-500MB
  - Decisão: Sempre ligado ou sob demanda?
- [ ] **Schema de embedding**
  - Que tipo de embeddings usar?
  - Dimensão: 384 (all-MiniLM-L6-v2) ou 768 (all-mpnet-base-v2)?
- [ ] **Queries de similaridade**
  - Buscar contexto relevante baseado na mensagem atual
  - Combinar com memória estruturada (PostgreSQL)

### 5.2 Médio Prazo (Próximo mês)

#### Ferramentas Reais via Self-Improvement
- [ ] **GitHub Search**
  - Buscar repositórios, issues, pull requests
  - API do GitHub via CLI
- [ ] **Web Search**
  - Buscar informações na internet
  - Brave Search API ou similar
- [ ] **Monitoramento**
  - Monitorar serviços externos
  - Notificar via Telegram quando algo falhar

#### Multiple LLMs Routing
- [ ] **Router inteligente**
  - MiniMax M2.1 para tarefas simples (barato)
  - Sonnet 4.5 para decisões arquiteturais (robusto)
  - Critérios de routing: complexidade, custo, privacidade
- [ ] **Fallback automático**
  - Se modelo primário falhar, tentar secundário
  - Log de erros e custos

#### Autonomia do Agente
- [ ] **Executor de código**
  - O agente pode executar código gerado?
  - Sandbox seguro (Docker container ephemeral)
- [ ] **Modifier de código existente**
  - O agente pode modificar arquivos do projeto?
  - Quais arquivos? Quais restrições?
- [ ] **Git operations**
  - Criar branches automaticamente
  - Commits de self-improvement

### 5.3 Longo Prazo (Próximos 3 meses)

#### Multi-Agente
- [ ] **Subagentes especializados**
  - Agente de monitoramento
  - Agente de pesquisa
  - Agente de desenvolvimento
- [ ] **Comunicação entre agentes**
  - Redis pub/sub para mensagens
  - Compartilhamento de contexto

#### Escalabilidade
- [ ] **Resource Manager v2**
  - Mais de 2 ferramentas simultâneas?
  - Priorização baseada em custo/benefício
- [ ] **Load balancing**
  - Múltiplas instâncias do agente?
  - Redis para estado compartilhado

#### Interfaces
- [ ] **WhatsApp Integration**
  - Evolution API ou similar
  - Mesma lógica do Telegram, canais diferentes
- [ ] **Web Interface**
  - Dashboard para ver status
  - Logs em tempo real

---

## 6. Decisões Arquiteturais Pendentes

### 6.1 Estrutura de Código

| Decisão | Opções | Status |
|----------|--------|--------|
| Pasta principal | `vps_langgraph/` vs `vps_agent/` | ⏳ Pendente |
| Arquivos na raiz | Manter ou mover para subpastas? | ⏳ Pendente |
| Imports absolutos vs relativos | `from vps_agent.agent` vs `from .agent` | ⏳ Pendente |

### 6.2 Memory Bank

| Decisão | Opções | Status |
|----------|--------|--------|
| PostgreSQL | Fatos, configs, histórico | ✅ Implementado |
| Redis | Cache, filas, pub/sub | ✅ Implementado |
| Qdrant | Embeddings, memória semântica | ⏳ Pendente |
| Arquivo local | Memory bank (kilocode) | ✅ Implementado |

**Pergunta:** Como integrar Qdrant com PostgreSQL?
- Opção A: Qdrant sempre ligado (mais rápido, mais RAM)
- Opção B: Qdrant sob demanda (mais RAM livre, mais lento)
- Opção C: Hybrid search (PostgreSQL + pgvector)

### 6.3 LangGraph

| Decisão | Opções | Status |
|----------|--------|--------|
| Nós síncronos | Python functions | ✅ Implementado |
| Nós assíncronos | Async functions | ⏳ Pendente |
| Checkpoints | Salvar estado do grafo | ⏳ Pendente |
| Human-in-the-loop | Aprovar antes de executar | ⏳ Pendente |

### 6.4 LLM Routing

| Decisão | Opções | Status |
|----------|--------|--------|
| Provider | OpenRouter (múltiplos modelos) | ✅ Implementado |
| Fallback | Se um modelo falha, tentar outro | ⏳ Pendente |
| Custo tracking | Log de tokens e custos | ⏳ Pendente |
| Cache de respostas | Redis cache para perguntas frequentes | ⏳ Pendente |

### 6.5 Self-Improvement

| Decisão | Opções | Status |
|----------|--------|--------|
| Execução de código | Sandbox Docker vs permitir tudo | ⏳ Pendente |
| Git integration | Auto-commit de mudanças | ⏳ Pendente |
| Aprovação | Humano aprova antes de aplicar | ⏳ Pendente |
| Rollback | Desfazer mudanças problemáticas | ⏳ Pendente |

---

## 7. Riscos e Mitigações

### 7.1 Riscos de Segurança

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|------------|
| Agente executa código malicioso | Média | Crítico | Sandbox Docker, whitelist de comandos |
| Vazamento de credenciais | Baixa | Crítico | .env com permissões 600, vault |
| Injeção de prompts | Média | Alto | Sanitização de inputs, validation |
| Acesso não autorizado | Baixa | Alto | Autenticação Telegram forte |
| Agente destrói própria infraestrutura | Baixa | Crítico | Read-only mode opção, backups |

### 7.2 Riscos de Performance

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|------------|
| RAM insuficiente | Alta | Alto | Resource Manager, monitoring |
| LLM timeout | Média | Médio | Timeouts, fallbacks, retries |
| Database connection pool | Média | Médio | Pool size adequado, monitoring |
| Qdrant memory leak | Baixa | Médio | Restart periódico, monitoring |

### 7.3 Riscos de Manutenibilidade

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|------------|
| Código duplicado | Alta | Médio | Architecture review, linting |
| Documentação defasada | Alta | Médio | Docs como código, auto-generated |
| Testes quebrando | Média | Alto | CI/CD com pytest, coverage |
| Dependências desatualizadas | Média | Médio | Renovate bot, dependabot |

### 7.4 Riscos de Negócio

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|------------|
| API key do LLM cara | Média | Alto | Routing para modelos baratos |
| VPS indisponível | Baixa | Alto | Monitoring, alerts, backup |
| Telegram bloqueado | Baixa | Alto | Múltiplos canais (WhatsApp, Web) |
| Custo operacional alto | Média | Médio | Otimização de recursos |

---

## 8. Estrutura de Arquivos

```
/opt/vps-agent/
├── core/                          # Módulo principal
│   ├── vps_agent/                 # Agente principal
│   │   ├── __init__.py
│   │   ├── agent.py              # process_message_async
│   │   ├── graph.py              # VERSÃO ANTIGA?
│   │   ├── nodes.py              # VERSÃO ANTIGA?
│   │   └── semantic_memory.py
│   │
│   ├── vps_langgraph/            # LangGraph atual
│   │   ├── __init__.py
│   │   ├── graph.py              # build_agent_graph()
│   │   ├── nodes.py              # node_classify_intent, etc
│   │   ├── state.py              # AgentState
│   │   └── memory.py             # AgentMemory
│   │
│   ├── capabilities/
│   │   ├── __init__.py
│   │   └── registry.py           # CapabilitiesRegistry
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py  # generate_response_sync
│   │   └── agent_identity.py
│   │
│   ├── resource-manager/
│   │   └── manager.py
│   │
│   ├── mcp_server.py             # FastAPI-MCP
│   ├── state.py                  # VERSÃO ANTIGA?
│   ├── memory.py                 # VERSÃO ANTIGA?
│   ├── nodes.py                  # VERSÃO ANTIGA?
│   └── semantic_memory.py        # VERSÃO ANTIGA?
│
├── telegram-bot/
│   └── bot.py                    # Telegram Bot main
│
├── configs/
│   ├── docker-compose.core.yml
│   ├── docker-compose.qdrant.yml
│   └── init-db.sql
│
├── scripts/
│   ├── setup-vps.sh
│   └── self_improve.sh
│
└── tests/
    └── test_graph.py
```

---

## 9. Código Relevante

### 9.1 agent.py - Função Principal

```python
# core/vps_agent/agent.py

async def process_message_async(user_id: str, message: str) -> str:
    """Processa mensagem do usuário através do LangGraph."""
    initial_state: AgentState = {
        "user_id": user_id,
        "user_message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    try:
        graph = build_agent_graph()
        result = await graph.ainvoke(initial_state)
        response = result.get("response", "...")
        return response
    except Exception as e:
        return f"❌ Erro ao processar mensagem: {str(e)}"
```

### 9.2 graph.py - Construção do Grafo

```python
# core/vps_langgraph/graph.py

def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Nós
    workflow.add_node("classify", node_classify_intent)
    workflow.add_node("load_context", node_load_context)
    workflow.add_node("plan", node_plan)
    workflow.add_node("execute", node_execute)
    workflow.add_node("respond", node_generate_response)
    workflow.add_node("save_memory", node_save_memory)
    workflow.add_node("check_capabilities", node_check_capabilities)
    workflow.add_node("self_improve", node_self_improve)
    workflow.add_node("implement_capability", node_implement_capability)
    
    # Fluxos
    workflow.set_entry_point("classify")
    workflow.add_edge("classify", "load_context")
    workflow.add_edge("load_context", "plan")
    
    workflow.add_conditional_edges("plan", lambda s: s.get("intent", "unknown"), {
        "command": "execute",
        "task": "execute",
        "question": "respond",
        "chat": "respond",
        "self_improve": "respond",  # PROBLEMA: não passa por capabilities?
        "unknown": "respond",
    })
    
    # ... mais fluxos
```

### 9.3 nodes.py - Classificação de Intent

```python
# core/vps_langgraph/nodes.py

def node_classify_intent(state: AgentState) -> AgentState:
    """Classifica a intenção do usuário."""
    message = state["user_message"].lower()
    
    # Self-Improvement keywords
    self_improve_keywords = [
        "criar", "crie", "criando", "novo", "novos", "nova",
        "implementar", "implementa", "implementando",
        "agente", "subagente", "mcp", "ferramenta",
        "buscar", "procurar", "monitorar", "pesquisar",
        "integração", "integrar", "conectar",
    ]
    
    if any(kw in message for kw in self_improve_keywords):
        return {
            **state,
            "intent": "self_improve",
            "intent_confidence": 0.90,
        }
    
    # ... outros intents
```

### 9.4 nodes.py - Geração de Resposta

```python
# core/vps_langgraph/nodes.py

def node_generate_response(state: AgentState) -> AgentState:
    """Gera resposta final ao usuário."""
    intent = state.get("intent")
    execution_result = state.get("execution_result")
    
    if execution_result:
        response = execution_result
    elif intent in ["chat", "question"]:
        # Chama LLM
        response = generate_response_sync(...)
    else:
        response = "Comando executado com sucesso! ✅"
    
    return {**state, "response": response}
```

### 9.5 capabilities/registry.py

```python
# core/capabilities/registry.py

from datetime import datetime, timezone  # PROBLEMA: timezone não estava importado

class Capability:
    def __init__(self, name: str, description: str, ...):
        self.name = name
        self.description = description
        self.implemented = implemented
        self.created_at = datetime.now(timezone.utc)  # ERRO: timezone não definido
```

---

## 10. Perguntas Específicas

### 10.1 Correções Imediatas (Hoje)

1. **Por que `result.get("response")` retorna `None` para intent `self_improve`?**
   - O node `respond` está sendo executado?
   - O fluxo condicional está correto?

2. **Qual é a correção mínima para `node_generate_response`?**
   - Adicionar `self_improve` na lista de intents tratados?
   - O fallback está funcionando?

3. **O import de `timezone` em `capabilities/registry.py` foi corrigido corretamente?**
   - Testamos após a correção?

### 10.2 Arquitetura de Código

4. **Qual estrutura de pastas é recomendada?**
   - `vps_langgraph/` ou `vps_agent/` como pasta principal?
   - Arquivos na raiz devem ser movidos?

5. **Como resolver a duplicação de arquivos?**
   - `/opt/vps-agent/core/graph.py` vs `/opt/vps-agent/core/vps_langgraph/graph.py`
   - `/opt/vps-agent/core/nodes.py` vs `/opt/vps-agent/core/vps_langgraph/nodes.py`

6. **Qual padrão de imports usar?**
   - Absolutos: `from vps_langgraph.nodes import node_classify_intent`
   - Relativos: `from .nodes import node_classify_intent`

### 10.3 LangGraph Patterns

7. **Como fazer o grafo retornar todas as chaves do estado?**
   - `result_keys` não inclui `response`
   - É preciso fazer algo especial no último node?

8. **Quando usar nós síncronos vs assíncronos?**
   - `node_classify_intent` é síncrono - está correto?
   - `node_check_capabilities` deveria ser assíncrono?

9. **Como implementar checkpoints no LangGraph?**
   - Salvar estado do grafo periodicamente?
   - Recovery após crash?

### 10.4 Self-Improvement Design

10. **Qual é o fluxo ideal para implementar uma nova capacidade?**
    - Classificar → Resposta inicial → Verificar capabilities → Self-improve → Implementar

11. **O agente deve executar código gerado automaticamente?**
    - Sandbox Docker necessário?
    - Whitelist de comandos seguros?

12. **Como implementar auto-commit no git?**
    - Criar branch automaticamente?
    - Humano aprova antes do merge?

13. **O que fazer em caso de erro na implementação?**
    - Rollback automático?
    - Notificar usuário?

### 10.5 Memória e Contexto

14. **Quando usar PostgreSQL vs Qdrant?**
    - PostgreSQL: fatos, configs, histórico estruturado
    - Qdrant: contexto semântico, embeddings

15. **Como fazer hybrid search (PostgreSQL + Qdrant)?**
    - Query estruturada no PostgreSQL
    - Similarity search no Qdrant
    - Combinar resultados

16. **Qual modelo de embedding usar?**
    - `sentence-transformers/all-MiniLM-L6-v2` (384d, rápido)
    - `sentence-transformers/all-mpnet-base-v2` (768d, mais preciso)

### 10.6 LLM Routing

17. **Como router inteligente entre MiniMax M2.1 e Sonnet 4.5?**
    - Complexidade da tarefa
    - Custo permitido
    - Privacidade necessária

18. **Como implementar fallback automático?**
    - Se modelo primário falha, tentar secundário
    - Log de erros por modelo

19. **Como fazer cache de respostas?**
    - Redis cache para perguntas frequentes
    - TTL configurável
    - Invalidation strategy

### 10.7 Resource Management

20. **Quando subir o Qdrant?**
    - Sempre ligado (mais rápido, mais RAM)
    - Sob demanda (mais RAM livre)

21. **Como gerenciar RAM com 2.4 GB total?**
    - Sempre ligados: PostgreSQL + Redis + LangGraph + Bot = ~650 MB
    - Sob demanda: Qdrant (~400MB) + 1 ferramenta (~300MB) = ~700 MB
    - Deixar ~150 MB de margem

### 10.8 Testing e CI/CD

22. **Como testar o LangGraph localmente?**
    - pytest + fixtures
    - Mock de LLM responses

23. **Por que o CI/CD falha no GitHub Actions?**
    - Module import errors
    - Dependências diferentes
    - Environment variables

24. **Como garantir coverage de testes?**
    - Mínimo 80%?
    - Quais arquivos priorizar?

### 10.9 Segurança

25. **Como sandbox de self-improvement?**
    - Docker container ephemeral
    - Read-only filesystem por padrão
    - Timeout para execuções

26. **Como proteger credenciais?**
    - .env com permissões 600
    - Variáveis de ambiente no systemd
    - Vault para secrets sensíveis

### 10.10 Future Features

27. **Multi-agente: como criar subagentes?**
    - Instâncias isoladas do LangGraph
    - Redis pub/sub para comunicação
    - Compartilhamento de contexto via Redis

28. **Web interface: vale a pena?**
    - Dashboard de status
    - Logs em tempo real
    - Controles de emergência

29. **WhatsApp integration?**
    - Evolution API
    - Mesma lógica do Telegram
    - Canal redundante

30. **Auto-scaling: é possível?**
    - Múltiplas instâncias do agente
    - Redis para estado compartilhado
    - Load balancer (nginx)

---

## 📌 Checklist de Debug

- [ ] Verificar se `timezone` foi corrigido em `capabilities/registry.py`
- [ ] Testar se `node_generate_response` trata `self_improve`
- [ ] Confirmar que grafo passa por `respond` para `self_improve`
- [ ] Limpar `__pycache__` em todas as pastas
- [ ] Verificar logs do bot: `journalctl -u telegram-bot -f`
- [ ] Testar fluxo completo: `python3 /tmp/debug.py`

---

## 🔗 Links Úteis

- **VPS:** SEU_HOST_VPS:22 (root)
- **GitHub:** https://github.com/Guitaitson/AgentVPS
- **Telegram:** @Molttaitbot
- **Stack Overflow:** [perguntas sobre LangGraph](https://python.langchain.com/docs/langgraph)

---

## 📝 Notas para o Modelo Analisador

Por favor, analise este documento e forneça:

1. **Diagnóstico dos problemas**
   - Por que `response` não aparece no resultado?
   - Qual a causa raiz da duplicação de arquivos?

2. **Recomendações de correção**
   - Modificações mínimas necessárias no código
   - Ordem de prioridade das correções

3. **Melhorias arquiteturais**
   - Sugestões para evitar problemas similares
   - Padrões recomendados para LangGraph + self-improving agent

4. **Código de exemplo**
   - Correção para `node_generate_response`
   - Exemplo de fluxo correto para self_improve

5. **Roadmap de implementação**
   - Prioridade de features futuras
   - Riscos antecipados e mitigações

---

**Data de criação:** 2026-02-08
**Modelo destinatário:** Claude Sonnet 4.5 / GPT-4.5 / equivalente
**Status do projeto:** FASE 13 completa, Self-Improvement Agent implementado, testando fluxo
