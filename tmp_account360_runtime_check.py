import asyncio
from core.vps_agent.agent import process_message_async

PROMPTS = [
    "Use BrazilCNPJ Enricher e FleetIntel para me dizer sobre o CNPJ 48.430.290/0001-30, com socios, grupo economico e frota.",
    "Use BrazilCNPJ Enricher e FleetIntel para me dizer sobre Addiante S.A. e seus socios.",
]

async def main():
    for idx, prompt in enumerate(PROMPTS, start=1):
        result = await process_message_async(user_id=f"codex-account360-{idx}", message=prompt)
        print(f"===PROMPT {idx}===")
        print(prompt)
        print("===RESPONSE===")
        print(result)
        print("===END===")

asyncio.run(main())
