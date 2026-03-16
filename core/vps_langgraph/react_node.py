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

from ..catalog.external_skill_contracts import get_external_skill_contract
from ..integrations import (
    assess_specialist_health,
    detect_external_skill,
    emit_health_failure_progress,
    format_specialist_health_failure,
    select_codex_execution_mode,
    wants_raw_specialist_output,
)
from ..orchestration import RuntimeExecutionRequest, RuntimeProtocol, get_runtime_router
from ..progress import emit_progress
from ..skills.registry import get_skill_registry
from .state import AgentState

logger = structlog.get_logger()

MAX_REACT_STEPS = 5  # Máximo de iterações tool→observation→thought


def _render_codex_response(payload: dict, *, heading: str | None = None) -> str:
    lines = [heading, ""] if heading else []
    answer = str(payload.get("answer") or payload.get("summary") or "").strip()
    if answer:
        lines.append(answer)
    facts = payload.get("facts") or []
    if facts:
        lines.append("")
        lines.append("Pontos principais:")
        for fact in facts[:4]:
            lines.append(f"- {fact}")
    unresolved = payload.get("unresolved_items") or []
    if unresolved:
        lines.append("")
        lines.append("Pendencias:")
        for item in unresolved[:3]:
            lines.append(f"- {item}")
    if payload.get("requires_human_approval"):
        lines.append("")
        lines.append("Esta resposta pede aprovacao humana antes de qualquer acao sensivel.")
    return "\n".join(lines).strip()


