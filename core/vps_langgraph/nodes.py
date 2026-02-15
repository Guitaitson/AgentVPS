"""
Nodes do agente LangGraph.
Cada função é um nó no grafo de decisões.
"""

from datetime import datetime

import structlog

from ..skills.registry import get_skill_registry
from .memory import AgentMemory
from .state import AgentState

logger = structlog.get_logger()
memory = AgentMemory()


def node_load_context(state: AgentState) -> AgentState:
    """Carrega contexto do usuário da memória."""
    user_id = state["user_id"]

    # Fatos do usuário
    user_facts = memory.get_user_facts(user_id)

    # Histórico recente
    history = memory.get_conversation_history(user_id, limit=5)

    logger.info(
        "node_load_context",
        user_id=user_id,
        facts_count=len(user_facts),
        history_count=len(history),
    )

    return {
        **state,
        "user_context": user_facts,
        "conversation_history": history,
    }


def node_security_check(state: AgentState) -> AgentState:
    """
    Verifica segurança antes de executar comandos.
    Consulta allowlist para bloquear comandos perigosos.
    """

    from ..security.allowlist import ResourceType, create_default_allowlist

    plan = state.get("plan", [])
    step = state.get("current_step", 0)

    # Log de debug via structlog
    debug_info = {
        "plan": plan,
        "step": step,
        "action_type": None,
        "action": None,
        "full_command": None,
        "result": None,
        "blocked": False,
    }

    if not plan or step >= len(plan):
        debug_info["result"] = "no_action"
        logger.debug("security_check_no_action", **debug_info)
        return {**state, "security_check": {"passed": True, "reason": "no_action"}}

    current_action = plan[step]
    action_type = current_action.get("type")
    action = current_action.get("action", "")

    debug_info["action_type"] = action_type
    debug_info["action"] = action

    # Carregar allowlist padrão
    allowlist = create_default_allowlist()

    # Verificar comando se for do tipo command ou execute
    if action_type in ["command", "execute"]:
        # Montar comando completo para verificação
        full_command = action if isinstance(action, str) else str(action)
        debug_info["full_command"] = full_command

        # Verificar na allowlist
        result = allowlist.check(ResourceType.COMMAND, full_command)
        debug_info["allowed"] = result.allowed
        debug_info["reason"] = result.reason

        if not result.allowed:
            debug_info["blocked"] = True
            logger.debug("security_check_blocked", **debug_info)
            return {
                **state,
                "security_check": {
                    "passed": False,
                    "reason": result.reason,
                    "rule": result.rule.name if result.rule else None,
                    "permission": result.permission.value,
                },
                "blocked_by_security": True,
                "execution_result": f"⛔ Comando bloqueado por segurança:\n{result.reason}\n\nPara executar este comando, adicione-o à allowlist ou use modo de aprovação.",
            }

        debug_info["result"] = "allowed"

    # Skills do tipo "skill" verificam o comando dentro dos args
    if action_type == "skill":
        skill_args = current_action.get("args", {})
        # Se o skill é shell_exec, verificar o comando
        if action == "shell_exec" and "command" in skill_args:
            full_command = skill_args["command"]
            debug_info["full_command"] = full_command
            result = allowlist.check(ResourceType.COMMAND, full_command)
            debug_info["allowed"] = result.allowed
            debug_info["reason"] = result.reason
            if not result.allowed:
                debug_info["blocked"] = True
                logger.debug("security_check_blocked_skill", **debug_info)
                return {
                    **state,
                    "security_check": {
                        "passed": False,
                        "reason": result.reason,
                        "rule": result.rule.name if result.rule else None,
                        "permission": result.permission.value,
                    },
                    "blocked_by_security": True,
                    "execution_result": f"⛔ Comando bloqueado por segurança:\n{result.reason}",
                }
        debug_info["result"] = "skill_allowed"

    # Tools do tipo "tool" são permitidas (são nossas tools controladas)
    if action_type == "tool":
        debug_info["result"] = "tool_allowed"

    logger.debug("security_check_allowed", **debug_info)

    return {
        **state,
        "security_check": {
            "passed": True,
            "reason": "allowed",
        },
        "blocked_by_security": False,
    }


