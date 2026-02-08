#!/usr/bin/env python3
"""Teste dos 5 intents principais."""
import sys
from pathlib import Path

# Add core/ to path dynamically
core_path = Path(__file__).parent / 'core'
sys.path.insert(0, str(core_path))

from vps_agent.agent import process_message_async
import asyncio

async def run_intent_test(name: str, message: str):
    """Helper function to test a single intent."""
    print(f"\n=== TESTANDO: {name} ===")
    print(f"Mensagem: {message}")
    try:
        result = await process_message_async('test', message)
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
        success = await test_intent(name, message)
        results.append((name, success))
    
    print("\n" + "="*50)
    print("RESUMO DOS TESTES:")
    print("="*50)
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{name}: {status}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\nTotal: {passed}/{total} testes passaram")
    
    return passed == total

if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
