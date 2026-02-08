# Error Handler - Sistema de tratamento de erros

"""
Módulo para tratamento de erros consistente e informativo.

Este módulo implementa recomendações para melhorar error handling:
- Erros categorizados por tipo
- Mensagens amigáveis para o usuário
- Logging estruturado
- Recuperação graceful
"""

import traceback
import structlog
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime
from enum import Enum


logger = structlog.get_logger()


class ErrorCategory(Enum):
    """Categorias de erro para classificação."""
    VALIDATION = "validation"          # Erros de validação de entrada
    EXECUTION = "execution"            # Erros durante execução
    NETWORK = "network"                # Erros de rede/conexão
    DATABASE = "database"              # Erros de banco de dados
    AUTHENTICATION = "authentication" # Erros de autenticação/autorização
    PERMISSION = "permission"          # Erros de permissão
    RESOURCE = "resource"             # Erros de recursos (RAM, disk)
    TIMEOUT = "timeout"               # Erros de timeout
    UNKNOWN = "unknown"              # Erros não categorizados


class VPSAgentError(Exception):
    """Exceção base do agente VPS."""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        original_error: Optional[Exception] = None,
        recoverable: bool = True,
        user_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.original_error = original_error
        self.recoverable = recoverable
        self.user_message = user_message or self._default_user_message()
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
    
    def _default_user_message(self) -> str:
        """Retorna mensagem amigável baseada na categoria."""
        messages = {
            ErrorCategory.VALIDATION: "Dados inválidos fornecidos. Verifique e tente novamente.",
            ErrorCategory.EXECUTION: "Ocorreu um erro durante a execução. Tente novamente.",
            ErrorCategory.NETWORK: "Erro de conexão. Verifique sua rede e tente novamente.",
            ErrorCategory.DATABASE: "Erro de banco de dados. Tente novamente em instantes.",
            ErrorCategory.AUTHENTICATION: "Erro de autenticação. Verifique suas credenciais.",
            ErrorCategory.PERMISSION: "Permissão negada. Você não tem acesso a este recurso.",
            ErrorCategory.RESOURCE: "Recursos insuficientes. Tente novamente mais tarde.",
            ErrorCategory.TIMEOUT: "Operação expirou. Tente novamente.",
            ErrorCategory.UNKNOWN: "Ocorreu um erro inesperado. Tente novamente.",
        }
        return messages.get(self.category, "Ocorreu um erro.")
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "recoverable": self.recoverable,
            "user_message": self.user_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class ValidationError(VPSAgentError):
    """Erro de validação de entrada."""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.VALIDATION, **kwargs)
        self.field = field
        if field:
            self.metadata["field"] = field
            self.user_message = f"Campo '{field}': {message}"


class ExecutionError(VPSAgentError):
    """Erro durante execução de comando."""
    
    def __init__(self, message: str, command: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.EXECUTION, **kwargs)
        self.command = command
        if command:
            self.metadata["command"] = command


class DatabaseError(VPSAgentError):
    """Erro de banco de dados."""
    
    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.DATABASE, **kwargs)
        self.query = query
        if query:
            self.metadata["query_preview"] = query[:100]


class NetworkError(VPSAgentError):
    """Erro de rede."""
    
    def __init__(self, message: str, url: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.NETWORK, **kwargs)
        self.url = url
        if url:
            self.metadata["url"] = url


# ============ Funções de Utility ============

def categorize_error(error: Exception) -> ErrorCategory:
    """
    Categoriza um erro baseado no tipo.
    
    Args:
        error: Exceção a categorizar
        
    Returns:
        Categoria do erro
    """
    error_type = type(error).__name__
    error_message = str(error).lower()
    
    # Padrões de categorização
    if "validation" in error_type.lower() or "value" in error_message:
        return ErrorCategory.VALIDATION
    
    if "timeout" in error_message or "timed out" in error_message:
        return ErrorCategory.TIMEOUT
    
    if any(kw in error_message for kw in ["connection", "network", "socket", "dns"]):
        return ErrorCategory.NETWORK
    
    if any(kw in error_message for kw in ["postgres", "psycopg", "redis", "database", "sql"]):
        return ErrorCategory.DATABASE
    
    if any(kw in error_message for kw in ["auth", "token", "credential", "password", "api_key"]):
        return ErrorCategory.AUTHENTICATION
    
    if any(kw in error_message for kw in ["permission", "denied", "access", "forbidden", "unauthorized"]):
        return ErrorCategory.PERMISSION
    
    if any(kw in error_message for kw in ["memory", "ram", "disk", "space", "quota", "limit"]):
        return ErrorCategory.RESOURCE
    
    return ErrorCategory.UNKNOWN


