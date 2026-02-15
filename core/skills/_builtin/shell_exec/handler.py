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
    """Executa comandos shell com classificação de segurança e interpretação inteligente."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        raw_input = (args or {}).get("raw_input", "")
        command = (args or {}).get("command") or raw_input

        if not command:
            return "❌ Nenhum comando fornecido. Exemplo: 'execute ls -la'"

        # Detectar se é uma pergunta e usar LLM para interpretar
        command = await self._interpret_and_generate_command(command, raw_input)
        
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

            # ============================================================
            # GERAR RESPOSTA CONVERSACIONAL
            # ============================================================
            
            # Detectar tipo de pergunta para gerar resposta adequada
            user_input_lower = raw_input.lower() if raw_input else ""
            
            # Respostas para perguntas sobre instalação
            if "tem o" in user_input_lower or "tem " in user_input_lower or "esta instalado" in user_input_lower or "está instalado" in user_input_lower:
                if output.strip() and process.returncode == 0:
                    # Encontrou o programa
                    return f"✅ Sim, está instalado em: `{output.strip()}`"
                else:
                    # Não encontrou - tentar extrair nome
                    programa = self._extract_program_name(user_input_lower)
                    if programa:
                        return f"❌ Não, **{programa}** não está instalado na VPS."
                    return "❌ Não encontrei o programa na VPS."
            
            # Respostas para perguntas sobre versão
            if any(p in user_input_lower for p in ["versão", "versao", "version"]):
                if output.strip() and process.returncode == 0:
                    return f"📋 Versão: `{output.strip()}`"
                else:
                    return "❌ Não foi possível obter a versão."
            
            # Respostas para perguntas sobre RAM
            if any(p in user_input_lower for p in ["memoria", "memória", "ram", "quanta ram", "quanto ram"]):
                if output.strip():
                    lines = output.strip().split('\n')
                    if len(lines) >= 2:
                        # Parse free -h output
                        parts = lines[1].split()
                        if len(parts) >= 2:
                            total = parts[1] if len(parts) > 1 else "?"
                            used = parts[2] if len(parts) > 2 else "?"
                            free = parts[3] if len(parts) > 3 else "?"
                            return f"💾 Memória RAM:\n• Total: {total}\n• Usado: {used}\n• Livre: {free}"
                    return f"💾 {output.strip()}"
            
            # Respostas para perguntas sobre containers
            if any(p in user_input_lower for p in ["container", "docker", "quantos container", "quantos docker"]):
                lines = output.strip().split('\n')
                count = len(lines) - 1  # Remove header
                if count > 0:
                    return f"🐳 {count} container(s) encontrado(s):\n```\n{output.strip()}\n```"
                return "🐳 Nenhum container rodando no momento."
            
            # Respostas para perguntas sobre disco
            if any(p in user_input_lower for p in ["disco", "espaço", "hd", "quanto espaç"]):
                if output.strip():
                    return f"💽 Espaço em disco:\n```\n{output.strip()}\n```"
            
            # Respostas para perguntas sobre processos
            if any(p in user_input_lower for p in ["processo", "processos", "rodando"]):
                lines = output.strip().split('\n')
                count = len(lines)
                return f"📊 {count} processos encontrados:\n```\n{output.strip()}\n```"
            
            # Respostas para perguntas sobre hostname
            if any(p in user_input_lower for p in ["hostname", "nome da maquina", "nome da máquina"]):
                return f"🏷️ Hostname: `{output.strip()}`"
            
            # Respostas para perguntas sobre usuário
            if any(p in user_input_lower for p in ["quem sou", "qual usuario", "qual usuário"]):
                return f"👤 Você é: `{output.strip()}`"
            
            # Respostas para perguntas sobre uptime
            if any(p in user_input_lower for p in ["uptime", "tempo ligado", "quanto tempo"]):
                return f"⏱️ Uptime: {output.strip()}"
            
            # Resposta padrão para outros comandos
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

    def _extract_program_name(self, text: str) -> str:
        """Extrai nome do programa da pergunta."""
        text_lower = text.lower()
        
        # Padrões comuns
        patterns = [
            "tem o ",
            "tem ",
            "esta instalado",
            "está instalado",
            "versão do ",
            "versao do ",
            "version do ",
            "version of ",
        ]
        
        for pattern in patterns:
            if pattern in text_lower:
                parte = text_lower.split(pattern)[1]
                # Pegar primeira palavra
                programa = parte.split()[0] if parte.split() else ""
                # Limpar pontuação
                programa = programa.strip("?!.,")
                if programa and len(programa) > 1:
                    return programa
        
        return ""

    async def _interpret_and_generate_command(self, user_input: str, raw_input: str = "") -> str:
        """
        Usa LLM para interpretar a pergunta do usuário e gerar o comando shell adequado.
        
        Este é o "Agente Interpretador" - transforma linguagem natural em comandos.
        """
        import structlog
        logger = structlog.get_logger()
        
        user_input_lower = user_input.lower().strip()
        
        # ============================================================
        # HEURÍSTICAS RÁPIDAS - casos comuns que não precisam de LLM
        # ============================================================
        
        # Se já parece um comando shell válido, não precisa interpretar
        shell_keywords = ["ls", "cd", "cat", "grep", "find", "docker", "apt", "pip", "git", "curl", "wget", "which", "psql", "redis", "free", "df", "ps", "whoami", "hostname", "uptime"]
        if any(user_input_lower.startswith(kw) for kw in shell_keywords):
            return user_input
        
        # Se tem "execute" ou prefixos claros
        for prefix in ["execute ", "executar ", "rode ", "roda ", "run "]:
            if user_input_lower.startswith(prefix):
                return user_input[len(prefix):].strip()
        
        # ============================================================
        # PERGUNTAS COMUNS - mapear diretamente para comandos
        # ============================================================
        
        # Detectar perguntas sobre instalação
        if "tem o" in user_input_lower or "tem " in user_input_lower or "esta instalado" in user_input_lower or "está instalado" in user_input_lower:
            programa = self._extract_program_name(user_input_lower)
            if programa:
                logger.info("shell_heuristic_installed", programa=programa)
                return f"which {programa}"
        
        # Detectar perguntas sobre versão
        if any(p in user_input_lower for p in ["versão", "versao", "version"]):
            programa = self._extract_program_name(user_input_lower)
            if programa:
                logger.info("shell_heuristic_version", programa=programa)
                # Tentar vários comandos de versão
                return f"{programa} --version 2>/dev/null || {programa} -v 2>/dev/null || which {programa}"
        
        # Detectar perguntas sobre RAM
        if any(p in user_input_lower for p in ["memoria", "memória", "ram", "quanta ram", "quanto ram", "como está a memoria"]):
            return "free -h"
        
        # Detectar perguntas sobre containers
        if any(p in user_input_lower for p in ["container", "docker", "quantos container", "quantos docker"]):
            return "docker ps"
        
        # Detectar perguntas sobre disco
        if any(p in user_input_lower for p in ["disco", "espaço", "hd", "quanto espaç"]):
            return "df -h"
        
        # Detectar perguntas sobre processos
        if any(p in user_input_lower for p in ["processo", "processos", "rodando"]):
            return "ps aux"
        
        # Detectar perguntas sobre hostname
        if any(p in user_input_lower for p in ["hostname", "nome da maquina", "nome da máquina"]):
            return "hostname"
        
        # Detectar perguntas sobre usuário
        if any(p in user_input_lower for p in ["quem sou", "qual usuario", "qual usuário"]):
            return "whoami"
        
        # Detectar perguntas sobre uptime
        if any(p in user_input_lower for p in ["uptime", "tempo ligado", "quanto tempo"]):
            return "uptime"
        
        # ============================================================
        # LLM - para casos não cobertos pelas heurísticas
        # ============================================================
        
        try:
            from core.llm.unified_provider import get_llm_provider
            
            system_prompt = """Você é um Interpretador de Comandos Shell.
