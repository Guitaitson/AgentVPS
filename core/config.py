"""
Configurações Centralizadas - Pydantic Settings v2

Este módulo centraliza todas as configurações do projeto usando Pydantic Settings.
Substitui os múltiplos os.getenv() dispersos pelo código.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.env import ENV_FILE_CANDIDATES


class PostgresSettings(BaseSettings):
    """Configurações do PostgreSQL."""

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
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
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", description="Host do Redis")
    port: int = Field(default=6379, description="Porta do Redis")
    password: Optional[str] = Field(default=None, description="Senha do Redis (opcional)")


class TelegramSettings(BaseSettings):
    """Configurações do Telegram Bot."""

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: Optional[str] = Field(default=None, description="Token do bot")
    allowed_users: str = Field(
        default="", description="IDs de usuários autorizados separados por vírgula"
    )

    @property
    def allowed_user_ids(self) -> list[int]:
        """Retorna lista de IDs de usuários autorizados."""
        return [int(uid.strip()) for uid in self.allowed_users.split(",") if uid.strip()]


class OpenRouterSettings(BaseSettings):
    """Configurações do OpenRouter (LLM)."""

    model_config = SettingsConfigDict(
        env_prefix="OPENROUTER_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: Optional[str] = Field(default=None, description="Chave API do OpenRouter")
    model: str = Field(default="minimax/minimax-m2.5", description="Modelo LLM padrão")
    max_tokens: int = Field(default=8192, description="Máximo de tokens na resposta")
    temperature: float = Field(default=0.7, description="Temperatura do LLM")
    timeout: int = Field(default=60, description="Timeout em segundos")


class QdrantSettings(BaseSettings):
    """Configurações do Qdrant (Memória Semântica)."""

    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str = Field(default="http://127.0.0.1:6333", description="URL do Qdrant")
    api_key: Optional[str] = Field(default=None, description="API key do Qdrant (opcional)")
    timeout_seconds: int = Field(default=5, description="Timeout para operacoes Qdrant")
    semantic_enabled: bool = Field(default=True, description="Habilita indexacao/recall semantico")
    semantic_collection: str = Field(
        default="agent_semantic_memory",
        description="Collection de memoria semantica",
    )
    semantic_vector_size: int = Field(default=64, description="Dimensao do vetor semantico")
    semantic_recall_limit: int = Field(
        default=3,
        description="Quantidade padrao de itens de recall semantico no runtime",
    )


class GatewaySettings(BaseSettings):
    """Configurações do Gateway API."""

    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", description="Host do Gateway")
    port: int = Field(default=8080, description="Porta do Gateway")
    api_key: Optional[str] = Field(default=None, description="Chave API do Gateway")
    dev_mode: bool = Field(default=False, description="Modo de desenvolvimento")


class OrchestrationSettings(BaseSettings):
    """Configurações de roteamento para runtimes externos."""

    model_config = SettingsConfigDict(
        env_prefix="ORCH_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enable_mcp: bool = Field(default=False, description="Habilita delegação MCP")
    mcp_base_url: str = Field(default="http://127.0.0.1:8765", description="URL base MCP")
    mcp_api_key: Optional[str] = Field(default=None, description="API key MCP (opcional)")

    enable_a2a: bool = Field(default=False, description="Habilita delegação A2A")
    a2a_endpoint: Optional[str] = Field(default=None, description="Endpoint A2A")

    enable_acp: bool = Field(default=False, description="Habilita delegação ACP")
    acp_endpoint: Optional[str] = Field(default=None, description="Endpoint ACP")

    enable_deepagents: bool = Field(default=False, description="Habilita delegacao DeepAgents")
    deepagents_endpoint: Optional[str] = Field(default=None, description="Endpoint DeepAgents")

    enable_openclaw: bool = Field(default=False, description="Habilita delegacao OpenClaw")
    openclaw_endpoint: Optional[str] = Field(default=None, description="Endpoint OpenClaw")
    openclaw_api_key: Optional[str] = Field(default=None, description="API key OpenClaw")

    timeout_seconds: int = Field(default=30, description="Timeout para delegações externas")


class IdentitySettings(BaseSettings):
    """Configurações da alma/identidade do agente."""

    model_config = SettingsConfigDict(
        env_prefix="SOUL_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    owner_name: str = Field(default="Guilherme", description="Nome do criador/owner")
    challenge_mode_enabled: bool = Field(
        default=True,
        description="Quando ativo, o agente deve contestar decisões frágeis antes de planos complexos",
    )


class CatalogSettings(BaseSettings):
    """Configurações do sync do catálogo de skills externos."""

    model_config = SettingsConfigDict(
        env_prefix="CATALOG_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(default=True, description="Habilita catálogo de skills externo")
    sources_file: str = Field(
        default="configs/skills-catalog-sources.json",
        description="Arquivo JSON com fontes do catálogo",
    )
    fallback_cache_file: str = Field(
        default="configs/skills-catalog-cache.json",
        description="Cache local quando DB está indisponível",
    )
    check_interval_seconds: int = Field(
        default=6 * 60 * 60,
        description="Intervalo para check automático no loop autônomo",
    )
    http_timeout_seconds: int = Field(default=20, description="Timeout HTTP das fontes remotas")
    approval_required_for_apply: bool = Field(
        default=True,
        description="Se true, apply automático via trigger gera proposal com aprovação humana",
    )


class AppSettings(BaseSettings):
    """
    Configurações principais da aplicação.
    Agrega todas as configurações em um só lugar.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sub-configurações
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    orchestration: OrchestrationSettings = Field(default_factory=OrchestrationSettings)
    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    catalog: CatalogSettings = Field(default_factory=CatalogSettings)

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
    "OrchestrationSettings",
    "IdentitySettings",
    "CatalogSettings",
    "get_settings",
    "settings",
]
