"""
Structured Logging - F1-08

Sistema de logging estruturado com formato JSON.
"""

import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from enum import Enum
import traceback


class LogLevel(Enum):
    """Níveis de log."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Categorias de log."""
    SYSTEM = "system"
    API = "api"
    LLM = "llm"
    SECURITY = "security"
    PERFORMANCE = "performance"
    USER = "user"
    ERROR = "error"


@dataclass
class LogContext:
    """Contexto do log."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    component: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LogEntry:
    """Entrada de log estruturado."""
    timestamp: str
    level: str
    category: str
    message: str
    context: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    performance: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Converte para JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class StructuredLogger:
    """Logger estruturado."""
    
    def __init__(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        output: Optional[str] = None
    ):
        self.name = name
        self.level = level
        self.output = output or sys.stdout
        self._context = LogContext()
    
    def set_context(self, **kwargs) -> None:
        """Define o contexto do logger."""
        for key, value in kwargs.items():
            if hasattr(self._context, key):
                setattr(self._context, key, value)
    
    def add_tag(self, tag: str) -> None:
        """Adiciona uma tag ao contexto."""
        if tag not in self._context.tags:
            self._context.tags.append(tag)
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Adiciona metadata ao contexto."""
        self._context.metadata[key] = value
    
    def _should_log(self, level: LogLevel) -> bool:
        """Verifica se deve logar no nível."""
        levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]
        return levels.index(level) >= levels.index(self.level)
    
    def _create_entry(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        **kwargs
    ) -> LogEntry:
        """Cria uma entrada de log."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level.value,
            category=category.value,
            message=message,
        )
        
        # Adicionar contexto
        context_dict = {}
        if self._context.user_id:
            context_dict["user_id"] = self._context.user_id
        if self._context.session_id:
            context_dict["session_id"] = self._context.session_id
        if self._context.request_id:
            context_dict["request_id"] = self._context.request_id
        if self._context.component:
            context_dict["component"] = self._context.component
        if self._context.tags:
            context_dict["tags"] = self._context.tags
        if self._context.metadata:
            context_dict.update(self._context.metadata)
        
        if context_dict:
            entry.context = context_dict
        
        # Adicionar informações adicionais
        if "error" in kwargs:
            entry.error = kwargs["error"]
        if "performance" in kwargs:
            entry.performance = kwargs["performance"]
        
        return entry
    
    def _write(self, entry: LogEntry) -> None:
        """Escreve a entrada de log."""
        self.output.write(entry.to_json() + "\n")
        self.output.flush()
    
    def debug(self, category: LogCategory, message: str, **kwargs) -> None:
        """Log nível DEBUG."""
        if not self._should_log(LogLevel.DEBUG):
            return
        entry = self._create_entry(LogLevel.DEBUG, category, message, **kwargs)
        self._write(entry)
    
    def info(self, category: LogCategory, message: str, **kwargs) -> None:
        """Log nível INFO."""
        if not self._should_log(LogLevel.INFO):
            return
        entry = self._create_entry(LogLevel.INFO, category, message, **kwargs)
        self._write(entry)
    
    def warning(self, category: LogCategory, message: str, **kwargs) -> None:
        """Log nível WARNING."""
        if not self._should_log(LogLevel.WARNING):
            return
        entry = self._create_entry(LogLevel.WARNING, category, message, **kwargs)
        self._write(entry)
    
    def error(self, category: LogCategory, message: str, **kwargs) -> None:
        """Log nível ERROR."""
        if not self._should_log(LogLevel.ERROR):
            return
        entry = self._create_entry(LogLevel.ERROR, category, message, **kwargs)
        self._write(entry)
    
    def critical(self, category: LogCategory, message: str, **kwargs) -> None:
        """Log nível CRITICAL."""
        if not self._should_log(LogLevel.CRITICAL):
            return
        entry = self._create_entry(LogLevel.CRITICAL, category, message, **kwargs)
        self._write(entry)
    
    def exception(
        self,
        category: LogCategory,
        message: str,
        exception: Exception,
        **kwargs
    ) -> None:
        """Log uma exceção."""
        error_info = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc(),
        }
        
        self.error(category, message, error=error_info, **kwargs)


class LoggerManager:
    """Gerenciador de loggers."""
    
    _loggers: Dict[str, StructuredLogger] = {}
    
    @classmethod
    def get_logger(
        cls,
        name: str,
        level: LogLevel = LogLevel.INFO,
        output: Optional[str] = None
    ) -> StructuredLogger:
        """
        Obtém ou cria um logger.
        
        Args:
            name: Nome do logger
            level: Nível de log
            output: Arquivo de saída (opcional)
            
        Returns:
            Instância do logger
        """
        if name not in cls._loggers:
            cls._loggers[name] = StructuredLogger(name, level, output)
        return cls._loggers[name]
    
    @classmethod
    def set_global_level(cls, level: LogLevel) -> None:
        """Define o nível global de log."""
        for logger in cls._loggers.values():
            logger.level = level
    
    @classmethod
    def close_all(cls) -> None:
        """Fecha todos os loggers."""
        for logger in cls._loggers.values():
            if logger.output != sys.stdout:
                logger.output.close()


def log_performance(
    logger: StructuredLogger,
    operation: str,
    duration_ms: float,
    **kwargs
) -> None:
    """
    Loga uma métrica de performance.
    
    Args:
        logger: Logger a usar
        operation: Nome da operação
        duration_ms: Duração em milissegundos
        **kwargs: Informações adicionais
    """
    performance_data = {
        "operation": operation,
        "duration_ms": duration_ms,
        **kwargs
    }
    
    logger.info(
        LogCategory.PERFORMANCE,
        f"Operation completed: {operation}",
        performance=performance_data
    )


def log_error(
    logger: StructuredLogger,
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """
    Loga um erro.
    
    Args:
        logger: Logger a usar
        error: Exceção a logar
        context: Contexto adicional
        **kwargs: Informações adicionais
    """
    error_info = {
        "type": type(error).__name__,
        "message": str(error),
        "traceback": traceback.format_exc(),
    }
    
    if context:
        error_info.update(context)
    
    logger.error(
        LogCategory.ERROR,
        f"Error occurred: {type(error).__name__}",
        error=error_info,
        **kwargs
    )


def get_logger(name: str) -> StructuredLogger:
    """
    Obtém um logger pelo nome.
    
    Args:
        name: Nome do logger
        
    Returns:
        Instância do logger
    """
    return LoggerManager.get_logger(name)
