"""
Skill: File Manager — Gerencia arquivos com segurança.

Operações: read, write, append, list
Paths permitidos: /opt/vps-agent/, /tmp/, /home/
Paths proibidos: /etc/shadow, /root/.ssh/, /etc/passwd
"""

import os
from typing import Any, Dict

from core.skills.base import SkillBase

# Paths permitidos para leitura
ALLOWED_READ_PATHS = ["/opt/vps-agent/", "/tmp/", "/home/", "/var/log/", "/proc/"]

# Paths permitidos para escrita
ALLOWED_WRITE_PATHS = ["/opt/vps-agent/", "/tmp/", "/home/"]

# Paths proibidos absolutos
FORBIDDEN_PATHS = [
    "/etc/shadow",
    "/etc/passwd",
    "/root/.ssh/",
    "/etc/sudoers",
    "/etc/group",
]


def is_path_allowed(path: str, operation: str = "read") -> tuple[bool, str]:
    """Verifica se path é permitido para a operação."""
    try:
        resolved = os.path.realpath(path)
    except Exception:
        return False, "Path inválido"

    # Verificar paths proibidos
    for forbidden in FORBIDDEN_PATHS:
        if resolved.startswith(forbidden):
            return False, f"Path proibido: {forbidden}"

    # Verificar contra lista de permitidos
    allowed = ALLOWED_WRITE_PATHS if operation in ["write", "append"] else ALLOWED_READ_PATHS
    for allowed_path in allowed:
        if resolved.startswith(allowed_path):
            return True, "OK"

    return False, f"Path fora dos diretórios permitidos: {resolved}"


class FileManagerSkill(SkillBase):
    """Gerencia arquivos com validação de segurança."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        args = args or {}

        # Detectar operação a partir do texto
        raw_input = args.get("raw_input", "")
        operation = args.get("operation", "")
        path = args.get("path", "")

        # Detectar operação automaticamente se não especificada
        if not operation:
            raw_lower = raw_input.lower()
            if "ler" in raw_lower or "leia" in raw_lower or "conteúdo" in raw_lower:
                operation = "read"
            elif "criar" in raw_lower or "escrever" in raw_lower:
                operation = "write"
            elif "listar" in raw_lower or "arquivos em" in raw_lower:
                operation = "list"
            else:
                operation = "read"  # default

        # Extrair path do raw_input se não especificado
        if not path:
            # Tentar extrair path do texto
            parts = raw_input.split()
            for i, part in enumerate(parts):
                if part.startswith("/") or part.startswith("."):
                    path = part
                    break
                # Procurar por padrões como "/opt/..."
                if "/" in part:
                    path = part
                    break

        if not path:
            return "❌ Path não especificado. Use: 'ler /caminho/arquivo'"

        # Verificar segurança
        allowed, reason = is_path_allowed(path, operation)
        if not allowed:
            return f"⛔ Acesso negado: {reason}"

        # Executar operação
        try:
            if operation == "read" or "ler" in raw_input.lower():
                return await self._read_file(path)
            elif operation == "list" or "listar" in raw_input.lower():
                return await self._list_dir(path)
            elif operation == "write" or "criar" in raw_input.lower():
                content = args.get("content", "")
                return await self._write_file(path, content)
            elif operation == "append":
                content = args.get("content", "")
                return await self._append_file(path, content)
            else:
                return f"❌ Operação '{operation}' não reconhecida. Use: read, write, append, list"
        except Exception as e:
            return f"❌ Erro: {e}"

    async def _read_file(self, path: str) -> str:
        """Lê arquivo."""
        if not os.path.isfile(path):
            return f"❌ Arquivo não encontrado: {path}"

        allowed, _ = is_path_allowed(path, "read")
        if not allowed:
            return "⛔ Acesso negado para leitura"

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            max_chars = self.config.max_output_chars
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n... [truncado, {len(content)} chars total]"

            return f"📄 **{path}**\n```\n{content}\n```"
        except UnicodeDecodeError:
            with open(path, "rb") as f:
                content = f.read(500)
            return f"📄 **{path}** (binary, primeiros 500 bytes)\n```\n{content}\n```"
        except Exception as e:
            return f"❌ Erro ao ler: {e}"

    async def _list_dir(self, path: str) -> str:
        """Lista diretório."""
        if not os.path.isdir(path):
            return f"❌ Diretório não encontrado: {path}"

        try:
            items = os.listdir(path)
            if not items:
                return f"📁 **{path}**\n\n(diretório vazio)"

            formatted = [f"📁 **{path}**\n"]
            formatted.append("```")
            for item in sorted(items)[:50]:
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    formatted.append(f"📁 {item}/")
                else:
                    size = os.path.getsize(item_path)
                    formatted.append(f"📄 {item} ({size} bytes)")
            formatted.append("```")

            return "\n".join(formatted)
        except Exception as e:
            return f"❌ Erro ao listar: {e}"

    async def _write_file(self, path: str, content: str) -> str:
        """Cria/escreve arquivo."""
        allowed, _ = is_path_allowed(path, "write")
        if not allowed:
            return "⛔ Acesso negado para escrita"

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"✅ Arquivo criado: {path}\n```\n{content}\n```"
        except Exception as e:
            return f"❌ Erro ao criar: {e}"

    async def _append_file(self, path: str, content: str) -> str:
        """Append em arquivo."""
        allowed, _ = is_path_allowed(path, "append")
        if not allowed:
            return "⛔ Acesso negado para escrita"

        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            return f"✅ Conteúdo adicionado a: {path}"
        except Exception as e:
            return f"❌ Erro ao adicionar: {e}"
