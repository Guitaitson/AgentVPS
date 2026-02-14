"""
Discovery Tools - Ferramentas para auto-descoberta e aprendizado.

Permite ao agente:
1. Descobrir o que está instalado na VPS
2. Executar comandos genéricos de forma segura
3. Aprender e salvar novas capabilities
"""

import asyncio
import json
import os
import subprocess  # FALTANDO - necessário para executar comandos
from typing import Optional

import structlog

logger = structlog.get_logger()

# Cache de aprendizado (simples, em memória)
_learned_commands: dict[str, str] = {}


def get_installed_packages() -> str:
    """
    Lista pacotes instalados no sistema.
    
    Tenta múltiplos métodos para compatibilidade com diferentes distros.
    """
    results = []
    
    # Método 1: dpkg (Debian/Ubuntu)
    try:
        result = subprocess.run(
            ["dpkg", "-l"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[:20]  # Primeiros 20
            results.append("📦 **Pacotes (dpkg):**\n")
            for line in lines[5:]:  # Pular header
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[1]
                    version = parts[2]
                    results.append(f"  • {name} ({version})")
            results.append("\n")
    except Exception as e:
        logger.debug("dpkg_failed", error=str(e))
    
    # Método 2: apt list
    try:
        result = subprocess.run(
            ["apt", "list", "--installed"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[:15]
            results.append("📦 **Pacotes (apt):**\n")
            for line in lines[1:]:
                if "/" in line:
                    name = line.split("/")[0]
                    results.append(f"  • {name}")
            results.append("\n")
    except Exception as e:
        logger.debug("apt_failed", error=str(e))
    
    # Método 3: Verificar comandos comuns + CLIs modernos
    common_commands = [
        # Comandos tradicionais
        "python3", "python", "node", "npm", "docker", "docker-compose",
        "git", "ssh", "curl", "wget", "nginx", "apache2", "mysql", "psql",
        "redis-cli", "mongo", "java", "javac", "go", "rustc", "cargo",
        # CLIs modernos de IA/Agent
        "claude", "cline", "openai", "anthropic",
        # Tools modernas
        "bun", "pnpm", "yarn", "pnpm",
        # Cloud CLIs
        "aws", "gcloud", "az", "kubectl", "terraform", "helm",
        # DevOps
        "docker", "podman", "docker-compose", "docker-compose",
    ]
    
    found = []
    for cmd in common_commands:
        try:
            result = subprocess.run(
                ["which", cmd],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                found.append(cmd)
        except:
            pass
    
    if found:
        results.append("🔧 **Comandos Disponíveis:**\n")
        results.append(", ".join(found))
        results.append("\n")
    
    # Método 4: Snap packages
    try:
        result = subprocess.run(
            ["snap", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:10]  # Primeiros 10
            results.append("📦 **Snap Packages:**\n")
            for line in lines:
                parts = line.split()
                if parts:
                    results.append(f"  • {parts[0]}")
            results.append("\n")
    except Exception as e:
        logger.debug("snap_failed", error=str(e))
    
    if not results:
        return (
            "❌ Não consegui listar pacotes instalados.\n\n"
            "Posso verificar comandos específicos se você perguntar:\n"
            "• 'você tem python?'\n"
            "• 'tem docker instalado?'\n"
            "• 'qual versão do node?'"
        )
    
    return "\n".join(results)


def check_command_available(command: str) -> str:
    """
    Verifica se um comando específico está disponível.
    
    Args:
        command: Nome do comando (ex: 'python3', 'docker')
        
    Returns:
        Status do comando
    """
    try:
        # Verificar se existe
        result = subprocess.run(
            ["which", command],
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode != 0:
            return f"❌ Comando '{command}' não encontrado"
        
        path = result.stdout.strip()
        
        # Tentar obter versão
        version = ""
        version_flags = ["--version", "-v", "-V", "version"]
        
        for flag in version_flags:
            try:
                ver_result = subprocess.run(
                    [command, flag],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if ver_result.returncode == 0:
                    version = ver_result.stdout.strip().split("\n")[0]
                    break
            except:
                continue
        
        if version:
            return f"✅ **{command}**\nLocal: `{path}`\nVersão: `{version}`"
        else:
            return f"✅ **{command}**\nLocal: `{path}`\nVersão: não detectada"
            
    except subprocess.TimeoutExpired:
        return f"⏱️ Timeout ao verificar '{command}'"
    except Exception as e:
        return f"❌ Erro ao verificar '{command}': {str(e)}"


def get_system_info() -> str:
    """
    Coleta informações gerais do sistema.
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
        info.append("🖥️ **Sistema:** Linux (detalhes não disponíveis)")
    
    # Kernel
    try:
        result = subprocess.run(
            ["uname", "-r"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            info.append(f"🔧 **Kernel:** {result.stdout.strip()}")
    except:
        pass
    
    # Arquitetura
    try:
        result = subprocess.run(
            ["uname", "-m"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            info.append(f"⚙️ **Arquitetura:** {result.stdout.strip()}")
    except:
        pass
    
    # Uptime
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.read().split()[0])
            uptime_hours = uptime_seconds / 3600
            info.append(f"⏱️ **Uptime:** {uptime_hours:.1f} horas")
    except:
        pass
    
    # Usuário atual
    info.append(f"👤 **Usuário:** {os.getenv('USER', 'unknown')}")
    
    return "\n".join(info)


def execute_discovered_command(
    command: str,
    args: Optional[list[str]] = None,
    timeout: int = 10
) -> str:
    """
    Executa um comando descoberto dinamicamente.
    
    Args:
        command: Comando principal
        args: Argumentos opcionais
        timeout: Timeout em segundos
        
    Returns:
        Resultado da execução
    """
    if args is None:
        args = []
    
    # Verificar se comando está na allowlist (básica)
    dangerous = ["rm", "mkfs", "dd", "shutdown", "reboot", "poweroff"]
    if command in dangerous:
        return f"⛔ Comando '{command}' bloqueado por segurança"
    
    try:
        result = subprocess.run(
            [command] + args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = result.stdout.strip()
        if result.stderr:
            output += f"\n⚠️ stderr: {result.stderr.strip()[:200]}"
        
        # Limitar output
        if len(output) > 2000:
            output = output[:2000] + "\n... (truncado)"
        
        return (
            f"✅ Comando: `{command} {' '.join(args)}`\n"
            f"```\n{output}\n```"
        )
        
    except subprocess.TimeoutExpired:
        return f"⏱️ Timeout ao executar '{command}'"
    except FileNotFoundError:
        return f"❌ Comando '{command}' não encontrado"
    except Exception as e:
        return f"❌ Erro: {str(e)}"


def learn_command(query: str, command: str) -> str:
    """
    Salva um comando aprendido para futuras consultas.
    
    Args:
        query: Pergunta/tipo de consulta (ex: "listar pacotes")
        command: Comando que resolve (ex: "dpkg -l")
        
    Returns:
        Confirmação
    """
    _learned_commands[query.lower()] = command
    logger.info("command_learned", query=query, command=command)
    return f"✅ Aprendi: '{query}' → `{command}`"


def get_learned_command(query: str) -> Optional[str]:
    """
    Recupera um comando previamente aprendido.
    
    Args:
        query: Pergunta a buscar
        
    Returns:
        Comando aprendido ou None
    """
    return _learned_commands.get(query.lower())


def list_learned_commands() -> str:
    """
    Lista todos os comandos aprendidos.
    """
    if not _learned_commands:
        return "📚 Nenhum comando aprendido ainda."
    
    lines = ["📚 **Comandos Aprendidos:**\n"]
    for query, command in _learned_commands.items():
        lines.append(f"• '{query}' → `{command}`")
    
    return "\n".join(lines)


# Async versions
import asyncio


async def get_installed_packages_async() -> str:
    """Async version."""
    return await asyncio.to_thread(get_installed_packages)


async def check_command_available_async(command: str) -> str:
    """Async version."""
    return await asyncio.to_thread(check_command_available, command)


async def get_system_info_async() -> str:
    """Async version."""
    return await asyncio.to_thread(get_system_info)


async def execute_discovered_command_async(
    command: str,
    args: Optional[list[str]] = None,
    timeout: int = 10
) -> str:
    """Async version."""
    return await asyncio.to_thread(execute_discovered_command, command, args, timeout)


# Registry
DISCOVERY_TOOLS_REGISTRY = {
    "get_installed_packages": {
        "function": get_installed_packages,
        "async_function": get_installed_packages_async,
        "description": "Lista pacotes e aplicativos instalados na VPS",
        "parameters": {},
    },
    "check_command": {
        "function": check_command_available,
        "async_function": check_command_available_async,
        "description": "Verifica se um comando específico está disponível",
        "parameters": {
            "command": "Nome do comando a verificar"
        },
    },
    "get_system_info": {
        "function": get_system_info,
        "async_function": get_system_info_async,
        "description": "Mostra informações gerais do sistema",
        "parameters": {},
    },
    "execute_command": {
        "function": execute_discovered_command,
        "async_function": execute_discovered_command_async,
        "description": "Executa um comando do sistema (com restrições de segurança)",
        "parameters": {
            "command": "Comando principal",
            "args": "Lista de argumentos (opcional)",
        },
    },
}


__all__ = [
    "get_installed_packages",
    "check_command_available",
    "get_system_info",
    "execute_discovered_command",
    "learn_command",
    "get_learned_command",
    "list_learned_commands",
    "DISCOVERY_TOOLS_REGISTRY",
]
