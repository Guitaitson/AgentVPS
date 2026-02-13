"""
Configurações Centralizadas - Pydantic Settings v2

Este módulo centraliza todas as configurações do projeto usando Pydantic Settings.
Substitui os múltiplos os.getenv() dispersos pelo código.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    """Configurações do PostgreSQL."""
    
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file="/opt/vps-agent/core/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    host: str = Field(default="127.0.0.1", description="Host do PostgreSQL")
    port: int = Field(default=5432, description="Porta do PostgreSQL")
    db: str = Field(default="vps_agent", description="Nome do banco de dados")
    user: Optional[str] = Field(default=None, description="Usuário do PostgreSQL")
    password: Optional[str] = Field(default=None, description="Senha do PostgreSQL")
    
    @property
    def dsn(self) -> str:
        """Retorna string de conexão DSN."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    """Configurações do Redis."""
    
    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file="/opt/vps-agent/core/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    host: str = Field(default="127.0.0.1", description="Host do Redis")
    port: int = Field(default=6379, description="Porta do Redis")
    password: Optional[str] = Field(default=None, description="Senha do Redis (opcional)")


class TelegramSettings(BaseSettings):
    """Configurações do Telegram Bot."""
    
    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file="/opt/vps-agent/core/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    bot_token: Optional[str] = Field(default=None, description="Token do bot")
    allowed_users: str = Field(default="", description="IDs de usuários autorizados separados por vírgula")
    
    @property
    def allowed_user_ids(self) -> list[int]:
        """Retorna lista de IDs de usuários autorizados."""
        return [int(uid.strip()) for uid in self.allowed_users.split(",") if uid.strip()]


class OpenRouterSettings(BaseSettings):
    """Configurações do OpenRouter (LLM)."""
    
    model_config = SettingsConfigDict(
        env_prefix="OPENROUTER_",
        env_file="/opt/vps-agent/core/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    api_key: Optional[str] = Field(default=None, description="Chave API do OpenRouter")
    model: str = Field(default="google/gemini-2.5-flash-lite", description="Modelo LLM padrão")
    max_tokens: int = Field(default=256, description="Máximo de tokens na resposta")
    temperature: float = Field(default=0.7, description="Temperatura do LLM")
    timeout: int = Field(default=10, description="Timeout em segundos")


class QdrantSettings(BaseSettings):
    """Configurações do Qdrant (Memória Semântica)."""
    
    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
        env_file="/opt/vps-agent/core/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    url: str = Field(default="http://127.0.0.1:6333", description="URL do Qdrant")


class GatewaySettings(BaseSettings):
    """Configurações do Gateway API."""
    
    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_",
        env_file="/opt/vps-agent/core/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    host: str = Field(default="0.0.0.0", description="Host do Gateway")
    port: int = Field(default=8080, description="Porta do Gateway")
    api_key: Optional[str] = Field(default=None, description="Chave API do Gateway")
    dev_mode: bool = Field(default=False, description="Modo de desenvolvimento")


class AppSettings(BaseSettings):
    """
    Configurações principais da aplicação.
    Agrega todas as configurações em um só lugar.
    """
    
    model_config = SettingsConfigDict(
        env_file="/opt/vps-agent/core/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Sub-configurações
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    
    # Configurações gerais
    env: str = Field(default="production", description="Ambiente (production/development)")
    debug: bool = Field(default=False, description="Modo debug")
    log_level: str = Field(default="INFO", description="Nível de logging")


@lru_cache()
def get_settings() -> AppSettings:
    """
    Retorna instância única das configurações (singleton cacheado).
    Uso: from core.config import get_settings
    """
    return AppSettings()


# Alias para uso rápido
settings = get_settings()


__all__ = [
    "AppSettings",
    "PostgresSettings", 
    "RedisSettings",
    "TelegramSettings",
    "OpenRouterSettings",
    "QdrantSettings",
    "GatewaySettings",
    "get_settings",
    "settings",
]
