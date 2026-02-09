"""
Testes para o LLM Provider Abstraction.
"""

import pytest

from core.llm.provider import (
    LLMProviderType,
    LLMMessage,
    LLMResponse,
    LLMConfig,
    LLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    LLMProviderFactory,
    create_openai_config,
    create_anthropic_config,
)


class TestLLMConfig:
    """Testes para configuração do LLM."""
    
    def test_create_openai_config(self):
        """Testa criação de configuração OpenAI."""
        config = create_openai_config(
            api_key="test-key",
            model="gpt-4o-mini",
            max_tokens=2048,
        )
        
        assert config.provider_type == LLMProviderType.OPENAI
        assert config.model == "gpt-4o-mini"
        assert config.api_key == "test-key"
        assert config.max_tokens == 2048
    
    def test_create_anthropic_config(self):
        """Testa criação de configuração Anthropic."""
        config = create_anthropic_config(
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
            temperature=0.5,
        )
        
        assert config.provider_type == LLMProviderType.ANTHROPIC
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.api_key == "test-key"
        assert config.temperature == 0.5


class TestLLMMessage:
    """Testes para mensagens do LLM."""
    
    def test_create_message(self):
        """Testa criação de mensagem."""
        message = LLMMessage(
            role="user",
            content="Olá!",
            metadata={"timestamp": "2024-01-01"},
        )
        
        assert message.role == "user"
        assert message.content == "Olá!"
        assert message.metadata["timestamp"] == "2024-01-01"


class TestLLMResponse:
    """Testes para resposta do LLM."""
    
    def test_create_response(self):
        """Testa criação de resposta."""
        response = LLMResponse(
            content="Olá! Como posso ajudar?",
            model="gpt-4o-mini",
            tokens_used=100,
            finish_reason="stop",
            metadata={"prompt_tokens": 50, "completion_tokens": 50},
        )
        
        assert response.content == "Olá! Como posso ajudar?"
        assert response.model == "gpt-4o-mini"
        assert response.tokens_used == 100
        assert response.finish_reason == "stop"
        assert response.metadata["prompt_tokens"] == 50


class TestLLMProviderFactory:
    """Testes para fábrica de provedores."""
    
    def test_create_openai_provider(self):
        """Testa criação de provedor OpenAI."""
        config = create_openai_config(api_key="test-key")
        provider = LLMProviderFactory.create(config)
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.config.provider_type == LLMProviderType.OPENAI
    
    def test_create_anthropic_provider(self):
        """Testa criação de provedor Anthropic."""
        config = create_anthropic_config(api_key="test-key")
        provider = LLMProviderFactory.create(config)
        
        assert isinstance(provider, AnthropicProvider)
        assert provider.config.provider_type == LLMProviderType.ANTHROPIC
    
    def test_create_unsupported_provider(self):
        """Testa criação de provedor não suportado."""
        config = LLMConfig(
            provider_type=LLMProviderType.MINIMAX,
            model="test-model",
            api_key="test-key",
        )
        
        with pytest.raises(ValueError, match="Provedor não suportado"):
            LLMProviderFactory.create(config)
    
    def test_register_custom_provider(self):
        """Testa registro de provedor customizado."""
        
        class CustomProvider(LLMProvider):
            def _validate_config(self) -> None:
                pass
            
            async def generate(self, messages, **kwargs) -> LLMResponse:
                return LLMResponse(content="test", model="test")
            
            async def generate_stream(self, messages, **kwargs):
                yield "test"
        
        # Registrar provedor
        LLMProviderFactory.register_provider(
            LLMProviderType.MINIMAX,
            CustomProvider
        )
        
        # Criar provedor
        config = LLMConfig(
            provider_type=LLMProviderType.MINIMAX,
            model="test-model",
            api_key="test-key",
        )
        provider = LLMProviderFactory.create(config)
        
        assert isinstance(provider, CustomProvider)


class TestOpenAIProvider:
    """Testes para provedor OpenAI."""
    
    def test_validate_config_without_api_key(self):
        """Testa validação sem API key."""
        config = LLMConfig(
            provider_type=LLMProviderType.OPENAI,
            model="gpt-4o-mini",
            api_key="",
        )
        
        with pytest.raises(ValueError, match="API key do OpenAI é obrigatória"):
            OpenAIProvider(config)
    
    def test_get_model_info(self):
        """Testa obtenção de informações do modelo."""
        config = create_openai_config(api_key="test-key")
        provider = OpenAIProvider(config)
        
        info = provider.get_model_info()
        
        assert info["provider"] == "openai"
        assert info["model"] == "gpt-4o-mini"
        assert info["max_tokens"] == 4096
        assert info["temperature"] == 0.7


class TestAnthropicProvider:
    """Testes para provedor Anthropic."""
    
    def test_validate_config_without_api_key(self):
        """Testa validação sem API key."""
        config = LLMConfig(
            provider_type=LLMProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key="",
        )
        
        with pytest.raises(ValueError, match="API key do Anthropic é obrigatória"):
            AnthropicProvider(config)
    
    def test_get_model_info(self):
        """Testa obtenção de informações do modelo."""
        config = create_anthropic_config(api_key="test-key")
        provider = AnthropicProvider(config)
        
        info = provider.get_model_info()
        
        assert info["provider"] == "anthropic"
        assert info["model"] == "claude-3-5-sonnet-20241022"
        assert info["max_tokens"] == 4096
        assert info["temperature"] == 0.7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
