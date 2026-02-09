#!/usr/bin/env python3
"""Teste do fluxo self_improve."""
import sys
from pathlib import Path

# Add the project root to the path for development mode
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio

from core.vps_agent.agent import process_message_async


async def main():
    print("Testando fluxo self_improve...")
    result = await process_message_async('test', 'voce consegue melhorar voce mesmo?')
    print('=== RESULTADO ===')
    print(result)
    return result

if __name__ == '__main__':
    asyncio.run(main())
