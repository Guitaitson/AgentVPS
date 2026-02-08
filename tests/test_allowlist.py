"""
Testes para o Allowlist de Segurança.
"""

import pytest
import sys
sys.path.insert(0, 'core')

from security.allowlist import (
    PermissionLevel,
    ResourceType,
    AllowlistRule,
    SecurityAllowlist,
    create_default_allowlist,
)


class TestAllowlistRule:
    """Testes para regras de allowlist."""
    
    def test_create_rule(self):
        """Testa criação de regra."""
        rule = AllowlistRule(
            name="test_rule",
            resource_type=ResourceType.COMMAND,
            pattern=r"^test$",
            permission=PermissionLevel.ALLOW,
            description="Regra de teste",
        )
        
        assert rule.name == "test_rule"
        assert rule.resource_type == ResourceType.COMMAND
        assert rule.permission == PermissionLevel.ALLOW
    
    def test_rule_matches(self):
        """Testa correspondência de padrão."""
        rule = AllowlistRule(
            name="test_rule",
            resource_type=ResourceType.COMMAND,
            pattern=r"^docker ps$",
            permission=PermissionLevel.ALLOW,
        )
        
        assert rule.matches("docker ps") is True
        assert rule.matches("docker ps -a") is False
        assert rule.matches("docker stats") is False


class TestSecurityAllowlist:
    """Testes para gerenciador de allowlist."""
    
    def test_create_empty_allowlist(self):
        """Testa criação de allowlist vazia."""
        allowlist = SecurityAllowlist()
        
        assert len(allowlist.rules) == 0
    
    def test_add_rule(self):
        """Testa adição de regra."""
        allowlist = SecurityAllowlist()
        rule = AllowlistRule(
            name="test_rule",
            resource_type=ResourceType.COMMAND,
            pattern=r"^test$",
            permission=PermissionLevel.ALLOW,
        )
        
        allowlist.add_rule(rule)
        
        assert len(allowlist.rules) == 1
        assert allowlist.rules[0].name == "test_rule"
    
    def test_remove_rule(self):
        """Testa remoção de regra."""
        allowlist = SecurityAllowlist()
        rule = AllowlistRule(
            name="test_rule",
            resource_type=ResourceType.COMMAND,
            pattern=r"^test$",
            permission=PermissionLevel.ALLOW,
        )
        allowlist.add_rule(rule)
        
        result = allowlist.remove_rule("test_rule")
        
        assert result is True
        assert len(allowlist.rules) == 0
    
    def test_remove_nonexistent_rule(self):
        """Testa remoção de regra inexistente."""
        allowlist = SecurityAllowlist()
        
        result = allowlist.remove_rule("nonexistent")
        
        assert result is False
    
    def test_check_allowed(self):
        """Testa verificação de operação permitida."""
        allowlist = SecurityAllowlist()
        allowlist.add_rule(AllowlistRule(
            name="allow_test",
            resource_type=ResourceType.COMMAND,
            pattern=r"^test$",
            permission=PermissionLevel.ALLOW,
        ))
        
        result = allowlist.check(ResourceType.COMMAND, "test")
        
        assert result.allowed is True
        assert result.permission == PermissionLevel.ALLOW
        assert "allow_test" in result.reason
    
    def test_check_denied(self):
        """Testa verificação de operação negada."""
        allowlist = SecurityAllowlist()
        allowlist.add_rule(AllowlistRule(
            name="deny_test",
            resource_type=ResourceType.COMMAND,
            pattern=r"^dangerous$",
            permission=PermissionLevel.DENY,
        ))
        
        result = allowlist.check(ResourceType.COMMAND, "dangerous")
        
        assert result.allowed is False
        assert result.permission == PermissionLevel.DENY
        assert "deny_test" in result.reason
    
    def test_check_require_approval(self):
        """Testa verificação de operação que requer aprovação."""
        allowlist = SecurityAllowlist()
        allowlist.add_rule(AllowlistRule(
            name="approval_test",
            resource_type=ResourceType.COMMAND,
            pattern=r"^sensitive$",
            permission=PermissionLevel.REQUIRE_APPROVAL,
        ))
        
        result = allowlist.check(ResourceType.COMMAND, "sensitive")
        
        assert result.allowed is False
        assert result.permission == PermissionLevel.REQUIRE_APPROVAL
        assert "approval_test" in result.reason
    
    def test_check_no_matching_rule(self):
        """Testa verificação sem regra correspondente."""
        allowlist = SecurityAllowlist()
        
        result = allowlist.check(ResourceType.COMMAND, "unknown")
        
        assert result.allowed is False
        assert result.permission == PermissionLevel.DENY
        assert "Nenhuma regra correspondente" in result.reason
    
    def test_get_rules_by_type(self):
        """Testa obtenção de regras por tipo."""
        allowlist = SecurityAllowlist()
        allowlist.add_rule(AllowlistRule(
            name="cmd1",
            resource_type=ResourceType.COMMAND,
            pattern=r"^cmd1$",
            permission=PermissionLevel.ALLOW,
        ))
        allowlist.add_rule(AllowlistRule(
            name="api1",
            resource_type=ResourceType.API_ENDPOINT,
            pattern=r"^/api1$",
            permission=PermissionLevel.ALLOW,
        ))
        
        cmd_rules = allowlist.get_rules_by_type(ResourceType.COMMAND)
        api_rules = allowlist.get_rules_by_type(ResourceType.API_ENDPOINT)
        
        assert len(cmd_rules) == 1
        assert len(api_rules) == 1
        assert cmd_rules[0].name == "cmd1"
        assert api_rules[0].name == "api1"
    
    def test_export_import_rules(self):
        """Testa exportação e importação de regras."""
        allowlist1 = SecurityAllowlist()
        allowlist1.add_rule(AllowlistRule(
            name="test_rule",
            resource_type=ResourceType.COMMAND,
            pattern=r"^test$",
            permission=PermissionLevel.ALLOW,
            description="Teste",
        ))
        
        # Exportar
        exported = allowlist1.export_rules()
        
        # Importar
        allowlist2 = SecurityAllowlist()
        allowlist2.import_rules(exported)
        
        assert len(allowlist2.rules) == 1
        assert allowlist2.rules[0].name == "test_rule"
        assert allowlist2.rules[0].description == "Teste"


