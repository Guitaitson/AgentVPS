"""
Testes de Integração - Sprint 3

Testes end-to-end do fluxo:
Telegram → Gateway → LangGraph → Tools → Response
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any


# ============================================
# Testes de Integração do Fluxo Principal
# ============================================

class TestIntegrationFlow:
    """Testes do fluxo completo de processamento de mensagem."""
    
    @pytest.fixture
    def mock_state(self) -> Dict[str, Any]:
        """State inicial para testes."""
        return {
            "user_id": "504326069",
            "user_message": "/status",
            "messages": [],
            "intent": None,
            "intent_confidence": 0.0,
            "plan": [],
            "current_step": 0,
            "tools_needed": [],
            "execution_result": None,
            "response": None,
            "timestamp": "2026-02-13T12:00:00Z"
        }
    
    def test_intent_classification_command(self, mock_state):
        """Testa classificação de intent para comando."""
        # Arrange
        from core.vps_langgraph.intent_classifier import classify_intent
        
        # Act
        result = classify_intent("/status")
        
        # Assert
        assert result["intent"] == "command"
        assert result["confidence"] > 0.8
    
    def test_intent_classification_question(self, mock_state):
        """Testa classificação de intent para pergunta."""
        from core.vps_langgraph.intent_classifier import classify_intent
        
        result = classify_intent("quanto RAM estamos usando?")
        
        assert result["intent"] == "question"
        assert result["confidence"] > 0.7
    
    def test_intent_classification_task(self, mock_state):
        """Testa classificação de intent para tarefa."""
        from core.vps_langgraph.intent_classifier import classify_intent
        
        result = classify_intent("liste meus containers")
        
        assert result["intent"] in ["command", "task"]
        assert result["confidence"] > 0.6


class TestToolsIntegration:
    """Testes de integração das tools do sistema."""
    
    def test_system_tools_available(self):
        """Verifica que todas as tools estão disponíveis."""
        from core.tools.system_tools import TOOLS_REGISTRY
        
        expected_tools = [
            "get_ram",
            "list_containers", 
            "get_system_status",
            "check_postgres",
            "check_redis"
        ]
        
        for tool in expected_tools:
            assert tool in TOOLS_REGISTRY, f"Tool {tool} não encontrada"
    
    def test_tool_execution_get_ram(self):
        """Testa execução da tool get_ram."""
        from core.tools.system_tools import get_ram_usage
        
        result = get_ram_usage()
        
        # Verifica que retornou algo estruturado
        assert isinstance(result, str)
        assert "RAM" in result or "MB" in result or "meminfo" in result
    
    def test_tool_execution_check_postgres(self):
        """Testa execução da tool check_postgres."""
        from core.tools.system_tools import check_postgres
        
        result = check_postgres()
        
        # Verifica que retornou algo
        assert isinstance(result, str)
        assert "PostgreSQL" in result or "Error" in result


class TestMemoryIntegration:
    """Testes de integração da memória."""
    
    @pytest.mark.asyncio
    async def test_memory_save_and_retrieve(self):
        """Testa salvar e recuperar memória."""
        # Skip se não houver banco disponível
        pytest.skip("Requer banco PostgreSQL configurado")
        
        from core.vps_langgraph.memory import AgentMemory
        
        memory = AgentMemory()
        
        # Save
        await memory.save_fact(
            user_id="test_user",
            fact="Test fact",
            category="test"
        )
        
        # Retrieve
        facts = await memory.get_facts("test_user", limit=5)
        
        assert len(facts) > 0
    
    def test_memory_config(self):
        """Testa configuração de memória via config."""
        from core.config import get_settings
        
        settings = get_settings()
        
        # Verifica configurações de banco
        assert settings.postgres.host is not None
        assert settings.redis.host is not None


class TestGatewayIntegration:
    """Testes de integração do Gateway."""
    
    def test_gateway_routing(self):
        """Testa roteamento de mensagens no Gateway."""
        from core.gateway.session_manager import SessionManager
        
        # Verifica que consegue criar manager
        manager = SessionManager()
        
        assert manager is not None
    
    def test_gateway_rate_limiter(self):
        """Testa rate limiter."""
        from core.gateway.rate_limiter import RateLimiter
        
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        # Testaallowance
        assert limiter.is_allowed("test_user") is True


class TestSecurityIntegration:
    """Testes de integração de segurança."""
    
    def test_allowlist_check(self):
        """Testa verificação de allowlist."""
        from core.security.allowlist import is_allowed
        
        # Verifica função existe e é callable
        assert callable(is_allowed)
    
    def test_action_classification(self):
        """Testa classificação de ações."""
        # Teste de classificação de ação
        # Safe: ler status
        # Moderate: criar arquivo
        # Dangerous: deletar sistema
        
        from core.security.allowlist import classify_action
        
        # Ação segura
        result = classify_action("read", "status")
        assert result in ["safe", "moderate", "dangerous"]
        
        # Ação perigosa
        result = classify_action("delete", "system")
        assert result == "dangerous"


class TestObservabilityIntegration:
    """Testes de integração de observabilidade."""
    
    def test_observability_init(self):
        """Testa inicialização de observabilidade."""
        from core.observability import init_observability, get_tracer
        
        # Inicializa (sem exporters para teste)
        init_observability(console_export=False)
        
        # Verifica que tracer foi criado
        tracer = get_tracer()
        assert tracer is not None
    
    def test_trace_decorators(self):
        """Testa decorators de tracing."""
        from core.observability import trace_sync, get_tracer
        
        @trace_sync("test_function")
        def test_func():
            return "test_result"
        
        # Executa função com trace
        result = test_func()
        
        assert result == "test_result"


# ============================================
# Fixtures para testes de integração
# ============================================

@pytest.fixture
def mock_telegram_update():
    """Mock de update do Telegram."""
    update = MagicMock()
    update.message.from_user.id = 504326069
    update.message.text = "/status"
    update.message.chat.id = 504326069
    return update


@pytest.fixture
def mock_langgraph_state():
    """Mock de state do LangGraph."""
    return {
        "user_id": "504326069",
        "user_message": "test message",
        "messages": [],
        "intent": "command",
        "plan": [{"type": "command", "action": "status"}],
        "response": None
    }


# ============================================
# Testes End-to-End
# ============================================

class TestEndToEnd:
    """Testes end-to-end completos."""
    
    @pytest.mark.asyncio
    async def test_full_message_flow(self):
        """Testa fluxo completo: mensagem → resposta."""
        pytest.skip("Requer configuração completa de serviços")
        
        # Este teste seria executado em ambiente de integração real
        # 1. Receber mensagem do Telegram
        # 2. Enviar para Gateway
        # 3. Processar pelo LangGraph
        # 4. Executar tools necessárias
        # 5. Gerar resposta
        # 6. Enviar resposta para Telegram
        
        pass
    
    def test_config_loading(self):
        """Testa que configurações são carregadas corretamente."""
        from core.config import get_settings
        
        settings = get_settings()
        
        # Verifica configurações básicas
        assert settings.env in ["production", "development"]
        assert settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]
