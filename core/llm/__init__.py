"""
LLM Module - Composição de prompts dinâmicos e abstração de provedores.

Este módulo fornece funcionalidades para:
- Composição de prompts baseados em contexto, histórico e templates
- Abstração para múltiplos provedores de LLM (OpenAI, Anthropic, etc)
"""

from .prompt_composer import (
    PromptComposer,
    PromptTemplate,
    PromptContext,
    ComposedPrompt,
    create_context,
    get_default_composer,
)

from .provider import (
    LLMProviderType,
    LLMMessage,
    LLMResponse,
    LLMConfig,
    LLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    LLMProviderFactory,
    create_openai_config,
    create_anthropic_config,
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
]
