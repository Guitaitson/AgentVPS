"""
Skill: Shell Exec — Executa comandos na VPS com segurança.

Classificação de comandos:
  SAFE:       ls, cat, df, uptime, whoami, pwd, free, ps, docker ps
  MODERATE:   apt list, pip list, git status, find
  DANGEROUS:  rm, kill, systemctl, docker stop/rm, apt install, pip install
  FORBIDDEN:  rm -rf /, chmod 777, dd if=, mkfs, iptables -F

Este skill é uma FUNÇÃO PURA:
- Recebe 'command' como argumento estruturado (do function calling)
- Classifica segurança
- Executa o comando
- Retorna output RAW (o LLM formata a resposta)
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
    """
    Executa comandos shell com classificação de segurança.

    Este skill é uma FUNÇÃO PURA:
    - Recebe 'command' como argumento estruturado
    - Retorna output RAW (sem formatação)
    - A formatação da resposta é feita pelo LLM
    """

    async def execute(self, args: Dict[str, Any] = None) -> str:
        # Receber command estruturado (do function calling) ou raw_input (fallback)
        command = (args or {}).get("command", "")

        # Fallback: se não recebeu command estruturado, tentar raw_input
        if not command:
            command = (args or {}).get("raw_input", "")

        if not command:
            return "ERROR: Nenhum comando fornecido. Use: shell_exec(command='ls -la')"

        # Limpar prefixos comuns (apenas para raw_input fallback)
        command_clean = command.strip()
        for prefix in [
            "execute ",
            "executar ",
            "rodar ",
            "run ",
            "me mostra ",
            "mostre ",
            "liste ",
        ]:
            if command_clean.lower().startswith(prefix):
                command_clean = command_clean[len(prefix) :].strip()
                break

        if command_clean != command:
            command = command_clean

        # Classificar segurança
        level = classify_command(command)

        if level == SecurityLevel.FORBIDDEN:
            return f"ERROR: Comando PROIBIDO: {command}"

        if level == SecurityLevel.DANGEROUS:
            return f"WARNING: Comando PERIGOSO requer aprovação: {command}"

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

            # Truncar output longo se necessário
            max_chars = self.config.max_output_chars
            if len(output) > max_chars:
                output = output[:max_chars] + f"\n... [truncated {len(output)} chars]"

            # Retornar output RAW (sem formatação)
            # O LLM via node_format_response vai formatar a resposta
            if errors:
                return f"{output}\n[stderr: {errors}]"
            return output

        except asyncio.TimeoutError:
            return f"ERROR: Timeout after {self.config.timeout_seconds}s: {command}"
        except Exception as e:
            return f"ERROR: {e}"
