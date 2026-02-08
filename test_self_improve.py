#!/usr/bin/env python3
"""Teste do fluxo self_improve."""
import sys
sys.path.insert(0, '/opt/vps-agent/core')

from vps_agent.agent import process_message_async
import asyncio

async def main():
    print("Testando fluxo self_improve...")
    result = await process_message_async('test', 'voce consegue melhorar voce mesmo?')
    print('=== RESULTADO ===')
    print(result)
    return result

if __name__ == '__main__':
    asyncio.run(main())
