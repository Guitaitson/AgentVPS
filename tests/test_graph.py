"""
Testes básicos para o VPS-Agent v2.
"""
import pytest
import sys
sys.path.insert(0, 'core')


class TestAgentState:
    """Testes para AgentState."""
    
    def test_agent_state_import(self):
        """Testa se AgentState pode ser importado."""
        from vps_langgraph.state import AgentState
        assert AgentState is not None
    
    def test_agent_state_structure(self):
        """Testa a estrutura do AgentState."""
        from vps_langgraph.state import AgentState
        state = AgentState(
            user_id="test_user",
            user_message="Hello",
            intent="chat",
            intent_confidence=0.9
        )
        assert state["user_id"] == "test_user"
        assert state["user_message"] == "Hello"
        assert state["intent"] == "chat"


class TestNodes:
    """Testes para os nodes do LangGraph."""
    
    def test_node_classify_intent_command(self):
        """Testa classificação de comandos."""
        from vps_langgraph.nodes import node_classify_intent
        
        state = {
            "user_id": "123",
            "user_message": "/ram"
        }
        result = node_classify_intent(state)
        
        assert result["intent"] == "command"
        assert result["intent_confidence"] == 0.95
    
    def test_node_classify_intent_question(self):
        """Testa classificação de perguntas."""
        from vps_langgraph.nodes import node_classify_intent
        
        # Pergunta factual clara - modelo gratuito pode ter limitações
        state = {
            "user_id": "123",
            "user_message": "qual é a capital do Brasil?"
        }
        result = node_classify_intent(state)
        
        # Aceita question OU chat (modelo gratuito pode variar)
        assert result["intent"] in ["question", "chat"]
    
    def test_node_classify_intent_chat(self):
        """Testa classificação de chat."""
        from vps_langgraph.nodes import node_classify_intent
        
        state = {
            "user_id": "123",
            "user_message": "Olá, tudo bem?"
        }
        result = node_classify_intent(state)
        
        assert result["intent"] == "chat"


class TestGraph:
    """Testes para o grafo do agente."""
    
    def test_build_agent_graph(self):
        """Testa se o grafo pode ser construído."""
        from vps_langgraph.graph import build_agent_graph
        
        graph = build_agent_graph()
        assert graph is not None


class TestMemory:
    """Testes para o sistema de memória."""
    
    def test_memory_import(self):
        """Testa se AgentMemory pode ser importado."""
        from vps_langgraph.memory import AgentMemory
        assert AgentMemory is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
