"""
ReAct Node — O cérebro inteligente do agente.

Usa function calling com loop iterativo para que o LLM:
1. Decida qual tool usar
2. Observe o resultado
3. Decida se precisa de outra tool ou se pode responder

Substitui: node_classify_intent + node_plan + interpretação do shell_exec.
Este é o núcleo da mudança de "botões pré-codificados" para "inteligência real".
"""

import json

import structlog

from ..skills.registry import get_skill_registry
from .state import AgentState

logger = structlog.get_logger()

MAX_REACT_STEPS = 3  # Máximo de iterações tool→observation→thought


def build_react_system_prompt() -> str:
    """Constrói system prompt dinâmico com identidade + skills reais."""
    from ..llm.agent_identity import get_full_system_prompt

    identity = get_full_system_prompt()

    # Listar skills reais do registry
    registry = get_skill_registry()
    skills_info = []
    for skill_data in registry.list_skills():
        name = skill_data["name"]
        desc = skill_data["description"]
        level = skill_data["security_level"]
        skills_info.append(f"- **{name}** ({level}): {desc}")

    skills_section = "\n".join(skills_info) if skills_info else "Nenhum skill registrado."

    return f"""{identity}

## Suas Ferramentas Reais (disponíveis agora)
{skills_section}

## Regras ReAct (IMPORTANTE)
1. Voce TEM acesso direto ao servidor Ubuntu. Use shell_exec para qualquer verificacao.
2. Para verificar se algo esta instalado: use shell_exec com "which <programa>" ou "<programa> --version".
3. Se uma ferramenta falhar, TENTE de outra forma. Nunca diga "nao consigo" sem ter tentado.
4. Use web_search para buscar informacoes na internet.
5. Use file_manager para ler, criar ou editar arquivos no servidor.
6. Sempre responda em portugues brasileiro de forma concisa e natural.
7. Quando usar uma tool, interprete o resultado e responda de forma conversacional.
8. Para perguntas gerais de conhecimento (sem relacao com o servidor), responda diretamente SEM tools.
9. Nunca diga que voce e "um modelo de linguagem". Voce e o VPS-Agent.
10. Se o usuario referenciar algo da conversa anterior, USE o historico para responder.
"""


async def node_react(state: AgentState) -> AgentState:
    """
    Nó ReAct com loop iterativo: Thought → Action → Observation → Thought.

    - Skills SAFE: executados inline, resultado alimentado de volta ao LLM.
    - Skills MODERATE/DANGEROUS: roteados para security_check → execute (path do grafo).
    - Máximo MAX_REACT_STEPS iterações para evitar loops infinitos.
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
    system_prompt = build_react_system_prompt()

    # Construir mensagens para multi-turn
    messages = [{"role": "system", "content": system_prompt}]

    # Adicionar histórico de conversa
    if conversation_history:
        for msg in conversation_history[-5:]:
            messages.append(
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                }
            )

    # Mensagem atual do usuário
    messages.append({"role": "user", "content": user_message})

    last_result = None

    for step in range(MAX_REACT_STEPS):
        response = await provider.generate(messages=messages, tools=tools)

        if not response.success:
            logger.error("react_llm_failed", error=response.error, step=step)
            return {
                **state,
                "intent": "chat",
                "response": "Desculpe, tive um problema ao processar sua mensagem. Tente novamente.",
            }

        # Se LLM respondeu diretamente (sem tool call) → pronto
        if not response.tool_calls:
            logger.info("react_direct_response", step=step)
            return {
                **state,
                "intent": "chat",
                "action_required": False,
                "response": response.content,
                "plan": None,
            }

        # LLM quer usar uma tool
        tool_call = response.tool_calls[0]
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("arguments", {})
        call_id = tool_call.get("id", f"call_{step}")

        logger.info("react_tool_call", tool=tool_name, args=str(tool_args)[:200], step=step)

        # Verificar nível de segurança
        security_level = registry.get_security_level(tool_name, tool_args)

        # MODERATE/DANGEROUS → rotear para security_check (path do grafo)
        if security_level in ("moderate", "dangerous", "forbidden"):
            logger.info(
                "react_route_to_graph",
                tool=tool_name,
                security=security_level,
                step=step,
            )
            return {
                **state,
                "intent": "task",
                "action_required": True,
                "tool_suggestion": tool_name,
                "plan": [{"type": "skill", "action": tool_name, "args": tool_args}],
                "current_step": 0,
                "tools_needed": [tool_name],
                "execution_result": None,
            }

        # SAFE → executar inline e alimentar resultado ao LLM
        try:
            result = await registry.execute_skill(tool_name, tool_args)
            last_result = str(result)
        except Exception as e:
            last_result = f"Erro ao executar {tool_name}: {e}"
            logger.error("react_inline_error", tool=tool_name, error=str(e), step=step)

        logger.info(
            "react_inline_executed",
            tool=tool_name,
            result_preview=last_result[:200] if last_result else "",
            step=step,
        )

        # Adicionar tool call + resultado ao contexto para próxima iteração
        # Formato OpenRouter/OpenAI para multi-turn tool calling
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args)
                            if isinstance(tool_args, dict)
                            else str(tool_args),
                        },
                    }
                ],
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": last_result,
            }
        )

    # Esgotou MAX_REACT_STEPS — retornar último resultado formatado
    logger.warning("react_max_steps_reached", steps=MAX_REACT_STEPS)
    return {
        **state,
        "intent": "task",
        "action_required": False,
        "response": last_result or "Executei múltiplas ações mas não consegui uma resposta final.",
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
