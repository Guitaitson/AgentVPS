"""
Resource Manager — Gerencia RAM subindo/descendo containers sob demanda.
Regra: nunca ultrapassar 2.4 GB total. Serviços core (~750 MB) sempre ligados.
"""

import os
import subprocess

import structlog

logger = structlog.get_logger()

# Configuração das ferramentas sob demanda
TOOLS_CONFIG = {
    "qdrant": {
        "compose_file": "/opt/vps-agent/tools/qdrant/docker-compose.yml",
        "ram_mb": 400,
        "health_cmd": "curl -sf http://127.0.0.1:6333/healthz",
        "description": "Busca vetorial / memória semântica",
    },
    "n8n": {
        "compose_file": "/opt/vps-agent/tools/n8n/docker-compose.yml",
        "ram_mb": 300,
        "health_cmd": "curl -sf http://127.0.0.1:5678/healthz",
        "description": "Automações no-code",
    },
    "flowise": {
        "compose_file": "/opt/vps-agent/tools/flowise/docker-compose.yml",
        "ram_mb": 350,
        "health_cmd": "curl -sf http://127.0.0.1:3000",
        "description": "Fluxos de LLM visuais",
    },
    "evolution-api": {
        "compose_file": "/opt/vps-agent/tools/evolution-api/docker-compose.yml",
        "ram_mb": 250,
        "health_cmd": "curl -sf http://127.0.0.1:8080/health",
        "description": "WhatsApp integration",
    },
}

# RAM reservada para core (PostgreSQL + Redis + Bot + LangGraph)
CORE_RAM_MB = 750
# RAM total da VPS
TOTAL_RAM_MB = 2400
# Margem de segurança
SAFETY_MARGIN_MB = 200


def get_available_ram() -> int:
    """Retorna RAM disponível em MB."""
    result = subprocess.run(["free", "-m"], capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")
    return int(lines[1].split()[6])


def get_running_tools() -> list:
    """Retorna lista de ferramentas sob demanda rodando."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True
    )
    containers = result.stdout.strip().split("\n") if result.stdout.strip() else []

    running = []
    for tool_name, config in TOOLS_CONFIG.items():
        # Verifica se algum container da ferramenta está rodando
        if any(tool_name in c for c in containers):
            running.append(tool_name)
    return running


def can_start_tool(tool_name: str) -> tuple[bool, str]:
    """Verifica se é possível iniciar uma ferramenta."""
    if tool_name not in TOOLS_CONFIG:
        return False, f"Ferramenta '{tool_name}' não existe."

    available = get_available_ram()
    needed = TOOLS_CONFIG[tool_name]["ram_mb"]
    running = get_running_tools()

    if tool_name in running:
        return False, f"'{tool_name}' já está rodando."

    if len(running) >= 2:
        return False, (
            f"Já existem 2 ferramentas rodando ({', '.join(running)}). "
            f"Pare uma antes de iniciar outra."
        )

    if available < needed + SAFETY_MARGIN_MB:
        return False, (
            f"RAM insuficiente. Disponível: {available}MB. "
            f"Necessário: {needed}MB + {SAFETY_MARGIN_MB}MB margem."
        )

    return True, "OK"


def start_tool(tool_name: str) -> tuple[bool, str]:
    """Inicia uma ferramenta sob demanda."""
    can_start, reason = can_start_tool(tool_name)
    if not can_start:
        return False, reason

    config = TOOLS_CONFIG[tool_name]
    compose_file = config["compose_file"]

    if not os.path.exists(compose_file):
        return False, f"Arquivo compose não encontrado: {compose_file}"

    logger.info("iniciando_ferramenta", tool=tool_name, ram_estimada=config["ram_mb"])

    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d"], capture_output=True, text=True
    )

    if result.returncode != 0:
        return False, f"Erro ao iniciar: {result.stderr[:300]}"

    return True, f"✅ {tool_name} iniciado com sucesso."


def stop_tool(tool_name: str) -> tuple[bool, str]:
    """Para uma ferramenta sob demanda."""
    if tool_name not in TOOLS_CONFIG:
        return False, f"Ferramenta '{tool_name}' não existe."

    config = TOOLS_CONFIG[tool_name]
    compose_file = config["compose_file"]

    if not os.path.exists(compose_file):
        return False, f"Arquivo compose não encontrado: {compose_file}"

    logger.info("parando_ferramenta", tool=tool_name)

    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "down"], capture_output=True, text=True
    )

    if result.returncode != 0:
        return False, f"Erro ao parar: {result.stderr[:300]}"

    return True, f"✅ {tool_name} parado."


def get_tools_status() -> dict:
    """Retorna status de todas as ferramentas."""
    running = get_running_tools()
    available_ram = get_available_ram()

    status = {}
    for name, config in TOOLS_CONFIG.items():
        is_running = name in running
        can_start_it, reason = can_start_tool(name) if not is_running else (False, "Já rodando")

        status[name] = {
            "running": is_running,
            "ram_mb": config["ram_mb"],
            "can_start": can_start_it,
            "reason": reason if not can_start_it and not is_running else "",
            "description": config["description"],
        }

    return {
        "tools": status,
        "running_count": len(running),
        "available_ram_mb": available_ram,
        "max_simultaneous": 2,
    }
