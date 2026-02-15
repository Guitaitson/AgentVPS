"""
Base class para todos os skills do AgentVPS.

Cada skill deve herdar de SkillBase e implementar execute().
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class SecurityLevel(Enum):
    """Nível de segurança do skill."""

    SAFE = "safe"  # Executa sem perguntar (leitura)
    MODERATE = "moderate"  # Executa + log
    DANGEROUS = "dangerous"  # Requer approval via Telegram
    FORBIDDEN = "forbidden"  # Nunca executa


@dataclass
class SkillConfig:
    """Configuração de um skill, carregada do config.yaml."""

    name: str
    description: str
    version: str = "1.0.0"
    security_level: SecurityLevel = SecurityLevel.SAFE
    triggers: List[str] = field(default_factory=list)  # keywords que ativam o skill
    parameters: Dict[str, Any] = field(default_factory=dict)
    parameters_schema: Dict[str, Any] = field(default_factory=dict)  # Schema para function calling
    max_output_chars: int = 2000
    timeout_seconds: int = 30
    enabled: bool = True


class SkillBase(ABC):
    """
    Classe base para skills.

    Para criar um skill novo:
    1. Criar diretório em core/skills/ (ex: core/skills/meu_skill/)
    2. Criar handler.py com classe que herda SkillBase
    3. Criar config.yaml com metadata
    4. O registry descobre automaticamente no startup
    """

    def __init__(self, config: SkillConfig):
        self.config = config

    @abstractmethod
    async def execute(self, args: Dict[str, Any] = None) -> str:
        """
        Executa o skill.

        Args:
            args: Argumentos opcionais (ex: {"command": "ls -la"})

        Returns:
            String com resultado da execução
        """
        pass

    def validate_args(self, args: Dict[str, Any] = None) -> bool:
        """Valida argumentos antes de executar. Override para validação custom."""
        return True

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def security_level(self) -> SecurityLevel:
        return self.config.security_level
