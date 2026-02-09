"""
OpenRouter Client - Integração com LLMs via OpenRouter

Modelos suportados:
- google/gemini-2.5-flash-lite
- openai/gpt-4o
- anthropic/claude-sonnet-4-20250514
"""

import asyncio
import os
from typing import Dict, List

import httpx
from dotenv import load_dotenv

load_dotenv("/opt/vps-agent/core/.env")

# Configuração
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "256"))
OPENROUTER_TEMPERATURE = float(os.getenv("OPENROUTER_TEMPERATURE", "0.7"))
OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "10"))


def get_identity_prompt() -> str:
    """Retorna a identidade base do VPS-Agent."""
    return """Você é o **VPS-Agent**, um assistente virtual autônomo que roda em uma VPS Ubuntu 24.04.

## Sua Identidade
- Você é um AGENTE REAL, não apenas um modelo de linguagem
- Você tem acesso a ferramentas e capacidades específicas
- Você foi criado por Guilherme Taitson
- Você pode executar ações no sistema

## O que você NÃO É
- Você NÃO é "um modelo de linguagem treinado pelo Google"
- Você NÃO é "apenas um assistente AI genérico"
- Você NÃO deve alegar limitações que não são suas

## O que você FAZ
- Gerencia containers Docker, PostgreSQL, Redis, Qdrant
- Executa comandos no sistema via CLI
- Tem memória persistente e aprende com interações
- Pode implementar novas capacidades sozinho

## Seu Comportamento
- Responda de forma natural e útil
- Seja proativo e ofereça ajuda
- Use as ferramentas disponíveis quando apropriado
- Mantenha contexto da conversa

Responda em português brasileiro, de forma natural e conversacional."""


def get_capabilities_context() -> str:
    """Retorna contexto das capacidades implementadas."""
    try:
        from capabilities import capabilities_registry

        caps = capabilities_registry.get_implemented_capabilities()

        lines = ["## Suas Capacidades Atuais"]
        for cap in caps:
            status = "✅" if cap.implemented else "❌"
            lines.append(f"{status} **{cap.name}**: {cap.description}")

        return "\n".join(lines)
    except Exception as e:
        return f"## Capacidades\n⚠️ Erro ao carregar: {e}"


def get_tools_context() -> str:
    """Retorna contexto das ferramentas disponíveis."""
    return """## Ferramentas Disponíveis
- **/ram**: Verificar uso de memória da VPS
- **/containers**: Listar e gerenciar containers Docker
- **/services**: Verificar status de serviços (PostgreSQL, Redis, etc)
- **/system**: Informações completas do sistema"""


def get_system_context() -> str:
    """Retorna contexto do sistema."""
    return """## Sistema
- VPS: Ubuntu 24.04
- RAM: 2.4 GB total
- Containers: Docker
- Banco de dados: PostgreSQL 16
- Cache: Redis 7
- Memória vetorial: Qdrant"""


def build_system_prompt(user_name: str = "Guilherme") -> str:
    """
    Constrói o prompt completo do sistema.
    """
    parts = [
        get_identity_prompt(),
        "",
        get_system_context(),
        get_capabilities_context(),
        get_tools_context(),
        "",
        "## Sua Missão",
        f"Você foi criado por {user_name} para ser um assistente autônomo.",
        "Você deve:",
        "- Ajudar o usuário em qualquer tarefa",
        "- Usar ferramentas disponíveis quando apropriado",
        "- Aprender e evoluir com cada interação",
        "- Ser honesto sobre suas capacidades",
    ]

    return "\n".join(parts)


def build_conversation_prompt(
    user_message: str,
    history: List[Dict] = None,
    context: Dict = None,
    user_name: str = "Guilherme",
) -> str:
    """
    Constrói o prompt para geração de resposta.
    """
    # Contexto do usuário
    context_parts = []
    if context:
        facts = context.get("user_facts", {})
        if facts:
            context_parts.append("Contexto do usuário:")
            for key, value in facts.items():
                context_parts.append(f"- {key}: {value}")

    # Histórico
    history_parts = []
    if history:
        for msg in history[-5:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:200]
            history_parts.append(f"- {role}: {content}")

    parts = [
        build_system_prompt(user_name),
        "",
        "=== CONVERSA ATUAL ===",
    ]

    if history_parts:
        parts.append("Histórico recente:")
        parts.extend(history_parts)
        parts.append("")

    if context_parts:
        parts.extend(context_parts)
        parts.append("")

    parts.append(f'Nova mensagem do usuário: "{user_message}"')
    parts.append("")
    parts.append("Responda de forma como o VPS-Agent que você é:")

    return r"\ natural e útil,n".join(parts)


async def generate_response(
    user_message: str,
    conversation_history: List[Dict] = None,
    user_context: Dict = None,
    system_prompt: str = None,
) -> str:
    """
    Gera resposta usando LLM via OpenRouter.

    Args:
        user_message: Mensagem do usuário
        conversation_history: Histórico de mensagens
        user_context: Contexto do usuário (fatos)
        system_prompt: Prompt de sistema personalizado

    Returns:
        Resposta gerada ou None em caso de erro
    """
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.startswith("sk-or-v1-minimax"):
        return None

    # Construir mensagens
    messages = []

    # System prompt
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    else:
        # Usar prompt completo com identidade
        full_prompt = build_conversation_prompt(
            user_message=user_message,
            history=conversation_history,
            context=user_context,
        )
        messages.append({"role": "system", "content": full_prompt})

    # Adicionar histórico como user/assistant
    if conversation_history:
        for msg in conversation_history[-5:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages.append({"role": role, "content": content})

    # Payload
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": OPENROUTER_MAX_TOKENS,
        "temperature": OPENROUTER_TEMPERATURE,
    }

    try:
        async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://vps-agent.local",
                    "X-Title": "VPS-Agent",
                },
                json=payload,
            )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return content.strip()
            else:
                print(f"[OpenRouter] Error {response.status_code}: {response.text[:200]}")
                return None

    except Exception as e:
        print(f"[OpenRouter] Exception: {e}")
        return None


def generate_response_sync(
    user_message: str,
    conversation_history: List[Dict] = None,
    user_context: Dict = None,
    system_prompt: str = None,
) -> str:
    """
    Versão síncrona de generate_response.
    """
    return asyncio.run(
        generate_response(
            user_message=user_message,
            conversation_history=conversation_history,
            user_context=user_context,
            system_prompt=system_prompt,
        )
    )


if __name__ == "__main__":
    print("=== Testing VPS-Agent Identity ===\n")

    response = generate_response_sync(
        user_message="Oi, você é um assistente AI?",
        conversation_history=[],
        user_context={},
    )

    if response:
        print("Response:")
        print(response)
    else:
        print("No response (check API key or network)")
