"""Testes para o Skill Registry."""

import pytest

from core.skills.base import SecurityLevel, SkillBase, SkillConfig
from core.skills.registry import SkillRegistry, get_skill_registry


class MockSkill(SkillBase):
    """Skill de teste."""

    async def execute(self, args=None):
        return "mock result"


@pytest.fixture
def mock_skill():
    config = SkillConfig(
        name="test_skill",
        description="Skill de teste",
        triggers=["teste", "test"],
        security_level=SecurityLevel.SAFE,
    )
    return MockSkill(config)


class TestSkillRegistry:
    """Testes do SkillRegistry."""

    def test_empty_registry(self):
        """Testa registry vazio."""
        registry = SkillRegistry(skill_dirs=[])
        assert registry.count == 0
        assert registry.list_skills() == []

    def test_get_nonexistent_skill(self):
        """Testa get de skill inexistente."""
        registry = SkillRegistry(skill_dirs=[])
        assert registry.get("nonexistent") is None

    def test_register_mock_skill(self, mock_skill):
        """Testa registro manual de skill."""
        registry = SkillRegistry(skill_dirs=[])
        registry._skills["test_skill"] = mock_skill
        assert registry.count == 1
        assert registry.get("test_skill") == mock_skill

    def test_find_by_trigger_exact(self, mock_skill):
        """Testa encontrar skill por trigger exato."""
        registry = SkillRegistry(skill_dirs=[])
        registry._skills["test_skill"] = mock_skill
        found = registry.find_by_trigger("teste")
        assert found is not None
        assert found.name == "test_skill"

    def test_find_by_trigger_case_insensitive(self, mock_skill):
        """Testa encontrar skill por trigger case insensitive."""
        registry = SkillRegistry(skill_dirs=[])
        registry._skills["test_skill"] = mock_skill
        found = registry.find_by_trigger("TESTE")
        assert found is not None
        assert found.name == "test_skill"

    def test_find_by_trigger_partial(self, mock_skill):
        """Testa encontrar skill por trigger parcial."""
        registry = SkillRegistry(skill_dirs=[])
        registry._skills["test_skill"] = mock_skill
        found = registry.find_by_trigger("quero fazer um teste agora")
        assert found is not None
        assert found.name == "test_skill"

    def test_find_by_trigger_no_match(self, mock_skill):
        """Testa encontrar skill sem match."""
        registry = SkillRegistry(skill_dirs=[])
        registry._skills["test_skill"] = mock_skill
        found = registry.find_by_trigger("completamente irrelevante")
        assert found is None

    @pytest.mark.asyncio
    async def test_execute_skill(self, mock_skill):
        """Testa execução de skill."""
        registry = SkillRegistry(skill_dirs=[])
        registry._skills["test_skill"] = mock_skill
        result = await registry.execute_skill("test_skill")
        assert result == "mock result"

    @pytest.mark.asyncio
    async def test_execute_nonexistent(self):
        """Testa execução de skill inexistente."""
        registry = SkillRegistry(skill_dirs=[])
        result = await registry.execute_skill("ghost")
        assert "não encontrado" in result

    def test_list_skills(self, mock_skill):
        """Testa listagem de skills."""
        registry = SkillRegistry(skill_dirs=[])
        registry._skills["test_skill"] = mock_skill
        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "test_skill"
        assert skills[0]["security_level"] == "safe"

    def test_discover_builtin(self):
        """Testa descoberta dos skills builtin reais."""
        registry = SkillRegistry()
        count = registry.discover_and_register()
        assert count >= 5  # ram, containers, status, postgres, redis

    def test_builtin_skills_exist(self):
        """Testa que os skills builtin esperados existem."""
        registry = get_skill_registry()

        assert registry.get("get_ram") is not None
        assert registry.get("list_containers") is not None
        assert registry.get("get_system_status") is not None
        assert registry.get("check_postgres") is not None
        assert registry.get("check_redis") is not None

    def test_find_ram_by_trigger(self):
        """Testa encontrar skill ram por trigger."""
        registry = get_skill_registry()

        found = registry.find_by_trigger("quanta ram?")
        assert found is not None
        assert found.name == "get_ram"

    def test_find_containers_by_trigger(self):
        """Testa encontrar skill containers por trigger."""
        registry = get_skill_registry()

        found = registry.find_by_trigger("listar containers")
        assert found is not None
        assert found.name == "list_containers"

    def test_find_status_by_trigger(self):
        """Testa encontrar skill status por trigger."""
        registry = get_skill_registry()

        found = registry.find_by_trigger("como está o sistema?")
        assert found is not None
        assert found.name == "get_system_status"


class TestSkillConfig:
    """Testes do SkillConfig."""

    def test_default_values(self):
        """Testa valores padrão do SkillConfig."""
        config = SkillConfig(name="test", description="Test skill")

        assert config.version == "1.0.0"
        assert config.security_level == SecurityLevel.SAFE
        assert config.triggers == []
        assert config.parameters == {}
        assert config.max_output_chars == 2000
        assert config.timeout_seconds == 30
        assert config.enabled is True


class TestSkillBase:
    """Testes do SkillBase."""

    @pytest.mark.asyncio
    async def test_skill_properties(self):
        """Testa propriedades do SkillBase."""
        config = SkillConfig(
            name="test_skill",
            description="Test",
            security_level=SecurityLevel.MODERATE,
        )
        skill = MockSkill(config)

        assert skill.name == "test_skill"
        assert skill.security_level == SecurityLevel.MODERATE
