"""
ReAct Node — O cérebro inteligente do agente.

Usa function calling para que o LLM decida qual tool usar.
Substitui: node_classify_intent + node_plan + interpretação do shell_exec.

Este é o núcleo da mudança de "botões pré-codificados" para "inteligência real".
"""

import structlog

from ..skills.registry import get_skill_registry
from .state import AgentState

logger = structlog.get_logger()

SYSTEM_PROMPT = """Você é o VPS-Agent, um assistente autônomo rodando em um servidor VPS Ubuntu.

Você tem acesso a ferramentas (tools) para executar ações no servidor. Use-as quando necessário.

Regras:
1. Para perguntas sobre o servidor (RAM, disco, processos, Docker, arquivos), USE uma tool.
2. Para perguntas gerais de conhecimento, responda diretamente SEM usar tools.
3. Para buscas na internet, use a tool web_search.
4. Para ler/criar/editar arquivos, use a tool file_manager.
5. Sempre responda em português brasileiro de forma concisa e natural.
6. Quando usar uma tool, interprete o resultado e responda de forma conversacional.

Exemplos de quando usar tools:
- "quanta RAM?" → use get_ram
- "tem docker?" → use shell_exec com command="which docker"
- "liste os containers" → use list_containers
- "leia o arquivo X" → use file_manager com operation="read"
- "busque sobre Y" → use web_search com query="Y"

Exemplos de quando NÃO usar tools:
- "o que é Python?" → responda diretamente
- "olá, tudo bem?" → responda diretamente
- "me ajude com um código" → responda diretamente
"""


async def node_react(state: AgentState) -> AgentState:
    """
    Nó ReAct: LLM decide se usa tool ou responde diretamente.

    Este nó substitui node_classify_intent + node_plan em uma única chamada LLM.
    O LLM recebe a lista de tools e decide qual usar (ou nenhuma).
    """
    from ..llm.unified_provider import get_llm_provider

    user_message = state.get("user_message", "")
    conversation_history = state.get("conversation_history", [])

    registry = get_skill_registry()
    tools = registry.list_tool_schemas()

    logger.info(
        "react_start",
        message=user_message[:80],
        tools_count=len(tools),
    )

    provider = get_llm_provider()

    # Primeira chamada: LLM decide se usa tool ou responde
    response = await provider.generate(
        user_message=user_message,
        system_prompt=SYSTEM_PROMPT,
        history=conversation_history[-5:] if conversation_history else None,
        tools=tools,
    )

    if not response.success:
        logger.error("react_llm_failed", error=response.error)
        return {
            **state,
            "intent": "chat",
            "response": "Desculpe, tive um problema ao processar sua mensagem. Tente novamente.",
        }

    # Se LLM retornou tool_calls
    if response.tool_calls:
        tool_call = response.tool_calls[0]  # Processar primeira tool
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("arguments", {})

        logger.info(
            "react_tool_call",
            tool=tool_name,
            args=tool_args,
        )

        return {
            **state,
            "intent": "task",
            "action_required": True,
            "tool_suggestion": tool_name,
            "plan": [{"type": "skill", "action": tool_name, "args": tool_args}],
            "current_step": 0,
            "tools_needed": [tool_name],
            "execution_result": None,  # Será preenchido pelo node_execute
        }

    # Se LLM respondeu diretamente
    logger.info("react_direct_response")
    return {
        **state,
        "intent": "chat",
        "action_required": False,
        "response": response.content,
        "plan": None,
    }


async def node_format_response(state: AgentState) -> AgentState:
    """
    Após execução da tool, envia resultado ao LLM para formatação.

    O skill retorna output raw (ex: "1.2Gi / 4.0Gi").
    O LLM interpreta e gera resposta conversacional.
    """
    from ..llm.unified_provider import get_llm_provider

    execution_result = state.get("execution_result", "")
    user_message = state.get("user_message", "")
    tool_name = state.get("tool_suggestion", "")

    if not execution_result:
        return state

    provider = get_llm_provider()

    format_prompt = f"""O usuário perguntou: "{user_message}"

Você usou a ferramenta '{tool_name}' e obteve este resultado:

{execution_result}

Responda a pergunta do usuário de forma natural e conversacional em português,
interpretando o resultado acima. Seja conciso."""

    response = await provider.generate(
        user_message=format_prompt,
        system_prompt="Responda de forma concisa e natural em português brasileiro.",
    )

    if response.success and response.content:
        logger.info("react_response_formatted", tool=tool_name)
        return {**state, "response": response.content}

    # Fallback: usar resultado raw
    logger.warning("react_response_format_failed", tool=tool_name)
    return {**state, "response": execution_result}


# Alias para compatibilidade com código antigo
def route_after_react(state: AgentState) -> str:
    """Roteia após o nó react - decide próximo passo."""
    if state.get("action_required"):
        return "security_check"
    return "respond"
