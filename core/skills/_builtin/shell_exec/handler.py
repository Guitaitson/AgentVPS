"""
Skill: Shell Exec — Executa comandos na VPS com segurança.

Classificação de comandos:
  SAFE:       ls, cat, df, uptime, whoami, pwd, free, ps, docker ps
  MODERATE:   apt list, pip list, git status, find
  DANGEROUS:  rm, kill, systemctl, docker stop/rm, apt install, pip install
  FORBIDDEN:  rm -rf /, chmod 777, dd if=, mkfs, iptables -F
"""

import asyncio
import re
from typing import Any, Dict

from core.skills.base import SecurityLevel, SkillBase


# Padrões de classificação (ordem importa: FORBIDDEN primeiro)
FORBIDDEN_PATTERNS = [
    r"rm\s+-rf\s+/\s*$",
    r"rm\s+-rf\s+/\*",
    r"chmod\s+777\s+/",
    r"dd\s+if=",
    r"mkfs\.",
    r"iptables\s+-F",
    r":\(\)\s*:\s*\|\s*:\s*&",  # Fork bomb
    r">\s*/dev/sd",
    r"wget.*\|\s*sh",
    r"curl.*\|\s*sh",
]

DANGEROUS_PATTERNS = [
    r"^rm\s",
    r"^kill\s",
    r"^killall\s",
    r"^systemctl\s+(stop|restart|disable|mask)",
    r"^docker\s+(stop|rm|rmi|prune)",
    r"^apt\s+(install|remove|purge)",
    r"^pip\s+install",
    r"^reboot",
    r"^shutdown",
    r"^passwd",
    r"^chown\s",
    r"^chmod\s",
    r"^mv\s+/",
]

SAFE_PATTERNS = [
    r"^ls\b",
    r"^cat\b",
    r"^head\b",
    r"^tail\b",
    r"^df\b",
    r"^uptime",
    r"^whoami",
    r"^pwd",
    r"^free\b",
    r"^ps\b",
    r"^docker\s+(ps|stats|logs|inspect|images)",
    r"^uname\b",
    r"^date\b",
    r"^hostname",
    r"^wc\b",
    r"^grep\b",
    r"^find\b.*-name",
    r"^echo\b",
    r"^id\b",
]


def classify_command(command: str) -> SecurityLevel:
    """Classifica nível de segurança de um comando."""
    cmd = command.strip()

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return SecurityLevel.FORBIDDEN

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return SecurityLevel.DANGEROUS

    for pattern in SAFE_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return SecurityLevel.SAFE

    # Default: MODERATE (desconhecido mas não proibido)
    return SecurityLevel.MODERATE


class ShellExecSkill(SkillBase):
    """Executa comandos shell com classificação de segurança."""

    # Mapeamento de perguntas para comandos shell
    QUESTION_TO_COMMAND = {
        # Instalação - tem X instalado?
        "tem o claude": "which claude",
        "tem claude": "which claude",
        "claude instalado": "which claude",
        "tem o docker": "which docker",
        "tem docker": "which docker",
        "docker instalado": "docker --version",
        "tem o postgres": "which psql",
        "tem postgres": "which psql",
        "postgres instalado": "psql --version",
        "tem o redis": "which redis-cli",
        "tem redis": "which redis-cli",
        "redis instalado": "redis-cli --version",
        "tem o node": "which node",
        "tem node": "which node",
        "node instalado": "node --version",
        "tem o npm": "which npm",
        "tem npm": "which npm",
        "tem o python": "which python3",
        "tem python": "which python3",
        "python instalado": "python3 --version",
        # Como ver X?
        "como ver a memoria": "free -h",
        "como ver memória": "free -h",
        "como ver ram": "free -h",
        "quanta ram": "free -h",
        "quanto память": "free -h",
        "como está a memória": "free -h",
        "como está a ram": "free -h",
        "quantos containers": "docker ps -a",
        "quais containers": "docker ps -a",
        "containers rodando": "docker ps",
        "status do sistema": "uptime && free -h && df -h",
        "estado do sistema": "uptime && free -h && df -h",
        # Versões
        "versão do": "lsb_release -a || cat /etc/os-release",
    }

    async def execute(self, args: Dict[str, Any] = None) -> str:
        raw_input = (args or {}).get("raw_input", "")
        command = (args or {}).get("command") or raw_input

        if not command:
            return "❌ Nenhum comando fornecido. Exemplo: 'execute ls -la'"

        # Detectar se é uma pergunta e extrair comando
        command = self._extract_command_from_question(command)
        
        # Limpar prefixos comuns
        for prefix in ["execute ", "executar ", "rodar ", "run ", "me mostra ", "mostre ", "liste "]:
            if command.lower().startswith(prefix):
                command = command[len(prefix):].strip()
                break

        # Classificar segurança
        level = classify_command(command)

        if level == SecurityLevel.FORBIDDEN:
            return f"🚫 Comando PROIBIDO por segurança: `{command}`\nEste comando pode causar danos irreversíveis."

        if level == SecurityLevel.DANGEROUS:
            # Retorna warning para comandos perigosos
            return (
                f"⚠️ **Comando PERIGOSO detectado**: `{command}`\n\n"
                "Este comando requer aprovação para executar.\n"
                "Deseja continuar? (Sim/Não)"
            )

        # Executar comando
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout_seconds,
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            # Truncar output longo
            max_chars = self.config.max_output_chars
            if len(output) > max_chars:
                output = output[:max_chars] + f"\n... [truncado, {len(output)} chars total]"

            # Montar resposta
            level_emoji = {
                SecurityLevel.SAFE: "✅",
                SecurityLevel.MODERATE: "⚠️",
                SecurityLevel.DANGEROUS: "🔴",
            }
            emoji = level_emoji.get(level, "⚙️")

            result = f"{emoji} `$ {command}`\n"
            if output.strip():
                result += f"```\n{output.strip()}\n```"
            if errors.strip():
                result += f"\n⚠️ stderr:\n```\n{errors.strip()}\n```"
            if process.returncode != 0:
                result += f"\n❌ Exit code: {process.returncode}"

            return result

        except asyncio.TimeoutError:
            return f"⏱️ Comando excedeu timeout de {self.config.timeout_seconds}s: `{command}`"
        except Exception as e:
            return f"❌ Erro ao executar: {e}"

    def _extract_command_from_question(self, text: str) -> str:
        """Extrai comando shell a partir de perguntas em linguagem natural."""
        text_lower = text.lower().strip()
        
        # Tentar encontrar correspondência no mapeamento
        for pattern, command in self.QUESTION_TO_COMMAND.items():
            if pattern in text_lower:
                return command
        
        # Se não encontrou mapeamento, retornar texto original
        return text
