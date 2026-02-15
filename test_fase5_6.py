"""Teste rápido das Fases 5-6: Intent LLM + Tools."""

import asyncio
from datetime import datetime, timezone

from core.vps_langgraph.graph import build_agent_graph
from core.vps_langgraph.state import AgentState


async def test_question_ram():
    """Testa: 'quanta RAM?' deve executar tool."""
    print("=" * 60)
    print("Teste: 'quanta RAM?'")
    print("=" * 60)

    graph = build_agent_graph()

    initial_state: AgentState = {
        "user_id": "test_user",
        "user_message": "quanta RAM?",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = await graph.ainvoke(initial_state)

        print(f"\nIntent detectado: {result.get('intent')}")
        print(f"Confiança: {result.get('intent_confidence')}")
        print(f"Tool sugerida: {result.get('tool_suggestion')}")
        print(f"Ação requerida: {result.get('action_required')}")
        print(f"\nResposta:\n{result.get('response')}")

        # Verificar se executou tool
        if result.get("intent") == "question" and result.get("action_required"):
            print("\n✅ PASSOU: Pergunta reconhecida e ação requerida!")
        else:
            print("\n❌ FALHOU: Esperava question + action_required")

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback

        traceback.print_exc()


async def test_command_status():
    """Testa: '/status' deve executar comando."""
    print("\n" + "=" * 60)
    print("Teste: '/status'")
    print("=" * 60)

    graph = build_agent_graph()

    initial_state: AgentState = {
        "user_id": "test_user",
        "user_message": "/status",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = await graph.ainvoke(initial_state)

        print(f"\nIntent detectado: {result.get('intent')}")
        print(f"Confiança: {result.get('intent_confidence')}")
        print(f"\nResposta:\n{result.get('response')}")

        if result.get("intent") == "command":
            print("\n✅ PASSOU: Comando reconhecido!")
        else:
            print("\n❌ FALHOU: Esperava 'command'")

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback

        traceback.print_exc()


async def test_chat():
    """Testa: 'oi' deve responder conversacionalmente."""
    print("\n" + "=" * 60)
    print("Teste: 'oi'")
    print("=" * 60)

    graph = build_agent_graph()

    initial_state: AgentState = {
        "user_id": "test_user",
        "user_message": "oi",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = await graph.ainvoke(initial_state)

        print(f"\nIntent detectado: {result.get('intent')}")
        print(f"Confiança: {result.get('intent_confidence')}")
        print(f"Ação requerida: {result.get('action_required')}")
        print(f"\nResposta:\n{result.get('response')}")

        if result.get("intent") == "chat" and not result.get("action_required"):
            print("\n✅ PASSOU: Chat reconhecido, sem ação requerida!")
        else:
            print("\n❌ FALHOU: Esperava 'chat' sem ação")

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback

        traceback.print_exc()


async def main():
    """Executa todos os testes."""
    print("\n" + "=" * 60)
    print("TESTE DAS FASES 5-6: Intent LLM + Tools")
    print("=" * 60)

    # Teste 1: Pergunta com execução
    await test_question_ram()

    # Teste 2: Comando direto
    await test_command_status()

    # Teste 3: Chat simples
    await test_chat()

    print("\n" + "=" * 60)
    print("Testes concluídos!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
