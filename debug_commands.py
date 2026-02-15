"""
Script de debug para investigar o fluxo de comandos /containers e /health.
Simula o fluxo completo do grafo para entender onde está falhando.
"""

import asyncio
import sys

sys.path.insert(0, "/opt/vps-agent")


async def debug_command(message: str):
    """Debuga o processamento de um comando."""
    print(f"\n{'=' * 60}")
    print(f"DEBUGANDO COMANDO: '{message}'")
    print(f"{'=' * 60}\n")

    # 1. Testar classificador de intent
    print("1. TESTANDO CLASSIFICADOR DE INTENT...")
    try:
        from core.vps_langgraph.intent_classifier_llm import classify_intent_llm

        result = await classify_intent_llm(message)
        print(f"   Intent: {result['intent']}")
        print(f"   Confidence: {result['confidence']}")
        print(f"   Action Required: {result['action_required']}")
        print(f"   Tool Suggestion: {result['tool_suggestion']}")
        print(f"   Reasoning: {result['reasoning']}")
    except Exception as e:
        print(f"   ERRO: {e}")
        import traceback

        traceback.print_exc()

    # 2. Testar allowlist
    print("\n2. TESTANDO ALLOWLIST...")
    try:
        from core.security.allowlist import ResourceType, create_default_allowlist

        allowlist = create_default_allowlist()

        # Verificar se o comando está na allowlist
        test_values = [
            ("containers", ResourceType.COMMAND),
            ("health", ResourceType.COMMAND),
            ("ram", ResourceType.COMMAND),
            ("status", ResourceType.COMMAND),
            ("list_containers", ResourceType.SYSTEM_OPERATION),
            ("get_system_status", ResourceType.SYSTEM_OPERATION),
            ("get_ram", ResourceType.SYSTEM_OPERATION),
        ]

        for value, resource_type in test_values:
            result = allowlist.check(resource_type, value)
            status = "✅ PERMITIDO" if result.allowed else "❌ BLOQUEADO"
            print(f"   {value} ({resource_type.value}): {status}")
            if not result.allowed:
                print(f"      Razão: {result.reason}")
    except Exception as e:
        print(f"   ERRO: {e}")
        import traceback

        traceback.print_exc()

    # 3. Testar skills via registry
    print("\n3. TESTANDO SKILL REGISTRY...")
    try:
        from core.skills.registry import get_skill_registry

        registry = get_skill_registry()
        skills = registry.list_skills()
        for skill_info in skills:
            print(f"   {skill_info['name']}: ✅ REGISTRADO")
        if not skills:
            print("   ❌ Nenhum skill registrado")
    except Exception as e:
        print(f"   ERRO: {e}")
        import traceback

        traceback.print_exc()

    # 4. Testar processamento completo
    print("\n4. TESTANDO PROCESSAMENTO COMPLETO...")
    try:
        from core.vps_agent.agent import process_message_async

        result = await process_message_async("test_user", message)
        print(f"   Resultado: {result[:200]}...")
    except Exception as e:
        print(f"   ERRO: {e}")
        import traceback

        traceback.print_exc()

    print(f"\n{'=' * 60}\n")


async def main():
    """Executa debug para todos os comandos."""
    commands = [
        "quanta RAM?",
        "status do sistema",
        "lista containers docker",
        "health check completo",
    ]

    for cmd in commands:
        await debug_command(cmd)


if __name__ == "__main__":
    asyncio.run(main())
