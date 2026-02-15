"""
Skill Registry — Descobre, registra e gerencia skills.

Substitui o TOOLS_REGISTRY hardcoded de core/tools/system_tools.py.
"""

import os
from typing import Any, Dict, List, Optional

import structlog
import yaml

from .base import SecurityLevel, SkillBase, SkillConfig

logger = structlog.get_logger()


class SkillRegistry:
    """
    Registry central de skills.
    
    Descobre skills automaticamente em diretórios configurados.
    Cada skill é um diretório com handler.py + config.yaml.
    """

    def __init__(self, skill_dirs: List[str] = None):
        self._skills: Dict[str, SkillBase] = {}
        # Default: diretório _builtin junto deste arquivo
        if skill_dirs is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            skill_dirs = [os.path.join(base_dir, "_builtin")]
        self._skill_dirs = skill_dirs

    def discover_and_register(self) -> int:
        """
        Descobre skills em todos os diretórios configurados.
        
        Returns:
            Número de skills registrados
        """
        count = 0
        for skill_dir in self._skill_dirs:
            if not os.path.isdir(skill_dir):
                logger.warning("skill_dir_not_found", path=skill_dir)
                continue

            logger.info("scanning_skill_dir", path=skill_dir)

            for entry in os.scandir(skill_dir):
                if not entry.is_dir() or entry.name.startswith("_"):
                    continue

                config_path = os.path.join(entry.path, "config.yaml")
                handler_path = os.path.join(entry.path, "handler.py")

                if not os.path.exists(config_path):
                    logger.debug("skill_missing_config", path=entry.path)
                    continue

                if not os.path.exists(handler_path):
                    logger.debug("skill_missing_handler", path=entry.path)
                    continue

                try:
                    skill = self._load_skill(entry.path, entry.name)
                    if skill and skill.config.enabled:
                        self._skills[skill.name] = skill
                        count += 1
                        logger.info("skill_registered", name=skill.name, path=entry.path)
                except Exception as e:
                    logger.error("skill_load_error", path=entry.path, error=str(e))

        logger.info("skill_discovery_complete", total=count)
        return count

    def _load_skill(self, skill_path: str, dir_name: str) -> Optional[SkillBase]:
        """Carrega um skill a partir do diretório."""
        import importlib.util
        import sys

        # Carregar config.yaml
        config_path = os.path.join(skill_path, "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)

        # Converter security_level string para enum
        sec_level = raw_config.get("security_level", "safe")
        if isinstance(sec_level, str):
            raw_config["security_level"] = SecurityLevel(sec_level)

        config = SkillConfig(**raw_config)

        # Importar handler.py dinamicamente
        handler_path = os.path.join(skill_path, "handler.py")

        # Criar módulo dinamicamente
        module_name = f"core.skills.{dir_name}.handler"

        spec = importlib.util.spec_from_file_location(module_name, handler_path)
        if spec is None or spec.loader is None:
            logger.error("skill_spec_error", path=skill_path)
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Procurar classe que herda SkillBase
        handler_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type)
                and issubclass(attr, SkillBase)
                and attr is not SkillBase):
                handler_class = attr
                break

        if handler_class is None:
            logger.error("no_skill_class_found", path=skill_path)
            return None

        return handler_class(config)

    def get(self, name: str) -> Optional[SkillBase]:
        """Retorna skill pelo nome."""
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """Lista todos os skills registrados."""
        return [
            {
                "name": s.name,
                "description": s.config.description,
                "security_level": s.config.security_level.value,
                "triggers": s.config.triggers,
                "enabled": s.config.enabled,
            }
            for s in self._skills.values()
        ]

    def find_by_trigger(self, text: str) -> Optional[SkillBase]:
        """Encontra skill que melhor corresponde ao texto."""
        text_lower = text.lower()

        # Primeiro: procurar trigger exato (case insensitive)
        for skill in self._skills.values():
            for trigger in skill.config.triggers:
                if trigger.lower() == text_lower:
                    return skill

        # Segundo: procurar trigger parcial
        for skill in self._skills.values():
            for trigger in skill.config.triggers:
                if trigger.lower() in text_lower:
                    return skill

        # Terceiro: procurar pelo nome do skill
        for skill in self._skills.values():
            if skill.name.lower() in text_lower:
                return skill

        return None

    async def execute_skill(self, name: str, args: Dict[str, Any] = None) -> str:
        """Executa um skill pelo nome."""
        skill = self.get(name)
        if not skill:
            return f"❌ Skill '{name}' não encontrado. Use /skills para ver disponíveis."

        if not skill.validate_args(args):
            return f"❌ Argumentos inválidos para skill '{name}'."

        try:
            return await skill.execute(args or {})
        except Exception as e:
            logger.error("skill_execution_error", skill=name, error=str(e))
            return f"❌ Erro ao executar skill '{name}': {e}"

    @property
    def count(self) -> int:
        return len(self._skills)

    def list_tool_schemas(self) -> List[dict]:
        """
        Retorna lista de tool schemas para function calling.
        
        Formato compatível com OpenRouter/Gemini function calling.
        """
        tools = []
        for skill in self._skills.values():
            properties = {}
            required = []

            # Usar parameters_schema do config, ou gerar do parameters
            schema = skill.config.parameters_schema
            if not schema and skill.config.parameters:
                # Gerar schema automaticamente do parameters
                for param_name, param_info in skill.config.parameters.items():
                    properties[param_name] = {
                        "type": param_info.get("type", "string"),
                        "description": param_info.get("description", ""),
                    }
                    if param_info.get("required", False):
                        required.append(param_name)
            elif schema:
                # Usar schema definido explicitamente
                for param_name, param_info in schema.items():
                    properties[param_name] = {
                        "type": param_info.get("type", "string"),
                        "description": param_info.get("description", ""),
                    }
                    if param_info.get("required", False):
                        required.append(param_name)

            tools.append({
                "type": "function",
                "function": {
                    "name": skill.name,
                    "description": skill.config.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    }
                }
            })

        logger.info("tool_schemas_generated", count=len(tools))
        return tools


# Singleton
_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Retorna instância global do registry (lazy init)."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _registry.discover_and_register()
    return _registry


def reload_skill_registry() -> SkillRegistry:
    """Recarrega o registry (para desenvolvimento)."""
    global _registry
    _registry = SkillRegistry()
    _registry.discover_and_register()
    return _registry
