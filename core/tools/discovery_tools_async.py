"""
Discovery Tools - Versões 100% Async

Usa asyncio.create_subprocess_exec para não bloquear o event loop.
"""

import asyncio
import os
from typing import Optional

import structlog

logger = structlog.get_logger()


async def _run_command(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """
    Executa comando de forma async.

    Returns:
        Tuple de (returncode, stdout, stderr)
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout
        )

        return (
            proc.returncode or 0,
            stdout.decode('utf-8', errors='ignore'),
            stderr.decode('utf-8', errors='ignore')
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except:
            pass
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


async def get_installed_packages_async() -> str:
    """
    Lista pacotes instalados no sistema (async).
    """
    results = []

    # Método 1: dpkg (Debian/Ubuntu)
    returncode, stdout, stderr = await _run_command(["dpkg", "-l"], timeout=10)
    if returncode == 0:
        lines = stdout.strip().split("\n")[:20]
        results.append("📦 **Pacotes (dpkg):**\n")
        for line in lines[5:]:
            parts = line.split()
            if len(parts) >= 3:
                name = parts[1]
                version = parts[2]
                results.append(f"  • {name} ({version})")
        results.append("\n")

    # Método 2: Verificar comandos comuns
    common_commands = [
        "python3", "python", "node", "npm", "docker", "docker-compose",
        "git", "ssh", "curl", "wget", "nginx", "apache2", "mysql", "psql",
        "redis-cli", "java", "go"
    ]

    found = []
    check_tasks = [
        _run_command(["which", cmd], timeout=2) for cmd in common_commands
    ]
    check_results = await asyncio.gather(*check_tasks, return_exceptions=True)

    for cmd, result in zip(common_commands, check_results):
        if isinstance(result, tuple) and result[0] == 0:
            found.append(cmd)

    if found:
        results.append("🔧 **Comandos Disponíveis:**\n")
        results.append(", ".join(found))
        results.append("\n")

    # Método 3: Snap packages
    returncode, stdout, stderr = await _run_command(["snap", "list"], timeout=5)
    if returncode == 0:
        lines = stdout.strip().split("\n")[1:10]
        results.append("📦 **Snap Packages:**\n")
        for line in lines:
            parts = line.split()
            if parts:
                results.append(f"  • {parts[0]}")
        results.append("\n")

    if not results:
        return (
            "❌ Não consegui listar pacotes instalados.\n\n"
            "Posso verificar comandos específicos se você perguntar."
        )

    return "\n".join(results)


async def check_command_available_async(command: str) -> str:
    """
    Verifica se um comando específico está disponível (async).
    """
    # Verificar se existe
    returncode, stdout, stderr = await _run_command(["which", command], timeout=3)

    if returncode != 0:
        return f"❌ Comando '{command}' não encontrado"

    path = stdout.strip()

    # Tentar obter versão
    version = ""
    version_flags = ["--version", "-v", "-V", "version"]

    for flag in version_flags:
        returncode, stdout, stderr = await _run_command([command, flag], timeout=3)
        if returncode == 0:
            version = stdout.strip().split("\n")[0]
            break

    if version:
        return f"✅ **{command}**\nLocal: `{path}`\nVersão: `{version}`"
    else:
        return f"✅ **{command}**\nLocal: `{path}`\nVersão: não detectada"


async def get_system_info_async() -> str:
    """
    Coleta informações gerais do sistema (async).
    """
    info = []

    # OS Info
    try:
        with open("/etc/os-release", "r") as f:
            os_info = f.read()
        for line in os_info.strip().split("\n"):
            if line.startswith("PRETTY_NAME="):
                os_name = line.split("=")[1].strip('"')
                info.append(f"🖥️ **Sistema:** {os_name}")
                break
    except:
        info.append("🖥️ **Sistema:** Linux")

    # Kernel e Arquitetura (em paralelo)
    kernel_task = _run_command(["uname", "-r"], timeout=3)
    arch_task = _run_command(["uname", "-m"], timeout=3)

    kernel_result, arch_result = await asyncio.gather(kernel_task, arch_task)

    if kernel_result[0] == 0:
        info.append(f"🔧 **Kernel:** {kernel_result[1].strip()}")

    if arch_result[0] == 0:
        info.append(f"⚙️ **Arquitetura:** {arch_result[1].strip()}")

    # Uptime
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.read().split()[0])
            uptime_hours = uptime_seconds / 3600
            info.append(f"⏱️ **Uptime:** {uptime_hours:.1f} horas")
    except:
        pass

    # Usuário
    info.append(f"👤 **Usuário:** {os.getenv('USER', 'unknown')}")

    return "\n".join(info)


async def execute_command_async(
    command: str,
    args: Optional[list[str]] = None,
    timeout: int = 10
) -> str:
    """
    Executa um comando de forma async.
    """
    if args is None:
        args = []

    # Verificar segurança
    dangerous = ["rm", "mkfs", "dd", "shutdown", "reboot", "poweroff", "halt"]
    if command in dangerous:
        return f"⛔ Comando '{command}' bloqueado por segurança"

    returncode, stdout, stderr = await _run_command([command] + args, timeout)

    if returncode == -1:
        return f"⏱️ Timeout ao executar '{command}'"

    output = stdout.strip()
    if stderr:
        output += f"\n⚠️ stderr: {stderr.strip()[:200]}"

    if len(output) > 2000:
        output = output[:2000] + "\n... (truncado)"

    return f"✅ Comando: `{command} {' '.join(args)}`\n```\n{output}\n```"


# Exportar funções
__all__ = [
    "get_installed_packages_async",
    "check_command_available_async",
    "get_system_info_async",
    "execute_command_async",
]
