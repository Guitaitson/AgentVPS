"""
Allowlist de Segurança - F1-07

Sistema de allowlist para comandos e operações permitidas.
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PermissionLevel(Enum):
    """Níveis de permissão."""
    DENY = "deny"
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"


class ResourceType(Enum):
    """Tipos de recursos."""
    COMMAND = "command"
    API_ENDPOINT = "api_endpoint"
    FILE_OPERATION = "file_operation"
    SYSTEM_OPERATION = "system_operation"
    LLM_OPERATION = "llm_operation"


@dataclass
class AllowlistRule:
    """Regra de allowlist."""
    name: str
    resource_type: ResourceType
    pattern: str  # Regex pattern
    permission: PermissionLevel
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, value: str) -> bool:
        """Verifica se o valor corresponde ao padrão."""
        try:
            return bool(re.match(self.pattern, value))
        except re.error:
            return False


@dataclass
class AllowlistResult:
    """Resultado da verificação de allowlist."""
    allowed: bool
    permission: PermissionLevel
    rule: Optional[AllowlistRule] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class SecurityAllowlist:
    """Gerenciador de allowlist de segurança."""

    def __init__(self, rules: Optional[List[AllowlistRule]] = None):
        self.rules = rules or []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compila os padrões regex."""
        for rule in self.rules:
            try:
                re.compile(rule.pattern)
            except re.error as e:
                raise ValueError(f"Padrão inválido na regra '{rule.name}': {e}")

    def add_rule(self, rule: AllowlistRule) -> None:
        """Adiciona uma regra."""
        try:
            re.compile(rule.pattern)
            self.rules.append(rule)
        except re.error as e:
            raise ValueError(f"Padrão inválido: {e}")

    def remove_rule(self, rule_name: str) -> bool:
        """Remove uma regra pelo nome."""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                self.rules.pop(i)
                return True
        return False

    def check(
        self,
        resource_type: ResourceType,
        value: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AllowlistResult:
        """
        Verifica se uma operação é permitida.

        Args:
            resource_type: Tipo de recurso
            value: Valor a verificar
            context: Contexto adicional

        Returns:
            Resultado da verificação
        """
        # Buscar regras correspondentes
        matching_rules = [
            rule for rule in self.rules
            if rule.resource_type == resource_type and rule.matches(value)
        ]

        if not matching_rules:
            # Sem regras correspondentes = DENY por padrão
            return AllowlistResult(
                allowed=False,
                permission=PermissionLevel.DENY,
                reason="Nenhuma regra correspondente encontrada"
            )

        # Priorizar DENY > REQUIRE_APPROVAL > ALLOW
        deny_rules = [r for r in matching_rules if r.permission == PermissionLevel.DENY]
        if deny_rules:
            return AllowlistResult(
                allowed=False,
                permission=PermissionLevel.DENY,
                rule=deny_rules[0],
                reason=f"Negado pela regra: {deny_rules[0].name}",
                metadata={"rule_name": deny_rules[0].name}
            )

        approval_rules = [r for r in matching_rules if r.permission == PermissionLevel.REQUIRE_APPROVAL]
        if approval_rules:
            return AllowlistResult(
                allowed=False,
                permission=PermissionLevel.REQUIRE_APPROVAL,
                rule=approval_rules[0],
                reason=f"Requer aprovação pela regra: {approval_rules[0].name}",
                metadata={"rule_name": approval_rules[0].name}
            )

        allow_rules = [r for r in matching_rules if r.permission == PermissionLevel.ALLOW]
        if allow_rules:
            return AllowlistResult(
                allowed=True,
                permission=PermissionLevel.ALLOW,
                rule=allow_rules[0],
                reason=f"Permitido pela regra: {allow_rules[0].name}",
                metadata={"rule_name": allow_rules[0].name}
            )

        return AllowlistResult(
            allowed=False,
            permission=PermissionLevel.DENY,
            reason="Nenhuma regra de permissão encontrada"
        )

    def get_rules_by_type(self, resource_type: ResourceType) -> List[AllowlistRule]:
        """Retorna todas as regras de um tipo."""
        return [r for r in self.rules if r.resource_type == resource_type]

    def export_rules(self) -> List[Dict[str, Any]]:
        """Exporta regras para formato serializável."""
        return [
            {
                "name": rule.name,
                "resource_type": rule.resource_type.value,
                "pattern": rule.pattern,
                "permission": rule.permission.value,
                "description": rule.description,
                "metadata": rule.metadata,
            }
            for rule in self.rules
        ]

    def import_rules(self, rules_data: List[Dict[str, Any]]) -> None:
        """Importa regras de formato serializável."""
        self.rules = []
        for rule_data in rules_data:
            rule = AllowlistRule(
                name=rule_data["name"],
                resource_type=ResourceType(rule_data["resource_type"]),
                pattern=rule_data["pattern"],
                permission=PermissionLevel(rule_data["permission"]),
                description=rule_data.get("description", ""),
                metadata=rule_data.get("metadata", {}),
            )
            self.rules.append(rule)

        self._compile_patterns()


def create_default_allowlist() -> SecurityAllowlist:
    """Cria allowlist com regras padrão seguras."""
    rules = [
        # Comandos permitidos (seguros)
        AllowlistRule(
            name="safe_docker_commands",
            resource_type=ResourceType.COMMAND,
            pattern=r"^(docker ps|docker stats|docker logs|docker inspect|docker top)$",
            permission=PermissionLevel.ALLOW,
            description="Comandos Docker seguros (leitura apenas)",
        ),

        AllowlistRule(
            name="safe_system_commands",
            resource_type=ResourceType.COMMAND,
            pattern=r"^(free -m|df -h|uptime|whoami|pwd|ls -la)$",
            permission=PermissionLevel.ALLOW,
            description="Comandos de sistema seguros (leitura apenas)",
        ),

        # Comandos que requerem aprovação
        AllowlistRule(
            name="docker_management_commands",
            resource_type=ResourceType.COMMAND,
            pattern=r"^docker (start|stop|restart|rm|rmi) ",
            permission=PermissionLevel.REQUIRE_APPROVAL,
            description="Comandos de gerenciamento Docker (requer aprovação)",
        ),

        # Comandos negados
        AllowlistRule(
            name="dangerous_commands",
            resource_type=ResourceType.COMMAND,
            pattern=r"^(rm -rf|dd if=|mkfs|:(){ :|:& };:)$",
            permission=PermissionLevel.DENY,
            description="Comandos perigosos (sempre negados)",
        ),

        # API endpoints permitidos
        AllowlistRule(
            name="safe_api_endpoints",
            resource_type=ResourceType.API_ENDPOINT,
            pattern=r"^/(health|status|metrics|api/v1/(chat|message|session))$",
            permission=PermissionLevel.ALLOW,
            description="Endpoints API seguros",
        ),

        # Operações de arquivo permitidas
        AllowlistRule(
            name="safe_file_operations",
            resource_type=ResourceType.FILE_OPERATION,
            pattern=r"^(read|list|info) ",
            permission=PermissionLevel.ALLOW,
            description="Operações de arquivo seguras (leitura apenas)",
        ),

        AllowlistRule(
            name="file_write_operations",
            resource_type=ResourceType.FILE_OPERATION,
            pattern=r"^(write|create|delete) ",
            permission=PermissionLevel.REQUIRE_APPROVAL,
            description="Operações de escrita (requer aprovação)",
        ),

        # Operações LLM permitidas
        AllowlistRule(
            name="safe_llm_operations",
            resource_type=ResourceType.LLM_OPERATION,
            pattern=r"^(generate|chat|complete)$",
            permission=PermissionLevel.ALLOW,
            description="Operações LLM seguras",
        ),
    ]

    return SecurityAllowlist(rules)


def load_allowlist_from_file(filepath: str) -> SecurityAllowlist:
    """Carrega allowlist de um arquivo JSON."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return SecurityAllowlist(rules_data=data.get("rules", []))


def save_allowlist_to_file(allowlist: SecurityAllowlist, filepath: str) -> None:
    """Salva allowlist em um arquivo JSON."""
    data = {
        "rules": allowlist.export_rules(),
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
