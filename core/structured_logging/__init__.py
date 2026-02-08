"""
Logging Module - Structured Logging.

Este módulo fornece funcionalidades para:
- Logging estruturado com formato JSON
- Múltiplos níveis de log
- Contexto e metadata
- Métricas de performance
"""

from .structured import (
    LogLevel,
    LogCategory,
    LogContext,
    LogEntry,
    StructuredLogger,
    LoggerManager,
    log_performance,
    log_error,
    get_logger,
)

__all__ = [
    "LogLevel",
    "LogCategory",
    "LogContext",
    "LogEntry",
    "StructuredLogger",
    "LoggerManager",
    "log_performance",
    "log_error",
    "get_logger",
]
