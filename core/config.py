"""
ConfiguraÃ§Ãµes Centralizadas - Pydantic Settings v2

Este mÃ³dulo centraliza todas as configuraÃ§Ãµes do projeto usando Pydantic Settings.
Substitui os mÃºltiplos os.getenv() dispersos pelo cÃ³digo.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.env import ENV_FILE_CANDIDATES


class PostgresSettings(BaseSettings):
    """ConfiguraÃ§Ãµes do PostgreSQL."""

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", description="Host do PostgreSQL")
    port: int = Field(default=5432, description="Porta do PostgreSQL")
    db: str = Field(default="vps_agent", description="Nome do banco de dados")
    user: Optional[str] = Field(default=None, description="UsuÃ¡rio do PostgreSQL")
    password: Optional[str] = Field(default=None, description="Senha do PostgreSQL")

    @property
    def dsn(self) -> str:
        """Retorna string de conexÃ£o DSN."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    """ConfiguraÃ§Ãµes do Redis."""

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
    """ConfiguraÃ§Ãµes do Telegram Bot."""

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: Optional[str] = Field(default=None, description="Token do bot")
    allowed_users: str = Field(
        default="", description="IDs de usuÃ¡rios autorizados separados por vÃ­rgula"
    )

    @property
    def allowed_user_ids(self) -> list[int]:
        """Retorna lista de IDs de usuÃ¡rios autorizados."""
        return [int(uid.strip()) for uid in self.allowed_users.split(",") if uid.strip()]


class OpenRouterSettings(BaseSettings):
    """ConfiguraÃ§Ãµes do OpenRouter (LLM)."""

    model_config = SettingsConfigDict(
        env_prefix="OPENROUTER_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: Optional[str] = Field(default=None, description="Chave API do OpenRouter")
    model: str = Field(default="minimax/minimax-m2.5", description="Modelo LLM padrÃ£o")
    max_tokens: int = Field(default=8192, description="MÃ¡ximo de tokens na resposta")
    temperature: float = Field(default=0.7, description="Temperatura do LLM")
    timeout: int = Field(default=60, description="Timeout em segundos")


class QdrantSettings(BaseSettings):
    """ConfiguraÃ§Ãµes do Qdrant (MemÃ³ria SemÃ¢ntica)."""

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
    """ConfiguraÃ§Ãµes do Gateway API."""

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
    """ConfiguraÃ§Ãµes de roteamento para runtimes externos."""

    model_config = SettingsConfigDict(
        env_prefix="ORCH_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enable_mcp: bool = Field(default=False, description="Habilita delegaÃ§Ã£o MCP")
    mcp_base_url: str = Field(default="http://127.0.0.1:8765", description="URL base MCP")
    mcp_api_key: Optional[str] = Field(default=None, description="API key MCP (opcional)")

    enable_a2a: bool = Field(default=False, description="Habilita delegaÃ§Ã£o A2A")
    a2a_endpoint: Optional[str] = Field(default=None, description="Endpoint A2A")

    enable_acp: bool = Field(default=False, description="Habilita delegaÃ§Ã£o ACP")
    acp_endpoint: Optional[str] = Field(default=None, description="Endpoint ACP")

    enable_deepagents: bool = Field(default=False, description="Habilita delegacao DeepAgents")
    deepagents_endpoint: Optional[str] = Field(default=None, description="Endpoint DeepAgents")

    enable_openclaw: bool = Field(default=False, description="Habilita delegacao OpenClaw")
    openclaw_endpoint: Optional[str] = Field(default=None, description="Endpoint OpenClaw")
    openclaw_api_key: Optional[str] = Field(default=None, description="API key OpenClaw")

    timeout_seconds: int = Field(default=30, description="Timeout para delegaÃ§Ãµes externas")


class IdentitySettings(BaseSettings):
    """ConfiguraÃ§Ãµes da alma/identidade do agente."""

    model_config = SettingsConfigDict(
        env_prefix="SOUL_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    owner_name: str = Field(default="Guilherme", description="Nome do criador/owner")
    challenge_mode_enabled: bool = Field(
        default=True,
        description="Quando ativo, o agente deve contestar decisÃµes frÃ¡geis antes de planos complexos",
    )


class CatalogSettings(BaseSettings):
    """ConfiguraÃ§Ãµes do sync do catÃ¡logo de skills externos."""

    model_config = SettingsConfigDict(
        env_prefix="CATALOG_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(default=True, description="Habilita catÃ¡logo de skills externo")
    sources_file: str = Field(
        default="configs/skills-catalog-sources.json",
        description="Arquivo JSON com fontes do catÃ¡logo",
    )
    fallback_cache_file: str = Field(
        default="configs/skills-catalog-cache.json",
        description="Cache local quando DB estÃ¡ indisponÃ­vel",
    )
    history_file: str = Field(
        default="configs/skills-catalog-history.json",
        description="Historico local para rollback/provenance",
    )
    pins_file: str = Field(
        default="configs/skills-catalog-pins.json",
        description="Pins locais quando DB estiver indisponivel",
    )
    check_interval_seconds: int = Field(
        default=6 * 60 * 60,
        description="Intervalo para check automÃ¡tico no loop autÃ´nomo",
    )
    http_timeout_seconds: int = Field(default=20, description="Timeout HTTP das fontes remotas")
    approval_required_for_apply: bool = Field(
        default=True,
        description="Se true, apply automÃ¡tico via trigger gera proposal com aprovaÃ§Ã£o humana",
    )


class VoiceContextSettings(BaseSettings):
    """Configuracoes da captura de contexto por voz."""

    model_config = SettingsConfigDict(
        env_prefix="VOICE_CONTEXT_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(default=True, description="Habilita ingestao de contexto por voz")
    user_id: Optional[str] = Field(
        default=None,
        description="User id alvo para memoria derivada dos audios",
    )
    inbox_dir: str = Field(
        default="/opt/vps-agent/data/voice/inbox",
        description="Diretorio de inbox para audios brutos",
    )
    processing_dir: str = Field(
        default="/opt/vps-agent/data/voice/processing",
        description="Diretorio temporario de processamento",
    )
    archive_dir: str = Field(
        default="/opt/vps-agent/data/voice/archive",
        description="Diretorio de arquivamento de audios processados",
    )
    failed_dir: str = Field(
        default="/opt/vps-agent/data/voice/failed",
        description="Diretorio para arquivos com falha",
    )
    transcripts_dir: str = Field(
        default="/opt/vps-agent/data/voice/transcripts",
        description="Diretorio para transcripts operacionais de curta retencao",
    )
    batch_hour: int = Field(default=2, description="Hora local para lote diario automatico")
    auto_commit_threshold: float = Field(
        default=0.75,
        description="Confianca minima para auto-commit de baixo risco",
    )
    transcript_ttl_days: int = Field(
        default=7,
        description="Retencao operacional de transcripts brutos",
    )
    max_files_per_run: int = Field(
        default=12,
        description="Limite de arquivos processados por rodada",
    )
    auto_commit_max_duration_minutes: int = Field(
        default=30,
        description="Audios acima desse limite exigem revisao humana para todos os itens",
    )
    file_extensions: str = Field(
        default=".mp3,.wav,.ogg,.m4a,.flac,.aac,.mp4",
        description="Extensoes aceitas na inbox, separadas por virgula",
    )
    extract_with_llm: bool = Field(
        default=True,
        description="Tenta usar LLM para extracao estruturada antes do fallback heuristico",
    )
    create_daily_summary: bool = Field(
        default=True,
        description="Gera item de resumo diario na memoria episodica",
    )
    whisper_model_size: str = Field(
        default="tiny",
        validation_alias="WHISPER_MODEL_SIZE",
        description="Modelo faster-whisper usado localmente",
    )
    whisper_device: str = Field(
        default="cpu",
        validation_alias="WHISPER_DEVICE",
        description="Dispositivo usado na transcricao local",
    )


class AppSettings(BaseSettings):
    """
    ConfiguraÃ§Ãµes principais da aplicaÃ§Ã£o.
    Agrega todas as configuraÃ§Ãµes em um sÃ³ lugar.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sub-configuraÃ§Ãµes
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    orchestration: OrchestrationSettings = Field(default_factory=OrchestrationSettings)
    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    catalog: CatalogSettings = Field(default_factory=CatalogSettings)
    voice_context: VoiceContextSettings = Field(default_factory=VoiceContextSettings)

    # ConfiguraÃ§Ãµes gerais
    env: str = Field(default="production", description="Ambiente (production/development)")
    debug: bool = Field(default=False, description="Modo debug")
    log_level: str = Field(default="INFO", description="NÃ­vel de logging")


@lru_cache()
def get_settings() -> AppSettings:
    """
    Retorna instÃ¢ncia Ãºnica das configuraÃ§Ãµes (singleton cacheado).
    Uso: from core.config import get_settings
    """
    return AppSettings()


# Alias para uso rÃ¡pido
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
    "VoiceContextSettings",
    "get_settings",
    "settings",
]
