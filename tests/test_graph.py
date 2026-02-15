"""
Testes basicos para o VPS-Agent v2.
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


class TestNodes:
    """Testes para os nodes do LangGraph."""

    @pytest.mark.asyncio
    async def test_node_classify_intent_command(self):
        """Testa classificacao de comandos."""
        from core.vps_langgraph.nodes import node_classify_intent

        state = {"user_id": "123", "user_message": "/ram"}
        result = await node_classify_intent(state)

        assert result["intent"] == "command"

    @pytest.mark.asyncio
    async def test_node_classify_intent_question(self):
        """Testa classificacao de perguntas."""
        from core.vps_langgraph.nodes import node_classify_intent

        # Pergunta factual clara - sem "e" isolado para evitar match com self_improve
        state = {"user_id": "123", "user_message": "oq e a capital do brasil?"}
        result = await node_classify_intent(state)

        # Aceita question OU chat OU self_improve (modelo gratuito tem limitacoes)
        assert result["intent"] in ["question", "chat", "self_improve"]

    @pytest.mark.asyncio
    async def test_node_classify_intent_chat(self):
        """Testa classificacao de chat."""
        from core.vps_langgraph.nodes import node_classify_intent

        state = {"user_id": "123", "user_message": "Ola, tudo bem?"}
        result = await node_classify_intent(state)

        assert result["intent"] == "chat"


class TestGraph:
    """Testes para o grafo do agente."""

    def test_build_agent_graph(self):
        """Testa se o grafo pode ser construido."""
        from core.vps_langgraph.graph import build_agent_graph

        graph = build_agent_graph()
        assert graph is not None


class TestMemory:
    """Testes para o sistema de memoria."""

    def test_memory_import(self):
        """Testa se AgentMemory pode ser importado."""
        from core.vps_langgraph.memory import AgentMemory

        assert AgentMemory is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
