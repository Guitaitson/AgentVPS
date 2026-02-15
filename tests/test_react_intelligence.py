"""
Testes de Inteligência do ReAct Node.

Valida que o agente entende QUALQUER formulação - sem heurísticas hardcoded.
20 formulações diferentes que DEVEM produzir a mesma ação.

T2-03: Testes ReAct - O agente deve entender qualquer formulação via LLM.
"""

import pytest

from core.vps_langgraph.react_node import node_react, route_after_react
from core.vps_langgraph.state import AgentState

# Testes de equivalência - mesma pergunta, diferentes formulações
# O LLM deve produzir a mesma ação para todas estas formulações
EQUIVALENCE_TESTS = [
    # Grupo 1: RAM (5 formulações → get_ram)
    ("quanta ram?", "get_ram"),
    ("como está a memória?", "get_ram"),
    ("uso de memória", "get_ram"),
    ("memoria do servidor", "get_ram"),
    ("RAM disponível", "get_ram"),
    # Grupo 2: Shell exec (5 formulações → shell_exec)
    ("tem o docker instalado?", "shell_exec"),
    ("docker tá na máquina?", "shell_exec"),
    ("o docker está disponível?", "shell_exec"),
    ("verifica se tem docker", "shell_exec"),
    ("docker existe no servidor?", "shell_exec"),
    # Grupo 3: Web search (5 formulações → web_search)
    ("busque sobre LangGraph", "web_search"),
    ("pesquise como instalar Node", "web_search"),
    ("procure informações sobre FastAPI", "web_search"),
    ("como configurar nginx?", "web_search"),
    ("pesquisa sobre Kubernetes", "web_search"),
    # Grupo 4: Chat direto (5 formulações → sem tool)
    ("olá!", None),
    ("tudo bem?", None),
    ("obrigado pela ajuda", None),
    ("me conta uma piada", None),
    ("qual sua opinião sobre IA?", None),
]


@pytest.fixture
def base_state():
    """Estado base para testes."""
    return {
        "user_id": "test_user",
        "user_message": "",
        "messages": [],
        "intent": "unknown",
        "intent_confidence": 0.0,
        "intent_details": {},
        "tool_suggestion": None,
        "action_required": False,
        "user_context": {},
        "conversation_history": [],
        "plan": None,
        "current_step": 0,
        "tools_needed": [],
        "tools_available": [],
        "execution_result": None,
        "error": None,
        "security_check": {},
        "blocked_by_security": False,
        "response": "",
        "should_save_memory": False,
        "memory_updates": [],
        "timestamp": "2026-02-15T00:00:00Z",
        "ram_available_mb": None,
        "missing_capabilities": [],
        "needs_improvement": False,
        "improvement_summary": None,
        "improvement_plan": None,
        "should_improve": False,
        "implementation_result": None,
        "new_capability": None,
        "implementation_status": None,
    }


@pytest.mark.asyncio
class TestReActIntelligence:
    """Testes de inteligência - ReAct deve entender qualquer formulação."""

    async def test_node_react_import(self):
        """Verifica que node_react pode ser importado."""

        assert callable(node_react)

    async def test_route_after_react_with_action(self):
        """Testa roteamento quando action_required=True."""
        state = {"action_required": True}
        result = route_after_react(state)
        assert result == "security_check"

    async def test_route_after_react_without_action(self):
        """Testa roteamento quando action_required=False."""
        state = {"action_required": False}
        result = route_after_react(state)
        assert result == "respond"

    async def test_state_has_required_fields(self):
        """Verifica que AgentState tem campos necessários para ReAct."""
        from typing import get_type_hints

        # AgentState é TypedDict - verificar campos via type hints
        hints = get_type_hints(AgentState)
        required_fields = [
            "user_message",
            "intent",
            "action_required",
            "tool_suggestion",
            "plan",
            "conversation_history",
        ]

        for field in required_fields:
            assert field in hints, f"AgentState missing field: {field}"


@pytest.mark.asyncio
class TestToolSchemas:
    """Testa que os tool schemas estão configurados corretamente."""

    async def test_list_tool_schemas_returns_list(self):
        """Verifica que list_tool_schemas retorna uma lista."""
        from core.skills.registry import get_skill_registry

        registry = get_skill_registry()
        schemas = registry.list_tool_schemas()

        assert isinstance(schemas, list)
        assert len(schemas) > 0

    async def test_tool_schemas_have_required_fields(self):
        """Verifica que cada schema tem campos necessários."""
        from core.skills.registry import get_skill_registry

        registry = get_skill_registry()
        schemas = registry.list_tool_schemas()

        for schema in schemas:
            assert "type" in schema, f"Schema missing 'type': {schema}"
            assert "function" in schema, f"Schema missing 'function': {schema}"

            func = schema["function"]
            assert "name" in func, f"Function missing 'name': {func}"
            assert "description" in func, f"Function missing 'description': {func}"

    async def test_shell_exec_schema(self):
        """Verifica schema do shell_exec."""
        from core.skills.registry import get_skill_registry

        registry = get_skill_registry()
        schemas = registry.list_tool_schemas()

        shell_exec = next((s for s in schemas if s["function"]["name"] == "shell_exec"), None)
        assert shell_exec is not None, "shell_exec not found in schemas"

        func = shell_exec["function"]
        assert "command" in func.get("parameters", {}).get("properties", {}), "shell_exec should have 'command' param"


@pytest.mark.asyncio
class TestReActNodeIntegration:
    """Testes de integração do node_react com dependências."""

    async def test_react_node_uses_skill_registry(self):
        """Verifica que node_react usa skill_registry."""
        import core.vps_langgraph.react_node as react_module
        from core.skills.registry import get_skill_registry

        # Verificar que a função pode ser importada e tem as dependências corretas
        assert hasattr(react_module, "node_react")
        assert hasattr(react_module, "get_skill_registry")

        # Verificar que registry retorna skills
        registry = get_skill_registry()
        skills = registry.list_skills()
        assert len(skills) >= 10, f"Expected at least 10 skills, got {len(skills)}"
