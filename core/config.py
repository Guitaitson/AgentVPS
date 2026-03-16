"""
ConfiguraÃƒÂ§ÃƒÂµes Centralizadas - Pydantic Settings v2

Este mÃƒÂ³dulo centraliza todas as configuraÃƒÂ§ÃƒÂµes do projeto usando Pydantic Settings.
Substitui os mÃƒÂºltiplos os.getenv() dispersos pelo cÃƒÂ³digo.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.env import ENV_FILE_CANDIDATES


class PostgresSettings(BaseSettings):
    """ConfiguraÃƒÂ§ÃƒÂµes do PostgreSQL."""

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", description="Host do PostgreSQL")
    port: int = Field(default=5432, description="Porta do PostgreSQL")
    db: str = Field(default="vps_agent", description="Nome do banco de dados")
    user: Optional[str] = Field(default=None, description="UsuÃƒÂ¡rio do PostgreSQL")
    password: Optional[str] = Field(default=None, description="Senha do PostgreSQL")

    @property
    def dsn(self) -> str:
        """Retorna string de conexÃƒÂ£o DSN."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    """ConfiguraÃƒÂ§ÃƒÂµes do Redis."""

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
    """ConfiguraÃƒÂ§ÃƒÂµes do Telegram Bot."""

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: Optional[str] = Field(default=None, description="Token do bot")
    allowed_users: str = Field(
        default="", description="IDs de usuÃƒÂ¡rios autorizados separados por vÃƒÂ­rgula"
    )

    @property
    def allowed_user_ids(self) -> list[int]:
        """Retorna lista de IDs de usuÃƒÂ¡rios autorizados."""
        return [int(uid.strip()) for uid in self.allowed_users.split(",") if uid.strip()]


class OpenRouterSettings(BaseSettings):
    """ConfiguraÃƒÂ§ÃƒÂµes do OpenRouter (LLM)."""

    model_config = SettingsConfigDict(
        env_prefix="OPENROUTER_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: Optional[str] = Field(default=None, description="Chave API do OpenRouter")
    model: str = Field(default="minimax/minimax-m2.5", description="Modelo LLM padrÃƒÂ£o")
    max_tokens: int = Field(default=8192, description="MÃƒÂ¡ximo de tokens na resposta")
    temperature: float = Field(default=0.7, description="Temperatura do LLM")
    timeout: int = Field(default=60, description="Timeout em segundos")


class QdrantSettings(BaseSettings):
    """ConfiguraÃƒÂ§ÃƒÂµes do Qdrant (MemÃƒÂ³ria SemÃƒÂ¢ntica)."""

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
    """ConfiguraÃƒÂ§ÃƒÂµes do Gateway API."""

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
    """ConfiguraÃƒÂ§ÃƒÂµes de roteamento para runtimes externos."""

    model_config = SettingsConfigDict(
        env_prefix="ORCH_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enable_mcp: bool = Field(default=False, description="Habilita delegaÃƒÂ§ÃƒÂ£o MCP")
    mcp_base_url: str = Field(default="http://127.0.0.1:8765", description="URL base MCP")
    mcp_api_key: Optional[str] = Field(default=None, description="API key MCP (opcional)")

    enable_a2a: bool = Field(default=False, description="Habilita delegaÃƒÂ§ÃƒÂ£o A2A")
    a2a_endpoint: Optional[str] = Field(default=None, description="Endpoint A2A")

    enable_acp: bool = Field(default=False, description="Habilita delegaÃƒÂ§ÃƒÂ£o ACP")
    acp_endpoint: Optional[str] = Field(default=None, description="Endpoint ACP")

    enable_deepagents: bool = Field(default=False, description="Habilita delegacao DeepAgents")
    deepagents_endpoint: Optional[str] = Field(default=None, description="Endpoint DeepAgents")

    enable_openclaw: bool = Field(default=False, description="Habilita delegacao OpenClaw")
    openclaw_endpoint: Optional[str] = Field(default=None, description="Endpoint OpenClaw")
    openclaw_api_key: Optional[str] = Field(default=None, description="API key OpenClaw")

    enable_codex_operator: bool = Field(
        default=False,
        description="Habilita delegacao para operador Codex local",
    )
    codex_command: str = Field(
        default="codex",
        description="Comando do Codex CLI disponivel no host do servico",
    )
    codex_workdir: Optional[str] = Field(
        default=None,
        description="Diretorio de trabalho usado pelo operador Codex",
    )
    codex_model: Optional[str] = Field(
        default=None,
        description="Modelo opcional passado ao Codex CLI",
    )
    codex_timeout_seconds: int = Field(
        default=360,
        description="Timeout duro em segundos para execucoes do operador Codex",
    )
    codex_heartbeat_seconds: int = Field(
        default=15,
        description="Intervalo entre heartbeats de status do operador Codex",
    )
    codex_abnormal_after_seconds: int = Field(
        default=45,
        description="A partir desse tempo sem resposta final o status do operador Codex vira anormal",
    )

    specialist_preflight_ttl_seconds: int = Field(
        default=300,
        description="TTL em segundos para cache de saude dos especialistas externos",
    )
    specialist_preflight_timeout_seconds: int = Field(
        default=8,
        description="Timeout curto em segundos para preflight FleetIntel/BrazilCNPJ",
    )
    specialist_preflight_max_attempts: int = Field(
        default=1,
        description="Tentativas para preflight dos especialistas externos",
    )

    timeout_seconds: int = Field(default=30, description="Timeout para delegaÃƒÂ§ÃƒÂµes externas")


class ConsumerSyncSettings(BaseSettings):
    """Configuracoes do consumer sync para credenciais externas FleetIntel/BrazilCNPJ."""

    model_config = SettingsConfigDict(
        env_prefix="CONSUMER_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sync_url: str = Field(
        default="https://consumer-sync.gtaitson.space/api/consumer-sync/v1/sync",
        description="Endpoint canonico do consumer sync machine-pull",
    )
    validation_report_url: str = Field(
        default="https://consumer-sync.gtaitson.space/api/consumer-sync/v1/validation-report",
        description="Endpoint canonico para publicar o validation report do consumidor",
    )
    slug: str = Field(default="agentvps", description="Consumer slug registrado no FleetIntel")
    bootstrap_secret: Optional[str] = Field(
        default=None,
        description="Bootstrap secret usado para obter o credential bundle externo",
    )
    state_file: str = Field(
        default="data/consumer-sync/agentvps.json",
        validation_alias="CONSUMER_SYNC_STATE_FILE",
        description="Arquivo local com release_id, bundle_hash e credential bundle atual",
    )
    timeout_seconds: int = Field(
        default=20,
        description="Timeout HTTP do consumer sync em segundos",
    )


class IdentitySettings(BaseSettings):
    """ConfiguraÃƒÂ§ÃƒÂµes da alma/identidade do agente."""

    model_config = SettingsConfigDict(
        env_prefix="SOUL_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    owner_name: str = Field(default="Guilherme", description="Nome do criador/owner")
    challenge_mode_enabled: bool = Field(
        default=True,
        description="Quando ativo, o agente deve contestar decisÃƒÂµes frÃƒÂ¡geis antes de planos complexos",
    )


class CatalogSettings(BaseSettings):
    """ConfiguraÃƒÂ§ÃƒÂµes do sync do catÃƒÂ¡logo de skills externos."""

    model_config = SettingsConfigDict(
        env_prefix="CATALOG_",
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(default=True, description="Habilita catÃƒÂ¡logo de skills externo")
    sources_file: str = Field(
        default="configs/skills-catalog-sources.json",
        description="Arquivo JSON com fontes do catÃƒÂ¡logo",
    )
    fallback_cache_file: str = Field(
        default="configs/skills-catalog-cache.json",
        description="Cache local quando DB estÃƒÂ¡ indisponÃƒÂ­vel",
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
        description="Intervalo para check automÃƒÂ¡tico no loop autÃƒÂ´nomo",
    )
    http_timeout_seconds: int = Field(default=20, description="Timeout HTTP das fontes remotas")
    approval_required_for_apply: bool = Field(
        default=True,
        description="Se true, apply automÃƒÂ¡tico via trigger gera proposal com aprovaÃƒÂ§ÃƒÂ£o humana",
    )

    live_source_name: str = Field(
        default="fleetintel_skillpack_repo",
        description="Nome da fonte viva do catalogo externo usada para auto-update",
    )
    auto_apply_external_skills: bool = Field(
        default=False,
        description="Aplica automaticamente diffs do catalogo externo sem proposal humana",
    )
    auto_apply_smoke_enabled: bool = Field(
        default=True,
        description="Roda smoke das skills externas apos apply automatico",
    )
    auto_rollback_on_failure: bool = Field(
        default=True,
        description="Faz rollback automatico quando o smoke falha apos auto-apply",
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
    quality_warn_score: float = Field(
        default=0.65,
        description="Abaixo disso o lote e marcado como qualidade questionavel e vai para revisao",
    )
    quality_min_score: float = Field(
        default=0.35,
        description="Abaixo disso o arquivo e descartado por baixa qualidade",
    )
    notify_on_job_completion: bool = Field(
        default=True,
        description="Envia resumo do lote de voz via Telegram quando um job termina",
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
    ConfiguraÃƒÂ§ÃƒÂµes principais da aplicaÃƒÂ§ÃƒÂ£o.
    Agrega todas as configuraÃƒÂ§ÃƒÂµes em um sÃƒÂ³ lugar.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sub-configuraÃƒÂ§ÃƒÂµes
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    orchestration: OrchestrationSettings = Field(default_factory=OrchestrationSettings)
    consumer_sync: ConsumerSyncSettings = Field(default_factory=ConsumerSyncSettings)
    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    catalog: CatalogSettings = Field(default_factory=CatalogSettings)
    voice_context: VoiceContextSettings = Field(default_factory=VoiceContextSettings)

    # ConfiguraÃƒÂ§ÃƒÂµes gerais
    env: str = Field(default="production", description="Ambiente (production/development)")
    debug: bool = Field(default=False, description="Modo debug")
    log_level: str = Field(default="INFO", description="NÃƒÂ­vel de logging")


@lru_cache()
def get_settings() -> AppSettings:
    """
    Retorna instÃƒÂ¢ncia ÃƒÂºnica das configuraÃƒÂ§ÃƒÂµes (singleton cacheado).
    Uso: from core.config import get_settings
    """
    return AppSettings()


# Alias para uso rÃƒÂ¡pido
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
    "ConsumerSyncSettings",
    "IdentitySettings",
    "CatalogSettings",
    "VoiceContextSettings",
    "get_settings",
    "settings",
]
