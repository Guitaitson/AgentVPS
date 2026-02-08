# ADR-001: Estratégia de Memória Multi-Camada

> **Número:** 001  
> **Título:** Estratégia de Memória Multi-Camada  
> **Status:** ACCEPTED  
> **Data:** 2026-02-06  
> **Decisor:** Arquitetura AgentVPS

---

## Contexto

O AgentVPS precisa armazenar diferentes tipos de informação:

1. **Fatos estruturados** — Preferências do usuário, configs, estado do sistema
2. **Memória conversacional** — Histórico de mensagens da conversa atual
3. **Memória semântica** — Embeddings de conversas para busca contextual
4. **Cache transient** — Dados temporários de acesso rápido

VPS tem restrições de RAM (2.4 GB total), então cada tipo de dado deve ir para o storage mais apropriado.

## Decisão

Usar **três camadas de armazenamento** otimizadas para cada caso de uso:

| Camada | Storage | Dados | Tamanho Typical |
|--------|---------|-------|-----------------|
| Estruturada | PostgreSQL | Fatos, configs, estado | ~200 MB |
| Cache | Redis | Sessions, cache, filas | ~60 MB |
| Semântica | Qdrant | Embeddings, contexto | ~500 MB (sob demanda) |

### PostgreSQL (core/vps_langgraph/memory.py)

```python
class AgentMemory:
    """Memória estruturada em PostgreSQL."""
    
    def __init__(self):
        self.conn = psycopg2.connect(POSTGRES_DSN)
    
    def save_fact(self, key: str, value: Any):
        """Salva fato estruturado."""
    
    def get_fact(self, key: str) -> Optional[Any]:
        """Recupera fato."""
    
    def save_lesson(self, lesson: Dict):
        """Salva aprendizado."""
```

### Redis (core/gateway/session_manager.py)

```python
class SessionManager:
    """Gerenciamento de sessões em Redis."""
    
    def create_session(self, user_id: str) -> Session:
        """Cria nova sessão."""
    
    def get_conversation_history(self, session_id: str) -> list:
        """Recupera histórico."""
```

### Qdrant (core/vps_agent/semantic_memory.py)

```python
class SemanticMemory:
    """Memória semântica com Qdrant."""
    
    def store_conversation(self, text: str, metadata: Dict):
        """Armazena embedding de conversa."""
    
    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Busca semântica."""
```

## Consequências

### Positivas

- ✅ **Performance** — Cada dado vai para o storage otimizado
- ✅ **Escalabilidade** — Qdrant escala independentemente
- ✅ **Custo** — Redis/PostgreSQL sempre-ligados; Qdrant sob demanda
- ✅ **Resiliência** — Falha em Qdrant não afeta operação básica

### Negativas

- ❌ **Complexidade** — Três sistemas para manter
- ❌ **Consistência** — Sincronização entre camadas pode ter latência
- ❌ **Operacional** — Mais pontos de falha potenciais

## Implementação

### Arquivos Afetados

| Arquivo | Responsabilidade |
|---------|-----------------|
| `core/vps_langgraph/memory.py` | PostgreSQL |
| `core/gateway/session_manager.py` | Redis |
| `core/vps_agent/semantic_memory.py` | Qdrant |

### Ordem de Implementação

1. PostgreSQL ✅ (completo)
2. Redis ✅ (completo)
3. Qdrant ⏳ (pendente - FASE 3)

## Referências

- [Arquitetura](../ARCHITECTURE.md#-camadas-de-memória)
- [Memory Manager](core/vps_langgraph/memory.py)
- [Session Manager](core/gateway/session_manager.py)
- [Semantic Memory](core/vps_agent/semantic_memory.py)

---

## Histórico de Mudanças

| Data | Versão | Descrição |
|------|--------|-----------|
| 2026-02-06 | 1.0 | Decisão inicial |
