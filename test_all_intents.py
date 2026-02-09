#!/usr/bin/env python3
"""Teste dos 5 intents principais."""

import sys
from pathlib import Path

# Add the project root to the path for development mode
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio

from core.vps_agent.agent import process_message_async


async def run_intent_test(name: str, message: str):
    """Helper function to test a single intent."""
    print(f"\n=== TESTANDO: {name} ===")
    print(f"Mensagem: {message}")
    try:
        result = await process_message_async("test", message)
        print(f"Resposta: {result[:200]}..." if len(result) > 200 else f"Resposta: {result}")
        return result is not None and result != ""
    except Exception as e:
        print(f"ERRO: {e}")
        return False


async def main():
    tests = [
        ("COMMAND", "/status"),
        ("TASK", "me mostre os containers rodando"),
        ("QUESTION", "qual a RAM disponível?"),
        ("CHAT", "oi, tudo bem?"),
        ("SELF_IMPROVE", "você consegue criar uma nova ferramenta?"),
    ]

    results = []
    for name, message in tests:
        success = await run_intent_test(name, message)
        results.append((name, success))

    print("\n" + "=" * 50)
    print("RESUMO DOS TESTES:")
    print("=" * 50)
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{name}: {status}")

    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\nTotal: {passed}/{total} testes passaram")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