def _format_specialist_contract_mismatch(
    specialist_name: str,
    *,
    codex_available: bool,
) -> str:
    specialist_label = {
        "fleetintel_analyst": "FleetIntel Analyst",
        "fleetintel_orchestrator": "FleetIntel Orchestrator",
        "brazilcnpj": "BrazilCNPJ",
    }.get(specialist_name, specialist_name)
    if codex_available:
        return (
            f"{specialist_label}\n\n"
            "A consulta trouxe working data tecnica, mas nao consegui consolidar isso em resposta executiva agora. "
            "Nao vou despejar JSON cru aqui. Posso tentar novamente depois ou mostrar o payload se voce pedir explicitamente."
        )
    return (
        f"{specialist_label}\n\n"
        "Esta consulta pede sintese executiva do especialista externo, mas o sintetizador Codex nao esta disponivel no momento. "
        "Nao vou despejar JSON cru aqui. Posso tentar novamente depois ou mostrar o payload se voce pedir explicitamente."
    )


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

    specialist_name = detect_external_skill(user_message)
    if specialist_name:
        specialist = registry.get(specialist_name)
        if specialist:
            logger.info("react_external_shortcut", skill=specialist_name)
            try:
                router = get_runtime_router()
                contract = get_external_skill_contract(specialist_name)
                health = await assess_specialist_health(user_message, specialist_name)
                if not health.healthy:
                    await emit_health_failure_progress(health)
                    return {
                        **state,
                        "intent": "task",
                        "action_required": False,
                        "response": format_specialist_health_failure(health),
                        "plan": None,
                    }
                codex_mode = select_codex_execution_mode(user_message, specialist_name)
                raw_requested = wants_raw_specialist_output(user_message)
                has_codex = router.has_protocol(RuntimeProtocol.CODEX_OPERATOR)
                if has_codex and codex_mode == "codex_operator":
                    if specialist_name.startswith("fleetintel"):
                        await emit_progress("external_call", server="fleetintel", status="start")
                    elif specialist_name == "brazilcnpj":
                        await emit_progress("external_call", server="brazilcnpj", status="start")
                    if contract is not None:
                        await emit_progress(
                            "routing",
                            server="codex_operator",
                            specialist=specialist_name,
                            response_owner=contract.response_owner,
                            execution_mode=contract.execution_mode,
                        )
                        codex_result = await router.dispatch(
                            RuntimeExecutionRequest(
                                action=specialist_name,
                                args={
                                    "query": user_message,
                                    "specialist_name": specialist_name,
                                },
                                user_id=state.get("user_id", ""),
                                context={
                                    "codex_mode": "operator",
                                    "conversation_history": conversation_history[-6:],
                                    "user_message": user_message,
                                    "specialist_name": specialist_name,
                                    "external_skill_contract": {
                                        "external_name": contract.external_name,
                                        "version": contract.version,
                                        "execution_mode": contract.execution_mode,
                                        "response_owner": contract.response_owner,
                                        "raw_output_policy": contract.raw_output_policy,
                                        "description": contract.description,
                                    }
                                    if contract
                                    else None,
                                },
                                context_keys=[
                                    "conversation_history",
                                    "user_message",
                                    "specialist_name",
                                    "external_skill_contract",
                                ],
                                preferred_protocol=RuntimeProtocol.CODEX_OPERATOR,
                            )
                        )
                        if codex_result.success and isinstance(codex_result.output, dict):
                            return {
                                **state,
                                "intent": "task",
                                "action_required": False,
                                "response": _render_codex_response(
                                    codex_result.output,
                                    heading="Operador Codex",
                                ),
                                "plan": None,
                            }
                        logger.warning(
                            "react_codex_operator_failed",
                            skill=specialist_name,
                            error=codex_result.error,
                        )
                if specialist_name.startswith("fleetintel"):
                    await emit_progress("external_call", server="fleetintel", status="start")
                elif specialist_name == "brazilcnpj":
                    await emit_progress("external_call", server="brazilcnpj", status="start")
                specialist_result = await registry.execute_skill(
                    specialist_name,
                    {"raw_input": user_message, "query": user_message},
                )
                if codex_mode == "codex_synthesizer" and not raw_requested:
                    if not has_codex:
                        return {
                            **state,
                            "intent": "task",
                            "action_required": False,
                            "response": _format_specialist_contract_mismatch(
                                specialist_name,
                                codex_available=False,
                            ),
                            "plan": None,
                        }
                    await emit_progress(
                        "routing",
                        server="codex_operator",
                        specialist=specialist_name,
                        mode="synthesizer",
                    )
                    codex_result = await router.dispatch(
                        RuntimeExecutionRequest(
                            action=specialist_name,
                            args={
                                "query": user_message,
                                "specialist_name": specialist_name,
                                "specialist_result": str(specialist_result),
                            },
                            user_id=state.get("user_id", ""),
                            context={
                                "codex_mode": "synthesizer",
                                "conversation_history": conversation_history[-6:],
                                "user_message": user_message,
                                "specialist_name": specialist_name,
                                "specialist_result": str(specialist_result),
                                "external_skill_contract": {
                                    "external_name": contract.external_name,
                                    "version": contract.version,
                                    "execution_mode": contract.execution_mode,
                                    "response_owner": contract.response_owner,
                                    "raw_output_policy": contract.raw_output_policy,
                                    "description": contract.description,
                                }
                                if contract
                                else None,
                            },
                            context_keys=[
                                "codex_mode",
                                "conversation_history",
                                "user_message",
                                "specialist_name",
                                "specialist_result",
                                "external_skill_contract",
                            ],
                            preferred_protocol=RuntimeProtocol.CODEX_OPERATOR,
                        )
                    )
                    if codex_result.success and isinstance(codex_result.output, dict):
                        return {
                            **state,
                            "intent": "task",
                            "action_required": False,
                            "response": _render_codex_response(codex_result.output),
                            "plan": None,
                        }
                    logger.warning(
                        "react_codex_synthesizer_failed",
                        skill=specialist_name,
                        error=codex_result.error,
                    )
                    return {
                        **state,
                        "intent": "task",
                        "action_required": False,
                        "response": _format_specialist_contract_mismatch(
                            specialist_name,
                            codex_available=True,
                        ),
                        "plan": None,
                    }
                return {
                    **state,
                    "intent": "task",
                    "action_required": False,
                    "response": str(specialist_result),
                    "plan": None,
                }
            except Exception as specialist_err:
                logger.error(
                    "react_external_shortcut_error",
                    skill=specialist_name,
                    error=str(specialist_err),
                )
                # Falhou; continua para o loop LLM normal.
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
    await emit_progress("formatting", tool=tool_name or "response")

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
