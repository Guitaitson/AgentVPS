"""
Testes de Integração - Sprint 3

Testes end-to-end do fluxo:
Telegram → Gateway → LangGraph → Tools → Response
"""

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

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
            "timestamp": "2026-02-13T12:00:00Z",
        }

    def test_react_node_import(self, mock_state):
        """Testa que react_node pode ser importado (substitui intent_classifier)."""
        from core.vps_langgraph.react_node import node_react, route_after_react

        assert node_react is not None
        assert route_after_react is not None

    def test_route_after_react_tool_call(self, mock_state):
        """Testa roteamento para tool call."""
        from core.vps_langgraph.react_node import route_after_react

        state = {
            "action_required": True,
            "plan": [{"type": "skill", "action": "get_ram", "args": {}}],
            "current_step": 0,
        }
        assert route_after_react(state) == "security_check"

    def test_route_after_react_direct(self, mock_state):
        """Testa roteamento para resposta direta."""
        from core.vps_langgraph.react_node import route_after_react

        state = {"action_required": False, "response": "Ola!"}
        assert route_after_react(state) == "respond"


class TestSkillRegistryIntegration:
    """Testes de integração do Skill Registry (substitui system_tools)."""

    def test_skill_registry_available(self):
        """Verifica que o skill registry carrega skills."""
        from core.skills.registry import get_skill_registry

        registry = get_skill_registry()
        skills = registry.list_skills()

        assert len(skills) > 0, "Nenhum skill registrado"

    def test_skill_registry_has_core_skills(self):
        """Verifica que skills core estao registrados."""
        from core.skills.registry import get_skill_registry

        registry = get_skill_registry()
        # Pelo menos shell_exec deve existir
        shell = registry.get("shell_exec")
        assert shell is not None, "shell_exec skill nao encontrado"

    def test_skill_registry_tool_schemas(self):
        """Verifica que tool schemas sao gerados para function calling."""
        from core.skills.registry import get_skill_registry

        registry = get_skill_registry()
        schemas = registry.list_tool_schemas()

        assert len(schemas) > 0, "Nenhum tool schema gerado"
        # Cada schema tem formato OpenAI function calling
        for schema in schemas:
            assert "type" in schema
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]


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
        await memory.save_fact(user_id="test_user", fact="Test fact", category="test")

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
        from core.observability import get_tracer, init_observability

        # Inicializa (sem exporters para teste)
        init_observability(console_export=False)

        # Verifica que tracer foi criado
        tracer = get_tracer()
        assert tracer is not None

    def test_trace_decorators(self):
        """Testa decorators de tracing."""
        from core.observability import trace_sync

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
        "response": None,
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
