# ADR-002: Abstração de Providers LLM

> **Número:** 002  
> **Título:** Abstração de Providers LLM com Strategy Pattern  
> **Status:** ACCEPTED  
> **Data:** 2026-02-06  
> **Decisor:** Arquitetura AgentVPS

---

## Contexto

O AgentVPS usa LLMs para:
1. **Classificação de intents** — Qual o tipo de mensagem?
2. **Geração de resposta** — O que responder ao usuário?
3. **Self-improvement** — Auto-análise e evolução

Diferentes provedores têm:
- **Preços diferentes** — OpenRouter (gratuito) vs Anthropic (caro)
- **Qualidades diferentes** — Sonnet 4.5 (melhor) vs MiniMax M2.1 (bom)
- **Disponibilidade diferente** — Alguns falham mais

Precisamos trocar de provider sem alterar código.

## Decisão

Usar **Strategy Pattern** com interface abstrata:

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Interface abstrata para providers LLM."""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Gera resposta."""
    
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Gera embedding."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do provider."""
```

### Providers Implementados

| Provider | Uso | Custo |
|----------|-----|-------|
| OpenRouter (MiniMax M2.1) | **Default** | Gratuito |
| OpenRouter (Claude 3.5) | Fallback | $3/1M tokens |
| Anthropic (Claude 3.5) | Alta qualidade | $3/1M tokens |

### Implementação

```python
# core/llm/provider.py
class LLMProvider(ABC):
    """Interface base para providers."""
    
    async def chat(self, messages: List[ChatMessage]) -> ChatResponse:
        """Método padrão de chat."""
        prompt = self._messages_to_prompt(messages)
        return await self.generate(prompt, **kwargs)


# core/llm/openrouter_client.py
class OpenRouterProvider(LLMProvider):
    """Provider via OpenRouter API."""
    
    SUPPORTED_MODELS = {
        "minimax/minimax-m2.1": {"cost": "free", "quality": "good"},
        "anthropic/claude-3.5-sonnet": {"cost": "$3/1M", "quality": "excellent"},
    }
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Usa httpx para chamada HTTP."""
```

## Consequências

### Positivas

- ✅ **Swap fácil** — Trocar provider em 1 linha de config
- ✅ **Fallback automático** — Se um falha, tenta outro
- ✅ **Testes** — Mock provider para testes rápidos
- ✅ **Extensibilidade** — Novo provider em ~100 linhas

### Negativas

- ❌ **Overhead** — Abstração adiciona uma camada
- ❌ **Features diferentes** — Cada provider tem capacidades únicas
- ❌ **Cache** — Não pode cachear entre providers

## Implementação

### Arquivos Afetados

| Arquivo | Responsabilidade |
|---------|-----------------|
| `core/llm/provider.py` | Interface abstrata |
| `core/llm/openrouter_client.py` | OpenRouter implementation |
| `core/llm/agent_identity.py` | Prompt de identidade |

### Configuração

```bash
# .env
LLM_PROVIDER=openrouter
LLM_MODEL=minimax/minimax-m2.1
LLM_FALLBACK=anthropic/claude-3.5-sonnet
```

## Referências

- [Arquitetura LLM](../ARCHITECTURE.md#-llm)
- [Provider Interface](core/llm/provider.py)
- [OpenRouter Client](core/llm/openrouter_client.py)
- [Testes](tests/test_llm_provider.py)

---

## Histórico de Mudanças

| Data | Versão | Descrição |
|------|--------|-----------|
| 2026-02-06 | 1.0 | Decisão inicial |
