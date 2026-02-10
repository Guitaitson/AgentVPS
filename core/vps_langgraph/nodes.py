"""
Nodes do agente LangGraph.
Cada função é um nó no grafo de decisões.
"""

import asyncio
from datetime import datetime

import structlog

from .memory import AgentMemory
from .state import AgentState

logger = structlog.get_logger()
memory = AgentMemory()


async def node_classify_intent(state: AgentState) -> AgentState:
    """Classifica a intenção do usuário usando LLM."""
    from .intent_classifier_llm import classify_intent_llm

    message = state["user_message"]
    conversation_history = state.get("conversation_history", [])

    logger.info(
        "node_classify_intent_start",
        message=message[:100],
        history_len=len(conversation_history),
    )

    # Usar classificador LLM moderno
    result = await classify_intent_llm(message, conversation_history)

    logger.info(
        "node_classify_intent_result",
        intent=result["intent"],
        confidence=result["confidence"],
        action_required=result["action_required"],
        tool_suggestion=result["tool_suggestion"],
    )

    return {
        **state,
        "intent": result["intent"],
        "intent_confidence": result["confidence"],
        "intent_details": {
            "entities": result["entities"],
            "action_required": result["action_required"],
            "tool_suggestion": result["tool_suggestion"],
            "reasoning": result["reasoning"],
        },
        "tool_suggestion": result["tool_suggestion"],
        "action_required": result["action_required"],
    }


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


def node_plan(state: AgentState) -> AgentState:
    """Cria plano de ação baseado na intenção."""
    intent = state.get("intent")
    tool_suggestion = state.get("tool_suggestion", "")
    action_required = state.get("action_required", False)

    logger.info(
        "node_plan",
        intent=intent,
        tool_suggestion=tool_suggestion,
        action_required=action_required,
    )

    if intent == "command":
        command = state["user_message"].split()[0].lstrip("/")
        return {
            **state,
            "plan": [{"type": "command", "action": command}],
            "current_step": 0,
            "tools_needed": [],
        }

    if intent == "question":
        # Se tem tool sugerida, incluir no plano
        if tool_suggestion and action_required:
            return {
                **state,
                "plan": [{"type": "tool", "action": tool_suggestion}],
                "current_step": 0,
                "tools_needed": [tool_suggestion],
            }
        return {
            **state,
            "plan": [{"type": "query", "action": "get_system_info"}],
            "current_step": 0,
            "tools_needed": [],
        }

    if intent == "task":
        action = state["user_message"]
        return {
            **state,
            "plan": [{"type": "execute", "action": action}],
            "current_step": 0,
            "tools_needed": ["docker"],
        }

    # Chat: resposta direta
    return {
        **state,
        "plan": None,
        "current_step": None,
    }


