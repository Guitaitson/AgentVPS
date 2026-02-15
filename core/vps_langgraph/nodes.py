"""
Nodes do agente LangGraph.
Cada função é um nó no grafo de decisões.
"""

import asyncio
from datetime import datetime

import structlog

from .memory import AgentMemory
from .state import AgentState
from ..skills.registry import get_skill_registry

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
    from ..skills.registry import get_skill_registry

    intent = state.get("intent")
    tool_suggestion = state.get("tool_suggestion", "")
    action_required = state.get("action_required", False)
    user_message = state.get("user_message", "")

    logger.info(
        "node_plan",
        intent=intent,
        tool_suggestion=tool_suggestion,
        action_required=action_required,
        message=user_message[:50],
    )

    # Obter registry de skills para roteamento inteligente
    registry = get_skill_registry()
    msg_lower = user_message.lower().strip()

    # ========================================
    # INTENT: COMMAND - Comandos diretos
    # ========================================
    if intent == "command":
        # Se começa com /, extrair comando
        if msg_lower.startswith("/"):
            command = msg_lower[1:].split()[0]
        # Se tem tool_suggestion, usar como comando
        elif tool_suggestion:
            command = tool_suggestion
        else:
            # Fallback: usar primeira palavra
            command = msg_lower.split()[0]
        
        logger.info("node_plan_command", command=command)
        
        return {
            **state,
            "plan": [{"type": "command", "action": command, "raw_message": user_message}],
            "current_step": 0,
            "tools_needed": [],
        }

    # ========================================
    # INTENT: TASK - Tarefas a executar
    # ========================================
    if intent == "task":
        # PRIORIDADE 1: Se tem tool_suggestion do LLM, usar ela primeiro
        if tool_suggestion:
            skill = registry.get(tool_suggestion) or registry.find_by_trigger(tool_suggestion)
            if skill:
                logger.info("node_plan_task_from_llm", skill=skill.name, tool_suggestion=tool_suggestion)
                return {
                    **state,
                    "plan": [{"type": "skill", "action": skill.name, "raw_message": user_message}],
                    "current_step": 0,
                    "tools_needed": [skill.name],
                }
        
        # PRIORIDADE 2: Tentar encontrar skill pelo trigger na mensagem
        skill = registry.find_by_trigger(user_message)
        
        if skill:
            logger.info("node_plan_task_found_skill", skill=skill.name, message=user_message[:50])
            return {
                **state,
                "plan": [{"type": "skill", "action": skill.name, "raw_message": user_message}],
                "current_step": 0,
                "tools_needed": [skill.name],
            }
        
        # Fallback: usar a mensagem como ação
        logger.info("node_plan_task_fallback", message=user_message[:50])
        return {
            **state,
            "plan": [{"type": "execute", "action": user_message, "raw_message": user_message}],
            "current_step": 0,
            "tools_needed": [],
        }

    # ========================================
    # INTENT: QUESTION - Perguntas sobre sistema
    # ========================================
    if intent == "question":
        # Se tem tool sugerida, usar ela
        if tool_suggestion:
            # Primeiro tentar encontrar skill pelo nome
            skill = registry.get(tool_suggestion)
            if not skill:
                # Tentar por trigger
                skill = registry.find_by_trigger(tool_suggestion)
            
            if skill:
                logger.info("node_plan_question_skill", skill=skill.name)
                return {
                    **state,
                    "plan": [{"type": "skill", "action": skill.name, "raw_message": user_message}],
                    "current_step": 0,
                    "tools_needed": [skill.name],
                }
            
            # Se não encontrou skill, mapear tool_suggestion antigo para comando
            command_map = {
                "get_ram": "ram",
                "list_containers": "containers",
                "get_system_status": "status",
                "check_postgres": "postgres",
                "check_redis": "redis",
            }
            if tool_suggestion in command_map:
                return {
                    **state,
                    "plan": [{"type": "command", "action": command_map[tool_suggestion], "raw_message": user_message}],
                    "current_step": 0,
                    "tools_needed": [],
                }
        
        # Tentar encontrar skill por trigger na mensagem
        skill = registry.find_by_trigger(user_message)
        if skill:
            logger.info("node_plan_question_trigger", skill=skill.name)
            return {
                **state,
                "plan": [{"type": "skill", "action": skill.name, "raw_message": user_message}],
                "current_step": 0,
                "tools_needed": [skill.name],
            }
        
        # Fallback: info do sistema
        return {
            **state,
            "plan": [{"type": "query", "action": "get_system_info", "raw_message": user_message}],
            "current_step": 0,
            "tools_needed": [],
        }

    # ========================================
    # INTENT: CHAT ou DEFAULT - Resposta direta
    # ========================================
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


