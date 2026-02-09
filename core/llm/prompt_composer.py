"""
Prompt Composer Dinâmico - Composição de prompts baseados em contexto.

Este módulo permite gerar prompts dinâmicos baseados em:
- Contexto do usuário
- Histórico de conversa
- Templates de prompts
- Capacidades do agente
- Estado atual da sessão
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class PromptTemplate:
    """Template de prompt."""

    name: str
    description: str
    template: str
    variables: List[str]


@dataclass
class PromptContext:
    """Contexto para composição de prompt."""

    user_id: str
    session_id: str
    conversation_history: List[Dict[str, Any]]
    current_intent: str
    capabilities: List[str]
    system_state: Dict[str, Any]
    timestamp: datetime


@dataclass
class ComposedPrompt:
    """Prompt composto."""

    system_prompt: str
    user_prompt: str
    context: PromptContext
    template_used: Optional[str]
    metadata: Dict[str, Any]


# Templates de prompts padrão
DEFAULT_TEMPLATES: Dict[str, PromptTemplate] = {
    "chat": PromptTemplate(
        name="chat",
        description="Conversa natural",
        template="""Você é um assistente VPS que responde mensagens de forma natural e amigável.

Contexto:
- Usuário: {user_id}
- Intenção: {intent}
- Histórico recente: {history_summary}

Capacidades disponíveis:
{capabilities}

Responda de forma natural, concisa e útil. Mantenha respostas curtas (1-2 frases) para conversas casuais.""",
        variables=["user_id", "intent", "history_summary", "capabilities"],
    ),
    "command": PromptTemplate(
        name="command",
        description="Execução de comandos do sistema",
        template="""Você é um assistente VPS especializado em executar comandos do sistema.

Contexto:
- Usuário: {user_id}
- Intenção: {intent}
- Capacidades disponíveis: {capabilities}
- Estado do sistema: {system_state}

Execute o comando e retorne o resultado de forma clara e concisa. Se houver erro, explique o que aconteceu.""",
        variables=["user_id", "intent", "capabilities", "system_state"],
    ),
    "task": PromptTemplate(
        name="task",
        description="Execução de tarefas",
        template="""Você é um assistente VPS especializado em executar tarefas.

Contexto:
- Usuário: {user_id}
- Intenção: {intent}
- Capacidades disponíveis: {capabilities}
- Estado do sistema: {system_state}
- Histórico recente: {history_summary}

Execute a tarefa e retorne o resultado de forma clara. Se precisar de mais informações, pergunte ao usuário.""",
        variables=["user_id", "intent", "capabilities", "system_state", "history_summary"],
    ),
    "question": PromptTemplate(
        name="question",
        description="Resposta a perguntas sobre o sistema",
        template="""Você é um assistente VPS especializado em responder perguntas sobre o sistema.

Contexto:
- Usuário: {user_id}
- Intenção: {intent}
- Capacidades disponíveis: {capabilities}
- Estado do sistema: {system_state}
- Histórico recente: {history_summary}

Responda à pergunta de forma clara e precisa. Se não souber a resposta, seja honesto e sugira alternativas.""",
        variables=["user_id", "intent", "capabilities", "system_state", "history_summary"],
    ),
    "self_improve": PromptTemplate(
        name="self_improve",
        description="Auto-melhoria do agente",
        template="""Você é um assistente VPS com capacidade de auto-melhoria.

Contexto:
- Usuário: {user_id}
- Intenção: {intent}
- Capacidades atuais: {capabilities}
- Estado do sistema: {system_state}
- Histórico recente: {history_summary}

Analise a solicitação de melhoria e determine:
1. É possível implementar com as capacidades atuais?
2. Quais componentes precisam ser criados/modificados?
3. Qual é a complexidade estimada?
4. Quais são os riscos?

