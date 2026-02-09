"""
Testes para o Error Handling + Circuit Breaker.
"""

import pytest

from core.resilience.circuit_breaker import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreaker,
    RetryPolicy,
    RetryError,
    retry_with_backoff,
    retry_with_backoff_sync,
    ErrorHandler,
    create_error_handler,
)


class TestCircuitBreaker:
    """Testes para circuit breaker."""
    
    def test_create_circuit_breaker(self):
        """Testa criação de circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=30.0,
        )
        cb = CircuitBreaker(config)
        
        assert cb.state == CircuitState.CLOSED
        assert cb.config.failure_threshold == 3
    
    def test_successful_call(self):
        """Testa chamada bem-sucedida."""
        cb = CircuitBreaker()
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.successful_calls == 1
    
    def test_failed_call(self):
        """Testa chamada com falha."""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        
        def fail_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            cb.call(fail_func)
        
        assert cb.stats.failed_calls == 1
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_opens_after_failures(self):
        """Testa que circuito abre após falhas."""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
        
        def fail_func():
            raise ValueError("Test error")
        
        # 3 falhas devem abrir o circuito
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(fail_func)
        
        assert cb.state == CircuitState.OPEN
    
    def test_circuit_blocks_when_open(self):
        """Testa que circuito bloqueia quando aberto."""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        
        def fail_func():
            raise ValueError("Test error")
        
        # Abrir circuito
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(fail_func)
        
        # Tentar chamar quando aberto
        with pytest.raises(CircuitBreakerError):
            cb.call(fail_func)
    
    def test_circuit_closes_after_successes(self):
        """Testa que circuito fecha após sucessos."""
        # Usar timeout curto (0.1s) para que o teste funcione rapidamente
        # success_threshold=7 significa que precisamos de 7 sucessos para fechar
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2, success_threshold=7, half_open_max_calls=10, timeout=0.1))
        
        def fail_func():
            raise ValueError("Test error")
        
        def success_func():
            return "success"
        
        # Abrir circuito
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(fail_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Esperar timeout expirar
        import time
        time.sleep(0.15)
        
        # 7 sucessos em HALF_OPEN devem fechar o circuito
        # Primeiro sucesso muda para HALF_OPEN
        cb.call(success_func)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Segundo sucesso continua em HALF_OPEN
        cb.call(success_func)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Terceiro sucesso continua em HALF_OPEN
        cb.call(success_func)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Quarto sucesso continua em HALF_OPEN
        cb.call(success_func)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Quinto sucesso continua em HALF_OPEN
        cb.call(success_func)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Sexto sucesso continua em HALF_OPEN
        cb.call(success_func)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Sétimo sucesso fecha o circuito
        cb.call(success_func)
        assert cb.state == CircuitState.CLOSED
    
    def test_reset(self):
        """Testa reset do circuit breaker."""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        
        def fail_func():
            raise ValueError("Test error")
        
        # Gerar falhas
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(fail_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Resetar
        cb.reset()
        
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.total_calls == 0


class TestRetryPolicy:
    """Testes para política de retry."""
    
    def test_create_retry_policy(self):
        """Testa criação de política de retry."""
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=0.5,
            max_delay=5.0,
            backoff_factor=2.0,
        )
        
        assert policy.max_attempts == 5
        assert policy.base_delay == 0.5
        assert policy.max_delay == 5.0
    
    def test_get_delay(self):
        """Testa cálculo de delay."""
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=1.0,
            backoff_factor=2.0,
        )
        
        delay1 = policy.get_delay(1)
        delay2 = policy.get_delay(2)
        delay3 = policy.get_delay(3)
        
        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0


class TestRetryWithBackoff:
    """Testes para retry com backoff."""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Testa retry com sucesso na primeira tentativa."""
        call_count = 0
        
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await retry_with_backoff(success_func)
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_fails_all_attempts(self):
        """Testa retry com falha em todas as tentativas."""
        call_count = 0
        
        async def fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")
        
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)
        
        with pytest.raises(RetryError):
            await retry_with_backoff(fail_func, policy)
        
        assert call_count == 3
    
    def test_retry_sync_success_on_first_attempt(self):
        """Testa retry síncrono com sucesso na primeira tentativa."""
        call_count = 0
        
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = retry_with_backoff_sync(success_func)
        
        assert result == "success"
        assert call_count == 1
    
    def test_retry_sync_fails_all_attempts(self):
        """Testa retry síncrono com falha em todas as tentativas."""
        call_count = 0
        
        def fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")
        
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)
        
        with pytest.raises(RetryError):
            retry_with_backoff_sync(fail_func, policy)
        
        assert call_count == 3


class TestErrorHandler:
    """Testes para error handler."""
    
    def test_create_error_handler(self):
        """Testa criação de error handler."""
        handler = ErrorHandler()
        
        assert handler.handlers == {}
        assert handler.default_handler is None
    
    def test_register_handler(self):
        """Testa registro de handler."""
        handler = ErrorHandler()
        
        def custom_handler(error, context):
            return {"handled": True}
        
        handler.register_handler("ValueError", custom_handler)
        
        assert "ValueError" in handler.handlers
    
    def test_handle_with_registered_handler(self):
        """Testa tratamento com handler registrado."""
        handler = ErrorHandler()
        
        def custom_handler(error, context):
            return {"handled": True, "error": str(error)}
        
        handler.register_handler("ValueError", custom_handler)
        
        error = ValueError("Test error")
        result = handler.handle(error, {"context": "test"})
        
        assert result["handled"] is True
        assert result["error"] == "Test error"
    
    def test_handle_with_default_handler(self):
        """Testa tratamento com handler padrão."""
        handler = ErrorHandler()
        
        def default_handler(error, context):
            return {"default": True, "error": str(error)}
        
        handler.set_default_handler(default_handler)
        
        error = RuntimeError("Test error")
        result = handler.handle(error, {"context": "test"})
        
        assert result["default"] is True
        assert result["error"] == "Test error"
    
    def test_handle_without_handler_raises(self):
        """Testa tratamento sem handler re-raise."""
        handler = ErrorHandler()
        
        error = ValueError("Test error")
        
        with pytest.raises(ValueError):
            handler.handle(error)


class TestCreateErrorHandler:
    """Testes para criação de error handler padrão."""
    
    def test_create_default_error_handler(self):
        """Testa criação de error handler padrão."""
        handler = create_error_handler()
        
        assert "ConnectionError" in handler.handlers
        assert "TimeoutError" in handler.handlers
        assert "ValueError" in handler.handlers
    
    def test_handle_connection_error(self):
        """Testa tratamento de erro de conexão."""
        handler = create_error_handler()
        
        error = ConnectionError("Connection failed")
        result = handler.handle(error)
        
        assert result["error"] == "connection_error"
        assert result["retryable"] is True
    
    def test_handle_timeout_error(self):
        """Testa tratamento de erro de timeout."""
        handler = create_error_handler()
        
        error = TimeoutError("Timeout")
        result = handler.handle(error)
        
        assert result["error"] == "timeout_error"
        assert result["retryable"] is True
    
    def test_handle_validation_error(self):
        """Testa tratamento de erro de validação."""
        handler = create_error_handler()
        
        error = ValueError("Invalid value")
        result = handler.handle(error)
        
        assert result["error"] == "validation_error"
        assert result["retryable"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
