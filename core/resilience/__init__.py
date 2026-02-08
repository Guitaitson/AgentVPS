"""
Resilience Module - Error Handling + Circuit Breaker.

Este módulo fornece funcionalidades para:
- Circuit breaker para evitar chamadas repetidas a serviços falhando
- Retry com backoff exponencial
- Tratamento centralizado de erros
"""

from .circuit_breaker import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerStats,
    CircuitBreakerError,
    CircuitBreaker,
    RetryPolicy,
    RetryError,
    retry_with_backoff,
    retry_with_backoff_sync,
    ErrorHandler,
    create_error_handler,
)

__all__ = [
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreakerStats",
    "CircuitBreakerError",
    "CircuitBreaker",
    "RetryPolicy",
    "RetryError",
    "retry_with_backoff",
    "retry_with_backoff_sync",
    "ErrorHandler",
    "create_error_handler",
]