async def _execute_with_hooks(registry, skill_name, skill_args, user_id):
    """Executa skill com pre/post hooks."""
    import time

    from ..hooks.runner import HookContext, get_hook_runner

    hook_runner = get_hook_runner()
    ctx = HookContext(skill_name=skill_name, args=skill_args, user_id=user_id)

    should_proceed = await hook_runner.run_pre(ctx)
    if not should_proceed:
        return None, "Execucao cancelada por politica de seguranca."

    start = time.time()
    try:
        result = await registry.execute_skill(skill_name, skill_args)
        ctx.duration_ms = (time.time() - start) * 1000
        ctx.result = str(result)
    except Exception as e:
        ctx.duration_ms = (time.time() - start) * 1000
        ctx.error = str(e)
        await hook_runner.run_post(ctx)
        raise

    await hook_runner.run_post(ctx)
    return result, None


async def node_execute(state: AgentState) -> AgentState:
    """Executa ação usando Skill Registry + Hook System."""
    from .error_handler import format_error_for_user, wrap_error

    if state.get("blocked_by_security"):
        logger.info("node_execute_blocked_by_security")
        return state

    registry = get_skill_registry()
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    tool_suggestion = state.get("tool_suggestion", "")
    user_message = state.get("user_message", "")
    user_id = state.get("user_id", "unknown")

    try:
        # 1. Tentar skill pelo plano
        if plan and step < len(plan):
            current_action = plan[step]
            action = current_action.get("action", "")
            raw_message = current_action.get("raw_message", user_message)

            skill = registry.get(action) or registry.find_by_trigger(action)
            if skill:
                skill_args = current_action.get("args", {})
                if not skill_args:
                    skill_args = {"raw_input": raw_message}
                result, veto = await _execute_with_hooks(registry, skill.name, skill_args, user_id)
                if veto:
                    return {**state, "execution_result": veto}
                return {**state, "execution_result": result}
            else:
                logger.warning("node_execute_skill_not_found", action=action)

        # 2. Tentar por tool_suggestion do LLM
        if tool_suggestion:
            skill = registry.get(tool_suggestion) or registry.find_by_trigger(tool_suggestion)
            if skill:
                result, veto = await _execute_with_hooks(
                    registry, skill.name, {"raw_input": user_message}, user_id
                )
                if veto:
                    return {**state, "execution_result": veto}
                return {**state, "execution_result": result}

        # 3. Skill não encontrado — tentar encontrar por trigger na mensagem
        skill = registry.find_by_trigger(user_message)
        if skill:
            result, veto = await _execute_with_hooks(
                registry, skill.name, {"raw_input": user_message}, user_id
            )
            if veto:
                return {**state, "execution_result": veto}
            return {**state, "execution_result": result}

        # 4. Skill não encontrado — resposta inteligente
        from .smart_responses import (
            detect_missing_skill_keywords,
            generate_smart_unavailable_response,
        )

        detected = detect_missing_skill_keywords(user_message.lower())
        available_skills = registry.list_skills()
        skills_list = ", ".join([s["name"] for s in available_skills])

        response = generate_smart_unavailable_response(user_message, detected_skills=detected)
        if available_skills:
            response += f"\n\n Skills disponíveis: {skills_list}"

        logger.warning("node_execute_no_skill_found", message=user_message[:50])
        return {**state, "execution_result": response}

    except Exception as e:
        wrapped = wrap_error(
            e, metadata={"skill": tool_suggestion, "action": action if "action" in dir() else None}
        )
        logger.error("node_execute_error", error=str(e))
        return {
            **state,
            "error": wrapped.to_dict(),
            "execution_result": format_error_for_user(e),
        }


