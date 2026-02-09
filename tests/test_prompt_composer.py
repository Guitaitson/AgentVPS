"""
Testes para o Prompt Composer Dinâmico.
"""

import pytest

from core.llm.prompt_composer import (
    PromptTemplate,
    create_context,
    get_default_composer,
)


class TestPromptComposer:
    """Testes para o PromptComposer."""

    def test_composer_initialization(self):
        """Testa se o compositor pode ser inicializado."""
        composer = get_default_composer()
        assert composer is not None
        assert len(composer.templates) > 0

    def test_get_template(self):
        """Testa recuperação de templates."""
        composer = get_default_composer()

        template = composer.get_template("chat")
        assert template is not None
        assert template.name == "chat"
        assert "user_id" in template.variables

        # Template inexistente
        template = composer.get_template("inexistente")
        assert template is None

    def test_add_remove_template(self):
        """Testa adição e remoção de templates."""
        composer = get_default_composer()

        # Adicionar template
        new_template = PromptTemplate(
            name="custom",
            description="Template customizado",
            template="Custom template: {var}",
            variables=["var"]
        )
        composer.add_template(new_template)
        assert "custom" in composer.templates

        # Remover template
        composer.remove_template("custom")
        assert "custom" not in composer.templates

    def test_summarize_history(self):
        """Testa resumo do histórico."""
        composer = get_default_composer()

        history = [
            {"intent": "chat", "user_message": "oi", "response": "Olá!"},
            {"intent": "question", "user_message": "qual e a capital?", "response": "Brasilia"},
            {"intent": "task", "user_message": "liste containers", "response": "2 containers"},
        ]

        summary = composer._summarize_history(history, max_items=5)
        assert "chat" in summary
        assert "oi" in summary
        assert "question" in summary
        assert "task" in summary
        assert "liste containers" in summary

    def test_format_capabilities(self):
        """Testa formatação de capacidades."""
        composer = get_default_composer()

        caps = ["ram", "containers", "status", "deploy"]
        formatted = composer._format_capabilities(caps)

        assert "ram" in formatted
        assert "containers" in formatted
        assert formatted == "ram, containers, status, deploy"

    def test_compose(self):
        """Testa composição de prompts."""
        composer = get_default_composer()

        context = create_context(
            user_id="test_user",
            session_id="test_session",
            conversation_history=[
                {"intent": "chat", "user_message": "oi", "response": "Olá!"},
            ],
            current_intent="question",
            capabilities=["ram", "containers"],
            system_state={"current_message": "quanto de RAM?"},
        )

        prompt = composer.compose_for_intent("question", context)

        assert prompt.template_used == "question"
        assert "test_user" in prompt.system_prompt
        assert "quanto de RAM?" in prompt.user_prompt
        assert "ram" in prompt.system_prompt
        assert "containers" in prompt.system_prompt

    def test_compose_with_context_awareness(self):
        """Testa composição com consciência de contexto."""
        composer = get_default_composer()

        context = create_context(
            user_id="test_user",
            session_id="test_session",
            conversation_history=[
                {"intent": "chat", "user_message": "oi", "response": "Olá!"},
                {"intent": "question", "user_message": "qual e a capital?", "response": "Brasilia"},
                {"intent": "task", "user_message": "crie arquivo", "response": "Arquivo criado"},
            ],
            current_intent="task",
            capabilities=["ram", "containers"],
        )

        prompt = composer.compose_with_context_awareness(context, max_history_items=10)

        assert prompt.template_used == "task"
        assert prompt.context.user_id == "test_user"
        assert "extended_history" in prompt.metadata.get("variables_used", [])

    def test_optimize_for_token_limit(self):
        """Testa otimização para limite de tokens."""
        composer = get_default_composer()

        context = create_context(
            user_id="test_user",
            session_id="test_session",
            conversation_history=[
                {"intent": "chat", "user_message": "oi", "response": "Olá!"},
            ] * 20,  # Histórico longo
            current_intent="chat",
            capabilities=["ram", "containers"],
        )

        # Criar um prompt com histórico longo
        prompt = composer.compose_for_intent("chat", context)

        # Otimizar para limite de tokens
        optimized = composer.optimize_for_token_limit(prompt, max_tokens=100)

        # Verificar que o prompt foi otimizado
        assert optimized is not None
        assert optimized.template_used == "chat"
        assert optimized.context.user_id == "test_user"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