async def node_execute(state: AgentState) -> AgentState:
    """Executa ação usando Skill Registry."""
    from .error_handler import format_error_for_user, wrap_error

    if state.get("blocked_by_security"):
        logger.info("node_execute_blocked_by_security")
        return state

    registry = get_skill_registry()
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    tool_suggestion = state.get("tool_suggestion", "")
    user_message = state.get("user_message", "")

    try:
        # 1. Tentar skill pelo plano
        if plan and step < len(plan):
            current_action = plan[step]
            action_type = current_action.get("type")
            action = current_action.get("action", "")
            raw_message = current_action.get("raw_message", user_message)
            
            logger.info(
                "node_execute_from_plan",
                action_type=action_type,
                action=action,
                raw_message=raw_message[:50],
            )

            # Mapear action para skill name
            skill = registry.get(action) or registry.find_by_trigger(action)
            if skill:
                logger.info("node_execute_skill_found", skill=skill.name)
                # Verificar se há args estruturados do function calling
                skill_args = current_action.get("args", {})
                if skill_args:
                    # Usar args estruturados do LLM (function calling)
                    result = await registry.execute_skill(skill.name, skill_args)
                else:
                    # Fallback: usar raw_input para compatibilidade
                    result = await registry.execute_skill(skill.name, {"raw_input": raw_message})
                return {**state, "execution_result": result}
            else:
                logger.warning("node_execute_skill_not_found", action=action)

        # 2. Tentar por tool_suggestion do LLM
        if tool_suggestion:
            skill = registry.get(tool_suggestion) or registry.find_by_trigger(tool_suggestion)
            if skill:
                logger.info("node_execute_tool_suggestion", skill=skill.name)
                result = await registry.execute_skill(skill.name, {"raw_input": user_message})
                return {**state, "execution_result": result}

        # 3. Skill não encontrado — tentar encontrar por trigger na mensagem
        skill = registry.find_by_trigger(user_message)
        if skill:
            logger.info("node_execute_trigger_fallback", skill=skill.name)
            result = await registry.execute_skill(skill.name, {"raw_input": user_message})
            return {**state, "execution_result": result}

        # 4. Skill não encontrado — resposta inteligente
        from .smart_responses import generate_smart_unavailable_response, detect_missing_skill_keywords
        detected = detect_missing_skill_keywords(user_message.lower())
        
        # Listar skills disponíveis para o usuário
        available_skills = registry.list_skills()
        skills_list = ", ".join([s["name"] for s in available_skills])
        
        response = generate_smart_unavailable_response(user_message, detected_skills=detected)
        
        # Adicionar informação sobre skills disponíveis
        if available_skills:
            response += f"\n\n📋 Skills disponíveis: {skills_list}"
        
        logger.warning("node_execute_no_skill_found", message=user_message[:50], available=len(available_skills))
        return {**state, "execution_result": response}

    except Exception as e:
        wrapped = wrap_error(e, metadata={"skill": tool_suggestion, "action": action if 'action' in dir() else None})
        logger.error("node_execute_error", error=str(e))
        return {
            **state,
            "error": wrapped.to_dict(),
            "execution_result": format_error_for_user(e),
        }


# Alias para compatibilidade com código legado
def get_async_tool(name: str):
    """Fallback para compatibilidade com código legado."""
    from ..tools.system_tools import get_async_tool as legacy_get_async_tool
    return legacy_get_async_tool(name)


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
    )

    response = None

    # Se há resultado de execução, usar diretamente (MESMO que seja string vazia)
    if execution_result is not None:
        # Verificar se é uma mensagem de "não implementado"
        result_str = str(execution_result).lower()
        if "não implementado" in result_str or "não encontrado" in result_str or "not implemented" in result_str:
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