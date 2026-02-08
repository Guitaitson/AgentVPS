"""
LLM Module - Composição de prompts dinâmicos.

Este módulo fornece funcionalidades para composição de prompts
baseados em contexto, histórico e templates.
"""

from .prompt_composer import (
    PromptComposer,
    PromptTemplate,
    PromptContext,
    ComposedPrompt,
    create_context,
    get_default_composer,
)

__all__ = [
    "PromptComposer",
    "PromptTemplate",
    "PromptContext",
    "ComposedPrompt",
    "create_context",
    "get_default_composer",
]
