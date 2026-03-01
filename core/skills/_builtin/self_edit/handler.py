"""
Skill: Self Edit - Permite que o agente edite seus próprios arquivos de código.

Sprint 09: Endurecido com backup, blocked paths, git commit, rollback, mode patch.
"""

import os
import shutil
import subprocess
from typing import Any, Dict

import structlog

from core.skills.base import SkillBase

logger = structlog.get_logger()

# Diretórios permitidos para self-editing
ALLOWED_DIRS = [
    "/opt/vps-agent/core/skills",
    "/opt/vps-agent/core/vps_agent",
    "/opt/vps-agent/core/vps_langgraph",
    "/opt/vps-agent/core/llm",
    "/opt/vps-agent/core/hooks",
    "/opt/vps-agent/core/autonomous",
]

# Paths explicitamente bloqueados (segurança)
BLOCKED_PATHS = [
    "/opt/vps-agent/core/security/",
    "/opt/vps-agent/core/.env",
    "/opt/vps-agent/telegram_bot/",
]


class SelfEditSkill(SkillBase):
    """Permite editar arquivos do projeto com safety nets."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        args = args or {}

        file_path = args.get("file_path", "")
        content = args.get("content", "")
        mode = args.get("mode", "overwrite")

        if not file_path:
            return "❌ Forneça o caminho do arquivo. Ex: file_path=/opt/vps-agent/core/test.py"

        if not content:
            return "❌ Forneça o conteúdo para gravar."

        # Validar path
        validation = self._validate_path(file_path)
        if not validation["valid"]:
            return f"❌ {validation['error']}"

        try:
            abs_path = os.path.abspath(file_path)

            # Backup antes de editar
            backup_path = None
            if os.path.exists(abs_path):
                backup_path = f"{abs_path}.bak"
                shutil.copy2(abs_path, backup_path)

            # Editar conforme mode
            if mode == "patch":
                result = await self._patch_file(abs_path, content, backup_path)
            else:
                result = await self._edit_file(abs_path, content, mode)

            if result.startswith("❌"):
                return result

            # Syntax check para arquivos Python
            if abs_path.endswith(".py"):
                syntax_ok, syntax_err = self._check_syntax(abs_path)
                if not syntax_ok:
                    # Rollback automático
                    if backup_path and os.path.exists(backup_path):
                        shutil.copy2(backup_path, abs_path)
                        logger.warning("self_edit_rollback", file=abs_path, error=syntax_err)
                        return f"❌ Erro de syntax detectado! Rollback aplicado.\n{syntax_err}"

            # Git commit para rastreabilidade
            git_msg = self._git_commit(abs_path)

            backup_info = f"\n📋 Backup: {backup_path}" if backup_path else ""
            return f"{result}{backup_info}\n{git_msg}"

        except Exception as e:
            logger.error("self_edit_error", error=str(e), file=file_path)
            return f"❌ Erro ao editar arquivo: {e}"

    def _validate_path(self, file_path: str) -> dict:
        """Valida se o path é permitido."""
        abs_path = os.path.abspath(file_path)

        # Verificar paths bloqueados PRIMEIRO
        for blocked in BLOCKED_PATHS:
            if abs_path.startswith(blocked) or blocked.rstrip("/") in abs_path:
                return {
                    "valid": False,
                    "error": (
                        f"Path bloqueado por segurança: {blocked}. "
                        f"Arquivos de segurança, .env e telegram_bot não podem ser editados."
                    ),
                }

        # Verificar se está em diretório permitido
        for allowed_dir in ALLOWED_DIRS:
            if abs_path.startswith(allowed_dir):
                return {"valid": True}

        return {
            "valid": False,
            "error": (
                f"Path não permitido: {abs_path}\nDiretórios permitidos: {', '.join(ALLOWED_DIRS)}"
            ),
        }

    async def _edit_file(self, abs_path: str, content: str, mode: str) -> str:
        """Edita o arquivo (overwrite ou append)."""
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        if mode == "append":
            with open(abs_path, "a") as f:
                f.write(content)
            action = "adicionado"
        else:
            with open(abs_path, "w") as f:
                f.write(content)
            action = "escrito"

        return f"✅ Arquivo {action}: `{abs_path}` ({len(content)} bytes)"

    async def _patch_file(self, abs_path: str, content: str, backup_path: str) -> str:
        """Aplica patch: content no formato 'OLD_TEXT|||NEW_TEXT'."""
        if "|||" not in content:
            return "❌ Mode patch requer formato: 'TEXTO_ANTIGO|||TEXTO_NOVO'"

        old_text, new_text = content.split("|||", 1)

        if not os.path.exists(abs_path):
            return f"❌ Arquivo não encontrado: {abs_path}"

        with open(abs_path, "r") as f:
            current = f.read()

        if old_text not in current:
            return "❌ Texto a substituir não encontrado no arquivo"

        new_content = current.replace(old_text, new_text, 1)

        with open(abs_path, "w") as f:
            f.write(new_content)

        return f"✅ Patch aplicado: `{abs_path}`"

    def _check_syntax(self, abs_path: str) -> tuple:
        """Verifica syntax do arquivo Python. Retorna (ok, error_msg)."""
        try:
            result = subprocess.run(
                [
                    "python3",
                    "-c",
                    f"import py_compile; py_compile.compile('{abs_path}', doraise=True)",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False, result.stderr[:500]
            return True, ""
        except Exception as e:
            logger.warning("self_edit_syntax_check_error", error=str(e))
            return True, ""

    def _git_commit(self, abs_path: str) -> str:
        """Faz git commit local para rastreabilidade (sem push)."""
        try:
            subprocess.run(
                ["git", "add", abs_path],
                cwd="/opt/vps-agent",
                capture_output=True,
                timeout=10,
            )
            result = subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"self-edit: {os.path.basename(abs_path)} (via VPS-Agent)",
                ],
                cwd="/opt/vps-agent",
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return "📦 Git commit criado"
            return "⚠️ Git commit falhou (sem alterações?)"
        except Exception as e:
            logger.warning("self_edit_git_error", error=str(e))
            return "⚠️ Git commit não disponível"

    async def _read_file(self, file_path: str) -> str:
        """Lê o arquivo."""
        abs_path = os.path.abspath(file_path)

        validation = self._validate_path(abs_path)
        if not validation["valid"]:
            return f"❌ {validation['error']}"

        if not os.path.exists(abs_path):
            return f"❌ Arquivo não encontrado: {abs_path}"

        with open(abs_path, "r") as f:
            content = f.read()

        return f"📄 **Conteúdo de:** `{abs_path}`\n\n```\n{content[:2000]}\n```"