def node_security_check(state: AgentState) -> AgentState:
    """
    Verifica segurança antes de executar comandos.
    Consulta allowlist para bloquear comandos perigosos.
    """
    from ..security.allowlist import ResourceType, create_default_allowlist
    import json
    from datetime import datetime

    plan = state.get("plan", [])
    step = state.get("current_step", 0)

    # DEBUG: Log para arquivo
    debug_info = {
        "timestamp": datetime.now().isoformat(),
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
        with open("/tmp/security_debug.log", "a") as f:
            f.write(json.dumps(debug_info) + "\n")
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
            with open("/tmp/security_debug.log", "a") as f:
                f.write(json.dumps(debug_info) + "\n")
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

    # Tools do tipo "tool" são permitidas (são nossas tools controladas)
    if action_type == "tool":
        debug_info["result"] = "tool_allowed"

    with open("/tmp/security_debug.log", "a") as f:
        f.write(json.dumps(debug_info) + "\n")

    return {
        **state,
        "security_check": {
            "passed": True,
            "reason": "allowed",
        },
        "blocked_by_security": False,
    }


async def node_execute(state: AgentState) -> AgentState:
    """Executa o plano definido usando tools modernas."""
    from ..tools.system_tools import (
        get_async_tool,
    )
    from .error_handler import format_error_for_user, wrap_error

    # Verificar se foi bloqueado pelo security check
    if state.get("blocked_by_security"):
        logger.info("node_execute_blocked_by_security")
        return state

    intent = state.get("intent")
    tool_suggestion = state.get("tool_suggestion", "")
    action_required = state.get("action_required", False)

    logger.info(
        "node_execute_start",
        intent=intent,
        tool_suggestion=tool_suggestion,
        action_required=action_required,
    )

    try:
        # Se há tool sugerida pelo LLM, usá-la
        if tool_suggestion and action_required:
            tool = get_async_tool(tool_suggestion)
            logger.info(
                "node_execute_tool_lookup",
                tool_suggestion=tool_suggestion,
                tool_found=tool is not None,
            )

            if tool:
                logger.info("node_execute_tool_calling", tool=tool_suggestion)
                result = await tool()
                logger.info(
                    "node_execute_tool_result",
                    tool=tool_suggestion,
                    result_preview=str(result)[:100] if result else "None",
                )

                if not result:
                    result = f"⚠️ Tool '{tool_suggestion}' executou mas não retornou dados"

                return {**state, "execution_result": result}
            else:
                logger.warning(
                    "node_execute_tool_not_found",
                    tool_suggestion=tool_suggestion,
                )
                return {
                    **state,
                    "execution_result": f"⚠️ Tool '{tool_suggestion}' não encontrada no registro",
                }

        # Fallback: comandos tradicionais via /command
        plan = state.get("plan", [])
        step = state.get("current_step", 0)

        if not plan or step >= len(plan):
            logger.info("node_execute_no_plan")
            return {**state, "execution_result": None}

        current_action = plan[step]
        action_type = current_action.get("type")
        action = current_action.get("action")

        logger.info(
            "node_execute_fallback",
            action_type=action_type,
            action=action,
        )

        # Mapear comandos para tools
        if action_type == "command" and action == "ram":
            from ..tools.system_tools import get_ram_usage_async

            result = await get_ram_usage_async()
            return {**state, "execution_result": result}

        elif action_type == "command" and action == "containers":
            from ..tools.system_tools import list_docker_containers_async

            result = await list_docker_containers_async()
            return {**state, "execution_result": result}

        elif action_type == "command" and action == "status":
            from ..tools.system_tools import get_system_status_async

            result = await get_system_status_async()
            return {**state, "execution_result": result}

        elif action_type == "command" and action == "health":
            # Executar checks em paralelo
            from ..tools.system_tools import check_postgres_async, check_redis_async

            postgres_task = check_postgres_async()
            redis_task = check_redis_async()

            postgres_result, redis_result = await asyncio.gather(
                postgres_task, redis_task, return_exceptions=True
            )

            # Format results
            checks = []
            checks.append(
                postgres_result
                if isinstance(postgres_result, str)
                else f"❌ PostgreSQL: {postgres_result}"
            )
            checks.append(
                redis_result
                if isinstance(redis_result, str)
                else f"❌ Redis: {redis_result}"
            )

            status_msg = "\n".join(checks)
            return {**state, "execution_result": status_msg}

        elif action_type == "tool":
            # Executar tool diretamente do plano
            tool = get_async_tool(action)
            if tool:
                result = await tool()
                return {**state, "execution_result": result}
            else:
                return {
                    **state,
                    "execution_result": f"⚠️ Tool '{action}' não encontrada",
                }

        else:
            # Comando não implementado - usar resposta smarter
            from .smart_responses import (
                detect_missing_skill_keywords,
                generate_smart_unavailable_response,
            )

            detected = detect_missing_skill_keywords(f"{action_type} {action}")
            response = generate_smart_unavailable_response(
                f"{action_type} {action}", detected_skills=detected, intent=intent
            )
            return {**state, "execution_result": response}

    except Exception as e:
        wrapped_error = wrap_error(
            e, metadata={"action": state.get("tool_suggestion", "unknown")}
        )
        logger.error(
            "node_execute_exception",
            error=str(e),
            tool_suggestion=tool_suggestion,
        )
        return {
            **state,
            "error": wrapped_error.to_dict(),
            "execution_result": format_error_for_user(e),
        }


async def node_generate_response(state: AgentState) -> str:
    """Gera resposta final ao usuário com identidade VPS-Agent."""
    from .smart_responses import (
        detect_missing_skill_keywords,
        generate_smart_unavailable_response,
        get_capabilities_summary,
    )

    intent = state.get("intent")
    execution_result = state.get("execution_result")
    user_context = state.get("user_context", {})
    user_message = state.get("user_message")
    conversation_history = state.get("conversation_history", [])
    missing_capabilities = state.get("missing_capabilities", [])

    logger.info(
        "node_generate_response_start",
        intent=intent,
        has_execution_result=execution_result is not None,
        execution_result_type=type(execution_result).__name__ if execution_result else None,
        execution_result_preview=str(execution_result)[:100] if execution_result else None,
    )

    # Se há resultado de execução, usar diretamente (MESMO que seja string vazia)
    if execution_result is not None:
        # Verificar se é uma mensagem de "não implementado"
        result_str = str(execution_result).lower()
        if "não implementado" in result_str or "not implemented" in result_str:
            # Gerar resposta smarter com plano de ação
            detected = detect_missing_skill_keywords(user_message.lower())
            response = generate_smart_unavailable_response(
                user_message, detected_skills=detected, intent=intent
            )
            logger.info("node_generate_response_unimplemented")
        else:
            response = execution_result
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
            print(f"LLM error: {e}")
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

    # Salvar memória se foi uma interação significativa
    should_save = intent in ["command", "task"] or len(user_message) > 50

    logger.info(
        "node_generate_response_end",
        response_preview=str(response)[:100] if response else "None",
    )

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


# ============ Self-Improvement Nodes ============


def node_check_capabilities(state: AgentState) -> AgentState:
    """Verifica se o agente tem as capacidades necessárias."""
    try:
        from ..capabilities import capabilities_registry

        task = state.get("user_message", "")
        missing = capabilities_registry.detect_missing(task)

        if missing:
            missing_list = [cap.to_dict() for cap in missing]
            return {
                **state,
                "missing_capabilities": missing_list,
                "needs_improvement": True,
                "improvement_summary": f"Detectei {len(missing)} capacidades faltantes: {', '.join(cap.name for cap in missing)}",
            }

        return {
            **state,
            "missing_capabilities": [],
            "needs_improvement": False,
            "improvement_summary": "Todas as capacidades necessárias estão disponíveis.",
        }
    except ImportError as e:
        return {
            **state,
            "missing_capabilities": [],
            "needs_improvement": False,
            "improvement_summary": f"Capabilities registry não disponível: {e}",
        }


def node_self_improve(state: AgentState) -> AgentState:
    """Planeja e executa auto-improvement."""
    try:
        from ..capabilities import capabilities_registry

        missing = state.get("missing_capabilities", [])

        if not missing:
            return {**state, "should_improve": False, "improvement_plan": None}

        # Criar plano de implementação
        plan = []
        for cap_dict in missing:
            cap_name = cap_dict["name"]
            cap = capabilities_registry.get_capability(cap_name)
            if cap:
                plan.append(
                    {
                        "capability": cap.to_dict(),
                        "steps": capabilities_registry.get_implementation_plan(cap),
                    }
                )

        return {
            **state,
            "improvement_plan": plan,
            "should_improve": True,
            "improvement_status": "planning",
        }
    except ImportError as e:
        return {
            **state,
            "should_improve": False,
            "improvement_plan": None,
            "improvement_summary": f"Não foi possível acessar capabilities registry: {e}",
        }


def node_implement_capability(state: AgentState) -> AgentState:
    """Implementa uma nova capacidade usando o CLI."""
    try:
        plan = state.get("improvement_plan", [])

        if not plan:
            return {
                **state,
                "implementation_result": "Nada para implementar",
                "new_capability": None,
            }

        # Chamar CLI para implementar a primeira capacidade
        target_cap = plan[0]["capability"]
        cap_name = target_cap["name"]
        cap_description = target_cap["description"]

        # Criar prompt para o CLI
        f"""# Auto-Implementação de Capacidade

## Capacidade a Implementar
**Nome:** {cap_name}
**Descrição:** {cap_description}

## Contexto
O agente detectou que esta capacidade está faltante e precisa ser implementada automaticamente.

## Requisitos
1. Criar módulo Python funcional
2. Integrar com sistemas existentes (LangGraph, MCP Server, etc.)
3. Adicionar testes
4. Documentar uso

## Plano de Implementação
{plan[0]["steps"]}

## Restrições
- Deve funcionar na VPS (Ubuntu 24.04)
- Deve respeitar limites de RAM (2.4 GB total)
- Deve ser testado antes de marcar como implementado

Por favor, implemente esta capacidade seguindo o plano acima.
"""

        # Simular chamada ao CLI (na implementação real, isso seria uma chamada real)
        # Por enquanto, vamos gerar um código placeholder
        implementation_code = f"""# Placeholder para {cap_name}
# Esta capacidade será implementada pelo CLI/Kilocode

def {cap_name.replace("-", "_")}():
    \"\"\"{cap_description}\"\"\"# TODO: Implementar funcionalidade
    pass
"""

        return {
            **state,
            "implementation_result": f"Código gerado para {cap_name}. Agora preciso integrar e testar.",
            "generated_code": implementation_code,
            "new_capability": cap_name,
            "implementation_status": "code_generated",
        }
    except ImportError as e:
        return {
            **state,
            "implementation_result": f"Não foi possível implementar: {e}",
            "new_capability": None,
        }