"""Skill: List Docker Containers — Lista containers Docker."""

import subprocess
from typing import Any, Dict

from core.skills.base import SkillBase


class ContainersSkill(SkillBase):
    """Lista containers Docker em execução."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
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
            return "⏱️ Timeout ao listar containers"
        except FileNotFoundError:
            return "❌ Docker não instalado ou não encontrado"
        except Exception as e:
            return f"❌ Erro: {str(e)}"
