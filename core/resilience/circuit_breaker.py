"""
Error Handling + Circuit Breaker - F1-09

Sistema de tratamento de erros e circuit breaker.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional


class CircuitState(Enum):
    """Estados do circuit breaker."""
    CLOSED = "closed"  # Funcionando normalmente
    OPEN = "open"  # Circuito aberto (falha)
    HALF_OPEN = "half_open"  # Testando se recuperou


@dataclass
class CircuitBreakerConfig:
    """Configuração do circuit breaker."""
    failure_threshold: int = 5  # Número de falhas para abrir
    success_threshold: int = 2  # Número de sucessos para fechar
    timeout: float = 60.0  # Tempo em segundos para tentar novamente
    half_open_max_calls: int = 3  # Máximo de chamadas em half_open


@dataclass
class CircuitBreakerStats:
    """Estatísticas do circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None

    @property
    def failure_rate(self) -> float:
        """Taxa de falha."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    @property
    def success_rate(self) -> float:
        """Taxa de sucesso."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls


class CircuitBreakerError(Exception):
    """Erro do circuit breaker."""
    def __init__(self, message: str, state: CircuitState):
        super().__init__(message)
        self.state = state


class CircuitBreaker:
    """Implementação de circuit breaker."""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self.half_open_calls = 0

    def _should_attempt(self) -> bool:
        """Verifica se deve tentar a chamada."""
        now = datetime.now(timezone.utc)

        # Se está OPEN, verificar se timeout expirou
        if self.state == CircuitState.OPEN:
            if self.stats.last_failure_time:
                elapsed = (now - self.stats.last_failure_time).total_seconds()
                if elapsed >= self.config.timeout:
                    # Timeout expirou, mudar para HALF_OPEN
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    return True
            return False

        # Se está HALF_OPEN, verificar se ainda pode tentar
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.config.half_open_max_calls

        # CLOSED, pode tentar
        return True

    def _record_success(self) -> None:
        """Registra um sucesso."""
        # Se está HALF_OPEN, incrementar contador primeiro
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1

        self.stats.successful_calls += 1
        self.stats.total_calls += 1
        self.stats.last_success_time = datetime.now(timezone.utc)

        # Se está HALF_OPEN, verificar se deve fechar
        if self.state == CircuitState.HALF_OPEN:
            if self.stats.successful_calls >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.stats.failed_calls = 0  # Resetar falhas
                self.stats.successful_calls = 0  # Resetar sucessos

    def _record_failure(self) -> None:
        """Registra uma falha."""
        self.stats.failed_calls += 1
        self.stats.total_calls += 1
        self.stats.last_failure_time = datetime.now(timezone.utc)

        # Se está HALF_OPEN, voltar para OPEN
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.half_open_calls = 0
        # Se está CLOSED, verificar se deve abrir
        elif self.state == CircuitState.CLOSED:
            if self.stats.failed_calls >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executa uma função com proteção do circuit breaker.

        Args:
            func: Função a executar
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados

        Returns:
            Resultado da função

        Raises:
            CircuitBreakerError: Se o circuito estiver aberto
        """
        if not self._should_attempt():
            raise CircuitBreakerError(
                f"Circuit breaker is {self.state.value}",
                self.state
            )

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executa uma função assíncrona com proteção do circuit breaker.

        Args:
            func: Função a executar
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados

        Returns:
            Resultado da função

        Raises:
            CircuitBreakerError: Se o circuito estiver aberto
        """
        if not self._should_attempt():
            raise CircuitBreakerError(
                f"Circuit breaker is {self.state.value}",
                self.state
            )

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise

    def get_state(self) -> CircuitState:
        """Retorna o estado atual."""
        return self.state

    def get_stats(self) -> CircuitBreakerStats:
        """Retorna as estatísticas."""
        return self.stats

    def reset(self) -> None:
        """Reseta o circuit breaker para estado inicial."""
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self.half_open_calls = 0


class RetryPolicy:
    """Política de retry."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        backoff_factor: float = 2.0
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def get_delay(self, attempt: int) -> float:
        """Calcula o delay para uma tentativa."""
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay)


class RetryError(Exception):
    """Erro de retry esgotado."""
    def __init__(self, message: str, attempts: int, last_error: Exception):
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


async def retry_with_backoff(
    func: Callable,
    policy: Optional[RetryPolicy] = None,
    *args,
    **kwargs
) -> Any:
    """
    Executa uma função com retry e backoff exponencial.

    Args:
        func: Função a executar
        policy: Política de retry
        *args: Argumentos posicionais
        **kwargs: Argumentos nomeados

    Returns:
        Resultado da função

    Raises:
        RetryError: Se todas as tentativas falharem
    """
    policy = policy or RetryPolicy()

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == policy.max_attempts:
                raise RetryError(
                    f"Max retry attempts ({policy.max_attempts}) reached",
                    policy.max_attempts,
                    e
                )

            # Aguardar antes da próxima tentativa
            delay = policy.get_delay(attempt)
            await asyncio.sleep(delay)


def retry_with_backoff_sync(
    func: Callable,
    policy: Optional[RetryPolicy] = None,
    *args,
    **kwargs
) -> Any:
    """
    Executa uma função síncrona com retry e backoff exponencial.

    Args:
        func: Função a executar
        policy: Política de retry
        *args: Argumentos posicionais
        **kwargs: Argumentos nomeados

    Returns:
        Resultado da função

    Raises:
        RetryError: Se todas as tentativas falharem
    """
    policy = policy or RetryPolicy()

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == policy.max_attempts:
                raise RetryError(
                    f"Max retry attempts ({policy.max_attempts}) reached",
                    policy.max_attempts,
                    e
                )

            # Aguardar antes da próxima tentativa
            delay = policy.get_delay(attempt)
            time.sleep(delay)


class ErrorHandler:
    """Gerenciador de erros centralizado."""

    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.default_handler: Optional[Callable] = None

    def register_handler(self, error_type: str, handler: Callable) -> None:
        """Registra um handler para um tipo de erro."""
        self.handlers[error_type] = handler

    def set_default_handler(self, handler: Callable) -> None:
        """Define o handler padrão."""
        self.default_handler = handler

    def handle(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Trata um erro.

        Args:
            error: Exceção a tratar
            context: Contexto adicional

        Returns:
            Resultado do handler
        """
        error_type = type(error).__name__

        # Buscar handler específico
        handler = self.handlers.get(error_type)
        if handler:
            return handler(error, context or {})

        # Usar handler padrão
        if self.default_handler:
            return self.default_handler(error, context or {})

        # Sem handler, re-raise
        raise error


def create_error_handler() -> ErrorHandler:
    """Cria um error handler com handlers padrão."""
    handler = ErrorHandler()

    # Handler padrão para erros de conexão
    def handle_connection_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "error": "connection_error",
            "message": str(error),
            "retryable": True,
            "context": context,
        }

    # Handler padrão para erros de timeout
    def handle_timeout_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "error": "timeout_error",
            "message": str(error),
            "retryable": True,
            "context": context,
        }

    # Handler padrão para erros de validação
    def handle_validation_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "error": "validation_error",
            "message": str(error),
            "retryable": False,
            "context": context,
        }

    handler.register_handler("ConnectionError", handle_connection_error)
    handler.register_handler("TimeoutError", handle_timeout_error)
    handler.register_handler("ValueError", handle_validation_error)

    return handler
