"""
System Tools - Ferramentas para execução na VPS.

Funções que executam comandos reais na VPS via subprocess.
Decoradas para serem usadas como tools pelo LLM.
"""

import asyncio
import os
import subprocess


def get_ram_usage() -> str:
    """
    Get current RAM usage in MB.

    Usa /proc/meminfo para compatibilidade universal (funciona sem 'free').

    Returns:
        Formatted string with RAM information
    """
    try:
        # Ler /proc/meminfo (funciona em qualquer Linux)
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()

        # Parse valores (em KB)
        mem_total = 0
        mem_available = 0
        mem_free = 0
        buffers = 0
        cached = 0

        for line in meminfo.strip().split("\n"):
            if line.startswith("MemTotal:"):
                mem_total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                mem_available = int(line.split()[1])
            elif line.startswith("MemFree:"):
                mem_free = int(line.split()[1])
            elif line.startswith("Buffers:"):
                buffers = int(line.split()[1])
            elif line.startswith("Cached:"):
                cached = int(line.split()[1])

        # Se MemAvailable não existe (kernels antigos), calcular
        if mem_available == 0:
            mem_available = mem_free + buffers + cached

        # Converter para MB
        total_mb = mem_total // 1024
        available_mb = mem_available // 1024
        used_mb = (mem_total - mem_available) // 1024

        # Calcular porcentagem
        usage_pct = (used_mb / total_mb) * 100 if total_mb > 0 else 0

        return (
            f"🧠 **Uso de RAM**\n\n"
            f"Total: {total_mb} MB\n"
            f"Usado: {used_mb} MB ({usage_pct:.1f}%)\n"
            f"Disponível: {available_mb} MB\n"
            f"Por Processos: `cat /proc/meminfo | grep -E '^(Mem|Swap)'`"
        )

    except FileNotFoundError:
        return "❌ /proc/meminfo não encontrado (sistema não é Linux?)"
    except Exception as e:
        return f"❌ Erro ao ler RAM: {str(e)}"