Retorne um plano detalhado com:
- Análise da solicitação
- Lista de componentes necessários
- Estimativa de complexidade (baixa/média/alta)
- Riscos identificados
- Próximos passos recomendados
- Confirmação se deve prosseguir""",
        variables=["user_id", "intent", "capabilities", "system_state", "history_summary"],
    ),
}


class PromptComposer:
    """Compositor de prompts dinâmicos."""

    def __init__(self, templates: Optional[Dict[str, PromptTemplate]] = None):
        self.templates = templates or DEFAULT_TEMPLATES.copy()

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Retorna um template pelo nome."""
        return self.templates.get(name)

    def add_template(self, template: PromptTemplate) -> None:
        """Adiciona um novo template."""
        self.templates[template.name] = template

    def remove_template(self, name: str) -> None:
        """Remove um template."""
        if name in self.templates:
            del self.templates[name]

    def _summarize_history(self, history: List[Dict[str, Any]], max_items: int = 5) -> str:
        """Gera um resumo do histórico de conversa."""
        if not history:
            return "Nenhum histórico recente"

        recent = history[-max_items:]
        summary_parts = []

        for msg in recent:
            intent = msg.get("intent", "desconhecido")
            content = msg.get("user_message", "")[:50]
            summary_parts.append(f"- {intent}: {content}")

        return "\n".join(summary_parts)

    def _format_capabilities(self, capabilities: List[str]) -> str:
        """Formata a lista de capacidades."""
        if not capabilities:
            return "Nenhuma capacidade disponível"

        return ", ".join(capabilities)

    def compose(
        self,
        template_name: str,
        context: PromptContext,
        additional_vars: Optional[Dict[str, Any]] = None,
    ) -> ComposedPrompt:
        """
        Compõe um prompt baseado em um template e contexto.

        Args:
            template_name: Nome do template a usar
            context: Contexto da conversa
            additional_vars: Variáveis adicionais

        Returns:
            Prompt composto
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' não encontrado")

        # Variáveis base do template
        variables = {
            "user_id": context.user_id,
            "session_id": context.session_id,
            "intent": context.current_intent,
            "history_summary": self._summarize_history(context.conversation_history),
            "capabilities": self._format_capabilities(context.capabilities),
            "system_state": str(context.system_state),
        }

        # Adicionar variáveis adicionais
        if additional_vars:
            variables.update(additional_vars)

        # Substituir variáveis no template
        try:
            system_prompt = template.template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Variável não encontrada no template: {e}")

        # Prompt do usuário é a mensagem atual
        user_prompt = context.system_state.get("current_message", "")

        return ComposedPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context=context,
            template_used=template_name,
            metadata={
                "composed_at": datetime.now().isoformat(),
                "variables_used": list(variables.keys()),
            },
        )

    def compose_for_intent(
        self,
        intent: str,
        context: PromptContext,
    ) -> ComposedPrompt:
        """
        Compõe um prompt baseado na intenção do usuário.

        Args:
            intent: Intenção classificada
            context: Contexto da conversa

        Returns:
            Prompt composto
        """
        # Mapeamento de intenção para template
        intent_to_template = {
            "chat": "chat",
            "command": "command",
            "task": "task",
            "question": "question",
            "self_improve": "self_improve",
        }

        template_name = intent_to_template.get(intent, "chat")

        return self.compose(template_name, context)

    def compose_with_context_awareness(
        self,
        context: PromptContext,
        max_history_items: int = 10,
    ) -> ComposedPrompt:
        """
        Compõe um prompt com consciência de contexto expandida.

        Args:
            context: Contexto da conversa
            max_history_items: Máximo de itens do histórico

        Returns:
            Prompt composto com contexto expandido
        """
        # Resumo do histórico expandido
        history_summary = self._summarize_history(context.conversation_history, max_history_items)

        # Adicionar consciência de contexto ao template
        additional_vars = {
            "extended_history": history_summary,
            "context_awareness": "Você tem acesso ao histórico completo da conversa.",
        }

        return self.compose(context.current_intent, context, additional_vars)

    def optimize_for_token_limit(
        self,
        prompt: ComposedPrompt,
        max_tokens: int = 4000,
    ) -> ComposedPrompt:
        """
        Otimiza o prompt para respeitar limite de tokens.

        Args:
            prompt: Prompt composto
            max_tokens: Máximo de tokens permitido

        Returns:
            Prompt otimizado
        """
        # Estimativa aproximada de tokens (4 caracteres ≈ 1 token)
        estimated_tokens = len(prompt.system_prompt) // 4 + len(prompt.user_prompt) // 4

        if estimated_tokens > max_tokens:
            # Truncar histórico se necessário
            max_history_items = max(
                1, (max_tokens - 1000) // 100
            )  # Reservar 1000 tokens para system + user
            history_summary = self._summarize_history(
                prompt.context.conversation_history, max_history_items
            )

            # Recompor com histórico resumido
            additional_vars = {
                "truncated_history": history_summary,
                "optimization_note": f"Histórico truncado para {max_history_items} mensagens devido ao limite de tokens.",
            }

            return self.compose(prompt.context.current_intent, prompt.context, additional_vars)

        return prompt


# Funções de conveniência
def create_context(
    user_id: str,
    session_id: str,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    current_intent: str = "chat",
    capabilities: Optional[List[str]] = None,
    system_state: Optional[Dict[str, Any]] = None,
) -> PromptContext:
    """Cria um contexto de prompt."""
    from datetime import datetime

    return PromptContext(
        user_id=user_id,
        session_id=session_id,
        conversation_history=conversation_history or [],
        current_intent=current_intent,
        capabilities=capabilities or [],
        system_state=system_state or {},
        timestamp=datetime.now(timezone.utc),
    )


def get_default_composer() -> PromptComposer:
    """Retorna o compositor padrão."""
    return PromptComposer()


# Testes
if __name__ == "__main__":
    # Teste básico
    composer = get_default_composer()

    context = create_context(
        user_id="test_user",
        session_id="test_session",
        conversation_history=[
            {"intent": "chat", "user_message": "oi", "response": "Olá!"},
            {"intent": "question", "user_message": "qual é a capital?", "response": "Brasília"},
        ],
        current_intent="question",
        capabilities=["ram", "containers", "status"],
        system_state={"current_message": "quanto de RAM está disponível?"},
    )

    prompt = composer.compose_for_intent("question", context)

    print("=== Prompt Composto ===")
    print(f"Template: {prompt.template_used}")
    print(f"\nSystem Prompt:\n{prompt.system_prompt}")
    print(f"\nUser Prompt:\n{prompt.user_prompt}")
    print(f"\nMetadata:\n{prompt.metadata}")