class TestDefaultAllowlist:
    """Testes para allowlist padrão."""
    
    def test_create_default_allowlist(self):
        """Testa criação de allowlist padrão."""
        allowlist = create_default_allowlist()
        
        assert len(allowlist.rules) > 0
    
    def test_safe_docker_commands_allowed(self):
        """Testa que comandos Docker seguros são permitidos."""
        allowlist = create_default_allowlist()
        
        result = allowlist.check(ResourceType.COMMAND, "docker ps")
        assert result.allowed is True
        
        result = allowlist.check(ResourceType.COMMAND, "docker stats")
        assert result.allowed is True
    
    def test_dangerous_commands_denied(self):
        """Testa que comandos perigosos são negados."""
        allowlist = create_default_allowlist()
        
        result = allowlist.check(ResourceType.COMMAND, "rm -rf /")
        assert result.allowed is False
        assert result.permission == PermissionLevel.DENY
        
        result = allowlist.check(ResourceType.COMMAND, "dd if=/dev/zero of=/dev/sda")
        assert result.allowed is False
        assert result.permission == PermissionLevel.DENY
    
    def test_docker_management_requires_approval(self):
        """Testa que comandos de gerenciamento Docker requerem aprovação."""
        allowlist = create_default_allowlist()
        
        result = allowlist.check(ResourceType.COMMAND, "docker stop container")
        assert result.allowed is False
        assert result.permission == PermissionLevel.REQUIRE_APPROVAL
        
        result = allowlist.check(ResourceType.COMMAND, "docker rm container")
        assert result.allowed is False
        assert result.permission == PermissionLevel.REQUIRE_APPROVAL
    
    def test_safe_api_endpoints_allowed(self):
        """Testa que endpoints API seguros são permitidos."""
        allowlist = create_default_allowlist()
        
        result = allowlist.check(ResourceType.API_ENDPOINT, "/health")
        assert result.allowed is True
        
        result = allowlist.check(ResourceType.API_ENDPOINT, "/api/v1/chat")
        assert result.allowed is True
    
    def test_safe_file_operations_allowed(self):
        """Testa que operações de arquivo seguras são permitidas."""
        allowlist = create_default_allowlist()
        
        result = allowlist.check(ResourceType.FILE_OPERATION, "read /path/to/file")
        assert result.allowed is True
        
        result = allowlist.check(ResourceType.FILE_OPERATION, "list /path/to/dir")
        assert result.allowed is True
    
    def test_file_write_requires_approval(self):
        """Testa que operações de escrita requerem aprovação."""
        allowlist = create_default_allowlist()
        
        result = allowlist.check(ResourceType.FILE_OPERATION, "write /path/to/file")
        assert result.allowed is False
        assert result.permission == PermissionLevel.REQUIRE_APPROVAL
        
        result = allowlist.check(ResourceType.FILE_OPERATION, "delete /path/to/file")
        assert result.allowed is False
        assert result.permission == PermissionLevel.REQUIRE_APPROVAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