async def node_generate_response(state: AgentState) -> AgentState:
    """Gera resposta final ao usuário com identidade VPS-Agent."""
    from .smart_responses import (
        detect_missing_skill_keywords,
        generate_smart_unavailable_response,
        get_capabilities_summary,
    )

    intent = state.get("intent")
    execution_result = state.get("execution_result")
    user_context = state.get("user_context", {})
    user_message = state.get("user_message", "")
    conversation_history = state.get("conversation_history", [])
    missing_capabilities = state.get("missing_capabilities", [])

    logger.info(
        "node_generate_response_start",
        intent=intent,
        has_execution_result=execution_result is not None,
        has_response=state.get("response") is not None,
    )

    # Se react_node ou format_response já definiu response, usar diretamente
    existing_response = state.get("response")
    if existing_response:
        logger.info("node_generate_response_from_react", preview=str(existing_response)[:100])
        return state

    response = None

    # Se há resultado de execução, usar diretamente (MESMO que seja string vazia)
    if execution_result is not None:
        # Verificar se é uma mensagem de "não implementado"
        result_str = str(execution_result).lower()
        if (
            "não implementado" in result_str
            or "não encontrado" in result_str
            or "not implemented" in result_str
        ):
            # Gerar resposta smarter com plano de ação
            detected = detect_missing_skill_keywords(user_message.lower())
            response = generate_smart_unavailable_response(
                user_message, detected_skills=detected, intent=intent
            )
            logger.info("node_generate_response_unimplemented")
        else:
            response = str(execution_result)
            logger.info(
                "node_generate_response_from_execution",
                response_preview=str(response)[:100] if response else "None",
            )

    # Para self_improve com capacidades faltantes
    elif intent == "self_improve" and missing_capabilities:
        response = generate_smart_unavailable_response(
            user_message,
            detected_skills=detect_missing_skill_keywords(user_message.lower()),
            intent=intent,
        )
        logger.info("node_generate_response_self_improve")

    # Para conversas e perguntas, usar LLM com identidade VPS-Agent
    elif intent in ["chat", "question"]:
        logger.info("node_generate_response_using_llm", intent=intent)
        try:
            from ..llm.openrouter_client import generate_response

            # Chamar LLM com contexto completo de identidade (versão async)
            response = await generate_response(
                user_message=user_message,
                conversation_history=conversation_history,
                user_context=user_context,
            )

            # Fallback se LLM falhou
            if not response:
                if intent == "chat":
                    response = (
                        "Oi! Sou o VPS-Agent! 😊\n\n"
                        "Seu assistente autônomo rodando na VPS.\n\n"
                        "Posso ajudar com:\n"
                        "• Gerenciamento da VPS (RAM, containers, serviços)\n"
                        "• Criação de novos agentes\n"
                        "• Integração de ferramentas\n"
                        "• E muito mais!\n\n"
                        "O que você precisa hoje?"
                    )
                else:
                    response = (
                        f"Sobre '{user_message}':\n\n"
                        "Posso ajudar! Como VPS-Agent, tenho acesso a várias ferramentas.\n\n"
                        f"{get_capabilities_summary()}"
                    )

        except Exception as e:
            logger.error("node_generate_response_llm_error", error=str(e))
            response = (
                "Sou o VPS-Agent! 😊\n\n"
                "Entendi sua mensagem.\n\n"
                "O que eu posso fazer:\n"
                "• Gerenciar sua VPS (RAM, containers)\n"
                "• Criar novos agentes\n"
                "• Integrar ferramentas\n\n"
                f"{get_capabilities_summary()}"
            )

    else:
        response = "Comando executado com sucesso! ✅"
        logger.info("node_generate_response_default")

    # Se nenhuma resposta foi definida, usar fallback
    if response is None:
        response = (
            "Sou o VPS-Agent! 😊\n\n"
            "Entendi sua mensagem. Como posso ajudar?\n\n"
            "Comandos disponíveis:\n"
            "• /status - Status da VPS\n"
            "• /ram - Memória RAM\n"
            "• /containers - Containers Docker\n"
            "• /health - Health check"
        )

    # Salvar memória se foi uma interação significativa
    should_save = intent in ["command", "task"] or len(user_message) > 50

    logger.info(
        "node_generate_response_end",
        response_preview=str(response)[:100] if response else "None",
    )

    # CORREÇÃO: Retornar dict (AgentState), não string!
    return {
        **state,
        "response": response,
        "should_save_memory": should_save,
        "memory_updates": [
            {
                "key": "last_interaction",
                "value": {"type": intent, "time": datetime.now().isoformat()},
            }
        ]
        if should_save
        else [],
    }


def node_save_memory(state: AgentState) -> AgentState:
    """Salva atualizações na memória."""
    user_id = state["user_id"]
    updates = state.get("memory_updates", [])

    for update in updates:
        key = update["key"]
        value = update["value"]
        memory.save_fact(user_id, key, value)

    return state
