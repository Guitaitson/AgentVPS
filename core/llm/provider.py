"""
LLM Provider Abstraction - F1-06

Abstração para múltiplos provedores de LLM (OpenAI, Anthropic, etc).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class LLMProviderType(Enum):
    """Tipos de provedores de LLM."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MINIMAX = "minimax"
    GLM = "glm"
    CUSTOM = "custom"


@dataclass
class LLMMessage:
    """Mensagem para o LLM."""
    role: str  # system, user, assistant
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Resposta do LLM."""
    content: str
    model: str
    tokens_used: int = 0
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMConfig:
    """Configuração do provedor de LLM."""
    provider_type: LLMProviderType
    model: str
    api_key: str
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Classe base abstrata para provedores de LLM."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Valida a configuração do provedor."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """
        Gera uma resposta do LLM.
        
        Args:
            messages: Lista de mensagens
            **kwargs: Parâmetros adicionais
            
        Returns:
            Resposta do LLM
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: List[LLMMessage],
        **kwargs
    ):
        """
        Gera uma resposta em streaming.
        
        Args:
            messages: Lista de mensagens
            **kwargs: Parâmetros adicionais
            
        Yields:
            Chunks da resposta
        """
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """Retorna informações sobre o modelo."""
        return {
            "provider": self.config.provider_type.value,
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }


class OpenAIProvider(LLMProvider):
    """Provedor OpenAI."""
    
    def _validate_config(self) -> None:
        """Valida a configuração do OpenAI."""
        if not self.config.api_key:
            raise ValueError("API key do OpenAI é obrigatória")
    
    async def generate(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """Gera uma resposta do OpenAI."""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            
            # Converter mensagens para formato OpenAI
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            # Chamar API
            response = await client.chat.completions.create(
                model=self.config.model,
                messages=openai_messages,
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
                **{k: v for k, v in kwargs.items() 
                   if k not in ["max_tokens", "temperature"]}
            )
            
            # Extrair resposta
            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content,
                model=response.model,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                finish_reason=choice.finish_reason,
                metadata={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                }
            )
        except Exception as e:
            raise RuntimeError(f"Erro ao chamar OpenAI: {e}")
    
    async def generate_stream(
        self,
        messages: List[LLMMessage],
        **kwargs
    ):
        """Gera uma resposta em streaming do OpenAI."""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            
            # Converter mensagens para formato OpenAI
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            # Chamar API em streaming
            stream = await client.chat.completions.create(
                model=self.config.model,
                messages=openai_messages,
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
                stream=True,
                **{k: v for k, v in kwargs.items() 
                   if k not in ["max_tokens", "temperature", "stream"]}
            )
            
            # Yield chunks
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise RuntimeError(f"Erro ao chamar OpenAI streaming: {e}")


class AnthropicProvider(LLMProvider):
    """Provedor Anthropic."""
    
    def _validate_config(self) -> None:
        """Valida a configuração do Anthropic."""
        if not self.config.api_key:
            raise ValueError("API key do Anthropic é obrigatória")
    
    async def generate(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """Gera uma resposta do Anthropic."""
        try:
            from anthropic import AsyncAnthropic
            
            client = AsyncAnthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )
            
            # Converter mensagens para formato Anthropic
            # Anthropic requer que a primeira mensagem seja "system"
            system_message = None
            anthropic_messages = []
            
            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    anthropic_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # Chamar API
            response = await client.messages.create(
                model=self.config.model,
                system=system_message,
                messages=anthropic_messages,
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
                **{k: v for k, v in kwargs.items() 
                   if k not in ["max_tokens", "temperature"]}
            )
            
            # Extrair resposta
            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                finish_reason=response.stop_reason,
                metadata={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                }
            )
        except Exception as e:
            raise RuntimeError(f"Erro ao chamar Anthropic: {e}")
    
    async def generate_stream(
        self,
        messages: List[LLMMessage],
        **kwargs
    ):
        """Gera uma resposta em streaming do Anthropic."""
        try:
            from anthropic import AsyncAnthropic
            
            client = AsyncAnthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )
            
            # Converter mensagens para formato Anthropic
            system_message = None
            anthropic_messages = []
            
            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    anthropic_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # Chamar API em streaming
            async with client.messages.stream(
                model=self.config.model,
                system=system_message,
                messages=anthropic_messages,
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
                **{k: v for k, v in kwargs.items() 
                   if k not in ["max_tokens", "temperature"]}
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            raise RuntimeError(f"Erro ao chamar Anthropic streaming: {e}")


class LLMProviderFactory:
    """Fábrica para criar provedores de LLM."""
    
    _providers = {
        LLMProviderType.OPENAI: OpenAIProvider,
        LLMProviderType.ANTHROPIC: AnthropicProvider,
    }
    
    @classmethod
    def create(cls, config: LLMConfig) -> LLMProvider:
        """
        Cria um provedor de LLM baseado na configuração.
        
        Args:
            config: Configuração do provedor
            
        Returns:
            Instância do provedor
        """
        provider_class = cls._providers.get(config.provider_type)
        if not provider_class:
            raise ValueError(f"Provedor não suportado: {config.provider_type}")
        
        return provider_class(config)
    
    @classmethod
    def register_provider(
        cls,
        provider_type: LLMProviderType,
        provider_class: type
    ) -> None:
        """
        Registra um novo provedor.
        
        Args:
            provider_type: Tipo do provedor
            provider_class: Classe do provedor
        """
        cls._providers[provider_type] = provider_class


def create_openai_config(
    api_key: str,
    model: str = "gpt-4o-mini",
    base_url: Optional[str] = None,
    **kwargs
) -> LLMConfig:
    """Cria configuração para OpenAI."""
    return LLMConfig(
        provider_type=LLMProviderType.OPENAI,
        model=model,
        api_key=api_key,
        base_url=base_url,
        **kwargs
    )


def create_anthropic_config(
    api_key: str,
    model: str = "claude-3-5-sonnet-20241022",
    **kwargs
) -> LLMConfig:
    """Cria configuração para Anthropic."""
    return LLMConfig(
        provider_type=LLMProviderType.ANTHROPIC,
        model=model,
        api_key=api_key,
        **kwargs
    )
