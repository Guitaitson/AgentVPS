#!/usr/bin/env python3
"""
Diagnóstico COMPLETO do fluxo /containers e /health
Rastreia cada etapa do processamento da mensagem
"""

import asyncio
import sys

sys.path.insert(0, '/opt/vps-agent')

# Configurar logging detalhado
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def diagnose_message(message: str, user_id: str = "test_user"):
    """Diagnostica o processamento completo de uma mensagem."""

    print(f"\n{'='*80}")
    print(f"DIAGNÓSTICO COMPLETO: '{message}'")
    print(f"{'='*80}\n")

    # ETAPA 1: Verificar o que o bot.py envia
    print("[ETAPA 1] Bot.py envia para agent.py:")
    print(f"  user_id: {user_id}")
    print(f"  message: {message}")

    # ETAPA 2: Classificar intent
    print("\n[ETAPA 2] Classificação de Intent:")
    try:
        from core.vps_langgraph.intent_classifier_llm import classify_intent_llm
        result = await classify_intent_llm(message)

        print(f"  Intent: {result['intent']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Tool Suggestion: {result['tool_suggestion']}")
        print(f"  Action Required: {result['action_required']}")
        print(f"  Reasoning: {result['reasoning']}")

        intent = result['intent']
        tool_suggestion = result['tool_suggestion']
        action_required = result['action_required']

    except Exception as e:
        print(f"  ERRO: {e}")
        import traceback
        traceback.print_exc()
        return

    # ETAPA 3: Criar estado inicial
    print("\n[ETAPA 3] Estado Inicial do Grafo:")
    state = {
        "user_id": user_id,
        "user_message": message,
        "intent": intent,
        "tool_suggestion": tool_suggestion,
        "action_required": action_required,
        "conversation_history": [],
        "user_context": {},
    }
    print(f"  state: {state}")

    # ETAPA 4: Executar node_plan
    print("\n[ETAPA 4] Execução do node_plan:")
    try:
        from core.vps_langgraph.nodes import node_plan
        planned_state = node_plan(state)

        plan = planned_state.get('plan')
        current_step = planned_state.get('current_step')

        print(f"  plan: {plan}")
        print(f"  current_step: {current_step}")

        if plan and current_step is not None and current_step < len(plan):
            current_action = plan[current_step]
            print(f"  current_action: {current_action}")
            print(f"  action_type: {current_action.get('type')}")
            print(f"  action: {current_action.get('action')}")
        else:
            print("  ALERTA: Nenhuma ação planejada!")

    except Exception as e:
        print(f"  ERRO: {e}")
        import traceback
        traceback.print_exc()
        return

    # ETAPA 5: Executar node_security_check
    print("\n[ETAPA 5] Execução do node_security_check:")
    try:
        from core.vps_langgraph.nodes import node_security_check
        security_state = node_security_check(planned_state)

        security_check = security_state.get('security_check', {})
        blocked = security_state.get('blocked_by_security', False)

        print(f"  security_check: {security_check}")
        print(f"  blocked_by_security: {blocked}")

        if blocked:
            print(f"  BLOQUEADO! Razão: {security_check.get('reason')}")
        else:
            print("  PERMITIDO - Seguindo para execução")

    except Exception as e:
        print(f"  ERRO: {e}")
        import traceback
        traceback.print_exc()
        return

    # ETAPA 6: Executar node_execute
    print("\n[ETAPA 6] Execução do node_execute:")
    try:
        from core.vps_langgraph.nodes import node_execute
        executed_state = await node_execute(security_state)

        execution_result = executed_state.get('execution_result')
        print(f"  execution_result: {execution_result[:200] if execution_result else 'None'}...")

    except Exception as e:
        print(f"  ERRO: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"\n{'='*80}")
    print("DIAGNÓSTICO CONCLUÍDO")
    print(f"{'='*80}\n")

async def main():
    # Testar os comandos problemáticos
    test_cases = [
        "/containers",
        "/health",
        "/status",
        "/ram",
    ]

    for message in test_cases:
        await diagnose_message(message)
        await asyncio.sleep(1)  # Pequena pausa entre testes

if __name__ == "__main__":
    asyncio.run(main())