def list_docker_containers() -> str:
    """
    List all running Docker containers.

    Returns:
        Formatted table with container information
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return f"❌ Erro Docker: {result.stderr}"

        if not result.stdout.strip():
            return "📦 **Containers Docker**\n\nNenhum container ativo"

        lines = result.stdout.strip().split("\n")
        formatted = ["📦 **Containers Docker**\n"]
        formatted.append("```")
        formatted.append(f"{'NOME':<20} {'STATUS':<15} {'PORTAS'}")
        formatted.append("-" * 55)

        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 2:
                name = parts[0][:18]
                status = parts[1][:13]
                ports = parts[2] if len(parts) > 2 else "-"
                formatted.append(f"{name:<20} {status:<15} {ports}")

        formatted.append("```")
        return "\n".join(formatted)

    except subprocess.TimeoutExpired:
        return "❌ Timeout ao listar containers"
    except FileNotFoundError:
        return "❌ Docker não instalado ou não encontrado"
    except Exception as e:
        return f"❌ Erro: {str(e)}"


def get_system_status() -> str:
    """
    Get overall system status.

    Returns:
        Summary of system health
    """

    checks = []

    # Check RAM (usando /proc/meminfo)
    try:
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()

        mem_total = 0
        mem_available = 0

        for line in meminfo.strip().split("\n"):
            if line.startswith("MemTotal:"):
                mem_total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                mem_available = int(line.split()[1])

        if mem_total > 0:
            usage_pct = ((mem_total - mem_available) / mem_total) * 100

            if usage_pct > 90:
                checks.append(("🚨 RAM", f"{usage_pct:.0f}% - CRÍTICO"))
            elif usage_pct > 75:
                checks.append(("⚠️  RAM", f"{usage_pct:.0f}% - Alto"))
            else:
                checks.append(("✅ RAM", f"{usage_pct:.0f}% - OK"))
        else:
            checks.append(("❌ RAM", "Não disponível"))
    except Exception:
        checks.append(("❌ RAM", "Não disponível"))

    # Check Disk
    try:
        result = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True,
            text=True,
            timeout=5
        )
        lines = result.stdout.strip().split("\n")
        disk_line = lines[1].split()
        usage = disk_line[4].replace("%", "")

        if int(usage) > 90:
            checks.append(("🚨 Disco", f"{usage}% - CRÍTICO"))
        elif int(usage) > 75:
            checks.append(("⚠️  Disco", f"{usage}% - Alto"))
        else:
            checks.append(("✅ Disco", f"{usage}% - OK"))
    except Exception:
        checks.append(("❌ Disco", "Não disponível"))

    # Check Docker
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            checks.append(("✅ Docker", f"v{version}"))
        else:
            checks.append(("❌ Docker", "Indisponível"))
    except Exception:
        checks.append(("❌ Docker", "Não instalado"))

    # Format output
    formatted = ["📊 **Status do Sistema**\n"]
    for name, status in checks:
        formatted.append(f"{name}: {status}")

    return "\n".join(formatted)


def check_postgres() -> str:
    """
    Check PostgreSQL connection.

    Returns:
        Status of PostgreSQL service
    """
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "vps_agent"),
            user=os.getenv("POSTGRES_USER", "vps_agent"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            connect_timeout=5
        )

        # Get version
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0].split()[1]

        # Get database size
        cursor.execute("""
            SELECT pg_size_pretty(pg_database_size(%s));
        """, (os.getenv("POSTGRES_DB", "vps_agent"),))
        size = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return (
            f"✅ **PostgreSQL**\n\n"
            f"Status: Online\n"
            f"Versão: {version}\n"
            f"Tamanho: {size}"
        )

    except psycopg2.OperationalError as e:
        return f"❌ **PostgreSQL**\n\nNão conecta: {str(e)}"
    except Exception as e:
        return f"❌ **PostgreSQL**\n\nErro: {str(e)}"


def check_redis() -> str:
    """
    Check Redis connection.

    Returns:
        Status of Redis service
    """
    try:
        import redis

        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD") or None,
            socket_timeout=5,
            socket_connect_timeout=5
        )

        # Test connection
        r.ping()

        # Get info
        info = r.info()
        version = info.get("redis_version", "unknown")
        used_memory = info.get("used_memory_human", "unknown")
        keys_count = r.dbsize()

        return (
            f"✅ **Redis**\n\n"
            f"Status: Online\n"
            f"Versão: {version}\n"
            f"Memória usada: {used_memory}\n"
            f"Chaves: {keys_count}"
        )

    except redis.ConnectionError:
        return "❌ **Redis**\n\nNão conecta: Connection refused"
    except redis.TimeoutError:
        return "❌ **Redis**\n\nTimeout na conexão"
    except Exception as e:
        return f"❌ **Redis**\n\nErro: {str(e)}"


# Async versions for modern LangGraph (Python 3.9+)
async def get_ram_usage_async() -> str:
    """Async version of get_ram_usage."""
    return await asyncio.to_thread(get_ram_usage)


async def list_docker_containers_async() -> str:
    """Async version of list_docker_containers."""
    return await asyncio.to_thread(list_docker_containers)


async def get_system_status_async() -> str:
    """Async version of get_system_status."""
    return await asyncio.to_thread(get_system_status)


async def check_postgres_async() -> str:
    """Async version of check_postgres."""
    return await asyncio.to_thread(check_postgres)


async def check_redis_async() -> str:
    """Async version of check_redis."""
    return await asyncio.to_thread(check_redis)


# Import discovery tools (async nativo)
try:
    from .discovery_tools_async import (
        check_command_available_async,
        get_installed_packages_async,
        get_system_info_async,
    )
    _discovery_available = True
except ImportError:
    _discovery_available = False

    # Fallback para versões com to_thread
    from .discovery_tools import (
        check_command_available_async,
        get_installed_packages_async,
        get_system_info_async,
    )


# Tool registry for LLM
TOOLS_REGISTRY = {
    "get_ram": {
        "function": get_ram_usage,
        "async_function": get_ram_usage_async,
        "description": "Get current RAM usage in MB",
        "parameters": {},
    },
    "list_containers": {
        "function": list_docker_containers,
        "async_function": list_docker_containers_async,
        "description": "List all running Docker containers",
        "parameters": {},
    },
    "get_system_status": {
        "function": get_system_status,
        "async_function": get_system_status_async,
        "description": "Get overall system status (RAM, disk, Docker)",
        "parameters": {},
    },
    "check_postgres": {
        "function": check_postgres,
        "async_function": check_postgres_async,
        "description": "Check PostgreSQL connection and status",
        "parameters": {},
    },
    "check_redis": {
        "function": check_redis,
        "async_function": check_redis_async,
        "description": "Check Redis connection and status",
        "parameters": {},
    },
    # Discovery tools
    "get_installed_packages": {
        "function": get_installed_packages_async,
        "async_function": get_installed_packages_async,
        "description": "List installed packages and applications on the VPS",
        "parameters": {},
    },
    "check_command": {
        "function": check_command_available_async,
        "async_function": check_command_available_async,
        "description": "Check if a specific command is available",
        "parameters": {"command": "Command name to check"},
    },
    "get_system_info": {
        "function": get_system_info_async,
        "async_function": get_system_info_async,
        "description": "Show general system information (OS, kernel, uptime)",
        "parameters": {},
    },
}


def get_tool(name: str):
    """Get tool by name."""
    tool = TOOLS_REGISTRY.get(name)
    if tool:
        return tool["function"]
    return None


def get_async_tool(name: str):
    """Get async tool by name."""
    tool = TOOLS_REGISTRY.get(name)
    if tool:
        return tool["async_function"]
    return None


def list_tools() -> list[dict]:
    """List all available tools."""
    return [
        {
            "name": name,
            "description": info["description"],
            "parameters": info["parameters"],
        }
        for name, info in TOOLS_REGISTRY.items()
    ]


__all__ = [
    "get_ram_usage",
    "list_docker_containers",
    "get_system_status",
    "check_postgres",
    "check_redis",
    "get_ram_usage_async",
    "list_docker_containers_async",
    "get_system_status_async",
    "check_postgres_async",
    "check_redis_async",
    "get_tool",
    "get_async_tool",
    "list_tools",
    "TOOLS_REGISTRY",
]
