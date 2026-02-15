"""
Skill: Self Edit - Permite que o agente edite seus próprios arquivos de código.
"""

import os
from typing import Any, Dict

from core.skills.base import SkillBase

# Allowed directories for self-editing
ALLOWED_DIRS = [
    "/opt/vps-agent/core/skills",
    "/opt/vps-agent/core/vps_agent",
    "/opt/vps-agent/core/vps_langgraph",
]


class SelfEditSkill(SkillBase):
    """Permite editar arquivos do projeto."""

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
            return await self._edit_file(file_path, content, mode)
        except Exception as e:
            return f"❌ Erro ao editar arquivo: {e}"

    def _validate_path(self, file_path: str) -> dict:
        """Valida se o path é permitido."""
        abs_path = os.path.abspath(file_path)

        # Verificar se está em diretório permitido
        for allowed_dir in ALLOWED_DIRS:
            if abs_path.startswith(allowed_dir):
                return {"valid": True}

        # Verificar se é um路径 dentro do projeto
        if "/opt/vps-agent/" in abs_path:
            return {"valid": True}

        return {
            "valid": False,
            "error": "Path não permitido. Apenas arquivos em /opt/vps-agent/ são permitidos.",
        }

    async def _edit_file(self, file_path: str, content: str, mode: str) -> str:
        """Edita o arquivo (sync I/O)."""
        abs_path = os.path.abspath(file_path)

        # Criar diretório se não existir
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        if mode == "append":
            with open(abs_path, "a") as f:
                f.write(content)
            action = "adicionado"
        else:
            with open(abs_path, "w") as f:
                f.write(content)
            action = "escrito"

        return f"✅ Arquivo {action} com sucesso!\n📄 `{abs_path}`\n📝 {len(content)} bytes"

    async def _read_file(self, file_path: str) -> str:
        """Lê o arquivo (sync I/O)."""
        abs_path = os.path.abspath(file_path)

        validation = self._validate_path(abs_path)
        if not validation["valid"]:
            return f"❌ {validation['error']}"

        if not os.path.exists(abs_path):
            return f"❌ Arquivo não encontrado: {abs_path}"

        with open(abs_path, "r") as f:
            content = f.read()

        return f"📄 **Conteúdo de:** `{abs_path}`\n\n```\n{content[:2000]}\n```"
