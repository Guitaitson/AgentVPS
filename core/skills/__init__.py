"""
Skill Registry - Sistema de skills dinâmicos para o AgentVPS.

Cada skill é um diretório com:
- handler.py: Classe que herda SkillBase
- config.yaml: Metadata do skill

Estrutura:
    core/skills/
    ├── __init__.py
    ├── base.py          # SkillBase class
    ├── registry.py      # SkillRegistry
    ├── _builtin/       # Skills do sistema
    │   ├── ram/
    │   ├── containers/
    │   ├── system_status/
    │   ├── check_postgres/
    │   └── check_redis/
    └── README.md
"""

from .base import SecurityLevel, SkillBase, SkillConfig
from .registry import SkillRegistry, get_skill_registry

__all__ = [
    "SkillBase",
    "SkillConfig",
    "SecurityLevel",
    "SkillRegistry",
    "get_skill_registry",
]
