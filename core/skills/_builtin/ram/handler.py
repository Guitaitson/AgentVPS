"""Skill: RAM Usage — Mostra uso de RAM do sistema."""

from typing import Any, Dict

from core.skills.base import SkillBase


class RamSkill(SkillBase):
    """Mostra uso atual de RAM."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()

            values = {}
            for line in meminfo.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    values[key.strip()] = int(val.strip().split()[0])

            total = values.get("MemTotal", 0) // 1024
            available = values.get("MemAvailable", 0) // 1024
            used = total - available
            pct = (used / total * 100) if total > 0 else 0

            return (
                f"🧠 **Uso de RAM**\n\n"
                f"Total: {total} MB\n"
                f"Usado: {used} MB ({pct:.1f}%)\n"
                f"Disponível: {available} MB"
            )
        except Exception as e:
            return f"❌ Erro ao ler RAM: {e}"
