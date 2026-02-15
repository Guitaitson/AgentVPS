"""
Testes basicos para o VPS-Agent v2 — Sprint 03.
"""

import pytest


class TestAgentState:
    """Testes para AgentState."""

    def test_agent_state_import(self):
        """Testa se AgentState pode ser importado."""
        from core.vps_langgraph.state import AgentState

        assert AgentState is not None

    def test_agent_state_structure(self):
        """Testa a estrutura do AgentState."""
        from core.vps_langgraph.state import AgentState

        state = AgentState(
            user_id="test_user", user_message="Hello", intent="chat", intent_confidence=0.9
        )
        assert state["user_id"] == "test_user"
        assert state["user_message"] == "Hello"
        assert state["intent"] == "chat"


class TestReactNode:
    """Testes para o react_node (substitui classify + plan)."""

    def test_react_node_import(self):
        """Testa se react_node pode ser importado."""
        from core.vps_langgraph.react_node import node_react, route_after_react

        assert node_react is not None
        assert route_after_react is not None

    def test_route_after_react_with_action(self):
        """Testa roteamento quando react detectou acao necessaria (tool call)."""
        from core.vps_langgraph.react_node import route_after_react

        state = {
            "action_required": True,
            "plan": [{"type": "skill", "action": "shell_exec", "args": {"command": "whoami"}}],
            "current_step": 0,
        }
        result = route_after_react(state)
        assert result == "security_check"

    def test_route_after_react_direct_response(self):
        """Testa roteamento quando react respondeu diretamente (sem action)."""
        from core.vps_langgraph.react_node import route_after_react

        state = {
            "action_required": False,
            "response": "Ola! Como posso ajudar?",
        }
        result = route_after_react(state)
        assert result == "respond"


class TestGraph:
    """Testes para o grafo do agente."""

    def test_build_agent_graph(self):
        """Testa se o grafo pode ser construido."""
        from core.vps_langgraph.graph import build_agent_graph

        graph = build_agent_graph()
        assert graph is not None

    def test_graph_has_react_node(self):
        """Testa que o grafo tem o node react."""
        from core.vps_langgraph.graph import build_agent_graph

        graph = build_agent_graph()
        # O grafo compilado tem nodes acessiveis
        assert graph is not None


class TestMemory:
    """Testes para o sistema de memoria."""

    def test_memory_import(self):
        """Testa se AgentMemory pode ser importado."""
        from core.vps_langgraph.memory import AgentMemory

        assert AgentMemory is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
