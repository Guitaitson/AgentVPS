"""Skill: System Status — Mostra status geral do sistema."""

import subprocess
from typing import Any, Dict

from core.skills.base import SkillBase


class SystemStatusSkill(SkillBase):
    """Mostra status geral do sistema (RAM, disco, Docker)."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        checks = []

        # Check RAM
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()

            mem_total = 0
            mem_available = 0

            for line in meminfo.strip().split("\n"):
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1])

            if mem_total > 0:
                usage_pct = ((mem_total - mem_available) / mem_total) * 100

                if usage_pct > 90:
                    checks.append(("🚨 RAM", f"{usage_pct:.0f}% - CRÍTICO"))
                elif usage_pct > 75:
                    checks.append(("⚠️  RAM", f"{usage_pct:.0f}% - Alto"))
                else:
                    checks.append(("✅ RAM", f"{usage_pct:.0f}% - OK"))
            else:
                checks.append(("❌ RAM", "Não disponível"))
        except Exception:
            checks.append(("❌ RAM", "Não disponível"))

        # Check Disk
        try:
            result = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True,
                text=True,
                timeout=5
            )
            lines = result.stdout.strip().split("\n")
            disk_line = lines[1].split()
            usage = disk_line[4].replace("%", "")

            if int(usage) > 90:
                checks.append(("🚨 Disco", f"{usage}% - CRÍTICO"))
            elif int(usage) > 75:
                checks.append(("⚠️  Disco", f"{usage}% - Alto"))
            else:
                checks.append(("✅ Disco", f"{usage}% - OK"))
        except Exception:
            checks.append(("❌ Disco", "Não disponível"))

        # Check Docker
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                checks.append(("✅ Docker", f"v{version}"))
            else:
                checks.append(("❌ Docker", "Indisponível"))
        except Exception:
            checks.append(("❌ Docker", "Não instalado"))

        # Format output
        formatted = ["📊 **Status do Sistema**\n"]
        for name, status in checks:
            formatted.append(f"{name}: {status}")

        return "\n".join(formatted)
