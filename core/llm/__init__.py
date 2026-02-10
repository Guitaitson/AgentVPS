"""
LLM Module - Composição de prompts dinâmicos e abstração de provedores.

Este módulo fornece funcionalidades para:
- Composição de prompts baseados em contexto, histórico e templates
- Abstração para múltiplos provedores de LLM (OpenAI, Anthropic, etc)
"""

from .prompt_composer import (
    ComposedPrompt,
    PromptComposer,
    PromptContext,
    PromptTemplate,
    create_context,
    get_default_composer,
)
from .provider import (
    AnthropicProvider,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMProviderFactory,
    LLMProviderType,
    LLMResponse,
    OpenAIProvider,
    create_anthropic_config,
    create_openai_config,
)
from .unified_provider import (
    UnifiedLLMProvider,
    IntentClassification,
    get_llm_provider,
    classify_intent_with_llm,
)

__all__ = [
    # Prompt Composer
    "PromptComposer",
    "PromptTemplate",
    "PromptContext",
    "ComposedPrompt",
    "create_context",
    "get_default_composer",
    # LLM Provider
    "LLMProviderType",
    "LLMMessage",
    "LLMResponse",
    "LLMConfig",
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "LLMProviderFactory",
    "create_openai_config",
    "create_anthropic_config",
    # Unified Provider (novo)
    "UnifiedLLMProvider",
    "IntentClassification",
    "get_llm_provider",
    "classify_intent_with_llm",
]