O usuário faz uma pergunta em linguagem natural e você deve gerar o comando shell adequado.

Regras:
1. Interprete o que o usuário quer saber
2. Gere o comando shell correto para obter essa informação
3. Retorne APENAS o comando, sem explicações

Exemplos:
- "tem o claude instalado?" → "which claude"
- "tem o docker?" → "which docker"
- "quanta ram temos?" → "free -h"
- "quantos containers estão rodando?" → "docker ps"
- "qual o status do sistema?" → "uptime && free -h && df -h"
- "como está a memória?" → "free -h"
- "quais processos estão rodando?" → "ps aux"
- "espaço em disco?" → "df -h"
- "quem sou eu?" → "whoami"
- "qual hostname?" → "hostname"
- "versão do python?" → "python3 --version"

Retorne EXATAMENTE o comando shell, sem aspas, sem explicações."""

            provider = get_llm_provider()
            response = await provider.generate(
                user_message=user_input,
                system_prompt=system_prompt,
            )
            
            if response.success and response.content:
                # Limpar resposta
                generated_command = response.content.strip()
                # Remover markdown se houver
                if generated_command.startswith("```"):
                    generated_command = generated_command.split("```")[1]
                    if generated_command.startswith("bash"):
                        generated_command = generated_command[4:]
                generated_command = generated_command.strip()
                
                logger.info(
                    "shell_command_generated_by_llm",
                    user_input=user_input[:50],
                    generated_command=generated_command,
                )
                
                return generated_command
            
        except Exception as e:
            logger.warning("llm_interpretation_failed", error=str(e), input=user_input[:50])
        
        # Fallback: retornar input original
        return user_input