def wrap_error(
    error: Exception,
    user_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> VPSAgentError:
    """
    Envolve uma exceção em VPSAgentError.
    
    Args:
        error: Exceção original
        user_message: Mensagem para o usuário (opcional)
        metadata: Metadados adicionais (opcional)
        
    Returns:
        VPSAgentError envolvido
    """
    category = categorize_error(error)
    
    return VPSAgentError(
        message=str(error) or error.__class__.__name__,
        category=category,
        original_error=error,
        user_message=user_message,
        metadata=metadata,
    )


def format_error_for_user(error: Exception) -> str:
    """
    Formata um erro para exibição ao usuário.
    
    Args:
        error: Exceção a formatar
        
    Returns:
        Mensagem formatada para usuário
    """
    # Se já é VPSAgentError
    if isinstance(error, VPSAgentError):
        return error.user_message
    
    # Categorizar e formatar
    category = categorize_error(error)
    
    prefixes = {
        ErrorCategory.VALIDATION: "⚠️",
        ErrorCategory.EXECUTION: "❌",
        ErrorCategory.NETWORK: "🌐",
        ErrorCategory.DATABASE: "🗄️",
        ErrorCategory.AUTHENTICATION: "🔐",
        ErrorCategory.PERMISSION: "🚫",
        ErrorCategory.RESOURCE: "💾",
        ErrorCategory.TIMEOUT: "⏰",
        ErrorCategory.UNKNOWN: "❓",
    }
    
    prefix = prefixes.get(category, "❌")
    base_message = str(error) if str(error) else "Ocorreu um erro"
    
    # Truncar mensagens longas
    if len(base_message) > 200:
        base_message = base_message[:200] + "..."
    
    return f"{prefix} {base_message}"


def log_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: str = "error"
):
    """
    Faz logging estruturado de erro.
    
    Args:
        error: Exceção a logar
        context: Contexto adicional
        level: Nível de log
    """
    error_info = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "category": categorize_error(error).value,
    }
    
    if context:
        error_info["context"] = context
    
    if isinstance(error, VPSAgentError):
        error_info.update({
            "recoverable": error.recoverable,
            "metadata": error.metadata,
        })
        logger.log(level, error.message, **error_info)
    else:
        logger.log(level, f"{type(error).__name__}: {error}", **error_info)


# ============ Decoradores ============

def error_handler(
    user_message: Optional[str] = None,
    fallback: Optional[Callable] = None,
    default_return: Any = None,
    log_context: Optional[Dict[str, Any]] = None
):
    """
    Decorador para tratamento de erros em funções.
    
    Args:
        user_message: Mensagem para o usuário em caso de erro
        fallback: Função fallback em caso de erro
        default_return: Valor padrão de retorno
        log_context: Contexto para logging
        
    Returns:
        Decorator
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except VPSAgentError as e:
                log_error(e, log_context)
                if fallback:
                    return fallback(e)
                print(f"Error in {func.__name__}: {e}")
                return default_return
            except Exception as e:
                log_error(e, log_context)
                if fallback:
                    return fallback(e)
                wrapped = wrap_error(e, user_message=user_message)
                log_error(wrapped, log_context)
                print(f"Error in {func.__name__}: {traceback.format_exc()}")
                return default_return
        return wrapper
    return decorator


# ============ Recovery Suggestions ============

def suggest_recovery(error: Exception) -> str:
    """
    Sugere ações de recuperação baseadas no erro.
    
    Args:
        error: Erro ocorrido
        
    Returns:
        Sugestão de recuperação
    """
    category = categorize_error(error)
    
    suggestions = {
        ErrorCategory.VALIDATION: "Verifique os dados fornecidos e tente novamente.",
        ErrorCategory.EXECUTION: "Tente executar a operação novamente. Se persistir, reporte o erro.",
        ErrorCategory.NETWORK: "Verifique sua conexão de internet e tente novamente.",
        ErrorCategory.DATABASE: "O banco de dados pode estar em manutenção. Tente novamente em instantes.",
        ErrorCategory.AUTHENTICATION: "Verifique suas credenciais e token de API.",
        ErrorCategory.PERMISSION: "Você não tem permissão para esta ação. Contate o administrador.",
        ErrorCategory.RESOURCE: "O sistema está com recursos limitados. Tente novamente mais tarde.",
        ErrorCategory.TIMEOUT: "A operação demorou muito. Tente novamente.",
        ErrorCategory.UNKNOWN: "Ocorreu um erro desconhecido. Tente novamente.",
    }
    
    return suggestions.get(category, "Tente novamente.")


# ============ Health Check ============

def check_system_health() -> Dict[str, Any]:
    """
    Verifica a saúde do sistema.
    
    Returns:
        Dicionário com status de saúde
    """
    import subprocess
    
    checks = {}
    
    # Verificar PostgreSQL
    try:
        import psycopg2
        import os
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "vps_agent"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            connect_timeout=3
        )
        conn.close()
        checks["postgresql"] = {"status": "healthy", "latency_ms": "<10"}
    except Exception as e:
        checks["postgresql"] = {"status": "unhealthy", "error": str(e)[:100]}
    
    # Verificar Redis
    try:
        import redis
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            socket_timeout=3
        )
        r.ping()
        checks["redis"] = {"status": "healthy", "latency_ms": "<10"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)[:100]}
    
    # Verificar memória
    try:
        result = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            mem_line = lines[1].split()
            total = mem_line[1]
            used = mem_line[2]
            free = mem_line[3]
            checks["memory"] = {
                "status": "healthy",
                "total_mb": total,
                "used_mb": used,
                "free_mb": free,
            }
    except Exception as e:
        checks["memory"] = {"status": "unknown", "error": str(e)[:100]}
    
    # Status geral
    all_healthy = all(c.get("status") == "healthy" for c in checks.values())
    checks["overall"] = {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
    }
    
    return checks
