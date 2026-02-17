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

MAX_REACT_STEPS = 5  # Máximo de iterações tool→observation→thought


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

## Suas Ferramentas Reais (disponiveis agora)
{skills_section}

## Regras ReAct (OBRIGATORIO — SIGA SEMPRE)
1. Voce TEM acesso direto ao servidor Ubuntu. Use shell_exec para QUALQUER verificacao do sistema.
2. ACAO IMEDIATA: Se o usuario pede algo que voce pode fazer, FACA. Nao pergunte. Nao peca confirmacao para acoes seguras.
3. Se uma ferramenta falhar, TENTE de outra forma. Nunca diga "nao consigo" sem ter tentado pelo menos 2 abordagens diferentes.
4. Use web_search para buscar informacoes na internet. Se web_search falhar, tente shell_exec com curl.
5. Use file_manager para ler, criar ou editar arquivos no servidor.
6. Sempre responda em portugues brasileiro de forma concisa e natural.
7. Quando usar uma tool, INTERPRETE o resultado. Nao copie output cru — explique o que significa para o usuario.
8. Para perguntas gerais de conhecimento (sem relacao com o servidor), responda diretamente SEM tools.
9. Voce e o VPS-Agent. Nunca diga que e "um modelo de linguagem".
10. Se o usuario referenciar algo da conversa anterior, USE o historico para responder com contexto.

## PROIBIDO (comportamento que NUNCA deve acontecer)
- Perguntar "Voce gostaria que eu verificasse..." quando a acao e clara e segura
- Responder com "Posso ajudar com..." ou "Preciso de mais detalhes" em vez de AGIR
- Dizer "nao tenho acesso" quando voce TEM shell_exec, web_search, file_manager
- Dizer "nao consigo" sem ter tentado pelo menos uma ferramenta
- Truncar output grande sem explicar (use head/tail se o output for extenso)
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

    # T4: Consultar learnings relevantes antes de responder
    try:
        from .learnings import learnings_manager

        recent_lessons = learnings_manager.search_learnings(user_message[:80], limit=3)
        if recent_lessons:
            lessons_text = "\n".join([f"- {lesson['lesson']}" for lesson in recent_lessons])
            system_prompt += f"\n\n## Licoes Aprendidas (evite repetir estes erros)\n{lessons_text}"
            logger.info("react_learnings_injected", count=len(recent_lessons))
    except Exception as e:
        logger.debug("react_learnings_skip", error=str(e))

    # Construir mensagens para multi-turn
    messages = [{"role": "system", "content": system_prompt}]

    # Adicionar histórico de conversa (SEM timestamp no content — evita LLM repetir timestamps)
    # Timestamps vão em bloco separado no system prompt para contexto temporal
    temporal_entries = []
    if conversation_history:
        for i, msg in enumerate(conversation_history[-20:]):
            ts = msg.get("timestamp", "")
            content = msg.get("content", "")
            role = msg.get("role", "user")
            messages.append({"role": role, "content": content})
            if ts:
                temporal_entries.append(f"msg{i + 1}({role}): {ts}")

    # Adicionar contexto temporal discreto ao system prompt (não polui mensagens)
    if temporal_entries:
        temporal_block = "\n## Contexto Temporal da Conversa\n" + ", ".join(temporal_entries[-5:])
        messages[0]["content"] += temporal_block

    # T4: Detectar feedback negativo do usuário e registrar learning
    negative_indicators = [
        "errado",
        "nao eh",
        "não é",
        "tem certeza",
        "incorreto",
        "wrong",
        "nao foi isso",
        "não foi isso",
        "ta errado",
        "tá errado",
        "voce errou",
        "você errou",
    ]
    msg_lower = user_message.lower()
    if any(ind in msg_lower for ind in negative_indicators) and conversation_history:
        try:
            from .learnings import learnings_manager

            last_assistant = [m for m in conversation_history if m.get("role") == "assistant"]
            if last_assistant:
                prev_response = last_assistant[-1].get("content", "")[:200]
                learnings_manager.add_learning(
                    category="user_feedback",
                    trigger=user_message[:200],
                    lesson=f"Resposta rejeitada pelo usuario. Resposta errada: '{prev_response}'. Correcao do usuario: '{user_message[:200]}'",
                    success=False,
                    metadata={"user_id": state.get("user_id", "unknown")},
                )
                logger.info("react_user_correction_captured", trigger=user_message[:50])
        except Exception as e:
            logger.debug("react_user_correction_skip", error=str(e))

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

    # Se nenhum tool foi executado, skip
    if execution_result is None and not tool_name:
        return state

    # Se tool foi executado mas resultado é vazio, informar ao LLM
    if not execution_result and tool_name:
        execution_result = (
            f"O comando '{tool_name}' foi executado mas não retornou output (saída vazia)."
        )

    provider = get_llm_provider()

    # Usar identidade condensada para que o LLM NUNCA esqueça que é o VPS-Agent
    from ..llm.agent_identity import get_identity_prompt_condensed

    identity_prompt = get_identity_prompt_condensed()

    format_prompt = f"""O usuário perguntou: "{user_message}"

Você usou a ferramenta '{tool_name}' e obteve este resultado:

{execution_result}

Responda a pergunta do usuário de forma natural e conversacional em português,
interpretando o resultado acima. Seja conciso."""

    response = await provider.generate(
        user_message=format_prompt,
        system_prompt=identity_prompt,
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
